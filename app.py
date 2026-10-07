import os
import sqlite3
import threading
import time
from datetime import date, datetime

import pytz
import requests
import telebot
from dotenv import load_dotenv

load_dotenv()

import affiliate_stats
from affiliate_access import add_affiliate_access, delete_affiliate_access
from get_advertiser_name import get_advertiser_name
from get_affiliate_access import get_affiliate_access
from get_offer_link import get_offer_link
from offer_details import get_offer_details
from reconciliation_handler import setup_reconciliation
from start import cmd_start
from tracking_test import test_registration_tracking
from daily_summary import setup_daily_ping


DB_PATH = "groups.db"

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
SOURCE_CHANNEL_ID = int(os.getenv("SOURCE_CHANNEL_ID", "0") or 0)
OWNER = int(os.getenv("OWNER_ID", "0") or 0) 
USER_1 = int(os.getenv("USER_1", "0") or 0) 
USER_2 = int(os.getenv("USER_2", "0") or 0) 
WATCHED_OFFER_IDS = os.getenv("WATCHED_OFFER_IDS", "").split(",")

SCALEO_API_BASE = (os.getenv("SCALEO_API_BASE", "").rstrip("/"))
SCALEO_API_KEY = os.getenv("SCALEO_API_KEY", "")

bot = telebot.TeleBot(TELEGRAM_TOKEN) 

setup_daily_ping(bot, OWNER)


def init_database():
    """Initialize the SQLite database and create the groups table if needed."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS groups(
        chat_id  INTEGER PRIMARY KEY,
        title    TEXT,
        added_at INTEGER,
        affiliate_id INTEGER
    )
    """)
    return conn

DB = init_database()

def add_group(chat_id: int, title: str | None):
    """Add a group to the database or update its existing record."""
    aff_id = extract_affiliate_id_from_title(title or "")
    with DB:
        DB.execute(
            """
            INSERT OR REPLACE INTO groups(chat_id, title, added_at, affiliate_id)
            VALUES(
                ?, 
                ?, 
                COALESCE((SELECT added_at FROM groups WHERE chat_id=?), ?),
                COALESCE((SELECT affiliate_id FROM groups WHERE chat_id=?), ?)
            )
            """,
            (
                chat_id,
                title,
                chat_id,
                int(time.time()),
                chat_id,
                aff_id
            )
        )

def remove_group(chat_id: int):
    """Remove a group from the database."""
    with DB:
        DB.execute("DELETE FROM groups WHERE chat_id=?", (chat_id,))

def list_groups() -> list[int]:
    """Return the IDs of all groups stored in the database."""
    return [row[0] for row in DB.execute("SELECT chat_id FROM groups").fetchall()]

def _is_from_source_channel(msg) -> bool:
    """Check whether a channel post came from the configured source channel."""
    if getattr(msg.chat, "type", None) != "channel":
        return False
    return bool(SOURCE_CHANNEL_ID and msg.chat.id == SOURCE_CHANNEL_ID)

def extract_affiliate_id_from_title(title: str) -> int | None:
    """Extract an affiliate ID from the beginning of a group title."""
    if not title:
        return None
    left = title.split("_", 1)[0].strip()
    if left.isdigit():
        return int(left)
    return None

def delete_message_later(chat_id, message_id, delay=45):
    """Delete a Telegram message after a specified delay."""
    def worker():
        time.sleep(delay)
        try:
            bot.delete_message(chat_id, message_id)
        except Exception:
            pass
    threading.Thread(target=worker, daemon=True).start()


_seen_conversions = set()


