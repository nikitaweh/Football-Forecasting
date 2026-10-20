# ops/ – running ORAKEL on the Hostinger VPS

The VPS runs the whole loop: data collection → prediction → website (`oracle-stats.io`) and
Shiny dashboard (private, SSH tunnel). Failures alert via WhatsApp (CallMeBot).

| File | Purpose |
|---|---|
| `bootstrap_vps.sh` | Phase 2: packages, users `orakel-admin` (sudo) + `orakel` (jobs), firewall, timezone; `--harden-ssh` afterwards |
| `install_app.sh` | Phase 3/5/6: Python 3.11 venv, systemd units, website copy, nginx site. Does **not** enable the timers |
| `bin/orakel_job.sh` | Every scheduled job (`collect-daily`, `predict-bundesliga`, `predict-international`, `postmatch`, `website-refresh`) |
| `bin/kickoff_guard.py` | Decides whether a prediction is due (fixture list + existing output) |
| `bin/notify_whatsapp.sh` | CallMeBot alert for a failed unit, max. one per unit per 6 h |
| `bin/publish_website.sh` | Copies the static site (allow-list) to `/var/www/orakel` |
| `systemd/` | `orakel-job@.service` template, five timers, `orakel-notify@.service`, `orakel-dashboard.service` |
| `nginx/oracle-stats.io.conf` | Static site, deny rules for config/source files |

## Schedule (Europe/Berlin)

| Timer | When | What |
|---|---|---|
| `orakel-collect-daily` | 05:15 daily | Bundesliga fixtures, injuries, weather; FIFA/UEFA fixtures, injuries |
| `orakel-predict-bundesliga` | hourly 06–21 | Runs only if the first kickoff of the next 9 unplayed matches is 3–36 h away and they are not predicted yet: fresh pre-match data → bwin odds snapshot → `AI_match_stats_prediction.py` (`future` + `predicted`) → archive table → website |
| `orakel-predict-international` | hourly 06:30–21:30 | Runs only if a competitive FIFA/UEFA match kicks off in 3–36 h and is not predicted yet |
| `orakel-postmatch` | 03:30 daily | Match/player stats, lineups, `update_match_results_references.py`, historical odds, dashboard data, website |
| `orakel-website-refresh` | every 10 min | `website/refresh_data.py` (no-op unless its sources changed) |

All jobs except the website refresh share one lock, so they never write the same CSVs at once.
`ORAKEL_MIN_LEAD_HOURS` must exceed the measured prediction runtime (step 4).

## Setup

Placeholders: `VPS=187.126.5.8`. Commands marked *(local)* run in Git Bash on Windows.

### 1. SSH key and access (Phase 2)
1. *(local)* `ssh-keygen -t ed25519 -C orakel-vps` (with a passphrase), then add
   `~/.ssh/id_ed25519.pub` to the VPS: hPanel → VPS → Settings → SSH keys (or via the Hostinger plugin).
2. Hostinger firewall (hPanel → VPS → Security → Firewall): allow 22, 80, 443 only.
3. `scp ops/bootstrap_vps.sh root@$VPS:` and `ssh root@$VPS bash bootstrap_vps.sh`
4. In a **second** terminal check `ssh orakel-admin@$VPS`, then `sudo bash bootstrap_vps.sh --harden-ssh`.

### 2. Code, data, secrets (Phase 3)
1. Code: `sudo -u orakel git clone --branch developement https://github.com/nikitaweh/Main-Project.git /srv/ki-projekt`
   (private repo: use a read-only deploy key). Without git-lfs on the VPS, data files arrive as LFS pointers;
   step 2 replaces them.
2. Data *(local, from the repo root)*:
   `tar -czf - "Sports Api Data" website/matchdays dashboard/data | ssh orakel-admin@$VPS "sudo tar -xzf - -C /srv/ki-projekt"`
   Then compare checksums of the key CSVs on both sides (`sha256sum` / `certutil -hashfile`).
3. Secrets: fill a copy of `.env.example` locally (API keys, the VPS-only block, CallMeBot) and
   `scp` it to `/etc/orakel/orakel.env` (it never goes through git or chat).
   CallMeBot: activate your number once as described on callmebot.com to get the API key.
4. `sudo bash /srv/ki-projekt/ops/install_app.sh`

### 3. Website and TLS (Phase 6)
1. DNS: A record `oracle-stats.io` (and `www`) → `187.126.5.8` (hPanel → Domains → DNS, or the plugin).
2. After it resolves: `sudo certbot --nginx -d oracle-stats.io -d www.oracle-stats.io`
3. Check: `curl -I https://oracle-stats.io/config/hosting_sftp.json` must be 404.

### 4. Reproducibility check before go-live (Phase 4)
Same code tag and data snapshot on laptop and VPS, on scratch copies (`KI_PROJECT_ROOT=<copy>`):
`backtest_matchdays.py --matchdays 30 31 --max-runs 30 --match-stats-mode predicted`.
- `predicted_match_stats.csv` (seeded GBR) must match to about 1e-6; larger gaps mean a library mismatch.
- Per matchday, the VPS median AvgNLL across runs must lie inside the local IQR (BART is not seeded).
- Note the runtime per run; set `ORAKEL_MIN_LEAD_HOURS` to at least runtime + 1 h.

### 5. Go-live (Phase 7)
1. Stop the Windows schedulers (`start_bundesliga_schedulers.ps1` processes, task "ORAKEL Website Refresh"):
   two machines must never collect or append to `surrogate_run_history.csv` at the same time.
2. `sudo systemctl enable --now orakel-collect-daily.timer orakel-predict-bundesliga.timer orakel-predict-international.timer orakel-postmatch.timer orakel-website-refresh.timer`
3. Test the alert once: `sudo systemctl start orakel-notify@test.service`
4. Take a Hostinger snapshot.

## Operation
- Status: `systemctl list-timers 'orakel-*'`, logs: `journalctl -u 'orakel-job@*' --since today`
- Run a job now: `sudo systemctl start orakel-job@postmatch.service`
- Dashboard *(local)*: `ssh -L 4849:127.0.0.1:4849 orakel-admin@$VPS`, then open http://127.0.0.1:4849
- Update code: `sudo -u orakel git -C /srv/ki-projekt pull`, then re-run `install_app.sh` if units changed.
- Data stays on the VPS (source of truth after go-live); copy it back for thesis analysis, never commit from the VPS.

## Known limits
- The published Bundesliga table is still the one surrogate-picked run per matchday; frozen weights and
  the draw recalibration (roadmap 1 and 4) are not part of this setup.
- The website's international page reads a static World Cup file (`build_data_international.py`);
  new international predictions do not reach the website yet.
- Ubuntu 26.04: some `r-cran-*` packages may be missing; `bootstrap_vps.sh` warns, install them from CRAN.
