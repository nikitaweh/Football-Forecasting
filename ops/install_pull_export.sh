#!/usr/bin/env bash
# install_pull_export.sh <pubkey file>  --  one-time, as root: lets the laptop pull data (read-only).
# Installs ops/bin/export_data.sh root-owned as /usr/local/bin/orakel_export and binds the
# laptop's pull key to it in ~orakel/.ssh/authorized_keys (no shell, no forwarding).
#   sudo bash /srv/ki-projekt/ops/install_pull_export.sh ~/orakel_pull.pub
# Re-run after export_data.sh changes; the key line is added only once.
set -euo pipefail
[ "$(id -u)" -eq 0 ] || { echo "run as root" >&2; exit 1; }
PUB=${1:?usage: install_pull_export.sh <pubkey file>}
key=$(tr -d '\r' < "$PUB")
[[ $key =~ ^ssh-ed25519\ [A-Za-z0-9+/=]+\ orakel-pull$ ]] || { echo "not an orakel-pull ed25519 key" >&2; exit 1; }

tr -d '\r' < "$(dirname "$0")/bin/export_data.sh" > /usr/local/bin/orakel_export
chown root:root /usr/local/bin/orakel_export && chmod 755 /usr/local/bin/orakel_export

ak=/home/orakel/.ssh/authorized_keys
install -d -m 700 -o orakel -g orakel /home/orakel/.ssh
touch "$ak"
grep -q ' orakel-pull$' "$ak" || echo "restrict,command=\"/usr/local/bin/orakel_export\" $key" >> "$ak"
chown orakel:orakel "$ak" && chmod 600 "$ak"
echo "pull export installed; key lines for orakel: $(grep -c . "$ak")"
