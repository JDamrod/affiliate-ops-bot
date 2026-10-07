import html
import os
import re

import requests
from dotenv import load_dotenv

load_dotenv()

SCALEO_API_BASE = (os.getenv("SCALEO_API_BASE", "").rstrip("/"))
SCALEO_API_KEY  = os.getenv("SCALEO_API_KEY", "")

COUNTRY_FLAGS = {
    "AF": "🇦🇫","AL": "🇦🇱","DZ": "🇩🇿","AD": "🇦🇩","AO": "🇦🇴","AG": "🇦🇬","AR": "🇦🇷","AM": "🇦🇲","AU": "🇦🇺","AT": "🇦🇹",
    "AZ": "🇦🇿","BS": "🇧🇸","BH": "🇧🇭","BD": "🇧🇩","BB": "🇧🇧","BY": "🇧🇾","BE": "🇧🇪","BZ": "🇧🇿","BJ": "🇧🇯","BT": "🇧🇹",
    "BO": "🇧🇴","BA": "🇧🇦","BW": "🇧🇼","BR": "🇧🇷","BN": "🇧🇳","BG": "🇧🇬","BF": "🇧🇫","BI": "🇧🇮","KH": "🇰🇭","CM": "🇨🇲",
    "CA": "🇨🇦","CV": "🇨🇻","CF": "🇨🇫","TD": "🇹🇩","CL": "🇨🇱","CN": "🇨🇳","CO": "🇨🇴","KM": "🇰🇲","CG": "🇨🇬","CR": "🇨🇷",
    "CI": "🇨🇮","HR": "🇭🇷","CU": "🇨🇺","CY": "🇨🇾","CZ": "🇨🇿","DK": "🇩🇰","DJ": "🇩🇯","DM": "🇩🇲","DO": "🇩🇴","EC": "🇪🇨",
    "EG": "🇪🇬","SV": "🇸🇻","GQ": "🇬🇶","ER": "🇪🇷","EE": "🇪🇪","ET": "🇪🇹","FJ": "🇫🇯","FI": "🇫🇮","FR": "🇫🇷","GA": "🇬🇦",
    "GM": "🇬🇲","GE": "🇬🇪","DE": "🇩🇪","GH": "🇬🇭","GR": "🇬🇷","GD": "🇬🇩","GT": "🇬🇹","GN": "🇬🇳","GW": "🇬🇼","GY": "🇬🇾",
    "HT": "🇭🇹","HN": "🇭🇳","HU": "🇭🇺","IS": "🇮🇸","IN": "🇮🇳","ID": "🇮🇩","IR": "🇮🇷","IQ": "🇮🇶","IE": "🇮🇪","IL": "🇮🇱",
    "IT": "🇮🇹","JM": "🇯🇲","JP": "🇯🇵","JO": "🇯🇴","KZ": "🇰🇿","KE": "🇰🇪","KI": "🇰🇮","KP": "🇰🇵","KR": "🇰🇷","KW": "🇰🇼",
    "KG": "🇰🇬","LA": "🇱🇦","LV": "🇱🇻","LB": "🇱🇧","LS": "🇱🇸","LR": "🇱🇷","LY": "🇱🇾","LI": "🇱🇮","LT": "🇱🇹","LU": "🇱🇺",
    "MG": "🇲🇬","MW": "🇲🇼","MY": "🇲🇾","MV": "🇲🇻","ML": "🇲🇱","MT": "🇲🇹","MH": "🇲🇭","MR": "🇲🇷","MU": "🇲🇺","MX": "🇲🇽",
    "FM": "🇫🇲","MD": "🇲🇩","MC": "🇲🇨","MN": "🇲🇳","ME": "🇲🇪","MA": "🇲🇦","MZ": "🇲🇿","MM": "🇲🇲","NA": "🇳🇦","NR": "🇳🇷",
    "NP": "🇳🇵","NL": "🇳🇱","NZ": "🇳🇿","NI": "🇳🇮","NE": "🇳🇪","NG": "🇳🇬","NO": "🇳🇴","OM": "🇴🇲","PK": "🇵🇰","PW": "🇵🇼",
    "PA": "🇵🇦","PG": "🇵🇬","PY": "🇵🇾","PE": "🇵🇪","PH": "🇵🇭","PL": "🇵🇱","PT": "🇵🇹","QA": "🇶🇦","RO": "🇷🇴","RU": "🇷🇺",
    "RW": "🇷🇼","KN": "🇰🇳","LC": "🇱🇨","VC": "🇻🇨","WS": "🇼🇸","SM": "🇸🇲","ST": "🇸🇹","SA": "🇸🇦","SN": "🇸🇳","RS": "🇷🇸",
    "SC": "🇸🇨","SL": "🇸🇱","SG": "🇸🇬","SK": "🇸🇰","SI": "🇸🇮","SB": "🇸🇧","SO": "🇸🇴","ZA": "🇿🇦","SS": "🇸🇸","ES": "🇪🇸",
    "LK": "🇱🇰","SD": "🇸🇩","SR": "🇸🇷","SZ": "🇸🇿","SE": "🇸🇪","CH": "🇨🇭","SY": "🇸🇾","TW": "🇹🇼","TJ": "🇹🇯","TZ": "🇹🇿",
    "TH": "🇹🇭","TL": "🇹🇱","TG": "🇹🇬","TO": "🇹🇴","TT": "🇹🇹","TN": "🇹🇳","TR": "🇹🇷","TM": "🇹🇲","TV": "🇹🇻","UG": "🇺🇬",
    "UA": "🇺🇦","AE": "🇦🇪","UK": "🇬🇧","US": "🇺🇸","UY": "🇺🇾","UZ": "🇺🇿","VU": "🇻🇺","VA": "🇻🇦","VE": "🇻🇪","VN": "🇻🇳",
    "YE": "🇾🇪","ZM": "🇿🇲","ZW": "🇿🇼"
}

