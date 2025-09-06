from threading import Thread
import time
import requests

# Function to ping the app URL
def ping_website():
    while True:
        try:
            print("Pinging self to stay awake...")
            # Replace this with your Render URL once you deploy!
            response = requests.get("https://room-expense-tracker.onrender.com")
            print(f"Ping successful! Status code: {response.status_code}")
        except Exception as e:
            print(f"Ping failed: {e}")
        # Time between pings (in seconds). 14 minutes = 840 seconds.
        # Pinging every 14 minutes prevents the 15-minute inactivity shutdown.
        time.sleep(14 * 60) 

# Function to run the ping in a separate thread
def run_keep_alive():
    t = Thread(target=ping_website)
    t.daemon = True  # This thread will die when the main thread dies
    t.start()