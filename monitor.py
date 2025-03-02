import os
import requests
from twilio.rest import Client
import time

# ================== TWILIO CREDENTIALS (KEEP THESE SECURE) ==================
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")  # Twilio Account SID from environment variable
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")    # Twilio Auth Token from environment variable
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER") # Twilio phone number

# ================== PHONE NUMBERS (CONFIGURED VIA ENV VARIABLES) ==================
YOUR_PHONE_NUMBER = os.getenv("YOUR_PHONE_NUMBER")      # Your personal phone number

# URLs to monitor
URLS_TO_MONITOR = [
    "https://musaid-donationbox.myfundbox.com/MultipleDBox.jsf?orgid=1331",
    "https://fcrm.myfundbox.com/MultipleDBox.jsf?orgid=1331"
]

# Path where SSL certificate will be temporarily stored
SSL_CERT_PATH = "/tmp/myfundbox.crt"

# Headers to bypass WAF
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

# ================== WRITE CERTIFICATE FROM ENVIRONMENT VARIABLE ==================
certificate_content = os.getenv("SSL_CERTIFICATE", "")

if certificate_content:
    with open(SSL_CERT_PATH, "w") as cert_file:
        cert_file.write(certificate_content)
    print("✅ SSL certificate loaded successfully.")
else:
    print("⚠️ WARNING: SSL_CERTIFICATE environment variable is empty!")


def wait_for_call_status(client, call_sid, timeout=60):
    """Waits for and returns the final status of a call."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        call = client.calls(call_sid).fetch()
        if call.status in ['completed', 'failed', 'busy', 'no-answer', 'canceled']:
            return call.status
        time.sleep(2)
    return 'no-answer'


def send_call_notification(phone_number):
    """Sends a call notification using Twilio API when the monitored website is down."""
    try:
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

        # Make first call
        first_call = client.calls.create(
            to=phone_number,
            from_=TWILIO_PHONE_NUMBER,
            twiml="<Response><Say>The monitored website is down. Please check immediately.</Say></Response>"
        )
        print(f"📞 First call initiated to {phone_number} with SID: {first_call.sid}")

        # Wait for call status
        call_status = wait_for_call_status(client, first_call.sid)
        print(f"📞 First call status: {call_status}")

        # Make second call ONLY if first call was not answered
        if call_status == 'no-answer':
            print(f"⚠️ First call was not answered. Attempting second call...")
            time.sleep(20)  # Wait 20 seconds before second attempt

            second_call = client.calls.create(
                to=phone_number,
                from_=TWILIO_PHONE_NUMBER,
                twiml="<Response><Say>This is a second attempt. The monitored website is down. Please check immediately.</Say></Response>"
            )
            print(f"📞 Second call initiated to {phone_number} with SID: {second_call.sid}")

            # Wait for second call status
            second_status = wait_for_call_status(client, second_call.sid)
            print(f"📞 Second call status: {second_status}")
        else:
            print(f"✅ First call was {call_status}. No second call needed.")

    except Exception as e:
        print(f"❌ ERROR: Unable to send call notification to {phone_number}. Exception: {e}")


def check_url(url):
    """Checks the status of a given URL. Calls if the server does NOT return 200."""
    try:
        response = requests.get(url, timeout=60, verify=SSL_CERT_PATH, headers=HEADERS)

        if response.status_code != 200:
            print(f"🚨 ALERT: {url} is down with status code {response.status_code}")
            send_call_notification(YOUR_PHONE_NUMBER)

        elif response.status_code == 403:
            print(f"⚠️ WAF Blocked Request! Received 403 Forbidden. Checking response content for hidden 502...")
            if "502 Bad Gateway" in response.text:
                print(f"🚨 Detected 502 in response body despite WAF returning 403.")
                send_call_notification(YOUR_PHONE_NUMBER)

            else:
                print(f"⚠️ Site is blocked by WAF. No action needed.")

        else:
            print(f"✅ SUCCESS: {url} is up with status code {response.status_code}")

    except requests.exceptions.RequestException as e:
        print(f"❌ ERROR: Unable to reach {url}. Exception: {e}")


if __name__ == "__main__":
    print("🔍 Monitoring URLs:")
    for url in URLS_TO_MONITOR:
        print(f" - {url}")  # ✅ Prints each URL separately
        check_url(url)  # ✅ Passes a single URL