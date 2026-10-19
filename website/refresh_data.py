# -*- coding: utf-8 -*-
"""
refresh_data.py  --  Unattended website refresh, meant for Windows Task Scheduler.

Every run it hashes the model's two source CSVs; if either changed since the
last successful build it calls build_data.build() (live mode: derive matchday,
snapshot inputs, rewrite data.js) and records the new hashes. Unchanged
sources are a quiet no-op, so a 10-minute schedule costs nothing.

State:  <repo root>/logs/refresh_state.json
Log:    <repo root>/logs/website_refresh.log

Register once on the main checkout (see website/README.md):

    Register-ScheduledTask "ORAKEL Website Refresh" ...

Exit code 0 = ok / nothing to do, 1 = build failed (visible in Task Scheduler's
"Last Run Result").
"""

import hashlib
import json
import logging
import os
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
LOG_DIR = os.path.join(ROOT, "logs")
STATE_FILE = os.path.join(LOG_DIR, "refresh_state.json")
LOG_FILE = os.path.join(LOG_DIR, "website_refresh.log")
SFTP_CONFIG_FILE = os.path.join(HERE, "config", "hosting_sftp.json")
# Pre-Hostinger name; only checked to warn that it is no longer read.
LEGACY_SFTP_CONFIG_FILE = os.path.join(HERE, "config", "ionos_sftp.json")

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


def load_sftp_config():
    """Optional website/config/hosting_sftp.json (gitignored, see .example.json
    for the shape). Missing file means remote upload is simply skipped, so
    local-only setups keep working unchanged."""
    if not os.path.exists(SFTP_CONFIG_FILE):
        if os.path.exists(LEGACY_SFTP_CONFIG_FILE):
            log.warning("found legacy ionos_sftp.json but no hosting_sftp.json -- "
                        "it is no longer read; create hosting_sftp.json")
        return None
    try:
        with open(SFTP_CONFIG_FILE, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (ValueError, OSError):
        log.exception("hosting_sftp.json unreadable -- skipping remote upload")
        return None


def upload_to_host(local_path, cfg):
    """Push a single file to the configured web host over SFTP,
    landing it at remote_dir/<basename>. Raises on failure; caller decides
    how loud to be."""
    import paramiko  # local import: only needed when a config is present

    transport = paramiko.Transport((cfg["host"], cfg.get("port", 22)))
    try:
        transport.connect(username=cfg["username"], password=cfg["password"])
        sftp = paramiko.SFTPClient.from_transport(transport)
        try:
            remote_path = cfg["remote_dir"].rstrip("/") + "/" + os.path.basename(local_path)
            sftp.put(local_path, remote_path)
        finally:
            sftp.close()
    finally:
        transport.close()


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
        state["hashes"] = hashes
        state["lastBuild"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        save_state(state)
        log.info("sources changed -> rebuilt %s (%s, %d matches, %d results, %d upcoming)",
                 os.path.basename(summary["output"]), summary["matchday"],
                 summary["matches"], summary["played"], summary["upcoming"])

        sftp_cfg = load_sftp_config()
        if sftp_cfg is None:
            log.info("no website/config/hosting_sftp.json -- live site not updated remotely")
        else:
            try:
                upload_to_host(summary["output"], sftp_cfg)
                log.info("uploaded %s to %s:%s", os.path.basename(summary["output"]),
                          sftp_cfg["host"], sftp_cfg["remote_dir"])
            except Exception:
                # data.js is correct locally either way; a failed upload just
                # means the live site is stale until the next successful run.
                log.exception("SFTP upload failed -- live site still shows the previous data.js")

        return 0
    except Exception:
        log.exception("refresh failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
