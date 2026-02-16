
import os
import requests
import time
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("CAPITAL_API_URL")
IDENTIFIER = os.getenv("CAPITAL_IDENTIFIER")
PASSWORD = os.getenv("CAPITAL_PASSWORD")
API_KEY = os.getenv("CAPITAL_API_KEY")

print(f"Connecting to: {BASE_URL}")

# authenticate
sess = requests.Session()
auth_headers = {
    "X-CAP-API-KEY": API_KEY,
    "Content-Type": "application/json"
}
auth_payload = {
    "identifier": IDENTIFIER,
    "password": PASSWORD
}

print("Authenticating...")
resp = sess.post(f"{BASE_URL}/api/v1/session", json=auth_payload, headers=auth_headers, timeout=10)
if resp.status_code != 200:
    print(f"Auth failed: {resp.status_code} {resp.text}")
    exit(1)

cst = resp.headers.get("CST")
x_security_token = resp.headers.get("X-SECURITY-TOKEN")
print("Authenticated successfully.")

headers = {
    "CST": cst,
    "X-SECURITY-TOKEN": x_security_token,
    "Content-Type": "application/json"
}

# Test prices with different params
resolutions = ["MINUTE", "M1", "1", "m1"]
epic = "EURUSD"

for r in resolutions:
    print(f"\n--- Testing resolution='{r}' ---")
    url = f"{BASE_URL}/api/v1/prices/{epic}"
    params = {
        "resolution": r,
        "max": 10
    }
    
    try:
        r_resp = sess.get(url, headers=headers, params=params, timeout=10)
        print(f"Status: {r_resp.status_code}")
        if r_resp.status_code == 200:
            data = r_resp.json()
            prices = data.get("prices", [])
            print(f"✅ Success! Got {len(prices)} bars.")
            if prices:
                print(f"Sample: {prices[0]}")
        else:
            print(f"❌ Failed: {r_resp.text}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
    
    time.sleep(1)
