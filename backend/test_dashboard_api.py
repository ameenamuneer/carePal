
import requests
import json
import sys

BASE_URL = "http://127.0.0.1:8001"
USERNAME = "ameena"
PASSWORD = "passme123"

def test_dashboard():
    print(f"Testing Dashboard API for user: {USERNAME}")
    
    # 1. Login
    login_url = f"{BASE_URL}/api/v1/auth/login/"
    print(f"1. logging in to {login_url}...")
    try:
        session = requests.Session()
        resp = session.post(login_url, json={"username": USERNAME, "password": PASSWORD})
        
        if resp.status_code != 200:
            print(f"FAILED: Login failed with status {resp.status_code}")
            print(resp.text)
            return

        token_data = resp.json()
        if 'tokens' in token_data:
             access_token = token_data['tokens'].get("access")
        elif 'access' in token_data:
             access_token = token_data.get("access")
        elif 'token' in token_data:
             access_token = token_data.get("token")
        
        if not access_token:
             print("Warning: Could not isolate access_token from response. Response keys:", token_data.keys())
             print("Response dump:", json.dumps(token_data, indent=2))
        else:
             print("Login successful. Token obtained.")
             session.headers.update({"Authorization": f"Bearer {access_token}"})

    except Exception as e:
        print(f"FAILED: Connectivity error during login: {e}")
        return

    # 2. Get Dashboard Data
    # First, try to get the patient ID if needed, but the view usually infers it.
    dashboard_url = f"{BASE_URL}/api/v1/analytics/dashboard/patient/"
    print(f"\n2. Fetching Dashboard Data from {dashboard_url}...")
    
    try:
        resp = session.get(dashboard_url)
        print(f"Status Code: {resp.status_code}")
        
        try:
            data = resp.json()
            print("Response Data:")
            print(json.dumps(data, indent=2))
        except:
            print("Response Text (Non-JSON):")
            print(resp.text)
            
    except Exception as e:
        print(f"FAILED: Error fetching dashboard: {e}")

if __name__ == "__main__":
    test_dashboard()
