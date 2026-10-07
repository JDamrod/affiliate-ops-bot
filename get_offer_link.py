import html
import json
import os
import re
from datetime import date

import requests
from dotenv import load_dotenv

load_dotenv()

SCALEO_API_BASE = os.getenv("SCALEO_API_BASE", "").rstrip("/")
SCALEO_API_KEY  = os.getenv("SCALEO_API_KEY", "")


def get_offer_link(offer_id: int, affiliate_id: int, custom_payout: float = 0):
    """Fetch offer details and generate a tracking link for an affiliate."""
    
    custom_params_status_code = None
    offer_url = f"{SCALEO_API_BASE}/api/v2/network/offers/{offer_id}"
    base_params = {"api-key": SCALEO_API_KEY}
    offer_response = requests.get(
                    offer_url,
                    params=base_params,
                    headers={"Accept": "application/json", "Content-Type": "application/json"},
                    timeout=15,
            )
    
    offer_data = offer_response.json()
    
    offer_status_code = offer_response.status_code
    offer = offer_data.get("info", {}).get("offer", {}) or {}
    offer_title = offer.get("title", "")
    offer_goals = offer_data.get("info", {}).get("offer", {}).get("goals", [])
    cpa_goal_id = next((g.get("goal_id") for g in offer_goals if g.get("goal_name") == "CPA"), None)
    
    custom_params_url = f"{SCALEO_API_BASE}/api/v2/network/offers/{offer_id}/custom-params"
    custom_payout_parameters = [
                    {
                            "type": 2,
                            "goal_id": {"id": cpa_goal_id},
                            "parameter": custom_payout
                    }
            ]
    custom_params_body = {
            "status": 1,
            "affiliates": affiliate_id,
            "start_date": date.today().strftime("%Y-%m-%d"),
            "end_date": "",
            "conditions": "",
            "parameters": json.dumps(custom_payout_parameters)
            }
    
    if custom_payout != 0:
            custom_params_response = requests.post(
                    custom_params_url,
                    params=base_params,
                    headers={"Accept": "application/json", "Content-Type": "application/json"},
                    json=custom_params_body,
                    timeout=15,
            )
            custom_params_status_code = custom_params_response.status_code
    else:
            payout = (offer.get("goals") or [{}])[0].get("payout", "")
            payout = str(payout).split('.', 1)[0]
            
    
    currency = offer.get("currency", "")
    terms = (offer.get("description", "") or "").split('Strictly prohibited:')[0]
    terms = (terms
            .replace('<br>', '\n')
            .replace('<br/>', '\n')
            .replace('<br />', '\n')
            .replace('</p>', '\n')
            .replace('</li>', '\n')
            )
    terms = html.unescape(re.sub(r'<.*?>', '', terms)).strip()
    tracking_link = f"https://tracking.example.com/click?o={offer_id}&a={affiliate_id}"
    
    
    if custom_payout != 0:
            return offer_title, currency, terms, tracking_link, offer_status_code, custom_params_status_code
    else:
            return offer_title, payout, currency, terms, tracking_link, offer_status_code, custom_params_status_code
    