def get_offer_details(offer_id):
    offer_url = f"{SCALEO_API_BASE}/api/v2/network/offers/{offer_id}"
    base_params = {"api-key": SCALEO_API_KEY}

    response = requests.get(
        offer_url,
        params=base_params,
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        timeout=15
    )

    offer_data = response.json()
    status_code = response.status_code

    if status_code != 200:
        final_text = None
        return final_text, status_code

    title = offer_data["info"]["offer"]["title"].split("/")[0]

    geo = offer_data["info"]["offer"]["title"].split("|")[1].strip().split(" ")[0]
    flag = COUNTRY_FLAGS.get(geo.upper(), "")

    revenue = int(float(offer_data["info"]["offer"]["goals"][0]["revenue"]))
    currency = offer_data["info"]["offer"]["currency"]

    desc = html.unescape(offer_data["info"]["offer"]["description"])

    # Convert HTML line breaks to newlines.
    desc = desc.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
    desc = desc.replace("<p>", "\n").replace("</p>", "\n")
    desc = desc.replace("<div>", "\n").replace("</div>", "\n")
    desc = desc.replace("<li>", "\n").replace("</li>", "\n")

    # Remove HTML tags while preserving line breaks.
    clean = re.sub(r"<.*?>", " ", desc).replace("\xa0", " ")

    # Remove everything after "Soft KPI".
    clean = clean.split("Soft KPI")[0]

    m = re.search(r"Mindep\s+([\d\s]+)\s*([A-Za-z]+)", clean, re.IGNORECASE)
    mindep = f"{m.group(1).strip()} {m.group(2)}" if m else None

    c = re.search(r"(?i)\b(?:test\s+)?cap\s+(\d+)", clean, re.IGNORECASE)
    cap = c.group(1) if c else None

    b = re.search(r"baseline\s+([\d\s]+)\s*([A-Za-z]+)", clean, re.IGNORECASE)
    baseline = f"{b.group(1).strip()} {b.group(2)}" if b else None

    w = re.search(r"wager\s+([\d\s]+)\s*([A-Za-z]+)", clean, re.IGNORECASE)
    wager = f"{w.group(1).strip()} {w.group(2)}" if w else None

    k = re.search(r"KPI\s*(.+)", clean, re.IGNORECASE)
    kpi = k.group(1).strip() if k else None

    extra_lines = []
    for line in clean.split("\n"):
        line = line.strip()
        if not line:
            continue
        # Exclude fields already parsed above.
        if re.search(r"(?i)mindep|baseline|wager|cap|kpi", line):
            continue
        extra_lines.append(line)

    extra_lines = [re.sub(r"\s{2,}", " ", l) for l in extra_lines]

    # --- COMBINE EXTRA LINES AND KPI ---
    combined = []

    # Add extra conditions first.
    combined.extend(extra_lines)

    # Add KPI if available.
    if kpi:
        combined.append(f"KPI: {kpi}")

    combined_html = ""
    if combined:
        combined_html = "<blockquote><b>" + "\n".join(combined) + "</b></blockquote>"



    # --- BUILD FINAL TEXT ---
    main_line = f"<b>{flag} {title} — CPA {revenue} {currency}</b>"

    after_mindep_parts = []
    if baseline:
        after_mindep_parts.append(f"baseline {baseline}")
    if wager:
        after_mindep_parts.append(f"wager {wager}")
    if cap:
        after_mindep_parts.append(f"{cap}ftd")
        
    after_mindep = " + ".join(after_mindep_parts)

    if after_mindep:
        bracket = f"(mindep {mindep}, <b>{after_mindep}</b>)"
    else:
        bracket = f"(mindep {mindep})"

    final_text = f"{main_line} {bracket}"

    if combined_html:
        final_text += "\n" + combined_html


    return final_text, status_code
