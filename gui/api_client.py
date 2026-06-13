import requests
from .logger import logger

BASE_URL = "http://127.0.0.1:8000"

def send_request(method, endpoint, payload=None):
    url = f"{BASE_URL}{endpoint}"
    try:
        method = method.upper()
        if method == "GET":
            r = requests.get(url, timeout=5)
        elif method == "POST":
            r = requests.post(url, json=payload, timeout=5)
        elif method == "PUT":
            r = requests.put(url, json=payload, timeout=5)
        elif method == "DELETE":
            r = requests.delete(url, json=payload, timeout=5)
        else:
            return {"error": f"Unsupported method {method}"}

        r.raise_for_status()
        return r.json()
    except Exception as e:
        logger.log(f"API error: {e}")
        return {"error": str(e)}