def check_registrations(bot):
    """Check for new registration conversions and notify the owner."""
    global _seen_conversions

    today = date.today().strftime("%Y-%m-%d")

    conversions_url = f"{SCALEO_API_BASE}/api/v2/network/reports/conversions"
    params = {
        "api-key": SCALEO_API_KEY,
        "lang": "en",
        "sortField": "added_timestamp",
        "sortDirection": "desc",
        "perPage": 1000,
        "fieldsType": "object",
        "page": 1
    }
    body = {
        "rangeFrom": today,
        "rangeTo": today,
        "columns": (
            "transaction_id,"
            "conversion_status,"
            "goal_type,"
            "profit,"
            "added_timestamp"
        ),
        "filters": {"offers": WATCHED_OFFER_IDS},
    }

    try:
        response = requests.post(
            conversions_url,
            params=params,
            headers={"Accept": "application/json",
                     "Content-Type": "application/json"},
            json=body,
            timeout=30,
        )
        response_data = response.json()

    except Exception as e:
        bot.send_message(OWNER, f"Ошибка при запросе Scaleo: {e}")
        return

    transactions = response_data.get("info", {}).get("transactions", [])
    if not transactions:
        return

    for transaction in transactions:
        transaction_id = transaction.get("transaction_id")
        status = transaction.get("conversion_status")
        profit = transaction.get("profit")
        timestamp = transaction.get("added_timestamp")

        goal_obj = transaction.get("goal_type", {})
        goal_value = goal_obj.get("value")  

        if transaction_id in _seen_conversions:
            continue

        if goal_value == "REG":
            msg = (
                f"🟢 Новая регистрация!\n"
                f"ID: <b>{transaction_id}</b>\n"
                f"Status: {status}\n"
                f"Goal: {goal_value}\n"
                f"Profit: {profit}\n"
                f"Time: {timestamp}"
            )
            bot.send_message(OWNER, msg, parse_mode="HTML")

        _seen_conversions.add(transaction_id)


def start_conversion_checker(bot):
    """Start a background loop that checks registrations every five minutes."""
    def loop():
        while True:
            check_registrations(bot)
            time.sleep(300)

    t = threading.Thread(target=loop, daemon=True)
    t.start()


@bot.my_chat_member_handler(func=lambda u: True)
def on_my_chat_member(update):
    """Track groups where the bot is added or removed."""
    chat = update.chat
    status = update.new_chat_member.status  
    if chat.type in ("group", "supergroup"):
        if status in ("member", "administrator"):
            add_group(chat.id, getattr(chat, "title", None))   
        elif status in ("left", "kicked"):
            remove_group(chat.id)                               

@bot.channel_post_handler(content_types=["text", "photo", "video", "animation", "document"])
def on_channel_post(m):
    """Forward posts from the source channel to registered groups."""
    if not _is_from_source_channel(m):
        return
    for gid in list_groups():
        try:
            bot.forward_message(gid, m.chat.id, m.message_id)
            time.sleep(0.1)
        except Exception as e:
            bot.send_message(OWNER, f"FORWARD ERROR, {gid}, {e}")


start_conversion_checker(bot)

@bot.message_handler(commands=['allow_aff'])
def cmd_allow_aff(message):
    """Grant an affiliate access to an offer."""
    if message.from_user.id not in (OWNER, USER_2):
        return bot.reply_to(message, "Недостаточно прав.")

    parts = (message.text or "").split()
    if len(parts) != 3 or not parts[1].isdigit() or not parts[2].isdigit():
        return bot.reply_to(
            message,
            "Использование:\n"
            "<code>/allow_aff &lt;offer_id&gt; &lt;affiliate_id&gt;</code>",
            parse_mode="HTML",
        )   

    offer_id = int(parts[1])
    affiliate_id = int(parts[2])

    offer_url = f"{SCALEO_API_BASE}/api/v2/network/offers/{offer_id}"
    base_params = {"api-key": SCALEO_API_KEY}

    response = requests.get(
        offer_url,
        params=base_params,
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        timeout=15,
    )

    offer_data = response.json()
    offer_title = offer_data.get("info", {}).get("offer", {}).get("title", "")

    try:
        offer_data = add_affiliate_access(offer_id, affiliate_id)
        text = (
            "✅ Доступ выдан.\n"
            f"<b>Offer ID:</b> <code>{offer_title} ({offer_id})</code>\n"
            f"<b>Affiliate ID:</b> <code>{affiliate_id}</code>\n\n"
        )
    except Exception as e:
        text = (
            "❌ Не удалось выдать доступ.\n"
        )

    msg = bot.reply_to(message, text, parse_mode="HTML")
    delete_message_later(msg.chat.id, msg.message_id, 45)
    delete_message_later(message.chat.id, message.message_id, 45)

