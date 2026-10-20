#!/usr/bin/env bash
# bootstrap_vps.sh  --  Phase 2: base system for ORAKEL on a fresh Ubuntu VPS. Run as root.
#
#   sudo bash bootstrap_vps.sh               # packages, users, folders, firewall, timezone
#   sudo bash bootstrap_vps.sh --harden-ssh  # afterwards: key-only SSH, no root login
#
# --harden-ssh refuses to run unless orakel-admin already has an authorized key, so it
# cannot lock you out. Test "ssh orakel-admin@<vps>" in a second terminal before closing
# the root session.
set -euo pipefail
[ "$(id -u)" -eq 0 ] || { echo "run as root" >&2; exit 1; }

ADMIN=orakel-admin
APP=orakel

if [ "${1:-}" = "--harden-ssh" ]; then
  [ -s "/home/$ADMIN/.ssh/authorized_keys" ] || { echo "no key for $ADMIN -- not hardening" >&2; exit 1; }
  cat > /etc/ssh/sshd_config.d/10-orakel.conf <<'EOF'
PermitRootLogin no
PasswordAuthentication no
KbdInteractiveAuthentication no
EOF
  sshd -t && systemctl reload ssh
  echo "SSH: keys only, root login disabled"
  exit 0
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get -y upgrade
apt-get -y install nginx certbot python3-certbot-nginx git rsync curl ufw fail2ban \
  unattended-upgrades build-essential r-base-core
# R packages for the dashboard as Ubuntu binaries (no compiling). If one is missing on
# this release, install it from CRAN in R instead: install.packages("<name>").
apt-get -y install r-cran-shiny r-cran-bslib r-cran-plotly r-cran-dplyr r-cran-tidyr \
  r-cran-readr r-cran-dt r-cran-jsonlite r-cran-ggplot2 r-cran-scales r-cran-stringr \
  || echo "WARNING: some r-cran-* packages are missing -- see dashboard/install_packages.R"

timedatectl set-timezone Europe/Berlin
dpkg-reconfigure -f noninteractive unattended-upgrades

# Admin user (sudo, SSH) gets root's key; the app user runs the jobs without sudo.
id "$ADMIN" >/dev/null 2>&1 || adduser --disabled-password --gecos "" "$ADMIN"
usermod -aG sudo "$ADMIN"
if [ -s /root/.ssh/authorized_keys ] && [ ! -s "/home/$ADMIN/.ssh/authorized_keys" ]; then
  install -d -m 700 -o "$ADMIN" -g "$ADMIN" "/home/$ADMIN/.ssh"
  install -m 600 -o "$ADMIN" -g "$ADMIN" /root/.ssh/authorized_keys "/home/$ADMIN/.ssh/authorized_keys"
fi
id "$APP" >/dev/null 2>&1 || adduser --system --group --home "/home/$APP" --shell /bin/bash "$APP"
usermod -aG systemd-journal "$APP"   # notify_whatsapp.sh reads the failed unit's journal

install -d -o "$APP" -g "$APP" -m 755 /srv/ki-projekt /var/www/orakel
install -d -o root -g "$APP" -m 750 /etc/orakel

ufw allow OpenSSH
ufw allow "Nginx Full"
ufw --force enable

systemctl enable --now fail2ban nginx
echo "Base system ready. Next: copy code + data to /srv/ki-projekt, then ops/install_app.sh"
