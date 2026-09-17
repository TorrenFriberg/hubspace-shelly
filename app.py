import os
import asyncio
import threading
import aiohttp
from flask import Flask
from aioafero import v1

app = Flask(__name__)

# These come from Render environment variables
EMAIL = os.environ["HUBSPACE_EMAIL"]
PASSWORD = os.environ["HUBSPACE_PASSWORD"]

# Your EcoSmart / Hubspace bulb
DEVICE_ID = "1522d79f-f5bd-4543-b9de-3b2b2bbf4b8d"

# Persistent Hubspace connection
session = None
bridge = None
loop = None


async def initialize_hubspace():
    global session, bridge, loop

    session = aiohttp.ClientSession()
    loop = asyncio.get_running_loop()

    auth = v1.AferoAuth.for_login(
        session,
        EMAIL,
        PASSWORD
    )

    token_data = await auth.login()

    bridge = v1.AferoBridgeV1(
        EMAIL,
        token_data.refresh_token,
        session
    )

    await bridge.initialize()

    print("Hubspace connection initialized!")


@app.route("/")
def home():
    return "Hubspace-Shelly server is running!"


@app.route("/on")
def on():
    future = asyncio.run_coroutine_threadsafe(
        bridge.lights.turn_on(DEVICE_ID),
        loop
    )

    future.result(timeout=15)

    return "Bulb turned on!"


@app.route("/off")
def off():
    future = asyncio.run_coroutine_threadsafe(
        bridge.lights.turn_off(DEVICE_ID),
        loop
    )

    future.result(timeout=15)

    return "Bulb turned off!"


def start_hubspace():
    global loop

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    loop.run_until_complete(initialize_hubspace())

    # Keep the Hubspace event loop alive
    loop.run_forever()


if __name__ == "__main__":
    # Start Hubspace in a background thread
    hubspace_thread = threading.Thread(
        target=start_hubspace,
        daemon=True
    )

    hubspace_thread.start()

    # Give Hubspace a moment to initialize
    hubspace_thread.join(timeout=10)

    # Start Flask locally
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000))
    )