@bot.message_handler(commands=['remove_aff'])
def cmd_remove_aff(message):
    """Remove an affiliate's access to an offer."""
    if message.from_user.id not in (OWNER, USER_2):
        return bot.reply_to(message, "Недостаточно прав.")

    parts = (message.text or "").split()
    if len(parts) != 3 or not parts[1].isdigit() or not parts[2].isdigit():
        return bot.reply_to(
            message,
            "Использование:\n"
            "<code>/remove_aff &lt;offer_id&gt; &lt;affiliate_id&gt;</code>",
            parse_mode="HTML",
        )

    offer_id = int(parts[1])
    affiliate_id = int(parts[2])

    offer_url = f"{SCALEO_API_BASE}/api/v2/network/offers/{offer_id}"
    base_params = {"api-key": SCALEO_API_KEY}

    response = requests.get(
        offer_url,
        params=base_params,
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        timeout=15,
    )

    offer_data = response.json()
    offer_title = offer_data.get("info", {}).get("offer", {}).get("title", "")

    try:
        offer_data = delete_affiliate_access(offer_id, affiliate_id)
        text = (
            "✅ Доступ удалён.\n"
            f"<b>Offer ID:</b> <code>{offer_title} ({offer_id})</code>\n"
            f"<b>Affiliate ID:</b> <code>{affiliate_id}</code>\n\n"
        )
    except Exception as e:
        text = (
            "❌ Не удалось удалить доступ.\n"
        )

    bot.reply_to(message, text, parse_mode="HTML")

@bot.message_handler(commands=['stats'])
def cmd_stats(message):
    """Generate and send statistics for an affiliate."""
    try:
        if message.from_user.id not in (OWNER, USER_1, USER_2):
            return bot.reply_to(message, "Недостаточно прав.")
        parts = (message.text or "").split()
        if len(parts) < 2 or not parts[1].isdigit():
            return bot.reply_to(message, "Использование:\n/stats <affiliate_id>\n\nпример:\n/stats 35")
        aff_id = int(parts[1])
        report_text = affiliate_stats.build_affiliate_dashboard(aff_id)
        for chunk in affiliate_stats.split_long(report_text):
            bot.send_message(message.chat.id, chunk, disable_web_page_preview=True, parse_mode="HTML")
            
    except Exception as e:
        bot.reply_to(message, f"Ошибка /stats:\n<code>{e!r}</code>", parse_mode="HTML")
            
@bot.message_handler(commands=['testreg'])
def cmd_testreg(message):
    """Run a registration tracking test for an affiliate link."""
    if message.from_user.id not in (OWNER, USER_2, USER_1):
        return bot.reply_to(message, "Недостаточно прав.")

    parts = (message.text or "").split(maxsplit=2)
    if len(parts) != 3 or not parts[2].isdigit():
        return bot.reply_to(
            message,
            "Использование:\n"
            "<code>/testreg &lt;affiliate_link&gt; &lt;affiliate_id&gt;</code>",
            parse_mode="HTML",
        )

    click_url = parts[1].strip()
    affiliate_id = int(parts[2])

    bot.reply_to(message, "<i>Запускаю тест...</i>", parse_mode="HTML")

    res = test_registration_tracking(click_url=click_url, affiliate_id=affiliate_id)

    aff_line = ""
    aff_click_id = res.get("aff_click_id")
    if aff_click_id:
        aff_line = f"<b>Your click_id:</b> <code>{aff_click_id}</code>\n"

    if res["ok"]:
        text = (
            "✅ <b>Тест регистрация успешна!</b>\n"
            f"<b>Click_ID:</b> <code>{res['click_id']}</code>\n"
            f"{aff_line}"
        )
    else:
        text = (
            "❌ <b>Тест регистрация НЕ удалась.</b>\n"
            f"Причина: <code>{res['error']}</code>\n"
        )

    bot.send_message(message.chat.id, text, parse_mode="HTML")

