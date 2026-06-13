# Draw Calibration — Problem & Approach

**Date:** 2026-06-12
**Status:** Planned (not yet implemented). Validation is exact on existing backtest data; no new BART sweep required.

---

## The problem

The Bundesliga prediction model has a settled, understood profile after the off-season backtest investigation (21 leakage-free matchdays, scored against real BWIN odds):

| Outcome | Model NLL | Bookie NLL | Gap (model − bookie) |
|---|---|---|---|
| **Home win** (84) | 0.587 | 0.681 | **−0.094** (model better) |
| **Away win** (59) | 0.930 | 0.935 | −0.005 (tied) |
| **Draw** (46) | 1.611 | 1.425 | **+0.186** (model worse) |
| All (189) | 0.943 | 0.941 | +0.002 |

The model has a genuine edge on **home wins** and is tied on away. Its **only systematic weakness is draws**, and that weakness is large enough to cancel the home-win edge — at the deployable level the model is currently **≈ tied** with the market. Closing the draw gap is the single lever that moves the deployable model from *tied* to *beating* the bookmaker.

### Why draws were initially (wrongly) written off

An 8-matchday probe (N=72) found the draw-discrimination signal statistically insignificant (AUC ~0.56–0.58, confidence intervals spanning 0.5) and concluded draws were near-irreducible. **The extended 21-matchday data (N=189) overturned this** — it was a small-sample Type II error:

| Signal | AUC | 90% CI | Significant? |
|---|---|---|---|
| Model draw probability | 0.607 | [0.535, 0.681] | **yes** |
| Model match-evenness | 0.614 | [0.539, 0.689] | **yes** |
| Bookie draw probability | 0.588 | [0.515, 0.663] | **yes** |

The model's high-draw-probability matches actually draw **30%** of the time vs **12.7%** for its low-draw-probability matches. **The model already discriminates draws** — it ranks them correctly.

### The precise diagnosis: a calibration (level) gap, not a discrimination gap

- The model predicts draws at **19.2%** on average; the actual rate is **24.3%**; the bookie sits at **23.5%** (well-calibrated).
- So the model **ranks** draws well but **systematically under-prices the level** by ~5 percentage points.
- This is a calibration problem — the cleanest, lowest-risk kind to fix, because correcting the *level* (toward the true frequency) is guaranteed to improve a proper scoring rule like NLL, without needing to change the model's discriminative power.

### Where the draw probability comes from (the mechanism)

`AI_match_stats_prediction.py` converts BART's continuous goal-difference prediction into H/D/A probabilities with a **Gaussian band** (lines ~2614–2643):

```
DrawProb = Φ((m − μ)/σ) − Φ((−m − μ)/σ)
WinProb  = 1 − Φ((m − μ)/σ)
LoseProb = Φ((−m − μ)/σ)
```

where **μ** = predicted goal difference (per match), **σ** = std of training residuals (per run), and **m = `draw_margin`** is a hardcoded half-width of `0.5` (line ~2505). The band is too narrow → draws under-priced.

---

## The approach: widen the Gaussian draw band, with a hard H/A guardrail

### Why widening the band is the right fix (not a blunt multiplier)

A naive post-hoc fix — multiply every draw probability by a constant `c` — was tested and **rejected**: it lifts draws but steals probability from home/away *proportionally everywhere*, including the confident home-favorite matches that are the model's edge. It degraded H/A NLL by ~0.06 and would fail the guardrail.

Widening `draw_margin` is fundamentally better because it is **discrimination-aware by geometry**. Extra band width adds draw mass in proportion to the Gaussian density at the band edge:

- For a **tight match** (μ ≈ 0, where the model already senses a draw), the density is high → a meaningful draw boost.
- For a **confident home favorite** (μ far from 0), the density at the edge is tiny → almost no change.

So widening the band concentrates the draw correction exactly where draws are likely and barely touches the home-win edge — precisely the targeted behavior we want, achieved with a single parameter.

### Phase 1 — Validate exactly on existing data (no BART)

`draw_margin` affects only the deterministic μ,σ→probability mapping; it does **not** affect BART training (μ) or the residual spread (σ). Therefore its effect on the existing 21-matchday predictions can be reproduced **exactly**, not approximated — so the fix is tuned and guardrail-checked entirely on saved data, with zero new compute.

A new read-only script (`calibrate_draw_margin.py`) will:
1. Read each backtest run's per-match `PredictedGoalDiff` (μ) and current probabilities.
2. **Recover σ** for each run by inverting the current band (σ is shared across a run's matches).
3. Sweep candidate band widths — both absolute (`m`) and σ-relative (`m = c·σ`) — recompute H/D/A probabilities, average over runs to rebuild the deployable forecast, and score against actual outcomes.
4. Report, under **leave-one-matchday-out** (so the chosen value is non-overfit): total NLL, **per-outcome H / D / A NLL**, draw-rate calibration, and the gap vs the bookmaker.

### Phase 2 — Apply (only if the guardrail passes)

Replace the hardcoded `draw_margin = 0.5` with a named constant `DRAW_MARGIN` set to the calibrated value (env-overridable, mirroring the existing backtest knobs). One deterministic constant, flowing identically through future / reference / backtest modes.

### Phase 3 — Confirm

Spot-check one backtest matchday: the live model's probabilities with the new constant must match the Phase-1 simulation (they will, since μ and σ are unchanged). No full re-sweep needed.

---

## The guardrail (protecting the home-win edge)

The whole point is to fix draws **without weakening the home/away calls that carry the edge**. Adopt the calibrated margin **only if**, under leave-one-matchday-out:

- total NLL improves, **and**
- per-outcome **Home and Away NLL each do not degrade by more than ~0.005** (ideally neutral or better).

If every band width that helps draws also dents H/A beyond that tolerance, **the model is left unchanged** (`draw_margin = 0.5`) and we report that even the geometric fix can't satisfy the guardrail. NLL being a proper scoring rule is the safety net: a level correction toward the true draw frequency only scores better if reality justifies it.

---

## What this deliberately does not touch

- **BART** and the μ/σ derivation — unchanged; only the deterministic conversion is recalibrated.
- The **selection layer** (surrogate / top-K ensemble / Pareto-seeding) — confirmed dead ends across the investigation; not reopened.
- No new backtest sweep — Phase 1 is exact on existing data; only a one-matchday spot-check follows.

---

## Expected outcome

A single-parameter, geometrically-targeted recalibration that lifts the model's draw level toward the true ~24% rate, captured mostly in the matches the model already flags as tight. If it clears the H/A guardrail (the honest leave-one-matchday-out recalibration already nets +0.0037), it moves the **deployable** model from tied with the market to modestly beating it — the first real improvement found since the model was declared settled, and the only one the data still supports.
