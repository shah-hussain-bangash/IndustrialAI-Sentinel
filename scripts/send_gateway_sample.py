"""One asset-scoped sample batch; credential is prompted, never printed or saved."""
import argparse
import getpass
import json
import time
import uuid
from urllib.error import HTTPError,URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler,Request,build_opener


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,request,fp,code,msg,headers,newurl):
        return None


def base_url(value):
    try:
        parsed=urlparse(value);port=parsed.port
    except ValueError:raise ValueError("Use a valid local HTTP or HTTPS base URL.")
    if parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ("","/") or not parsed.hostname:
        raise ValueError("Base URL must contain only scheme, host and optional port.")
    if parsed.scheme!="https" and not (parsed.scheme=="http" and parsed.hostname in ("127.0.0.1","localhost","::1")):
        raise ValueError("HTTP is allowed only for loopback. Remote senders require HTTPS.")
    return value.rstrip("/")


def send(base,token):
    opener=build_opener(NoRedirect())
    def request(path,payload=None,key=None):
        encoded=json.dumps(payload,allow_nan=False).encode() if payload is not None else None
        headers={"Authorization":"Bearer "+token,"Accept":"application/json"}
        if encoded is not None:headers.update({"Content-Type":"application/json","Idempotency-Key":key})
        for attempt in range(3):
            try:
                with opener.open(Request(base+path,data=encoded,headers=headers),timeout=15) as response:
                    raw=response.read(1024*1024+1)
                    if len(raw)>1024*1024:raise ValueError("Response too large")
                    return json.loads(raw)
            except HTTPError as e:
                if e.code>=500 and attempt<2:time.sleep(.5);continue
                raise SystemExit(f"Sender request failed with HTTP {e.code}. Check the credential, asset scope and server logs.")
            except (URLError,TimeoutError):
                if attempt<2:time.sleep(.5);continue
                raise SystemExit("Could not reach the gateway API. Check the local server and base URL.")
    identity=request("/api/gateway-identity")
    gateway_id=str(uuid.UUID(identity["gateway_id"]))
    expected={"vibration":("mm/s",2),"temperature":("degC",70),"pressure":("bar",5),"flow":("m3/h",120)}
    sensors={s["channel"]:s for s in identity["sensors"]}
    if set(sensors)!=set(expected):raise ValueError("Gateway must expose exactly four canonical sensors.")
    clock=time.time()-1;batch=str(uuid.uuid4());records=[]
    for channel,(unit,value) in expected.items():
        sensor=sensors[channel]
        if sensor["unit"]!=unit:raise ValueError("Unexpected canonical sensor unit.")
        id=str(uuid.UUID(sensor["id"]))
        records.append({"sensor_id":id,"message_id":batch+"-"+channel,"observed_at":clock,"raw_value":value,"raw_unit":unit,"quality":"good"})
    result=request("/api/gateway-events/batches",{"records":records},batch)
    return {"gateway_id":gateway_id,"inserted":int(result["inserted"]),"duplicates":int(result["duplicates"]),"snapshot_projection":False}


def main():
    parser=argparse.ArgumentParser(description="Send one four-channel sample through an asset-scoped credential.")
    parser.add_argument("--base-url",default="http://127.0.0.1:8127")
    args=parser.parse_args()
    try:base=base_url(args.base_url)
    except ValueError as e:raise SystemExit(str(e))
    token=getpass.getpass("Gateway credential (input hidden): ").strip()
    if not token.startswith("sgw.") or len(token)>200:raise SystemExit("Use a scoped gateway credential, not your account password.")
    try:result=send(base,token)
    except (ValueError,KeyError,TypeError):raise SystemExit("The gateway API returned an unexpected response. No credential was printed.")
    print(json.dumps(result,indent=2))
    print("Independent events submitted. Review Equipment alignment before publishing a snapshot.")


if __name__=="__main__":main()