@bot.message_handler(commands=['getlink'])
def cmd_getlink(message):
    """Generate an offer tracking link for an affiliate."""
    if message.from_user.id not in (OWNER, USER_2, USER_1):
        return bot.reply_to(message, "Недостаточно прав.")
    parts = (message.text or "").split()
    
    if len(parts) < 3 or len(parts) > 4:
        return bot.reply_to(
            message,
            "Использование:\n"
            "<code>/getlink &lt;offer_id&gt; &lt;affiliate_id&gt; &lt;custom_payout (optional)&gt;</code>",
            parse_mode="HTML",
    )

    if not parts[1].isdigit() or not parts[2].isdigit():
        return bot.reply_to(
            message,
            "Использование:\n"
            "<code>/getlink &lt;offer_id&gt; &lt;affiliate_id&gt; &lt;custom_payout (optional)&gt;</code>",
            parse_mode="HTML",
    )

    offer_id = int(parts[1])
    affiliate_id = int(parts[2])

    if len(parts) == 4:
        try:
            custom_payout = float(parts[3])
        except ValueError:
            return bot.reply_to(message, "Третий параметр (выплата) должен быть числом.")
    else:
        custom_payout = 0  

    add_affiliate_access(offer_id, affiliate_id)

    affiliate_access_url = f"{SCALEO_API_BASE}/api/v2/network/offers/{offer_id}/affiliate-access"
    base_params = {"api-key": SCALEO_API_KEY}
    access_response = requests.get(
                        affiliate_access_url,
                        params=base_params,
                        headers={"Accept": "application/json"},
                        timeout=15,
                )
    access_data = access_response.json()

    allowed_affiliates = access_data.get("info", {}).get("affiliate-access", {}).get("allowed_affiliates", [])
    allowed_affiliate_ids = [affiliate.get("id") for affiliate in allowed_affiliates]

    if affiliate_id not in allowed_affiliate_ids:
        return bot.reply_to(message, f"Ошибка - оффер «{offer_id}» не доступен для партнёра «{affiliate_id}».")

    if custom_payout != 0:
        offer_title, currency, terms, tracking_link, status_code, custom_params_status_code = get_offer_link(offer_id=offer_id, affiliate_id=affiliate_id, custom_payout=custom_payout)
    else:
        offer_title, payout, currency, terms, tracking_link, status_code, custom_params_status_code = get_offer_link(offer_id=offer_id, affiliate_id=affiliate_id, custom_payout=custom_payout)

    if custom_payout != 0:
        if custom_params_status_code != 201:
            return bot.reply_to(message, "Ошибка в создании кастомного параметра.")
    if status_code == 404:
        return bot.reply_to(message, f"Ошибка - оффер «{offer_id}» не создан.")
    elif status_code == 401:
        return bot.reply_to(message, "Ошибка - не авторизован.")
    if custom_payout != 0:
        formatted = ('%.2f' % custom_payout).rstrip('0').rstrip('.')
        msg = bot.reply_to(message, 
                f"{offer_title}\n"
                f"{formatted} {currency}\n"
                "\n"
                f"REG - {tracking_link}\n"
                "\n"
                f"{terms}"
                )
        bot.pin_chat_message(message.chat.id, msg.message_id)
    else:
        msg = bot.reply_to(message, 
                f"{offer_title}\n"
                f"{payout} {currency}\n"
                "\n"
                f"REG - {tracking_link}\n"
                "\n"
                f"{terms}"
                )
        bot.pin_chat_message(message.chat.id, msg.message_id)

