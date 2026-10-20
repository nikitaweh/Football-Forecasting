# -*- coding: utf-8 -*-
"""
refresh_data.py  --  Unattended website refresh (systemd timer on the VPS,
or Windows Task Scheduler locally).

Every run it hashes the model's two source CSVs; if either changed since the
last successful build it calls build_data.build() (live mode: derive matchday,
snapshot inputs, rewrite data.js) and records the new hashes. Unchanged
sources are a quiet no-op, so a 10-minute schedule costs nothing.

State:  <repo root>/logs/refresh_state.json
Log:    <repo root>/logs/website_refresh.log

If ORAKEL_WEB_ROOT is set (VPS), a rebuilt data.js is also copied into the
nginx web root. Scheduling: ops/systemd/orakel-website-refresh.timer.

Exit code 0 = ok / nothing to do, 1 = build or publish failed.
"""

import hashlib
import json
import logging
import os
import shutil
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
LOG_DIR = os.path.join(ROOT, "logs")
STATE_FILE = os.path.join(LOG_DIR, "refresh_state.json")
LOG_FILE = os.path.join(LOG_DIR, "website_refresh.log")

LEAGUE = "bundesliga"

sys.path.insert(0, HERE)
import build_data  # noqa: E402

log = logging.getLogger("orakel.refresh")


def sha256_file(path):
    if not os.path.exists(path):
        return None
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def load_state():
    if not os.path.exists(STATE_FILE):
        return {}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (ValueError, OSError):
        log.warning("State file unreadable -- treating sources as changed")
        return {}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2)


def publish(local_path):
    """Copy a rebuilt file into the nginx web root (ORAKEL_WEB_ROOT, set on the
    VPS). Unset means local-only mode: data.js is only rewritten in website/.
    Copy + rename keeps readers from ever seeing a half-written file."""
    web_root = os.environ.get("ORAKEL_WEB_ROOT", "").strip()
    if not web_root:
        return None
    target = os.path.join(web_root, os.path.basename(local_path))
    tmp = target + ".tmp"
    shutil.copyfile(local_path, tmp)
    os.replace(tmp, target)
    return target


def heartbeat(state):
    """At most one liveness line per day, so the log shows the task is alive
    without filling up with no-op entries."""
    today = datetime.now().strftime("%Y-%m-%d")
    if state.get("lastHeartbeat") != today:
        state["lastHeartbeat"] = today
        save_state(state)
        log.info("heartbeat -- sources unchanged, nothing to do")


def main():
    os.makedirs(LOG_DIR, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8"),
                  logging.StreamHandler()],
    )

    try:
        cfg = build_data.load_config(LEAGUE)
        sources = {
            name: os.path.join(ROOT, *rel.split("/"))
            for name, rel in cfg["sources"].items()
            if name in ("predictions", "results")
        }
        hashes = {name: sha256_file(path) for name, path in sources.items()}

        missing = [name for name, digest in hashes.items() if digest is None]
        if "predictions" in missing:
            log.warning("predictions CSV missing (%s) -- skipping", sources["predictions"])
            return 0

        state = load_state()
        if state.get("hashes") == hashes:
            heartbeat(state)
            return 0

        summary = build_data.build(league=LEAGUE)
        log.info("sources changed -> rebuilt %s (%s, %d matches, %d results, %d upcoming)",
                 os.path.basename(summary["output"]), summary["matchday"],
                 summary["matches"], summary["played"], summary["upcoming"])

        # Publish before recording the hashes, so a failed copy is retried next run.
        published = publish(summary["output"])
        if published:
            log.info("published %s", published)

        state["hashes"] = hashes
        state["lastBuild"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        save_state(state)
        return 0
    except Exception:
        log.exception("refresh failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
