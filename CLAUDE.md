# CLAUDE.md – KI-Projekt (football outcome prediction with BART)

## How to work (mandatory)

- **Sober and neutral.** No affirmations, no praise, no filler. Answer first, reasoning second.
- **Push back.** If an idea is methodologically weak, statistically wrong or implemented incorrectly, say so clearly, explain why, and name the better alternative. Agree only when it is justified.
- **Self-check before every answer.** Before replying, question your own claim: Is the assumption right? Does it match the actual code? Is there leakage, overfitting, selection bias, or too small a sample? Mark uncertain points as uncertain.
- **Evidence, not assertion.** Back claims about the project with `file:line`, CSV values or run results. Mark anything that is only inferred as an inference.
- **Efficient.** Read and change only what the task needs. `AI_match_stats_prediction.py` is large (~3,700 lines): work with grep and line ranges.
- **Statistics over intuition.** Base decisions on distributions, proper scoring rules and out-of-sample evidence, not on single runs.
- Language: English. Explanations may use simple analogies and short, tersely labelled visualizations when they genuinely improve understanding.

## The project in one sentence

Predicting Bundesliga (and international) match outcomes: BART predicts the goal difference, which is turned into win/draw/loss probabilities; a GBR surrogate drives the search over feature weights. The project feeds a Bachelor's thesis on **calibration and reliability of forecasts (Gradient Boosting vs. Bayesian models)**.

## Code layout

- `Sports Api Data/Testruns/Code/AI_match_stats_prediction.py` – main pipeline (Bundesliga)
- `Sports Api Data/Testruns/Code/AI_MATCH_STATS_PREDICTION_DOCUMENTATION.md` – modes, features, leakage controls
- `Sports Api Data/Testruns/Code/*.py` – backtests and diagnostics (`backtest_matchdays.py`, `diagnose_draws.py`, `diagnose_weight_transfer.py`, `compare_models_vs_bookie.py`, Dixon-Coles evaluations …)
- `Sports Api Data/International/Code/AI_international_competitive_prediction.py` – international variant
- `Sports Api Data/Bundesliga|International/**/Code/` – data collection (API-Football, weather, lineups, injuries)
- `Sports Api Data/Testruns/Datacollection future|reference|backtest/` – outputs
- `website/`, `dashboard/` (R/Shiny) – presentation only, no model logic
- `Supportdateien/` – venvs, logs, fallback copies; do not touch, do not treat as a source of truth

## Model architecture (facts from the code)

1. **Match-stats layer (GBR):** one `GradientBoostingRegressor` per match statistic (shots, corners, cards …), using pre-match information only. Training rows get out-of-fold predictions (leakage protection).
2. **`Weight_*` parameters** are a **custom pre-processing layer in front of BART** (weighting of feature signals, plus `H2H_K` scaling). They are not internal BART parameters.
3. **BART (`bartpy.SklearnModel`, currently `n_trees=200`)** is trained **from scratch** on `GoalDiff` for every weight candidate. Nothing of the BART model persists between runs; only weight→performance pairs do.
4. **Probabilities (`normal` mode):** a normal distribution around the BART point prediction, σ = std of the **in-sample residuals**, draw = |GoalDiff| < `draw_margin`. Alternatives via `OUTCOME_PROBABILITY_MODE`: `score_poisson`, `score_dixon_coles`, `*_draw_ratio`, `draw_multilayer_overlay`.
5. **Surrogate (`SURROGATE_MODEL='gbr'`, optionally `'nn'`):** a GBR learns from `surrogate_run_history.csv` which weight configurations give low NLL / high accuracy; selection via a Pareto front, with 20 % random candidates for exploration.
6. **Modes:** `PREDICTION_MODE` = `future` | `reference`; `MATCH_STATS_MODE` = `actual` | `predicted` | `off`. `future`+`actual` is blocked (leakage). The honest end-to-end backtest is `reference`+`predicted`.

## Statistical guardrails

