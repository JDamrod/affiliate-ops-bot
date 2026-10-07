# Affiliate Ops Bot

A Telegram bot I built to take over the repetitive parts of my work as an affiliate manager. It connects to a [Scaleo](https://www.scaleo.io/) affiliate network through its REST API, so I can check a partner's stats, give them access to an offer or test their tracking link straight from Telegram, without opening the admin panel.

I deployed the first version about a year ago and I still use it every day, adding features as my work needs them. This repository is a cleaned-up copy: everything company-specific (offers, IDs, links, amounts) has been removed or moved to environment variables.

## What it does

- `/stats` – 30-day overview of a partner: which offers are running, which stopped, FTD count vs. cap
- `/getlink`, `/allow_aff`, `/remove_aff`, `/affs` – give or remove access to an offer, generate a message with a tracking link, list connected partners
- `/deal`, `/adv` – format an offer description into a ready-to-send message, look up the advertiser
- `/testreg` – click a partner link and check that the click and registration were tracked (a colleague also uses this one to avoid testing by hand)
- `/broadcast`, `/set_aff`, `/debug_groups` – send a message to all partner groups, link a group to an affiliate ID
- Background jobs: a notification on new registrations (polled every 5 minutes) and a daily profit summary
- Auto-reply to partners asking about reconciliation periods

`/help` inside the bot lists all commands. Access is limited to a few Telegram user IDs set in `.env`.

## How it was built

I started this project with a lot of help from AI, since I had little Python and API experience at the time. As I learned, I took over more and more of the code myself: today I write most of it on my own and use AI mainly as a helper for code review and ideas. The bot is built around my own day-to-day tasks, so I use it much more than anyone else does.

## Example output

Bot messages are in Russian. All names and numbers below are made up.

`/stats 42`

```
Статистика 07.10

✅ Активные потоки:
• Example Offer (1001) Gambling — 12/50 ftd

‼️ Неактивные потоки:
—

❌ Приостановленные потоки:
• Demo Offer (1002) Betting — 3/∞ ftd
```

`/affs 1001`

```
Подключенные аффилиаты:
- Partner A
- Partner B
```

## Stack

Python, pyTelegramBotAPI, requests, SQLite, python-dotenv, pytz.

## Running it

```bash
git clone <repo-url>
cd <repo-folder>
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # fill in your values
python app.py
```

Settings are read from `.env`:

| Variable | Purpose |
|---|---|
| `TELEGRAM_TOKEN` | bot token from @BotFather |
| `SCALEO_API_BASE`, `SCALEO_API_KEY` | your Scaleo instance URL and API key |
| `SOURCE_CHANNEL_ID` | channel whose posts get forwarded to groups |
| `OWNER_ID`, `USER_1`, `USER_2` | Telegram IDs allowed to use the bot |
| `AFFILIATE_MANAGER_ID` | manager ID used for the daily summary |
| `WATCHED_OFFER_IDS` | comma-separated offer IDs for registration alerts |
| `MONTH_GOAL` | monthly profit target for the daily summary |
| `EUR_TO_USD_RATE` | exchange rate used in profit calculation |

A `Procfile` is included for running it as a worker on Heroku-style hosting. The group list is stored in a local SQLite file, so it resets on hosts with an ephemeral filesystem.

## Notes

- The bot's messages are in Russian because that's the language of the team it was built for.
- The code grew feature by feature, so some parts are repetitive (for example, several modules make the same Scaleo requests). A shared API client and some tests are the next things I'd add.
- Not affiliated with Scaleo.

## License

MIT, see [LICENSE](LICENSE).
