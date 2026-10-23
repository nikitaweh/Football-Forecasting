#!/usr/bin/env bash
# phase3_code_data.sh  --  one-time Phase 3 on the VPS: GitHub deploy key, code clone, data unpack.
#
#   sudo bash phase3_code_data.sh /home/orakel-admin/orakel-data.tgz /home/orakel-admin/bundesliga.json
#
# The repo is private: the script creates a key for the orakel user, prints its public half
# and waits until you have added it on GitHub (repo Settings -> Deploy keys, read-only).
# Code comes from git; data (LFS files) comes from the uploaded archive, because the VPS
# has no git-lfs and must not depend on GitHub's LFS bandwidth.
set -euo pipefail
[ "$(id -u)" -eq 0 ] || { echo "run with sudo" >&2; exit 1; }

ARCHIVE=${1:?data archive}
LEAGUE_CFG=${2:?website/config/leagues/bundesliga.json}
APP=orakel
ROOT=/srv/ki-projekt
REPO=git@github.com:nikitaweh/Main-Project.git
HOME_APP=/home/$APP
KEY=$HOME_APP/.ssh/github_deploy
# GitHub's published ed25519 host key fingerprint
GITHUB_FP="SHA256:+DiY3wvvV6TuJJhbpZisF/zLDA0zPMSvHdkr4UvCOqU"

as_app() { sudo -u "$APP" -H "$@"; }

# 1. deploy key + pinned GitHub host key
install -d -m 700 -o "$APP" -g "$APP" "$HOME_APP/.ssh"
[ -f "$KEY" ] || as_app ssh-keygen -q -t ed25519 -N "" -C "orakel-vps-deploy" -f "$KEY"
if ! as_app ssh-keygen -F github.com -f "$HOME_APP/.ssh/known_hosts" >/dev/null 2>&1; then
  hostkey=$(ssh-keyscan -t ed25519 github.com 2>/dev/null)
  fp=$(echo "$hostkey" | ssh-keygen -lf - | awk '{print $2}')
  [ "$fp" = "$GITHUB_FP" ] || { echo "GitHub host key mismatch: $fp" >&2; exit 1; }
  echo "$hostkey" | as_app tee -a "$HOME_APP/.ssh/known_hosts" >/dev/null
fi
printf 'Host github.com\n  IdentityFile %s\n  IdentitiesOnly yes\n' "$KEY" | as_app tee "$HOME_APP/.ssh/config" >/dev/null

# "ssh -T git@github.com" exits 1 even on success, so test its output, not its exit code
# (with pipefail a pipe into grep would always look like a failure).
github_ok() { local out; out=$(as_app ssh -o BatchMode=yes -T git@github.com 2>&1 || true); [[ $out == *"successfully authenticated"* ]]; }
until github_ok; do
  echo
  echo "Add this key on GitHub: nikitaweh/Main-Project -> Settings -> Deploy keys -> Add deploy key"
  echo "(title: orakel-vps, leave 'Allow write access' OFF):"
  echo
  cat "$KEY.pub"
  echo
  read -r -p "Press Enter once it is saved on GitHub... "
done
echo "GitHub access OK"

# 2. code (LFS files arrive as pointers and are replaced in step 3)
if [ ! -d "$ROOT/.git" ]; then
  as_app env GIT_LFS_SKIP_SMUDGE=1 git clone --branch developement --single-branch "$REPO" "$ROOT"
fi
as_app git -C "$ROOT" log --oneline -1

# 3. data
tar -xzf "$ARCHIVE" -C "$ROOT"
install -m 644 "$LEAGUE_CFG" "$ROOT/website/config/leagues/bundesliga.json"
chown -R "$APP":"$APP" "$ROOT"

pointers=$(grep -rlI --include='*.csv' --include='*.json' --include='*.pkl' "^version https://git-lfs" "$ROOT" | wc -l || true)
echo "LFS pointer files left (should be 0): $pointers"
du -sh "$ROOT/Sports Api Data"
echo "Phase 3 code + data done. Next: /etc/orakel/orakel.env, then ops/install_app.sh"