def schedule_reply(chat_id, message_id, text, year, month, day, hour, minute):
    def worker():
        """Schedule a delayed reply to a Telegram message."""
        tz = pytz.timezone("Europe/Warsaw")
        now = datetime.now(tz)
        target = tz.localize(datetime(year, month, day, hour, minute, 0))

        seconds = (target - now).total_seconds()
        if seconds <= 0:
            return

        time.sleep(seconds)

        try:
            bot.send_message(
                chat_id,
                text,
                reply_to_message_id=message_id
            )
        except Exception as e:
            print("Ошибка при отправке напоминания:", e)

    threading.Thread(target=worker, daemon=True).start()

@bot.message_handler(commands=['debug_groups'])
def cmd_debug_groups(message):
    """Show groups currently stored in the database."""
    if message.from_user.id != OWNER:
        return bot.reply_to(message, "Недостаточно прав.")

    rows = DB.execute("SELECT chat_id, title, affiliate_id FROM groups").fetchall()
    if not rows:
        return bot.reply_to(message, "В БД нет ни одной группы.")

    text_lines = []
    for chat_id, title, aff_id in rows:
        text_lines.append(f"{chat_id} | {title} | affiliate_id={aff_id}")
    bot.reply_to(message, "Группы в БД:\n" + "\n".join(text_lines))


@bot.message_handler(commands=['broadcast'])
def cmd_broadcast(message):
    """Broadcast a message or media to registered groups."""
    if message.chat.type == "private" and message.from_user.id != OWNER:
        return bot.reply_to(message, "Недостаточно прав.")

    if message.from_user.id not in (OWNER, USER_1, USER_2):
        return bot.reply_to(message, "Недостаточно прав.")

    raw_text = (message.caption or message.text or "")
    payload = raw_text.partition(" ")[2].lstrip()
    broadcast_text = payload.split("$skip", 1)[0].strip()  

    skip_titles = set()
    if "$skip" in raw_text:
        tail = raw_text.split("$skip", 1)[1]
        skip_titles = {x.strip().casefold() for x in tail.split(",") if x.strip()}

    source_message = message.reply_to_message or message

    def message_has_media(message):
        return any([
            bool(getattr(message, "photo", None)),
            bool(getattr(message, "video", None)),
            bool(getattr(message, "animation", None)),
            bool(getattr(message, "document", None)),
            bool(getattr(message, "audio", None)),
            bool(getattr(message, "voice", None)),
            bool(getattr(message, "video_note", None)),
            bool(getattr(message, "sticker", None)),
        ])

    if not broadcast_text and not message_has_media(source_message) and source_message.message_id == message.message_id:
        return bot.reply_to(
            message,
            "Использование:\n"
            "/broadcast <текст> [$skip Группа1, Группа2]\n"
            "или ответьте командой /broadcast на сообщение (фото/видео/док и т.д.)"
        )

    text_to_send = broadcast_text or (source_message.text or source_message.caption or "")
    caption_override = (broadcast_text if broadcast_text else None)

    is_reply_without_body = (message.reply_to_message is not None and not broadcast_text)

    exclude_chat_id = message.chat.id if message.chat.type in ("group", "supergroup") else None

    for group_id     in list_groups():
        if exclude_chat_id and group_id  == exclude_chat_id:
            continue

        title_cf = ""
        try:
            chat = bot.get_chat(group_id    )
            title_cf = (chat.title or "").casefold()
        except Exception:
            pass
        if title_cf and title_cf in skip_titles:
            continue

        try:
            if message_has_media(source_message):
                bot.copy_message(
                    group_id    ,
                    source_message.chat.id,
                    source_message.message_id,
                    caption=caption_override,  
                )
            else:
                if is_reply_without_body:
                    bot.copy_message(group_id   , source_message.chat.id, source_message.message_id)
                else:
                    if not text_to_send.strip():
                        continue
    
                    bot.send_message(group_id   , text_to_send, disable_web_page_preview=True)

            time.sleep(0.1)
        except Exception as e:
            try:
                bot.send_message(OWNER, f"BROADCAST ERROR, {group_id    }, {e}")
            except Exception:
                pass

    bot.reply_to(message, "Разослано ✅")

