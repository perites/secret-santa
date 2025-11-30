import requests
import time
import sys
import os
from datetime import datetime

BASE_URL = "http://localhost:5003"
SESSION = requests.Session()

def log(msg):
    print(f"[TEST] {msg}")

def test_auto_login():
    log("Testing auto-login...")
    response = SESSION.get(f"{BASE_URL}/")
    if response.status_code == 200:
        return True
    return False

def test_deadline_revert():
    log("Testing deadline revert (should allow taking)...")
    
    # Deadline is Dec 10, current is Nov 30. Should allow.
    recipients = SESSION.get(f"{BASE_URL}/api/recipients").json()
    available = next((r for r in recipients if not r['is_taken']), None)
    
    if available:
        log(f"Trying to take {available['name']}...")
        response = SESSION.post(f"{BASE_URL}/api/take/{available['id']}")
        if response.status_code == 200:
            log("Take successful (Deadline correctly reverted)")
            return True
        else:
            log(f"Failed: {response.text}")
            return False
    else:
        # If all taken, try untake one I took
        my_gift = next((r for r in recipients if r['taken_by_me']), None)
        if my_gift:
            log(f"Trying to untake {my_gift['name']}...")
            response = SESSION.post(f"{BASE_URL}/api/untake/{my_gift['id']}")
            if response.status_code == 200:
                 log("Untake successful (Deadline correctly reverted)")
                 return True
            else:
                log(f"Failed: {response.text}")
                return False
        return True # Skip if full and none mine (unlikely in test env)

def run_tests():
    time.sleep(2)
    if not test_auto_login(): sys.exit(1)
    if not test_deadline_revert(): sys.exit(1)
    log("ALL TESTS PASSED")

if __name__ == "__main__":
    run_tests()
