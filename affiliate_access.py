import os

import requests

SCALEO_API_BASE = os.getenv("SCALEO_API_BASE", "").rstrip("/")
SCALEO_API_KEY  = os.getenv("SCALEO_API_KEY", "")


def _call_access_api(offer_id: int, affiliate_id: int, action: str) -> dict:
    """Add or remove an affiliate's access to an offer."""

    if action not in ("add", "delete"):
        raise ValueError("action must be 'add' or 'delete'")

    access_url = f"{SCALEO_API_BASE}/api/v2/network/offers/{offer_id}/affiliate-access-{action}"
    params = {"api-key": SCALEO_API_KEY}

    body = {
        "allowed_affiliates": str(affiliate_id),
    }

    response = requests.put(
        access_url,
        params=params,
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        json=body,
        timeout=15,
    )
    response.raise_for_status()
    try:
        return response.json()
    except Exception:
        return {"raw": response.text, "status_code": response.status_code}

def add_affiliate_access(offer_id: int, affiliate_id: int) -> dict:
    return _call_access_api(offer_id, affiliate_id, "add")


def delete_affiliate_access(offer_id: int, affiliate_id: int) -> dict:
    return _call_access_api(offer_id, affiliate_id, "delete")