@bot.message_handler(commands=['start'])
def handle_start(message):
    """Handle the /start command and send the bot greeting."""
    greetings = cmd_start()
    bot.send_message(message.chat.id, greetings, parse_mode="HTML", disable_web_page_preview=True)

@bot.message_handler(commands=['set_aff'])
def cmd_set_aff(message):
    """Set or remove the affiliate ID associated with the current group."""
    if message.from_user.id != OWNER:
        return bot.reply_to(message, "Недостаточно прав.")

    if message.chat.type not in ("group", "supergroup"):
        return bot.reply_to(message, "Эту команду нужно писать в самой группе.")

    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        return bot.reply_to(
            message,
            "Использование:\n/set_aff <affiliate_id>\n"
            "или: /set_aff off — чтобы убрать привязку"
        )

    arg = parts[1].strip()
    chat_id = message.chat.id

    if arg.lower() in ("off", "none", "null", "-", "0"):
        DB.execute("UPDATE groups SET affiliate_id = NULL WHERE chat_id = ?", (chat_id,))
        DB.commit()
        return bot.reply_to(message, "Привязка удалена ✅")

    if not arg.isdigit():
        return bot.reply_to(message, "affiliate_id должен быть числом.")
    aff_id = int(arg)

    cur = DB.execute("UPDATE groups SET affiliate_id = ? WHERE chat_id = ?", (aff_id, chat_id))
    if cur.rowcount == 0:
        DB.execute("INSERT INTO groups (chat_id, affiliate_id) VALUES (?, ?)", (chat_id, aff_id))
    DB.commit()

    bot.reply_to(message, f"Для этой группы установлен affiliate_id = {aff_id} ✅")

@bot.message_handler(commands=['adv'])
def cmd_adv(message):
    """Show the advertiser associated with an offer."""
    if message.from_user.id not in (OWNER, USER_2):
        return bot.reply_to(message, "Недостаточно прав.")
        
    parts = (message.text or "").split()
    if len(parts) != 2 or not parts[1].isdigit():
        return bot.reply_to(
            message,
            "Использование:\n"
            "<code>/adv &lt;offer_id&gt;</code>",
            parse_mode="HTML",
        )

    offer_id = int(parts[1])

    advertiser_name, status_code = get_advertiser_name(offer_id)

    if status_code == 404:
        bot.reply_to(message, "Ошибка - такого оффера не существует.")
    elif status_code == 401:
        bot.reply_to(message, "Ошибка - не авторизован.")
    elif status_code != 200:
        bot.reply_to(message, "Ошибка.")
    else:
        bot.reply_to(message, f"Оффер от {advertiser_name}.")

@bot.message_handler(commands=['deal'])
def cmd_deal(message):
    """Generate a formatted offer message for an offer."""
    if message.from_user.id not in (OWNER, USER_2):
        return bot.reply_to(message, "Недостаточно прав.")
        
    parts = (message.text or "").split()
    if len(parts) != 2 or not parts[1].isdigit():
        return bot.reply_to(
            message,
            "Использование:\n"
            "<code>/deal &lt;offer_id&gt;</code>",
            parse_mode="HTML",
        )

    offer_id = int(parts[1])

    offer_text, status_code = get_offer_details(offer_id)

    if status_code == 404:
        bot.reply_to(message, "Ошибка - такого оффера не существует.")
    elif status_code == 401:
        bot.reply_to(message, "Ошибка - не авторизован.")
    elif status_code != 200:
        bot.reply_to(message, "Ошибка.")
    else:
        bot.reply_to(message, f"{offer_text}", parse_mode="HTML", disable_web_page_preview=True,)
    
