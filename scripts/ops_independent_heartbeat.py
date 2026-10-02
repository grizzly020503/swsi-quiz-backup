#!/usr/bin/env python3
"""Zero-secret SWSI heartbeat evaluator intended for schedulers outside GitHub Actions."""
from __future__ import annotations

import argparse, hashlib, json, time, urllib.error, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

COMPONENTS = {"site", "data_freshness", "grading", "ai", "review_backlog", "task_heartbeat"}
STATUSES = {"healthy", "warning", "degraded", "failed", "unknown"}
SEVERITY = {
    "site": {"warning":"high","degraded":"high","failed":"critical","unknown":"warning"},
    "data_freshness": {"warning":"warning","degraded":"high","failed":"high","unknown":"warning"},
    "grading": {"warning":"high","degraded":"high","failed":"critical","unknown":"high"},
    "ai": {"warning":"warning","degraded":"warning","failed":"warning","unknown":"warning"},
    "review_backlog": {"warning":"warning","degraded":"high","failed":"high","unknown":"warning"},
    "task_heartbeat": {"warning":"warning","degraded":"high","failed":"high","unknown":"warning"},
}
RANK = {"warning":1,"high":2,"critical":3}


def parse_time(value: str) -> datetime:
    raw = str(value or "").strip()
    if not raw: raise ValueError("timestamp is empty")
    if raw.endswith("Z"): raw = raw[:-1] + "+00:00"
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def incident_key(component: str, failure: str, scope: str) -> str:
    raw = f"v1\n{component}\n{failure}\n{scope}".encode()
    return "inc1:" + hashlib.sha256(raw).hexdigest()[:24]


