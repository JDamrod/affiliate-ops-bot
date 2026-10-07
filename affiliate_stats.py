import html
import json
import os
from datetime import date, datetime, timedelta
from dotenv import load_dotenv

import requests

load_dotenv()

SCALEO_API_BASE = os.getenv("SCALEO_API_BASE", "").rstrip("/")
SCALEO_API_KEY = os.getenv("SCALEO_API_KEY", "")

def html_escape(s: str) -> str:
    return html.escape(s or "", quote=False)


def _do_clicks_request(dt_from: date, dt_to: date, filters: dict) -> list[dict]:
    """Fetch paginated click report rows for the given date range."""
    clicks_url = f"{SCALEO_API_BASE}/api/v2/network/reports/clicks"
    base_params = {
        "api-key": SCALEO_API_KEY,
        "lang": "en",
        "sortField": "added_timestamp",
        "sortDirection": "desc",
        "perPage": 1000,
        "fieldsType": "object",
    }
    rows_all, page = [], 1
    while True:
        params = dict(base_params, page=page)
        body = {
            "rangeFrom": dt_from.isoformat(),
            "rangeTo": dt_to.isoformat(),
            "columns": (
                "transaction_id,"
                "offer,"          
                "affiliate,"      
                "added_timestamp"
            ),
            "filters": filters,
        }
        response = requests.post(
            clicks_url, params=params,
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            json=body, timeout=60
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


def _fetch_clicks_by_offer_for_affiliate(affiliate_id: int, days: int = 30) -> dict[int, str]:
    """Return offers with clicks for an affiliate during the given period."""
    dt_to = date.today()
    dt_from = dt_to - timedelta(days=days - 1)

    try:
        rows = _do_clicks_request(dt_from, dt_to, {"affiliates": [affiliate_id]})
    except RuntimeError:
        rows = _do_clicks_request(dt_from, dt_to, {})  # fallback

    by_offer: dict[int, str] = {}
    for row in rows:
        affiliate = row.get("affiliate") or {}
        try:
            if int(affiliate.get("id")) != int(affiliate_id):
                continue
        except (TypeError, ValueError):
            continue

        offer = row.get("offer") or {}
        offer_id = offer.get("id")
        if not offer_id:
            continue
        title = (offer.get("value") or offer.get("title") or "").strip()
        # Store each offer once.
        by_offer[int(offer_id)] = title
    return by_offer

def _do_conversions_request(dt_from: date, dt_to: date, filters: dict) -> list[dict]:
    """Fetch paginated conversion report rows for the given date range."""
    conversions_url = f"{SCALEO_API_BASE}/api/v2/network/reports/conversions"
    base_params = {
        "api-key": SCALEO_API_KEY,
        "lang": "en",
        "sortField": "added_timestamp",
        "sortDirection": "desc",
        "perPage": 1000,
        "fieldsType": "object",
    }
    rows_all = []
    page = 1
    while True:
        params = dict(base_params, page=page)
        body = {
            "rangeFrom": dt_from.isoformat(),
            "rangeTo": dt_to.isoformat(),
            "columns": (
                "transaction_id,"
                "conversion_status,"  
                "offer,"              
                "affiliate,"          
                "goal_type,"        
                "added_timestamp"
            ),
            "filters": filters,
        }
        response = requests.post(
            conversions_url, params=params,
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            json=body, timeout=60
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

def _fetch_conversions_for_affiliate(affiliate_id: int, days: int = 30) -> list[dict]:
    """Fetch conversions for an affiliate, with a fallback to local filtering."""
    if not SCALEO_API_BASE or not SCALEO_API_KEY:
        raise RuntimeError("SCALEO_API_BASE or SCALEO_API_KEY is not set")

    dt_to = date.today()
    dt_from = dt_to - timedelta(days=days - 1)

    try:
        conversions = _do_conversions_request(
            dt_from, dt_to, {"affiliates": [affiliate_id]}
        )
        if conversions:
            return conversions
    except RuntimeError as error:
        if str(error) != "server500-ultra":
            raise
    except requests.exceptions.RequestException:
        pass

    conversions = _do_conversions_request(dt_from, dt_to, {})
    filtered_conversions = []

    for row in conversions:
        affiliate = row.get("affiliate") or {}
        try:
            if int(affiliate.get("id")) == int(affiliate_id):
                filtered_conversions.append(row)
        except (TypeError, ValueError):
            continue

    return filtered_conversions

def _fetch_offer_details(offer_id: int) -> dict:
    """Fetch raw offer details from the Scaleo API."""
    offer_url = f"{SCALEO_API_BASE}/api/v2/network/offers/{offer_id}"
    params = {"api-key": SCALEO_API_KEY}
    response = requests.get(
        offer_url,
        params=params,
        headers={"Accept": "application/json"},
        timeout=60,
    )
    response.raise_for_status()
    response_data = response.json()
    return ((response_data.get("info") or {}).get("offer")) or {}

_offer_cache: dict[int, dict] = {}

def is_affiliate_allowed_for_offer(affiliate_id: int, offer_id: int) -> bool:
    """Return whether an affiliate is explicitly allowed to access an offer."""
    access_url = (
        f"{SCALEO_API_BASE}/api/v2/network/offers/{offer_id}/affiliate-access"
    )
    params = {"api-key": SCALEO_API_KEY}
    response = requests.get(
        access_url,
        params=params,
        headers={"Accept": "application/json"},
        timeout=60,
    )
    response.raise_for_status()
    response_data = response.json()
    access_data = ((response_data.get("info") or {}).get("affiliate-access")) or {}

    allowed_raw = access_data.get("allowed_affiliates") or []
    allowed_ids = []

    for affiliate in allowed_raw:
        try:
            allowed_ids.append(int(affiliate.get("id")))
        except (TypeError, ValueError):
            continue

    return bool(allowed_ids) and int(affiliate_id) in allowed_ids

def get_offer_meta(offer_id: int) -> tuple[list[str], int | None]:
    """Return cached offer categories and cap information."""
    if offer_id in _offer_cache:
        cached = _offer_cache[offer_id]
        return cached["cats"], cached["cap"]

    offer_full = _fetch_offer_details(offer_id)

    # Extract categories.
    cats = []
    for c in (offer_full.get("categories") or []):
        t = (c.get("title") or "").strip()
        if t:
            cats.append(t)

    # Extract the cap from the relevant goal.
    cap_limit = None
    for g in (offer_full.get("goals") or []):
        alias = str(g.get("alias") or "").lower()
        gtype_name = str(g.get("goal_type_name") or "").upper()
        if alias == "dep" or gtype_name in ("CPA", "FTD", "DEPOSIT"):
            caps_raw = g.get("caps")
            if caps_raw:
                try:
                    for cobj in json.loads(caps_raw):
                        v = cobj.get("value")
                        if v and str(v).isdigit():
                            cap_limit = int(v)
                            break
                except Exception:
                    pass
        if cap_limit is not None:
            break

    _offer_cache[offer_id] = {"cats": cats, "cap": cap_limit}
    return cats, cap_limit

def _aggregate_offers(txs: list[dict]) -> dict[int, dict]:
    """Aggregate registration and FTD counts by offer."""
    offers_stats: dict[int, dict] = {}
    today_d = date.today()
    last2_start = today_d - timedelta(days=1)  # Today and yesterday.

    for row in txs:

        offer_obj = row.get("offer") or {}
        offer_id = offer_obj.get("id")
        if not offer_id:
            continue
        offer_title = offer_obj.get("value") or ""

        goal_obj = row.get("goal_type") or {}
        goal_name = (goal_obj.get("value") or "").upper().strip()

        added_ts = row.get("added_timestamp") or ""
        added_date = None
        if isinstance(added_ts, str) and len(added_ts) >= 10:
            try:
                added_date = datetime.strptime(added_ts[:10], "%Y-%m-%d").date()
            except Exception:
                pass

        stat = offers_stats.setdefault(
            int(offer_id),
            {"offer_id": int(offer_id), "title": offer_title,
             "reg_total": 0, "ftd_total": 0, "reg_last2": 0, "ftd_last2": 0}
        )

        if goal_name == "REG":
            stat["reg_total"] += 1
            if added_date and added_date >= last2_start:
                stat["reg_last2"] += 1
        else:
            stat["ftd_total"] += 1
            if added_date and added_date >= last2_start:
                stat["ftd_last2"] += 1

    return offers_stats

def _classify_offers(offers_stats: dict[int, dict]) -> tuple[list[str], list[str], list[str]]:
    """Classify offers into active, inactive, and suspended groups."""
    active_lines, inactive_lines, suspended_lines = [], [], []

    for oid, st in offers_stats.items():
        clean_title = (st["title"] or "").strip()
        if clean_title.startswith("[STOP]"):
            continue

        reg_last2 = st["reg_last2"]
        ftd_last2 = st["ftd_last2"]
        ftd_total = st["ftd_total"]

        try:
            cats, cap_limit = get_offer_meta(oid)
        except Exception:
            cats, cap_limit = ([], None)

        approach_str = ", ".join(cats)
        cap_text = "∞" if not cap_limit or cap_limit <= 0 else str(cap_limit)
        title_html = html_escape(clean_title)
        approach_html = html_escape(approach_str)

        if approach_html:
            prefix = f"• {title_html} ({oid}) {approach_html} —"
        else:
            prefix = f"• {title_html} ({oid}) —"

        line = f"<b>{prefix}</b> {ftd_total}/{cap_text} ftd"

        is_active = (reg_last2 >= 3) or ((reg_last2 >= 2) and (ftd_last2 >=1))

        if is_active:
            active_lines.append(line)
        else:
            (suspended_lines if ftd_total > 0 else inactive_lines).append(line)

    active_lines.sort()
    inactive_lines.sort()
    suspended_lines.sort()
    return active_lines, inactive_lines, suspended_lines

def build_affiliate_dashboard(affiliate_id: int) -> str:
    today_str = date.today().strftime("%d.%m")
    try:
        txs = _fetch_conversions_for_affiliate(affiliate_id, days=30)
        clicks_by_offer = _fetch_clicks_by_offer_for_affiliate(affiliate_id, days=30)
    except Exception as e:
        return (
            f"Статистика {today_str}\n\n"
            f"Не удалось получить данные по этому аффилиату.\n"
            f"[err: {e!r}]\n"
            f"#o"
        )

    offers_stats = _aggregate_offers(txs)

    # Add offers that had clicks but no conversions.
    for oid, click_title in clicks_by_offer.items():
        if oid not in offers_stats:
            offers_stats[oid] = {
                "offer_id": oid,
                "title": click_title,
                "reg_total": 0,
                "ftd_total": 0,
                "reg_last2": 0,
                "ftd_last2": 0,
            }
    filtered_offers_stats: dict[int, dict] = {}
    for oid, st in offers_stats.items():
        try:
            if is_affiliate_allowed_for_offer(affiliate_id, oid):
                filtered_offers_stats[oid] = st
        except Exception:
            # If access lookup fails, keep the offer visible.
            filtered_offers_stats[oid] = st
    active_lines, inactive_lines, suspended_lines = _classify_offers(filtered_offers_stats)

    def block(title, lines):
        header = f"<b><u>{html_escape(title)}</u></b>:"
        if not lines:
            return f"{header}\n—"
        return header + "\n" + "\n".join(lines)

    return (
        f"<i>Статистика {today_str}</i>\n\n"
        f"✅ {block('Активные потоки', active_lines)}\n\n"
        f"‼️ {block('Неактивные потоки', inactive_lines)}\n\n"
        f"❌ {block('Приостановленные потоки', suspended_lines)}\n\n"
        f"#o\n"
     )

def split_long(text: str, limit: int = 4000) -> list[str]:
    """Split text into chunks that fit Telegram message limits."""
    return [text[i:i+limit] for i in range(0, len(text), limit)]

