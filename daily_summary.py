import os
import threading
import time

import requests
from datetime import date, datetime, time as dtime, timedelta

_daily_loop_started = False

SCALEO_API_BASE = os.getenv("SCALEO_API_BASE", "").rstrip("/")
SCALEO_API_KEY  = os.getenv("SCALEO_API_KEY", "")
OWNER = int (os.getenv("OWNER_ID", "0") or 0)
USER_1 = int(os.getenv("USER_1", "0") or 0) 
AFFILIATE_MANAGER_ID = int(os.getenv("AFFILIATE_MANAGER_ID", "1") or 1)

MONTH_GOAL = float(os.getenv("MONTH_GOAL", "999"))

def _do_conversions_request(dt_from: date, dt_to: date) -> list[dict]:
    """Fetch conversions from the Scaleo API for the specified date range."""

    report_url = f"{SCALEO_API_BASE}/api/v2/network/reports/conversions"
    base_params = {
        "api-key":      SCALEO_API_KEY,
        "lang":         "en",
        "sortField":    "added_timestamp",
        "sortDirection":"desc",
        "perPage":      1000,
        "fieldsType":   "object",
    }

    rows_all: list[dict] = []
    page = 1

    while True:
        params = dict(base_params, page=page)
        body = {
            "rangeFrom": dt_from.isoformat(),
            "rangeTo":   dt_to.isoformat(),
            "columns": (
                "transaction_id,"
                "conversion_status,"
                "goal_type,"
                "profit,"
                "added_timestamp"
            ),
            "filters": { "affiliates_managers": AFFILIATE_MANAGER_ID},
        }

        response = requests.post(
            report_url,
            params=params,
            headers={"Accept": "application/json",
                     "Content-Type": "application/json"},
            json=body,
            timeout=30,
        )
        if response.status_code >= 500:
            raise RuntimeError("server500-ultra")

        response.raise_for_status()
        response_data = response.json()
        page_rows = ((response_data.get("info") or {}).get("transactions")) or []
        rows_all.extend(page_rows)

        if len(page_rows) < base_params["perPage"]:
            break
        page += 1

    return rows_all

def _status_ok(row) -> bool:
    """Allow only Approved and Pending conversion statuses."""

    raw = row.get("conversion_status")
    if raw is None:
        raw = row.get("status")

    sid = None
    sval = ""

    if isinstance(raw, dict):
        sid = raw.get("id")
        sval = str(raw.get("value") or "").lower()
    elif isinstance(raw, str):
        sval = raw.lower()
        if sval.isdigit():
            sid = int(sval)
    elif isinstance(raw, int):
        sid = raw

    if sval in ("approved", "pending"):
        return True
    if sid in (2, 3):
        return True
    return False


def _parse_added_ts(value) -> datetime | None:
    """
    Parse a Scaleo added_timestamp value into a naive datetime.
    Supports timestamps with or without milliseconds and timezone information.
    """

    if not isinstance(value, str) or len(value) < 10:
        return None

    s = value.strip().replace("T", " ")
    # Remove timezone information if present.
    if "+" in s:
        s = s.split("+", 1)[0]
    if "Z" in s:
        s = s.replace("Z", "")
    s = s.strip()
    # Remove milliseconds.
    if "." in s:
        s = s.split(".", 1)[0]

    try:
        return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
    except Exception:
        try:
            return datetime.strptime(s[:10], "%Y-%m-%d")
        except Exception:
            return None


def _sum_profit_ftd_between(start_dt: datetime,
                            end_dt: datetime):
    """Calculate total approved and pending profit for the specified time range."""

    dt_from = start_dt.date()
    dt_to   = end_dt.date()

    rows = _do_conversions_request(dt_from, dt_to)

    total_profit = 0.0

    EUR_TO_USD_RATE = float(os.getenv("EUR_TO_USD_RATE", "1"))

    for row in rows:
        if not _status_ok(row):
            continue

        ts = _parse_added_ts(row.get("added_timestamp"))
        if not ts:
            continue

        if not (start_dt <= ts < end_dt):
            continue

        profit_raw = row.get("profit")
        currency = (row.get("currency") or "").upper().strip()

        try:
            profit_val = float(profit_raw or 0)
        except (TypeError, ValueError):
            profit_val = 0.0


        if currency == "EUR":
            profit_val *= EUR_TO_USD_RATE

        total_profit += profit_val

    return total_profit


def get_month_progress():
    """Return the current month's profit and goal completion percentage."""
    today = date.today()
    month_start = today.replace(day=1)
    # Get the first day of the next month.
    next_month = (month_start + timedelta(days=32)).replace(day=1)

    start_dt = datetime.combine(month_start, dtime(0, 0))
    end_dt   = datetime.combine(next_month, dtime(0, 0))

    month_profit = _sum_profit_ftd_between(start_dt, end_dt)
    percent = (month_profit / MONTH_GOAL) * 100.0
    
    return percent, month_profit


def setup_daily_ping(bot, OWNER):
    """Start a background loop that sends daily profit summaries."""

    global _daily_loop_started
    if _daily_loop_started:
        return


    def send_evening_summary():
        today = date.today()

        start_today = datetime.combine(today, dtime(0, 0))
        end_today   = datetime.combine(today + timedelta(days=1), dtime(0, 0))

        try:
            profit_today = _sum_profit_ftd_between(start_today, end_today)
            percent, month_profit = get_month_progress()
        except Exception as e:
            bot.send_message(OWNER, f"Ошибка daily ping: {e}")
            return
        

        status = ""
        if profit_today < 500: # example
            status = "🟥"
        elif profit_today < 503: # example
            status = "🟨"
        elif profit_today < 505: # example
            status = "🟩"
        else:
            status = "💎"

        text = (
        f"<b>{status} Заработано за сегодня — {profit_today:.0f}$ </b>{status}\n"
        f"<b>Месячная цель выполнена на {percent:.0f}%</b>\n"
        f"<b><tg-spoiler>Заработано за текущий месяц {month_profit:.0f}$</tg-spoiler></b>"
        )


        bot.send_message(OWNER, text, parse_mode="HTML")
        time.sleep(2)
        

        if USER_1:
            try:
                bot.send_message(USER_1, text, parse_mode="HTML")
            except Exception:
                bot.send_message(OWNER, "Failed to send to USER_1")

    def loop():
        last_evening_day = None

        while True:
            now = datetime.utcnow()
            day_key = now.strftime("%Y-%m-%d")
            weekday_pl = now.weekday()  

            if now.hour == 16 and now.minute == 0 and last_evening_day != day_key:
                if weekday_pl in (0, 1, 2, 3, 4): 
                    send_evening_summary()
                    last_evening_day = day_key

            time.sleep(60)

    t = threading.Thread(target=loop, daemon=True)
    t.start()
    _daily_loop_started = True
