import json
import os

import requests
from dotenv import load_dotenv

load_dotenv()

SCALEO_API_BASE = os.getenv("SCALEO_API_BASE", "").rstrip("/")
SCALEO_API_KEY = os.getenv("SCALEO_API_KEY", "")


def get_advertiser_name(offer_id):
    """Get the advertiser company name for an offer."""

    offer_url = f"{SCALEO_API_BASE}/api/v2/network/offers/{offer_id}"
    base_params = {"api-key": SCALEO_API_KEY}

    response = requests.get(
        offer_url,
        params=base_params,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        timeout=15,
    )

    response_data = response.json()
    status_code = response.status_code

    if status_code != 200:
        return None, status_code
        
    advertiser_raw = response_data["info"]["offer"]["advertiser"]
    advertiser_info = json.loads(advertiser_raw)
    company_name = advertiser_info["company_name"]

    return company_name, status_code