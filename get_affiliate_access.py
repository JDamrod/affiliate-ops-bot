import os

import requests
from dotenv import load_dotenv

load_dotenv()

SCALEO_API_BASE = (os.getenv("SCALEO_API_BASE", "").rstrip("/"))
SCALEO_API_KEY  = os.getenv("SCALEO_API_KEY", "")

def get_affiliate_access(offer_id):
    affiliate_access_url = f"{SCALEO_API_BASE}/api/v2/network/offers/{offer_id}/affiliate-access"
    base_params = {"api-key": SCALEO_API_KEY}
    response = requests.get(
            affiliate_access_url,
            params=base_params,
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            timeout=15 )

    response_data = response.json()

    status_code = response.status_code

    if status_code != 200:
        titles = None
        count = None
        return titles, count, status_code

    allowed_affiliates = response_data["info"]["affiliate-access"]["allowed_affiliates"]
    titles = [a["title"] for a in allowed_affiliates]
    count = len(titles)

    return titles, count, status_code

