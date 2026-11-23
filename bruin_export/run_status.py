"""Parses a `bruin run` log into a machine-readable execution status record."""
import argparse
import json
import re
import os
import subprocess

ANSI = re.compile(r"\x1b\[[0-9;]*m")


def nonblocking_assets(assets_dir: str = "pipeline/assets") -> set[str]:
    """Assets that declare at least one `blocking: false` check in their @bruin header."""
    out = set()
    for root, _, files in os.walk(assets_dir):
        for f in files:
            t = open(os.path.join(root, f), errors="ignore").read()
            m = re.search(r"^name:\s*([\w.]+)", t, re.M)
            if m and re.search(r"blocking:\s*false", t):
                out.add(m.group(1))
    return out


def parse_log(text: str) -> dict:
    text = ANSI.sub("", text)
    assets = [{"asset": a, "status": {"PASS": "passed", "FAIL": "failed", "UPSTREAM FAILED": "skipped_upstream_failed"}[s],
               "checks": {"passed": c.count("."), "failed": c.count("F"), "skipped": c.count("U")}}
              for s, a, c in re.findall(r"^(PASS|FAIL|UPSTREAM FAILED) ([\w.]+)\s*([.FU]*)\s*$", text, re.M)]
    failures = [{"asset": a, "check": c.strip()} for a, c in re.findall(r"[└├]── ([\w.]+)\n\s*[│ ]*└── (.+)", text)]
    nonblocking = nonblocking_assets()
    checks_failed = sum(a["checks"]["failed"] for a in assets)
    blocking_failures = [f for f in failures if f["asset"] not in nonblocking]
    hard_failed = [a for a in assets if a["status"] != "passed"]
    return {
        "assets_total": len(assets),
        "assets_passed": sum(a["status"] == "passed" for a in assets),
        "checks_passed": sum(a["checks"]["passed"] for a in assets),
        "checks_failed": checks_failed,
        "checks_failed_blocking": len(blocking_failures),
        "check_failures": [f | {"blocking": f["asset"] not in nonblocking} for f in failures],
        "assets": assets,
        "validated": not hard_failed and not blocking_failures,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", required=True)
    ap.add_argument("--exit", type=int, required=True)
    ap.add_argument("--started")
    ap.add_argument("--finished")
    ap.add_argument("--bruin-version", default="")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip() or None
    except OSError:
        commit = None
    status = {"pipeline": "backfield_scouting_combine", "tool": "bruin", "bruin_version": a.bruin_version,
              "started_at": a.started, "finished_at": a.finished, "exit_code": a.exit, "git_commit": commit,
              **parse_log(open(a.log, errors="ignore").read())}
    json.dump(status, open(a.out, "w"), indent=2)
    print(f"run status: validated={status['validated']} assets {status['assets_passed']}/{status['assets_total']} "
          f"checks {status['checks_passed']} passed, {status['checks_failed']} failed ({status['checks_failed_blocking']} blocking)")


if __name__ == "__main__":
    main()
