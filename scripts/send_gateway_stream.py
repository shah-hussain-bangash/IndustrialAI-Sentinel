"""Bounded simulated event sender. No passwords, credentials or events are saved."""
import argparse
import getpass
import json
import math
import time
import uuid
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from send_gateway_sample import base_url


class SenderError(Exception):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


class GatewayClient:
    def __init__(self, base, token, retries=5, retry_delay=3, opener=None, sleep=time.sleep):
        self.base = base_url(base)
        self.token = token
        self.retries = retries
        self.retry_delay = retry_delay
        self.opener = opener or build_opener(NoRedirect())
        self.sleep = sleep

    def request(self, path, payload=None, key=None):
        body = json.dumps(payload, allow_nan=False).encode() if payload is not None else None
        headers = {"Authorization": "Bearer " + self.token, "Accept": "application/json"}
        if body is not None:
            headers.update({"Content-Type": "application/json", "Idempotency-Key": key})
        for attempt in range(self.retries + 1):
            try:
                with self.opener.open(Request(self.base + path, data=body, headers=headers), timeout=10) as response:
                    raw = response.read(1024 * 1024 + 1)
                    if len(raw) > 1024 * 1024:
                        raise SenderError("Gateway response exceeded the size limit.")
                    return json.loads(raw)
            except HTTPError as exc:
                if exc.code not in (408, 429) and exc.code < 500:
                    raise SenderError(f"HTTP {exc.code}: request rejected. Check gateway scope, expiry and permissions.") from None
            except (URLError, TimeoutError, ConnectionError):
                pass
            except (ValueError, TypeError):
                raise SenderError("Unexpected gateway response. Stop and check the server.") from None
            if attempt < self.retries:
                print(f"Connection interrupted; retrying the same request ({attempt + 1}/{self.retries}).")
                self.sleep(self.retry_delay)
        raise SenderError("Retry limit reached. Delivery of the last batch is unconfirmed. No local queue is saved; inspect sensor history before restarting.")


CHANNELS = {"vibration": ("mm/s", 2.0, 0.15), "temperature": ("degC", 70.0, 0.5),
            "pressure": ("bar", 5.0, 0.05), "flow": ("m3/h", 120.0, 1.5)}


def validate_identity(identity):
    uuid.UUID(identity["gateway_id"])
    items = identity["sensors"]
    if len(items) != 4:
        raise ValueError("Expected four sensors")
    sensors = {sensor["channel"]: sensor for sensor in items}
    if set(sensors) != set(CHANNELS):
        raise ValueError("Unexpected channels")
    for channel, sensor in sensors.items():
        uuid.UUID(sensor["id"])
        if sensor["unit"] != CHANNELS[channel][0]:
            raise ValueError("Unexpected units")
    return sensors


def make_batch(sensors, run_id, sequence, observed_at):
    key = f"test-stream-{run_id}-{sequence}"
    records = []
    for offset, (channel, (unit, baseline, amplitude)) in enumerate(CHANNELS.items()):
        records.append({"sensor_id": sensors[channel]["id"], "message_id": key + "-" + channel,
                        "observed_at": observed_at, "raw_value": round(baseline + amplitude * math.sin(sequence / 3 + offset), 4),
                        "raw_unit": unit, "quality": "good"})
    return key, {"records": records}


def stream(client, frames, interval, sleep=time.sleep, clock=time.time):
    sensors = validate_identity(client.request("/api/gateway-identity"))
    run_id = str(uuid.uuid4())
    inserted = duplicates = 0
    print("SIMULATED TEST DATA: independent events only; equipment snapshot publication remains manual.")
    for sequence in range(frames):
        key, payload = make_batch(sensors, run_id, sequence, clock() - 1)
        result = client.request("/api/gateway-events/batches", payload, key)
        new, duplicate = result["inserted"], result["duplicates"]
        if type(new) is not int or type(duplicate) is not int or new < 0 or duplicate < 0 or new + duplicate != 4:
            raise SenderError("Unexpected batch receipt. Stop and inspect sensor history.")
        inserted += new
        duplicates += duplicate
        print(f"Batch {sequence + 1}/{frames}: inserted={new}, duplicates={duplicate}, snapshot_projection=false")
        if sequence + 1 < frames:
            sleep(interval)
    print(f"Finished: inserted={inserted}, duplicates={duplicates}. Review the sensor event histories.")


def main():
    parser = argparse.ArgumentParser(description="Send bounded simulated readings through one equipment-scoped gateway.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8127")
    parser.add_argument("--frames", type=int, default=12, help="Number of four-event batches, 1–120 (default 12).")
    parser.add_argument("--interval", type=float, default=5, help="Seconds between accepted batches, 5–60 (default 5).")
    args = parser.parse_args()
    try:
        base = base_url(args.base_url)
        if not 1 <= args.frames <= 120 or not 5 <= args.interval <= 60:
            parser.error("Use 1–120 frames and an interval of 5–60 seconds.")
        print("Pause Sentinel demo replay first. Use a gateway named SIMULATED TEST for DEMO-PUMP-001.")
        token = getpass.getpass("Gateway credential (hidden; not your Sentinel password): ").strip()
        if not token.startswith("sgw.") or len(token) > 200:
            raise SenderError("Use an equipment-scoped gateway credential.")
        stream(GatewayClient(base, token), args.frames, args.interval)
    except KeyboardInterrupt:
        raise SystemExit("Stopped. An in-flight batch may have been accepted; check sensor history. No queue was saved.") from None
    except (ValueError, KeyError, TypeError):
        raise SystemExit("Invalid URL or unexpected sensor response. No credential was printed.") from None
    except SenderError as exc:
        raise SystemExit(str(exc)) from None


if __name__ == "__main__":
    main()