def validate(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise ValueError("heartbeat must be schema_version=1")
    producer = str(payload.get("producer") or "").strip()
    generated = str(payload.get("generated_at") or "").strip()
    rows = payload.get("components")
    if not producer or not generated or not isinstance(rows, dict):
        raise ValueError("producer, generated_at and components{} are required")
    parse_time(generated)
    if set(rows) - COMPONENTS: raise ValueError("unknown component")
    out = {}
    for name in sorted(COMPONENTS):
        row = rows.get(name)
        if not isinstance(row, dict): raise ValueError(f"missing component: {name}")
        status = str(row.get("status") or "").lower()
        checked = str(row.get("checked_at") or "")
        if status not in STATUSES: raise ValueError(f"{name}: invalid status")
        parse_time(checked)
        detail = row.get("detail") or {}
        if not isinstance(detail, dict): raise ValueError(f"{name}: detail must be object")
        out[name] = {
            "status": status,
            "checked_at": checked,
            "scope": str(row.get("scope") or name),
            "failure_class": str(row.get("failure_class") or status),
            "detail": detail,
        }
    return {"producer": producer, "generated_at": generated, "components": out}


class Redirects(urllib.request.HTTPRedirectHandler):
    def __init__(self, hosts: set[str]): super().__init__(); self.hosts = hosts
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        u = urllib.parse.urlparse(newurl)
        if u.scheme != "https" or (u.hostname or "").lower() not in self.hosts:
            raise urllib.error.HTTPError(newurl, code, "redirect target not allowlisted", headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch(url: str, timeout: float, retries: int, redirect_hosts: set[str]) -> tuple[bool,int|None,bytes|None,str|None]:
    u = urllib.parse.urlparse(url)
    if u.scheme != "https" or not u.hostname: raise ValueError("URL must be absolute HTTPS")
    opener = urllib.request.build_opener(Redirects({u.hostname.lower(), *{x.lower() for x in redirect_hosts}}))
    failure = "network_error"; status = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent":"swsi-independent-heartbeat/1.0"})
            with opener.open(req, timeout=timeout) as r:
                return True, r.status, r.read(2_000_000), None
        except urllib.error.HTTPError as e:
            status = e.code; failure = "http_5xx" if e.code >= 500 else "http_4xx"
            if e.code < 500: break
        except (urllib.error.URLError, TimeoutError) as e:
            failure = "timeout" if "time" in str(e).lower() else "network_error"
        if attempt < retries: time.sleep(min(.25 * (2 ** attempt), 1))
    return False, status, None, failure


def incident(component: str, status: str, failure: str, scope: str, message: str) -> dict[str, Any]:
    return {
        "incident_key": incident_key(component, failure, scope),
        "component": component, "status": status, "failure_class": failure, "scope": scope,
        "severity": SEVERITY.get(component, {}).get(status, "warning"), "message": message[:300],
    }


def current_incidents(payload: dict[str, Any], now: datetime, max_age_h: float, skew_min: float) -> list[dict[str, Any]]:
    rows = []
    generated = parse_time(payload["generated_at"])
    if generated > now and (generated-now).total_seconds() > skew_min*60:
        rows.append(incident("task_heartbeat","failed","future_timestamp","heartbeat","heartbeat timestamp is too far in the future"))
    elif (now-generated).total_seconds()/3600 > max_age_h:
        rows.append(incident("task_heartbeat","failed","heartbeat_stale","heartbeat","heartbeat freshness window exceeded"))
    for name, row in payload["components"].items():
        checked = parse_time(row["checked_at"])
        if checked > now and (checked-now).total_seconds() > skew_min*60:
            rows.append(incident(name,"failed","future_timestamp",row["scope"],"component timestamp is too far in the future")); continue
        if (now-checked).total_seconds()/3600 > max_age_h:
            rows.append(incident(name,"failed","component_stale",row["scope"],"component freshness window exceeded")); continue
        if row["status"] != "healthy":
            msg = str(row["detail"].get("message") or f"{name} reported {row['status']}")
            rows.append(incident(name,row["status"],row["failure_class"],row["scope"],msg))
    return list({r["incident_key"]: r for r in rows}.values())


def recovery_observed(row: dict[str, Any], hb: dict[str, Any] | None,
                      now: datetime, max_age_h: float, skew_min: float,
                      site_ok: bool | None) -> bool:
    """Absence of an incident is not evidence of recovery."""
    def fresh(value: str) -> bool:
        age = (now - parse_time(value)).total_seconds()
        return -skew_min * 60 <= age <= max_age_h * 3600

    component, scope = row.get("component"), row.get("scope")
    if component == "site" and scope == "homepage":
        return site_ok is True
    if hb is None or not fresh(hb["generated_at"]):
        return False
    if component == "task_heartbeat" and scope == "heartbeat":
        return True  # Valid, fresh envelope recovers an envelope incident only.
    current = hb["components"].get(component)
    return bool(current and current["scope"] == scope
                and current["status"] == "healthy" and fresh(current["checked_at"]))


def previous(path: Path|None) -> dict[str, dict[str, Any]]:
    if not path: return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    rows = raw.get("incidents") if isinstance(raw, dict) else None
    if not isinstance(rows, list): raise ValueError("previous state must contain incidents[]")
    return {r["incident_key"]: r for r in rows if isinstance(r,dict) and r.get("incident_key")}


def evaluate(heartbeat: Any, now: datetime, max_age_h: float, skew_min: float, prev: dict[str,dict[str,Any]], independent: bool,
             site_ok: bool|None=None, site_status: int|None=None, site_failure: str|None=None) -> dict[str, Any]:
    try:
        hb = validate(heartbeat); active = current_incidents(hb, now, max_age_h, skew_min); hb_error = None
    except Exception as e:
        hb = None; hb_error = str(e); active = [incident("task_heartbeat","failed","invalid_heartbeat","heartbeat",hb_error)]
    if site_ok is False:
        active.append(incident("site","failed",site_failure or f"http_{site_status or 0}","homepage","public homepage probe failed"))
    active_map = {r["incident_key"]: r for r in active}
    out, resolved = [], []
    for key, row in active_map.items():
        prior = prev.get(key); x = dict(row)
        x["transition"] = "ongoing" if prior else "new"
        x["first_seen_at"] = prior.get("first_seen_at") if prior else iso(now); x["last_seen_at"] = iso(now); out.append(x)
    for key, row in prev.items():
        if key not in active_map:
            x = dict(row)
            if recovery_observed(row, hb, now, max_age_h, skew_min, site_ok):
                x["transition"] = "resolved"; x["resolved_at"] = iso(now); resolved.append(x)
            else:
                # Keep last_seen_at as the last actual failure observation.
                x["transition"] = "ongoing"; x["observation_status"] = "recovery_unconfirmed"
                x["last_evaluated_at"] = iso(now); out.append(x)
    rank = max([RANK.get(x["severity"],1) for x in out] or [0])
    return {
        "schema_version":1, "evaluated_at":iso(now), "independent_monitoring_active":bool(independent),
        "monitoring_note":"external runtime asserted" if independent else "independent runtime not asserted",
        "overall_status":"unavailable" if rank>=3 else "degraded" if rank else "healthy",
        "heartbeat_generated_at": hb.get("generated_at") if hb else None, "heartbeat_error":hb_error,
        "incidents":sorted(out,key=lambda x:x["incident_key"]), "resolved_incidents":sorted(resolved,key=lambda x:x["incident_key"]),
    }


def self_test() -> dict[str, Any]:
    now = parse_time("2026-10-02T12:00:00Z")
    def hb():
        return {"schema_version":1,"producer":"fixture","generated_at":"2026-10-02T11:30:00Z","components":{
            n:{"status":"healthy","checked_at":"2026-10-02T11:30:00Z","scope":n,"detail":{}} for n in COMPONENTS}}
    ok = evaluate(hb(),now,8,5,{},True,True,200,None); assert ok["overall_status"]=="healthy"
    stale=hb(); stale["generated_at"]="2026-10-01T00:00:00Z"; a=evaluate(stale,now,8,5,{},False); key=a["incidents"][0]["incident_key"]
    b=evaluate(stale,now,8,5,{key:a["incidents"][0]},False); assert b["incidents"][0]["incident_key"]==key and b["incidents"][0]["transition"]=="ongoing"
    c=evaluate(hb(),now,8,5,{key:a["incidents"][0]},False); assert c["resolved_incidents"][0]["transition"]=="resolved"
    for component,status,failure,severity in [
        ("ai","degraded","fallback_active","warning"),
        ("data_freshness","degraded","source_stale","high"),
        ("review_backlog","warning","sla_breach","warning"),
        ("grading","failed","grading_contract_failed","critical")]:
        x=hb(); x["components"][component].update({"status":status,"failure_class":failure}); r=evaluate(x,now,8,5,{},False)
        assert next(i for i in r["incidents"] if i["component"]==component)["severity"]==severity
    assert evaluate({"schema_version":9},now,8,5,{},False)["incidents"][0]["failure_class"]=="invalid_heartbeat"
    future=hb(); future["generated_at"]="2026-10-03T12:00:00Z"; assert any(i["failure_class"]=="future_timestamp" for i in evaluate(future,now,8,5,{},False)["incidents"])
    assert evaluate(hb(),now,8,5,{},False,False,None,"timeout")["overall_status"]=="unavailable"
    return {"ok":True,"cases":9,"stable_incident_key":key}


def main() -> int:
    p=argparse.ArgumentParser(); p.add_argument("--heartbeat-url"); p.add_argument("--homepage-url"); p.add_argument("--fixture",type=Path)
    p.add_argument("--previous-state",type=Path); p.add_argument("--out",type=Path); p.add_argument("--now"); p.add_argument("--max-age-hours",type=float,default=8)
    p.add_argument("--future-skew-minutes",type=float,default=5); p.add_argument("--timeout-seconds",type=float,default=10); p.add_argument("--retries",type=int,default=1)
    p.add_argument("--allow-redirect-host",action="append",default=[]); p.add_argument("--independent-runtime",action="store_true"); p.add_argument("--self-test",action="store_true")
    args=p.parse_args()
    if args.self_test: print(json.dumps(self_test(),ensure_ascii=False,indent=2)); return 0
    if bool(args.fixture)==bool(args.heartbeat_url): raise SystemExit("provide exactly one of --fixture or --heartbeat-url")
    if args.retries<0 or args.retries>3 or args.timeout_seconds<=0 or args.max_age_hours<=0: raise SystemExit("invalid probe settings")
    now=parse_time(args.now) if args.now else datetime.now(timezone.utc); site_ok=site_status=site_failure=None
    if args.homepage_url: site_ok,site_status,_,site_failure=fetch(args.homepage_url,args.timeout_seconds,args.retries,set(args.allow_redirect_host))
    if args.fixture: heartbeat=json.loads(args.fixture.read_text(encoding="utf-8"))
    else:
        ok,status,body,failure=fetch(args.heartbeat_url,args.timeout_seconds,args.retries,set(args.allow_redirect_host))
        try: heartbeat=json.loads(body.decode()) if ok and body else {"schema_version":-1,"fetch_error":failure or status}
        except Exception as e: heartbeat={"schema_version":-1,"decode_error":str(e)}
    report=evaluate(heartbeat,now,args.max_age_hours,args.future_skew_minutes,previous(args.previous_state),args.independent_runtime,site_ok,site_status,site_failure)
    text=json.dumps(report,ensure_ascii=False,indent=2)+"\n"; print(text,end="")
    if args.out: args.out.parent.mkdir(parents=True,exist_ok=True); args.out.write_text(text,encoding="utf-8")
    return 3 if report["overall_status"]=="unavailable" else 0

if __name__=="__main__": raise SystemExit(main())
