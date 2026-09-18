import os
import asyncio
import threading
import aiohttp
from flask import Flask, render_template_string
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


HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta
        name="viewport"
        content="width=device-width, initial-scale=1.0,
                 maximum-scale=1.0, user-scalable=no"
    >

    <title>Bathroom Light</title>

    <style>
        * {
            box-sizing: border-box;
            -webkit-tap-highlight-color: transparent;
        }

        html, body {
            margin: 0;
            padding: 0;
            width: 100%;
            height: 100%;
            font-family: Arial, Helvetica, sans-serif;
            background: #111;
            color: white;
        }

        body {
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
        }

        .container {
            width: 100%;
            max-width: 700px;
            padding: 30px;
            text-align: center;
        }

        h1 {
            font-size: 42px;
            margin: 0 0 10px 0;
        }

        .subtitle {
            font-size: 22px;
            opacity: 0.7;
            margin-bottom: 35px;
        }

        .button {
            width: 100%;
            height: 200px;
            border: none;
            border-radius: 30px;
            margin-bottom: 25px;
            font-size: 48px;
            font-weight: bold;
            color: white;
            cursor: pointer;
            touch-action: manipulation;
            transition: transform 0.08s;
        }

        .button:active {
            transform: scale(0.97);
        }

        .on {
            background: #159447;
        }

        .off {
            background: #b72c2c;
        }

        .status {
            min-height: 35px;
            font-size: 20px;
            margin-top: 10px;
            opacity: 0.8;
        }

        .loading {
            opacity: 0.5;
            pointer-events: none;
        }

        @media (max-width: 600px) {
            .container {
                padding: 20px;
            }

            h1 {
                font-size: 34px;
            }

            .subtitle {
                font-size: 18px;
            }

            .button {
                height: 180px;
                font-size: 40px;
            }
        }
    </style>
</head>

<body>

<div class="container">

    <h1>Bathroom Light</h1>

    <div class="subtitle">
        Tap a button to control the light
    </div>

    <button
        id="onButton"
        class="button on"
        onclick="controlLight('/on', 'onButton', 'TURN ON')"
    >
        TURN ON
    </button>

    <button
        id="offButton"
        class="button off"
        onclick="controlLight('/off', 'offButton', 'TURN OFF')"
    >
        TURN OFF
    </button>

    <div id="status" class="status">
        Ready
    </div>

</div>

<script>
async function controlLight(url, buttonId, originalText) {

    const button = document.getElementById(buttonId);
    const status = document.getElementById("status");

    button.classList.add("loading");
    button.innerText = "PLEASE WAIT...";
    status.innerText = "Sending command...";

    try {
        const response = await fetch(url);

        const text = await response.text();

        if (response.ok) {
            if (url === "/on") {
                status.innerText = "Light is ON";
            } else {
                status.innerText = "Light is OFF";
            }
        } else {
            status.innerText = "Something went wrong";
            console.error(text);
        }

    } catch (error) {
        status.innerText = "Connection error";
        console.error(error);

    } finally {
        button.classList.remove("loading");
        button.innerText = originalText;
    }
}
</script>

</body>
</html>
"""


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

    await bridge.async_block_until_done()

    print("Hubspace connection initialized!")
    print("Hubspace device discovery completed!")


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
    return render_template_string(HTML)


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


@app.route("/status")
def status():
    if not ensure_hubspace_ready():
        if hubspace_error:
            return f"Hubspace error: {hubspace_error}", 500

        return "Hubspace is not ready.", 503

    try:
        device = bridge.lights.get_device(DEVICE_ID)

        return str(device)

    except Exception as e:
        return f"STATUS ERROR: {type(e).__name__}: {e}", 500