**BART**
- Bayesian sum-of-trees model; priors keep trees shallow (regularization), MCMC (grow/prune/change/swap via Metropolis-Hastings, backfitting on partial residuals). Iterations modify existing trees; they do not add new ones.
- Real uncertainty comes from the **posterior samples** (`model._model_samples`), not from a point prediction plus a global σ. The current σ construction (in-sample residuals, homoscedastic) tends to underestimate uncertainty and ignores match heterogeneity – always account for this in calibration questions.
- Burn-in, number of samples and convergence are part of result quality; MCMC noise causes run-to-run variance.

**Gradient Boosting (sklearn GBR) / XGBoost**
- Additive trees; each new tree fits the negative gradient of the loss (residuals for squared error). Shrinkage (learning_rate), tree depth, subsampling and n_estimators control bias/variance.
- XGBoost: regularized objective (L1/L2 on leaf weights, γ per leaf), second-order Taylor approximation (gradient + Hessian), split-gain formula, sparsity-aware splits, weighted quantile sketch for candidate splits. Reference: Chen & Guestrin 2016 (`2939672.2939785.pdf`).
- **Quantile regression with XGBoost is out of scope for this project** – do not suggest it or go into it.
- GB produces point estimates without built-in uncertainty; probabilities derived from GB are not automatically calibrated without post-hoc calibration.

**Evaluation**
- **Median across runs, never the best run.** Best-run results are selection bias. This is the project's evaluation standard.
- Primary metrics: NLL / log loss and Brier score (strictly proper, Gneiting & Raftery 2007); accuracy only as a supplement. Calibration via reliability diagrams / ECE, separately for H/D/A.
- The benchmark is bookmaker odds (overround removed). Backtest status (32 matchdays, median): ~50 % beat rate, mean NLL gap near 0 → **parity, no demonstrated edge.**
- **Weight transfer does not work:** LOMO Spearman ≈ 0.0016. Per-matchday optimization of `Weight_*` does not generalize; further weight tuning is expected to be worthless. Scrutinize proposals in that direction.
- **Draws are the weak spot** (NLL ~1.61 vs. ~0.59 for home wins). A constant recalibration (c ≈ 1.35) is the documented candidate fix.
- Validate in correct time order (walk-forward); no random splits across matchdays. Small samples (9 matches per matchday) → report the uncertainty of the metrics too.

## Status and roadmap

Backtesting is complete; the focus is the live season:
1. Freeze a robust, median-stable weight set (no more per-matchday search)
2. Automation with error handling and monitoring
3. True walk-forward live validation
4. Launch with realistic expectations (bookmaker parity) and the draw recalibration applied

Open architecture question: `future`/`reference` as one pipeline with optional reference scoring (preferred), or a shared core plus two thin entry points – no full duplication.

## Literature (project files)

BART: Chipman, George & McCulloch (2010); Linero & Yang (2018, smoothness/sparsity). XGBoost: Chen & Guestrin (2016). Calibration/scoring: Gneiting & Raftery (2007). Uncertainty: Hüllermeier & Waegeman (2021, aleatoric vs. epistemic); review of predictive uncertainty estimation.

## Agents and skills

- **Plan mode:** whenever Claude Code is in plan mode, delegate the planning to the `planner` agent (`.claude/agents/planner.md`, pinned to plan mode, read-only) and present its plan for approval.
- Other agents: `debugger` (failures, minimal verified fixes), `efficiency` (measured, result-preserving speedups), `security` (secrets, git exposure, dependencies, Hostinger deployment; report only).
- Recurring tasks are skills in `.claude/skills/` (see its README). `run-backtest` and `collect-matchday-data` are manual only (`/run-backtest`, `/collect-matchday-data`) because they run for hours or use API quota.
- **Recurring tasks without a skill:** when the same task comes up a second time, use the `skillwriter` skill: propose a new skill, wait for approval, then write it in the existing style.

## Conventions

- Paths in the code are absolute (`C:/AI Projekt/KI-Projekt/...`).
- Configuration via module constants and environment variables (`OUTCOME_PROBABILITY_MODE`, `FUTURE_ENSEMBLE_ENABLED`, `DISABLE_PLAYER_WORKLOAD`, `BACKTEST_DATE_CUTOFF` …).
- Surrogate history is filtered by `MatchStatsMode` and feature schema; do not mix histories from different schemas.
- Before changing the main pipeline: check leakage paths (pre-match only, OOF stats, reference matches excluded from training).
