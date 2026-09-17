import os
import asyncio
import threading
import aiohttp
from flask import Flask
from aioafero import v1

app = Flask(__name__)

# ============================================================
# CONFIGURATION
# ============================================================

EMAIL = os.environ["HUBSPACE_EMAIL"]
PASSWORD = os.environ["HUBSPACE_PASSWORD"]

DEVICE_ID = "1522d79f-f5bd-4543-b9de-3b2b2bbf4b8d"

# ============================================================
# HUBSPACE CONNECTION
# ============================================================

session = None
bridge = None
loop = None

# This lets Flask know when Hubspace is ready
hubspace_ready = threading.Event()


async def initialize_hubspace():
    global session, bridge, loop

    session = aiohttp.ClientSession()
    loop = asyncio.get_running_loop()

    print("Logging into Hubspace...")

    auth = v1.AferoAuth.for_login(
        session,
        EMAIL,
        PASSWORD
    )

    token_data = await auth.login()

    print("Hubspace login successful!")

    bridge = v1.AferoBridgeV1(
        EMAIL,
        token_data.refresh_token,
        session
    )

    await bridge.initialize()

    print("Hubspace connection initialized!")


def start_hubspace():
    global loop

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Initialize Hubspace first
        loop.run_until_complete(initialize_hubspace())

        # Tell Flask that Hubspace is ready
        hubspace_ready.set()

        print("Hubspace event loop running.")

        # Keep the Hubspace connection alive
        loop.run_forever()

    except Exception as e:
        print("Hubspace initialization failed:")
        print(type(e).__name__)
        print(str(e))


# ============================================================
# FLASK ROUTES
# ============================================================

@app.route("/")
def home():
    return "Hubspace-Shelly server is running!"


@app.route("/on")
def on():
    # Wait for Hubspace to finish initializing
    if not hubspace_ready.wait(timeout=30):
        return "Hubspace connection is not ready.", 503

    try:
        future = asyncio.run_coroutine_threadsafe(
            bridge.lights.turn_on(DEVICE_ID),
            loop
        )

        future.result(timeout=15)

        print("Bulb turned ON.")

        return "Bulb turned on!"

    except Exception as e:
        print("ON command failed:")
        print(type(e).__name__)
        print(str(e))

        return "Failed to turn bulb on.", 500


@app.route("/off")
def off():
    # Wait for Hubspace to finish initializing
    if not hubspace_ready.wait(timeout=30):
        return "Hubspace connection is not ready.", 503

    try:
        future = asyncio.run_coroutine_threadsafe(
            bridge.lights.turn_off(DEVICE_ID),
            loop
        )

        future.result(timeout=15)

        print("Bulb turned OFF.")

        return "Bulb turned off!"

    except Exception as e:
        print("OFF command failed:")
        print(type(e).__name__)
        print(str(e))

        return "Failed to turn bulb off.", 500


# ============================================================
# START HUBSPACE WHEN APP IS LOADED
# ============================================================

hubspace_thread = threading.Thread(
    target=start_hubspace,
    daemon=True
)

hubspace_thread.start()


# ============================================================
# LOCAL DEVELOPMENT
# ============================================================

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000))
    )