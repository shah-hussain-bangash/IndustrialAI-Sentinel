"""Optional real MQTT -> authenticated HTTP ingestion connector.

Topic: sentinel/<asset UUID>/snapshot
Payload: timestamp, vibration, temperature, pressure, flow, message_id, quality.
Credentials come from the environment, never command arguments or source.
"""

import json
import os
import sys
import time
from pathlib import Path
import httpx
import paho.mqtt.client as mqtt
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
api_url = os.getenv("SENTINEL_API_URL", "http://127.0.0.1:8127")
email = os.getenv("INGEST_EMAIL")
password = os.getenv("INGEST_PASSWORD")
if not email or not password:
    raise SystemExit("Set INGEST_EMAIL and INGEST_PASSWORD for a permitted ingestion account.")
http = httpx.Client(base_url=api_url, timeout=20)


def authenticate():
    login = http.post("/api/auth/login", json={"email": email, "password": password})
    login.raise_for_status()
    http.headers["X-CSRF-Token"] = login.json()["csrf"]


authenticate()


def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        client.subscribe("sentinel/+/snapshot", qos=1)
        print("Subscribed to permitted snapshot topics; application authorization still applies.")


def on_message(client, userdata, message):
    try:
        if len(message.payload) > 65536:
            raise ValueError("Payload exceeds connector limit.")
        payload = json.loads(message.payload)
        payload["asset_id"] = message.topic.split("/")[1]
        # Use the same identity across redelivery. Publisher must provide stable identity.
        message_id = payload.get("message_id")
        if not isinstance(message_id, str) or not message_id:
            raise ValueError("Stable message_id is required.")
        body = {"records": [payload]}
        headers = {
            "Idempotency-Key": "mqtt-"
            + __import__("hashlib").sha256(message_id.encode()).hexdigest()
        }
        result = http.post("/api/telemetry/batches", json=body, headers=headers)
        if result.status_code == 401:
            authenticate()
            result = http.post("/api/telemetry/batches", json=body, headers=headers)
        result.raise_for_status()
        print("Snapshot stored:", message_id)
    except Exception as exc:
        print(
            "Snapshot rejected; publisher must replay after correction:",
            type(exc).__name__,
            str(exc)[:160],
            file=sys.stderr,
        )


client = mqtt.Client(
    mqtt.CallbackAPIVersion.VERSION2,
    client_id=os.getenv("MQTT_CLIENT_ID", "sentinel-reference-bridge"),
)
client.on_connect = on_connect
client.on_message = on_message
if os.getenv("MQTT_USERNAME"):
    client.username_pw_set(os.environ["MQTT_USERNAME"], os.getenv("MQTT_PASSWORD"))
if os.getenv("MQTT_TLS", "true").lower() == "true":
    client.tls_set()
client.connect(os.getenv("MQTT_HOST", "localhost"), int(os.getenv("MQTT_PORT", "8883")), 60)
try:
    client.loop_forever()
finally:
    http.close()
    client.disconnect()
