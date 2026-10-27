#!/usr/bin/env bash
# notify_whatsapp.sh <unit>  --  WhatsApp alert via CallMeBot for a failed systemd unit.
#
# Needs CALLMEBOT_PHONE (international format, e.g. +4917...) and CALLMEBOT_APIKEY in the
# EnvironmentFile. CallMeBot is a free third-party gateway: the message text passes through
# it, so only the unit name, host and the last log lines are sent, with key-like strings
# masked. Delivery is best effort; a failed alert is logged, never retried in a loop.
set -uo pipefail

UNIT=${1:?usage: notify_whatsapp.sh <unit>}
: "${CALLMEBOT_PHONE:?CALLMEBOT_PHONE not set}" "${CALLMEBOT_APIKEY:?CALLMEBOT_APIKEY not set}"

# At most one alert per unit per ORAKEL_ALERT_THROTTLE_MIN (default 6 h): an hourly job that
# keeps failing must not flood the phone. The journal still has every failure.
STAMP_DIR=${ORAKEL_STATE_DIR:-/srv/ki-projekt/logs}/alerts
mkdir -p "$STAMP_DIR"
stamp="$STAMP_DIR/${UNIT//[^A-Za-z0-9_.@-]/_}"
if [ -n "$(find "$stamp" -mmin -"${ORAKEL_ALERT_THROTTLE_MIN:-360}" 2>/dev/null)" ]; then
  echo "alert for $UNIT suppressed (sent recently)"
  exit 0
fi

tail_lines=$(journalctl -u "$UNIT" -n 8 --no-pager -o cat 2>/dev/null \
  | sed -E 's/[0-9a-fA-F]{32,}/<masked>/g' | cut -c1-160)
text="ORAKEL $(hostname): ${UNIT} failed at $(date '+%Y-%m-%d %H:%M')
${tail_lines}"
text=${text:0:900}

if curl -fsS --max-time 30 -G "https://api.callmebot.com/whatsapp.php" \
     --data-urlencode "phone=${CALLMEBOT_PHONE}" \
     --data-urlencode "text=${text}" \
     --data-urlencode "apikey=${CALLMEBOT_APIKEY}" -o /dev/null; then
  touch "$stamp"
  echo "alert sent for $UNIT"
else
  echo "CallMeBot request failed for $UNIT" >&2
  exit 1
fi
