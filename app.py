import os
import asyncio
import threading
import aiohttp
from flask import Flask
from aioafero import v1

app = Flask(__name__)

EMAIL = os.environ["HUBSPACE_EMAIL"]
PASSWORD = os.environ["HUBSPACE_PASSWORD"]
DEVICE_ID = "1522d79f-f5bd-4543-b9de-3b2b2bbf4b8d"

bridge = None
loop = None
hubspace_ready = threading.Event()
hubspace_error = None
startup_lock = threading.Lock()
startup_started = False


async def initialize_hubspace():
    global bridge

    session = aiohttp.ClientSession()

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


def hubspace_worker():
    global loop, hubspace_error

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        loop.run_until_complete(initialize_hubspace())

        print("Hubspace is READY!")
        hubspace_ready.set()

        loop.run_forever()

    except Exception as e:
        hubspace_error = e

        print("Hubspace ERROR:")
        print(type(e).__name__)
        print(str(e))

        hubspace_ready.set()


def start_hubspace():
    global startup_started

    with startup_lock:
        if startup_started:
            return

        startup_started = True

        print("Starting Hubspace connection...")

        threading.Thread(
            target=hubspace_worker,
            daemon=True
        ).start()


def ensure_hubspace_ready():
    start_hubspace()

    if not hubspace_ready.wait(timeout=60):
        return False

    return hubspace_error is None


@app.route("/")
def home():
    return "Hubspace-Shelly server is running!"


@app.route("/on")
def on():
    if not ensure_hubspace_ready():
        if hubspace_error:
            return f"Hubspace error: {hubspace_error}", 500

        return "Hubspace is still starting.", 503

    try:
        future = asyncio.run_coroutine_threadsafe(
            bridge.lights.turn_on(DEVICE_ID),
            loop
        )

        future.result(timeout=30)

        print("Bulb turned ON!")

        return "Bulb turned on!"

    except Exception as e:
        print("ON ERROR:")
        print(type(e).__name__)
        print(str(e))

        return "Failed to turn bulb on.", 500


@app.route("/off")
def off():
    if not ensure_hubspace_ready():
        if hubspace_error:
            return f"Hubspace error: {hubspace_error}", 500

        return "Hubspace is still starting.", 503

    try:
        future = asyncio.run_coroutine_threadsafe(
            bridge.lights.turn_off(DEVICE_ID),
            loop
        )

        future.result(timeout=30)

        print("Bulb turned OFF!")

        return "Bulb turned off!"

    except Exception as e:
        print("OFF ERROR:")
        print(type(e).__name__)
        print(str(e))

        return "Failed to turn bulb off.", 500

@app.route("/devices")
def devices():
    if not ensure_hubspace_ready():
        if hubspace_error:
            return f"Hubspace error: {hubspace_error}", 500
        return "Hubspace is not ready.", 503

    try:
        devices = list(bridge.lights.devices)

        print("LIGHT DEVICES:")
        print(devices)

        return "<br>".join(
            f"{device.id} — {device.name}"
            for device in devices
        )

    except Exception as e:
        print("DEVICES ERROR:")
        print(type(e).__name__)
        print(str(e))

        return f"DEVICES ERROR: {type(e).__name__}: {e}", 500

@app.route("/status")
def status():
    print("STATUS ROUTE CALLED")
    print(f"hubspace_ready = {hubspace_ready.is_set()}")
    print(f"bridge = {bridge}")
    print(f"loop = {loop}")
    print(f"startup_started = {startup_started}")
    print(f"hubspace_error = {hubspace_error}")

    if not ensure_hubspace_ready():
        print("Hubspace was NOT ready.")
        print(f"hubspace_error = {hubspace_error}")

        if hubspace_error:
            return f"Hubspace error: {hubspace_error}", 500

        return "Hubspace is not ready.", 503

    print("Hubspace IS ready.")

    try:
        device = bridge.lights.get_device(DEVICE_ID)

        print("DEVICE FOUND!")
        print(device)

        return str(device)

    except Exception as e:
        print("STATUS ERROR:")
        print(type(e).__name__)
        print(str(e))

        return f"STATUS ERROR: {type(e).__name__}: {e}", 500