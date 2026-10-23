#!/usr/bin/env bash
# install_app.sh  --  Phase 3/5/6: Python env, systemd units, website, nginx. Run as root
# after the code and data are in /srv/ki-projekt and /etc/orakel/orakel.env exists.
#
#   sudo bash /srv/ki-projekt/ops/install_app.sh
#
# Timers are installed but NOT enabled: enable them only after the reproducibility check
# (see ops/README.md), with: systemctl enable --now orakel-*.timer
set -euo pipefail
[ "$(id -u)" -eq 0 ] || { echo "run as root" >&2; exit 1; }

ROOT=/srv/ki-projekt
APP=orakel
ENV_FILE=/etc/orakel/orakel.env
[ -f "$ENV_FILE" ] || { echo "missing $ENV_FILE (copy from .env.example)" >&2; exit 1; }
sed -i 's/\r$//' "$ENV_FILE"   # a file copied from Windows must not pass "\r" into the keys
chown root:"$APP" "$ENV_FILE" && chmod 640 "$ENV_FILE"
chown -R "$APP":"$APP" "$ROOT"
chmod +x "$ROOT"/ops/bin/*.sh

# Python 3.11 to match the local reference venv (Ubuntu ships a newer python3).
sudo -u "$APP" -H bash -c '
  set -euo pipefail
  command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
  cd /srv/ki-projekt
  uv python install 3.11
  [ -x .venv/bin/python ] || uv venv --python 3.11 .venv
  uv pip install --python .venv/bin/python -r requirements-vps.txt
  # bartpy without its declared deps (they include the dead "sklearn" package)
  uv pip install --python .venv/bin/python --no-deps "bartpy @ git+https://github.com/JakeColtman/bartpy.git@09e409e91dd1b9d44784c788c2d731dafb181eb0"
  .venv/bin/python -c "import bartpy.sklearnmodel, sklearn, numpy, pandas; print(\"python ok:\", sklearn.__version__, numpy.__version__, pandas.__version__)"
'

# systemd units (copied, so a git pull never changes a running unit unnoticed)
install -m 644 "$ROOT"/ops/systemd/*.service "$ROOT"/ops/systemd/*.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now orakel-dashboard.service

# website + nginx
sudo -u "$APP" ORAKEL_WEB_ROOT=/var/www/orakel "$ROOT/ops/bin/publish_website.sh"
install -m 644 "$ROOT/ops/nginx/oracle-stats.io.conf" /etc/nginx/sites-available/oracle-stats.io
ln -sf /etc/nginx/sites-available/oracle-stats.io /etc/nginx/sites-enabled/oracle-stats.io
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

echo "Installed. Timers are NOT enabled yet:"
systemctl list-unit-files 'orakel-*' --no-pager
echo "TLS (after the DNS A record points here): certbot --nginx -d oracle-stats.io -d www.oracle-stats.io"
