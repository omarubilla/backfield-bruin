"""Minimal PFF Developer API client (https://developer.pff.com/).

Auth: `Authorization: Bearer $PFF_API_KEY` (PFF Pro). The key is read from the
environment only and never logged. Rate limit: 100 reads/min per account; we pace
requests and honour 429 Retry-After.
"""
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://api.pff.com"
LICENSE = "PFF Pro licensed data - internal analysis only; redistribution not confirmed"
_last = [0.0]


class PffError(RuntimeError):
    pass


def key() -> str | None:
    return os.environ.get("PFF_API_KEY") or None


def get(path: str, **params) -> dict:
    k = key()
    if not k:
        raise PffError("PFF_API_KEY not set")
    url = BASE + path + ("?" + urllib.parse.urlencode({p: v for p, v in params.items() if v is not None}) if params else "")
    for attempt in range(4):
        wait = 0.7 - (time.time() - _last[0])  # <= ~85 req/min
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.time()
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {k}", "User-Agent": "backfield-bruin"})
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="ignore")[:500]
            try:
                err = json.loads(body).get("error", {})
            except ValueError:
                err = {"message": body[:200]}
            if e.code == 429 and attempt < 3:
                time.sleep(float(e.headers.get("Retry-After", "10")))
                continue
            if e.code >= 500 and attempt < 3:
                time.sleep(3 * (attempt + 1))
                continue
            raise PffError(f"HTTP {e.code} {err.get('code')}: {err.get('message')} {err.get('details') or ''}".strip())
    raise PffError("retries exhausted")


def whoami() -> dict:
    d = get("/v1/auth/whoami")
    return {k: d.get(k) for k in ("tier", "entitled", "entitlement_reason", "credential")}  # no email / ids


def facet_frame(report: str, leagues=("nfl", "ncaa"), seasons=(2024, 2025)):
    """League-wide season rows for a /v1/facet/<report> endpoint, with lineage columns."""
    import pandas as pd
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()
    frames, status = [], []
    for league in leagues:
        for season in seasons:
            path = f"/v1/facet/{report}"
            try:
                d = get(path, league=league, season=season)
            except PffError as e:
                status.append({"league": league, "season": season, "endpoint": path, "ok": False, "detail": str(e)[:300]})
                continue
            rows = next((v for v in d.values() if isinstance(v, list)), [])
            df = pd.DataFrame(rows)
            for c in df.columns:  # nested values -> JSON text so the raw layer stays lossless
                if df[c].map(lambda v: isinstance(v, (dict, list))).any():
                    df[c] = df[c].map(lambda v: json.dumps(v) if isinstance(v, (dict, list)) else v)
            df["_league"], df["_season"], df["_endpoint"] = league, season, f"{path}?league={league}&season={season}"
            frames.append(df)
            status.append({"league": league, "season": season, "endpoint": path, "ok": True, "rows": len(df)})
    out = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    out["_source_provider"] = "pff"
    out["_license_category"] = LICENSE
    out["_ingested_at"] = now
    return out, status