@bot.message_handler(commands=['affs'])
def cmd_affs(message):
    """Show affiliates who have access to an offer."""
    if message.from_user.id not in (OWNER, USER_2):
        return bot.reply_to(message, "Недостаточно прав.")
        
    parts = (message.text or "").split()
    if len(parts) != 2 or not parts[1].isdigit():
        return bot.reply_to(
            message,
            "Использование:\n"
            "<code>/affs &lt;offer_id&gt;</code>",
            parse_mode="HTML",
        )

    offer_id = int(parts[1])

    affiliate_titles, affiliate_count, status_code = get_affiliate_access(offer_id)

    if status_code == 404:
        bot.reply_to(message, "Ошибка - такого оффера не существует.")
    elif status_code == 401:
        bot.reply_to(message, "Ошибка - не авторизован.")
    elif status_code != 200:
        bot.reply_to(message, "Ошибка.")
    else:
        if affiliate_count == 0:
            bot.reply_to(message, "Нету подключённых аффилиатов.")
        else:
            text = "Подключенные аффилиаты:\n"
            for title in affiliate_titles:
                text += f"- {title}\n"

            bot.reply_to(message, text)

@bot.message_handler(commands=['help'])
def cmd_help(message):
    """Show the list of available bot commands."""
    if message.from_user.id not in (OWNER, USER_2):
        return bot.reply_to(message, "Недостаточно прав.")    
    bot.reply_to(message, 
    """<b>🤖 Команды бота:</b>

• <code>/stats &lt;affiliate_id&gt;</code> — показывает статистику партнёра за 30 дней. 
• <code>/broadcast &lt;text&gt; [$skip &lt;Group name 1&gt;, &lt;Group name 2&gt; и т.д.]</code> - рассылка сообщения в группы.
• <code>/debug_groups</code> - показывает группы, которые на данный момент находятся в БД.
• <code>/set_aff &lt;affiliate_id&gt;</code> - сохраняет (в БД) ID партнёра для группы, в которой вызвана команда.
• <code>/allow_aff &lt;offer_id&gt; &lt;affiliate_id&gt;</code> — привязывает партнёра к офферу. 
• <code>/remove_aff &lt;offer_id&gt; &lt;affiliate_id&gt;</code> — отвязывает партнёра от оффера.
• <code>/testreg &lt;affiliate_link&gt; &lt;affiliate_id&gt;</code> — делает тестовую регистрацию по ссылке партнёра.  
• <code>/getlink &lt;offer_id&gt; &lt;affiliate_id&gt; [&lt;custom_payout&gt;]</code> — предоставляет оффер партнёру.  
• <code>/adv &lt;offer_id&gt;</code> — отображает рекламодателя, предоставляющего оффер.
• <code>/affs &lt;offer_id&gt;</code> — показывает список партнёров подключённых к офферу. 
• <code>/deal &lt;offer_id&gt;</code> — формирует готовое предложение по офферу с ❗️TOTAL❗️ ставкой. 

<code>[...]</code> - опциональные параметры.
""",
    parse_mode="HTML",
    disable_web_page_preview=True,
    )

@bot.message_handler(func=lambda m: m.chat.type == "private", content_types=['text'])
def handle_private_message(message):
    """Forward private messages from users to the bot owner."""
    if message.from_user.id != OWNER:
        bot.send_message(OWNER, f"Сообщение от @{message.from_user.username}. Текст: «{message.text}»")

setup_reconciliation(bot)

if __name__ == "__main__":
    bot.infinity_polling(
        skip_pending=True,
        allowed_updates=["my_chat_member", "channel_post", "message"]
    )