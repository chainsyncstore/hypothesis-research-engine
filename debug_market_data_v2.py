
import os
import requests
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("CAPITAL_API_URL")
IDENTIFIER = os.getenv("CAPITAL_IDENTIFIER")
PASSWORD = os.getenv("CAPITAL_PASSWORD")
API_KEY = os.getenv("CAPITAL_API_KEY")

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
headers = {
    "CST": cst,
    "X-SECURITY-TOKEN": x_security_token,
    "Content-Type": "application/json"
}

epic = "EURUSD"
url = f"{BASE_URL}/api/v1/prices/{epic}"

# Scenario 1: 1000-minute range WITH max=1000 (Simulating fetch_historical)
print("\n--- Test 1: 1000m Range + max=1000 ---")
to_dt = datetime.now()
from_dt = to_dt - timedelta(minutes=1000)
params_1 = {
    "resolution": "MINUTE",
    "max": 1000,
    "from": from_dt.strftime("%Y-%m-%dT%H:%M:%S"),
    "to": to_dt.strftime("%Y-%m-%dT%H:%M:%S")
}
try:
    r = sess.get(url, headers=headers, params=params_1, timeout=10)
    print(f"Status: {r.status_code}")
    if r.status_code != 200:
        print(f"Response: {r.text}")
    else:
        print(f"Success! Got {len(r.json()['prices'])} bars")
except Exception as e:
    print(f"Error: {e}")

# Scenario 2: 1000-minute range WITHOUT max
print("\n--- Test 2: 1000m Range (NO max) ---")
params_2 = {
    "resolution": "MINUTE",
    # "max": 1000,
    "from": from_dt.strftime("%Y-%m-%dT%H:%M:%S"),
    "to": to_dt.strftime("%Y-%m-%dT%H:%M:%S")
}
try:
    r = sess.get(url, headers=headers, params=params_2, timeout=10)
    print(f"Status: {r.status_code}")
    if r.status_code != 200:
        print(f"Response: {r.text}")
    else:
        print(f"Success! Got {len(r.json()['prices'])} bars")
except Exception as e:
    print(f"Error: {e}")

# Scenario 3: ONLY from + max=1000
print("\n--- Test 3: Only from + max=1000 ---")
params_3 = {
    "resolution": "MINUTE",
    "max": 1000,
    "from": from_dt.strftime("%Y-%m-%dT%H:%M:%S"),
    # "to": ...
}
try:
    r = sess.get(url, headers=headers, params=params_3, timeout=10)
    print(f"Status: {r.status_code}")
    if r.status_code != 200:
        print(f"Response: {r.text}")
    else:
         print(f"Success! Got {len(r.json()['prices'])} bars")
except Exception as e:
    print(f"Error: {e}")
