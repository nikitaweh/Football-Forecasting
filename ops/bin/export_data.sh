#!/usr/bin/env bash
# export_data.sh  --  forced command of the laptop's pull key (one-way data sync VPS -> laptop).
#
# Runs as orakel (some collector files are 0600). Installed root-owned as
# /usr/local/bin/orakel_export (outside the repo, so a git update cannot change what the key
# runs) and bound to the key in ~orakel/.ssh/authorized_keys:
#   restrict,command="/usr/local/bin/orakel_export" ssh-ed25519 AAAA... orakel-pull
# The client sends "<epoch of its last pull> [all]"; the reply is a tar.gz of the data files
# changed since then plus .orakel_pull_stamp (the VPS time the file list was taken). Read-only.
#
# Not exported: code and docs (they come through git), the laptop-owned experiment folders
# Testruns/Datacollection reference + backtest (surrogate history, reference/backtest outputs),
# and without "all" the raw */Unfiltered/* API dumps (hundreds of MB rewritten nightly; the
# model reads only the filtered data).
set -euo pipefail

ROOT=${KI_PROJECT_ROOT:-/srv/ki-projekt}
read -r since mode <<< "${SSH_ORIGINAL_COMMAND:-}"
[[ ${since:-} =~ ^[0-9]{1,12}$ && ${mode:-} =~ ^(all)?$ ]] \
  || { echo "usage: <epoch seconds of the last pull> [all]" >&2; exit 2; }
raw=(! -path '*/Unfiltered/*')
[ "${mode:-}" = all ] && raw=()

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

# Wait while a pipeline job writes (they hold the lock exclusively). The lock file is created by
# the first job after boot; without it no job has run, so there is nothing to wait for.
lock=${ORAKEL_LOCK_DIR:-/run/lock/orakel}/pipeline.lock
if [ -r "$lock" ]; then
  exec 9<"$lock"
  flock -s -w 3600 9 || { echo "pipeline busy for 1 h -- try later" >&2; exit 75; }
fi

stamp=$(date +%s)
cd "$ROOT"
# 2 min overlap: a file written in the same second as the previous stamp is sent again, not lost.
find "Sports Api Data" website/matchdays dashboard/data -type f -newermt "@$((since - 120))" \
  ! -name '*.py' ! -name '*.pyc' ! -name '*.md' ! -name '*.bak' ! -path '*/__pycache__/*' ! -path '*/Code/*' "${raw[@]}" \
  ! -path 'Sports Api Data/Testruns/Datacollection reference/*' \
  ! -path 'Sports Api Data/Testruns/Datacollection backtest/*' -print0 > "$tmp/list"
echo "$stamp" > "$tmp/.orakel_pull_stamp"
# Pack under the lock into a file, stream after releasing it: a slow download must not block jobs.
tar --format=pax -czf "$tmp/data.tgz" --null -T "$tmp/list" -C "$tmp" .orakel_pull_stamp
exec 9<&-
cat "$tmp/data.tgz"
