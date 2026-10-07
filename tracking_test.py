import os
import time
from datetime import date, timedelta
import requests

SCALEO_API_BASE = (os.getenv("SCALEO_API_BASE", "").rstrip("/"))
SCALEO_API_KEY = os.getenv("SCALEO_API_KEY", "")


def test_registration_tracking(click_url: str, affiliate_id: int, days: int = 1) -> dict:
    """ Validate click tracking and registration goal for an affiliate. """
    
    result = {
        "ok": False,
        "click_id": None,
        "aff_click_id": None,
        "click_http": None,
        "report_http": None,
        "goal_http": None,
        "error": None,
    }      
    try:
        click_response = requests.get(click_url, timeout=10)
        result["click_http"] = click_response.status_code
        if click_response.status_code != 200:
            result["error"] = f"click HTTP {click_response.status_code}"
            return result
    except Exception as e:
        result["error"] = f"click error: {e!r}"
        return result      
    time.sleep(1)      
    try:
        dt_to = date.today()
        dt_from = dt_to - timedelta(days=days - 1)     
        url = f"{SCALEO_API_BASE}/api/v2/network/reports/clicks"
        params = {
            "api-key":       SCALEO_API_KEY,
            "lang":          "en",
            "sortField":     "added_timestamp",
            "sortDirection": "desc", 
            "perPage":       1,        
            "page":          1,
            "fieldsType":    "object",
        }      
        body = {
            "rangeFrom": dt_from.isoformat(),
            "rangeTo":   dt_to.isoformat(),
            "columns": (
                "click_id,"
                "offer,"
                "affiliate,"
                "aff_click_id,"
                "added_timestamp"
            ),
            "filters": {
                "affiliates": affiliate_id,
            },
        }      
        report_response = requests.post(
            url,
            params=params,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            json=body,
            timeout=30,
        )      
        result["report_http"] = report_response.status_code
        report_response.raise_for_status()
        data = report_response.json()      
        time.sleep(5)      
        rows = ((data.get("info") or {}).get("transactions")) or []
        if not rows:
            result["error"] = "no clicks found in report"
            return result      
        click_row = rows[0]
        click_id = click_row.get("click_id")
        if not click_id:
            result["error"] = "click_id not found in row"
            return result      
        result["click_id"] = click_id
        result["aff_click_id"] = click_row.get("aff_click_id")     
    except Exception as e:
        result["error"] = f"report error: {e!r}"
        return result      
    try:
        registration_url = (
            f"{SCALEO_API_BASE}/track/goal-by-click-id"
            f"?click_id={result['click_id']}&goal_alias=reg"
        )
        goal_response = requests.get(registration_url, timeout=10)
        result["goal_http"] = goal_response.status_code    
        if goal_response.status_code == 200:
            result["ok"] = True
        else:
            result["error"] = f"goal HTTP {goal_response.status_code}"     
    except Exception as e:
        result["error"] = f"goal error: {e!r}"     
    return result      