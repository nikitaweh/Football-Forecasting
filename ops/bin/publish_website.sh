#!/usr/bin/env bash
# publish_website.sh  --  copy the static site (allow-list only) into the nginx web root.
# Run after a layout change or on first install; data.js is published by refresh_data.py.
set -euo pipefail
ROOT=${KI_PROJECT_ROOT:-$(cd "$(dirname "$0")/../.." && pwd)}
WEB_ROOT=${ORAKEL_WEB_ROOT:-/var/www/orakel}

rsync -a --delete-excluded \
  --include='/index.html' --include='/select.html' --include='/international.html' \
  --include='/app.js' --include='/data.js' --include='/data.international.js' \
  --include='/styles.css' \
  --include='/logos/' --include='/logos/*.png' \
  --include='/mobile/' --include='/mobile/*.html' --include='/mobile/*.js' --include='/mobile/*.css' \
  --exclude='*' \
  "$ROOT/website/" "$WEB_ROOT/"
echo "published website/ -> $WEB_ROOT"
