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
| `orakel-collect-daily` | 05:15 daily | Bundesliga fixtures, injuries, weather; FIFA/UEFA fixtures, injuries; bookmaker odds (Bwin, Bet365, Betano) |
| `orakel-predict-bundesliga` | hourly 06–21 | Runs only if the first kickoff of the next 9 unplayed matches is 3–36 h away and they are not predicted yet: fresh pre-match data → bookmaker odds → `AI_match_stats_prediction.py` (`future` + `predicted`) → archive table → website |
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
1. Data *(local, from the repo root)*: upload an archive without code files to the admin home:
   `tar --exclude='*.py' --exclude='__pycache__' --exclude='*.bak' -czf - "Sports Api Data" website/matchdays dashboard/data | ssh orakel-admin@$VPS "cat > orakel-data.tgz"`
   and `scp ops/phase3_code_data.sh website/config/leagues/bundesliga.json orakel-admin@$VPS:`
   (`bundesliga.json` is the only LFS file outside the data folders).
2. Secrets: a filled copy of `.env.example` (API keys + VPS block) as `orakel.env` in the admin home,
   via `scp`; it never goes through git or chat. CallMeBot: activate your number once as described on
   callmebot.com, then add `CALLMEBOT_PHONE`/`CALLMEBOT_APIKEY`.
3. `ssh -t orakel-admin@$VPS "sudo bash phase3_code_data.sh orakel-data.tgz bundesliga.json && sudo install -m 640 -o root -g orakel orakel.env /etc/orakel/orakel.env && rm orakel.env"`
   It creates a GitHub deploy key for `orakel`, waits until you add it (repo Settings -> Deploy keys,
   read-only), clones `developement` without LFS and unpacks the data over the LFS pointers.
4. Compare checksums of the key CSVs on both sides (`sha256sum`).
5. `sudo bash /srv/ki-projekt/ops/install_app.sh`

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
- Update code without touching data (data files differ from the LFS pointers in git):
  `sudo -u orakel -H sh -c 'cd /srv/ki-projekt && git fetch && git checkout origin/developement -- . ":(exclude)*.csv" ":(exclude)*.json" ":(exclude)*.pkl"'`,
  then re-run `install_app.sh` if units changed.
- Data stays on the VPS (source of truth after go-live); copy it back for thesis analysis, never commit from the VPS.

## Laptop data pull (VPS -> laptop, one way)
The VPS collects and predicts live (`future` mode); the laptop runs backtests and model experiments
on a copy of that data. Model changes go laptop -> git -> VPS code update, never as copied outputs.
- What: data files changed since the last pull, without code/docs, `Testruns/Datacollection reference`
  and `backtest` (laptop-owned experiment folders) and the raw `*/Unfiltered/*` dumps (`-All` adds them).
- How: key `~/.ssh/orakel_pull` *(local)* may only run `/usr/local/bin/orakel_export`
  (`ops/bin/export_data.sh`) as `orakel`; it waits for the pipeline lock, then sends a tar.gz.
- Setup, once: *(local)* `ssh-keygen -t ed25519 -N "" -C orakel-pull -f ~/.ssh/orakel_pull`, copy the
  `.pub` to the admin home, `sudo bash /srv/ki-projekt/ops/install_pull_export.sh ~/orakel_pull.pub`,
  then *(local, PowerShell)* `ops\laptop\pull_vps_data.ps1 -Since <epoch of the last data sync>`
  and `ops\laptop\register_pull_task.ps1` (task "ORAKEL VPS Data Pull": daily 07:00 + at logon).
- The pull skips while a backtest/pipeline runs on the laptop; log and state in `logs/vps_pull/` (gitignored).

## Known limits
- The published Bundesliga table is still the one surrogate-picked run per matchday; frozen weights and
  the draw recalibration (roadmap 1 and 4) are not part of this setup.
- The website's international page reads a static World Cup file (`build_data_international.py`);
  new international predictions do not reach the website yet.
- Ubuntu 26.04: some `r-cran-*` packages may be missing; `bootstrap_vps.sh` warns, install them from CRAN.
