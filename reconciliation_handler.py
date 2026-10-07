from datetime import datetime
import time
import os

from dotenv import load_dotenv

last_reply_time = {}

load_dotenv() 

COOLDOWN_SECONDS = 600
DELAY_SECONDS = 3
OWNER = int(os.getenv("OWNER_ID", "0") or 0)
USER_1 = int(os.getenv("USER_1", "0") or 0)
USER_2 = int(os.getenv("USER_2", "0") or 0)


def setup_reconciliation(bot):
    """Register a Telegram handler for reconciliation-related messages."""
    
    @bot.message_handler(func=lambda m: m.chat.type in ["group", "supergroup"] and m.text)
    def handle_reconciliation(message):
        text = message.text.lower()

        if message.from_user.id in (OWNER, USER_1, USER_2):
            return

        if not any(word in text for word in ["сверка", "сверимся", "сверку", "свериться", "сверочку", "сверить", "звіритись", "звірка"]):
            return

        chat_id = message.chat.id
        now = time.time()

        if chat_id in last_reply_time:  
            if now - last_reply_time[chat_id] < COOLDOWN_SECONDS:
                return  

        last_reply_time[chat_id] = now

        time.sleep(DELAY_SECONDS)

        day = datetime.now().day

        if 1 <= day < 15:
            bot.reply_to(
                message,
                "Привет! Сверочный период начнётся с 15-го числа."
            )
        else:
            bot.reply_to(
                message,
                "Привет! Ваш менеджер подскажет на каком этапе находится сверочный период."
            )