# plots.R - pure plotting helpers (plotly). Each takes an already-filtered data
# frame and returns a plotly object; data prep / coercion happens in app.R.

suppressMessages({
  library(plotly)
  library(dplyr)
})

# simple centered moving average (window n, NA-padded) for the rolling overlay
.roll_mean <- function(x, n = 3) {
  if (length(x) < n) return(rep(NA_real_, length(x)))
  as.numeric(stats::filter(x, rep(1 / n, n), sides = 2))
}

# ── Season curve: NLL across matchdays, deployable floor vs bookie ───────────
# Headline = Floor (mean forecast over runs, no hindsight). Best run shown only
# as a faint grey reference so the selection headroom stays visible.
season_nll_plot <- function(df, rolling = FALSE) {
  if (is.null(df) || !nrow(df)) return(empty_plot("No matchday data"))
  df <- dplyr::arrange(df, Matchday)
  marker_col <- ifelse(isTRUE_vec(df$FloorBeatsBookie), PAL$good, PAL$bad)

  p <- plot_ly(df, x = ~Matchday)
  if ("BestNLL" %in% names(df)) {
    p <- add_trace(p, y = ~BestNLL, type = "scatter", mode = "lines",
                   name = "best run (hindsight)", line = list(color = "#cdd5e0", width = 1.4, dash = "dash"),
                   hovertemplate = "MD%{x}: best %{y:.3f}<extra></extra>")
  }
  p <- add_trace(p, y = ~BookieNLL, type = "scatter", mode = "lines",
                 name = "Bookie (BWIN)", line = list(color = PAL$bookie, dash = "dot", width = 2),
                 hovertemplate = "MD%{x}: bookie %{y:.3f}<extra></extra>")
  p <- add_trace(p, y = ~FloorNLL, type = "scatter", mode = "lines+markers",
                 name = "Baseline (floor)", line = list(color = PAL$model, width = 2.4),
                 marker = list(color = marker_col, size = 8, line = list(color = "white", width = 1)),
                 text = ifelse(isTRUE_vec(df$FloorBeatsBookie), "beats bookie", "below bookie"),
                 hovertemplate = "MD%{x}: floor %{y:.3f}<br>%{text}<extra></extra>")
  if (rolling) {
    p <- add_trace(p, y = .roll_mean(df$FloorNLL, 3), type = "scatter", mode = "lines",
                   name = "Floor (3-MD avg)", line = list(color = PAL$model, width = 1, dash = "dash"),
                   hoverinfo = "skip")
  }
  plotly_base(p, ylab = "Deployable-floor NLL (lower = better)", xlab = "Matchday")
}

# ── Season curve: accuracy across matchdays (deployable floor) ───────────────
season_acc_plot <- function(df) {
  if (is.null(df) || !nrow(df)) return(empty_plot("No matchday data"))
  df <- dplyr::arrange(df, Matchday)
  p <- plot_ly(df, x = ~Matchday)
  if ("BestAcc" %in% names(df)) {
    p <- add_trace(p, y = ~BestAcc, type = "scatter", mode = "lines",
                   name = "best run (hindsight)", line = list(color = "#cdd5e0", width = 1.4, dash = "dash"),
                   hovertemplate = "MD%{x}: best %{y:.0%}<extra></extra>")
  }
  p <- add_trace(p, y = ~FloorAcc, type = "scatter", mode = "lines+markers",
                 name = "Baseline (floor)", line = list(color = PAL$model, width = 2.4),
                 marker = list(color = PAL$model, size = 7, line = list(color = "white", width = 1)),
                 hovertemplate = "MD%{x}: floor %{y:.0%}<extra></extra>")
  plotly_base(p, ylab = "Deployable-floor accuracy", xlab = "Matchday") |>
    plotly::layout(yaxis = list(tickformat = ".0%", gridcolor = PAL$grid))
}

# ── Mode comparison: deployable-floor metric per variant for one matchday ────
mode_metric_bar <- function(df, metric = c("FloorAvgNLL", "FloorAccuracy"), bookie = NA_real_) {
  metric <- match.arg(metric)
  if (is.null(df) || !nrow(df)) return(empty_plot("No mode data for this matchday"))
  df <- dplyr::arrange(df, .data[[metric]])
  is_base <- df$Mode == "baseline"
  bar_col <- ifelse(is_base, PAL$model, PAL$ensemble)
  is_acc <- metric == "FloorAccuracy"
  fmt <- if (is_acc) ".0%" else ".3f"
  p <- plot_ly(df, x = ~Variant, y = df[[metric]], type = "bar",
               marker = list(color = bar_col),
               hovertemplate = paste0("%{x}: %{y:", fmt, "}<extra></extra>"))
  if (!is_acc && is.finite(bookie)) {
    p <- add_trace(p, x = df$Variant, y = rep(bookie, nrow(df)), type = "scatter",
                   mode = "lines", name = "Bookie", inherit = FALSE,
                   line = list(color = PAL$bookie, dash = "dot", width = 2),
                   hoverinfo = "skip")
  }
  ylab <- if (is_acc) "Floor accuracy" else "Floor NLL"
  pb <- plotly_base(p, ylab = ylab, xlab = NULL, hovermode = "closest") |>
    plotly::layout(showlegend = FALSE, xaxis = list(tickangle = -20))
  if (is_acc) pb <- plotly::layout(pb, yaxis = list(tickformat = ".0%", gridcolor = PAL$grid))
  pb
}

# ── Mode comparison: per-outcome (H/D/A) NLL guardrail for one matchday ───────
per_outcome_bar <- function(df) {
  if (is.null(df) || !nrow(df)) return(empty_plot("No per-outcome data"))
  df <- df[df$Outcome %in% c("H", "D", "A"), , drop = FALSE]
  if (!nrow(df)) return(empty_plot("No per-outcome data"))
  df$Outcome <- factor(df$Outcome, levels = c("H", "D", "A"))
  variants <- unique(df$Variant)
  p <- plot_ly()
  pal_cycle <- c(PAL$model, PAL$ensemble, "#0ea5e9", "#f59e0b", "#10b981", "#ec4899")
  for (i in seq_along(variants)) {
    v <- variants[[i]]
    sub <- df[df$Variant == v, ]
    col <- if (v == "BWIN bookie") PAL$bookie else pal_cycle[((i - 1) %% length(pal_cycle)) + 1]
    p <- add_trace(p, x = sub$Outcome, y = sub$NLL, type = "bar", name = v,
                   marker = list(color = col),
                   hovertemplate = paste0(v, " %{x}: %{y:.3f}<extra></extra>"))
  }
  plotly_base(p, ylab = "Per-outcome NLL", xlab = "Actual outcome", hovermode = "closest") |>
    plotly::layout(barmode = "group")
}

# ── Run distributions: box of per-run metric per matchday ────────────────────
run_box_plot <- function(df, metric = c("AvgNLL", "Accuracy")) {
  metric <- match.arg(metric)
  if (is.null(df) || !nrow(df)) return(empty_plot("No run data"))
  df$Matchday <- factor(df$Matchday, levels = sort(unique(df$Matchday)))
  df$Group <- ifelse(df$Mode == "baseline", "baseline", "mode variant")
  p <- plot_ly()
  for (g in unique(df$Group)) {
    sub <- df[df$Group == g, ]
    col <- if (g == "baseline") PAL$model else PAL$ensemble
    p <- add_trace(p, x = sub$Matchday, y = sub[[metric]], type = "box", name = g,
                   marker = list(color = col, size = 3), line = list(color = col),
                   fillcolor = paste0(col, "22"), boxpoints = "outliers")
  }
  ylab <- if (metric == "Accuracy") "Per-run accuracy" else "Per-run NLL"
  pb <- plotly_base(p, ylab = ylab, xlab = "Matchday", hovermode = "closest") |>
    plotly::layout(boxmode = "group")
  if (metric == "Accuracy") pb <- plotly::layout(pb, yaxis = list(tickformat = ".0%", gridcolor = PAL$grid))
  pb
}

# ── Mode explorer: every mode across matchdays, one clickable series each ────
MODE_COLORS <- c(
  "baseline (v2)"           = "#2563eb",
  "normal (v3-workload)"    = "#f97316",
  "dixon_coles"             = "#7c3aed",
  "draw_multilayer_overlay" = "#f59e0b",
  "score_dixon_coles"       = "#ec4899",
  "bookie"                  = "#9aa3b2"
)
MODE_LABELS <- c(
  "baseline (v2)"           = "Baseline (v2)",
  "normal (v3-workload)"    = "Player workload (v3)",
  "dixon_coles"             = "Dixon-Coles",
  "draw_multilayer_overlay" = "Draw overlay",
  "score_dixon_coles"       = "Score Dixon (runs)",
  "bookie"                  = "Bookie (BWIN)"
)

mode_curve_plot <- function(df, metric = c("NLL", "Acc")) {
  metric <- match.arg(metric)
  if (is.null(df) || !nrow(df)) return(empty_plot("No mode data"))
  ordered <- names(MODE_COLORS)
  modes <- c(intersect(ordered, unique(df$Mode)), setdiff(unique(df$Mode), ordered))
  cycle <- c("#0ea5e9", "#10b981", "#a855f7", "#ef4444", "#eab308")
  p <- plot_ly()
  for (i in seq_along(modes)) {
    m <- modes[[i]]
    sub <- df[df$Mode == m, ]
    sub <- sub[order(sub$Matchday), ]
    col <- if (m %in% names(MODE_COLORS)) MODE_COLORS[[m]] else cycle[((i - 1) %% length(cycle)) + 1]
    lab <- if (m %in% names(MODE_LABELS)) MODE_LABELS[[m]] else m
    p <- add_trace(p, x = sub$Matchday, y = sub[[metric]], type = "scatter", mode = "lines+markers",
                   name = lab, legendgroup = m,
                   line = list(color = col, width = if (m == "bookie") 2 else 2.3,
                               dash = if (m == "bookie") "dot" else "solid"),
                   marker = list(color = col, size = 7, line = list(color = "white", width = 1)),
                   hovertemplate = paste0(lab, " · MD%{x}: %{y:", if (metric == "Acc") ".0%" else ".3f",
                                          "}<extra></extra>"))
  }
  ylab <- if (metric == "Acc") "Deployable-floor accuracy" else "Deployable-floor NLL (lower = better)"
  pb <- plotly_base(p, ylab = ylab, xlab = "Matchday", hovermode = "closest") |>
    plotly::layout(legend = list(orientation = "h", x = 0, y = 1.1))
  if (metric == "Acc") pb <- plotly::layout(pb, yaxis = list(tickformat = ".0%", gridcolor = PAL$grid))
  pb
}

# ── Dixon-Coles: base vs Dixon NLL across matchdays ──────────────────────────
dixon_nll_plot <- function(df) {
  if (is.null(df) || !nrow(df)) return(empty_plot("No Dixon-Coles data"))
  df <- dplyr::arrange(df, Matchday)
  p <- plot_ly(df, x = ~Matchday)
  p <- add_trace(p, y = ~BookieNLL, type = "scatter", mode = "lines", name = "Bookie (BWIN)",
                 line = list(color = PAL$bookie, dash = "dot", width = 2),
                 hovertemplate = "MD%{x}: bookie %{y:.3f}<extra></extra>")
  p <- add_trace(p, y = ~BaseNLL, type = "scatter", mode = "lines+markers", name = "Baseline (floor)",
                 line = list(color = PAL$mean, width = 2), marker = list(color = PAL$mean, size = 6),
                 hovertemplate = "MD%{x}: base %{y:.3f}<extra></extra>")
  p <- add_trace(p, y = ~DixonNLL, type = "scatter", mode = "lines+markers", name = "Dixon-Coles",
                 line = list(color = PAL$model, width = 2.4),
                 marker = list(color = ifelse(isTRUE_vec(df$DixonImproves), PAL$good, PAL$bad),
                               size = 8, line = list(color = "white", width = 1)),
                 text = ifelse(isTRUE_vec(df$DixonImproves), "improves vs base", "worse than base"),
                 hovertemplate = "MD%{x}: dixon %{y:.3f}<br>%{text}<extra></extra>")
  plotly_base(p, ylab = "Deployable-floor NLL", xlab = "Matchday")
}

# ── Dixon-Coles: per-matchday delta (Dixon - base) ───────────────────────────
dixon_delta_plot <- function(df) {
  if (is.null(df) || !nrow(df)) return(empty_plot("No Dixon-Coles data"))
  df <- dplyr::arrange(df, Matchday)
  p <- plot_ly(df, x = ~Matchday, y = ~Delta, type = "bar",
               marker = list(color = ifelse(df$Delta <= 0, PAL$good, PAL$bad)),
               hovertemplate = "MD%{x}: %{y:+.4f}<extra></extra>")
  plotly_base(p, ylab = "Dixon - Base NLL (neg = better)", xlab = "Matchday", hovermode = "closest") |>
    plotly::layout(showlegend = FALSE)
}

# ── Dixon-Coles: pooled per-outcome (H/D/A) guardrail ────────────────────────
dixon_outcome_plot <- function(po) {
  if (is.null(po) || !nrow(po)) return(empty_plot("No Dixon-Coles data"))
  po <- po[po$Outcome %in% c("H", "D", "A"), , drop = FALSE]
  if (!nrow(po)) return(empty_plot("No Dixon-Coles data"))
  po$Outcome <- factor(po$Outcome, levels = c("H", "D", "A"))
  p <- plot_ly(po, x = ~Outcome)
  p <- add_trace(p, y = ~Base, type = "bar", name = "Baseline (floor)", marker = list(color = PAL$mean),
                 hovertemplate = "base %{x}: %{y:.3f}<extra></extra>")
  p <- add_trace(p, y = ~Dixon, type = "bar", name = "Dixon-Coles", marker = list(color = PAL$model),
                 hovertemplate = "dixon %{x}: %{y:.3f}<extra></extra>")
  p <- add_trace(p, y = ~Bookie, type = "bar", name = "Bookie", marker = list(color = PAL$bookie),
                 hovertemplate = "bookie %{x}: %{y:.3f}<extra></extra>")
  plotly_base(p, ylab = "Pooled per-outcome NLL", xlab = "Actual outcome", hovermode = "closest") |>
    plotly::layout(barmode = "group")
}

# ── International: mean metric by competition ─────────────────────────────────
intl_competition_bar <- function(df, metric = c("NLL", "Accuracy")) {
  metric <- match.arg(metric)
  if (is.null(df) || !nrow(df)) return(empty_plot("No international data"))
  agg <- df |>
    dplyr::group_by(Competition) |>
    dplyr::summarise(value = if (metric == "Accuracy") mean(Correct, na.rm = TRUE) else mean(NLL, na.rm = TRUE),
                     n = dplyr::n(), .groups = "drop") |>
    dplyr::arrange(value)
  fmt <- if (metric == "Accuracy") ".0%" else ".3f"
  p <- plot_ly(agg, x = ~value, y = ~Competition, type = "bar", orientation = "h",
               marker = list(color = PAL$model),
               text = ~paste0("n=", n), textposition = "outside", cliponaxis = FALSE,
               hovertemplate = paste0("%{y}: %{x:", fmt, "} (n=%{text})<extra></extra>"))
  xlab <- if (metric == "Accuracy") "Accuracy" else "Mean NLL"
  pb <- plotly_base(p, ylab = NULL, xlab = xlab, hovermode = "closest") |>
    plotly::layout(margin = list(l = 150))
  if (metric == "Accuracy") pb <- plotly::layout(pb, xaxis = list(tickformat = ".0%", gridcolor = PAL$grid))
  pb
}

# ── International: actual outcome distribution ────────────────────────────────
intl_outcome_bar <- function(df) {
  if (is.null(df) || !nrow(df)) return(empty_plot("No international data"))
  tab <- as.data.frame(table(factor(df$Outcome, levels = c("H", "D", "A"))))
  names(tab) <- c("Outcome", "n")
  p <- plot_ly(tab, x = ~Outcome, y = ~n, type = "bar",
               marker = list(color = c(PAL$H, PAL$D, PAL$A)),
               hovertemplate = "%{x}: %{y} matches<extra></extra>")
  plotly_base(p, ylab = "Matches", xlab = "Actual outcome", hovermode = "closest") |>
    plotly::layout(showlegend = FALSE)
}

# ── Intl games: per-game NLL delta, model vs a chosen bookmaker ──────────────
intl_games_delta_plot <- function(j, bk_label = "bookie") {
  if (is.null(j) || !nrow(j)) return(empty_plot("No games with odds under this filter"))
  j <- j[is.finite(j$NLL) & is.finite(j$BookieNLL), , drop = FALSE]
  if (!nrow(j)) return(empty_plot("No games with odds under this filter"))
  j$Delta <- j$NLL - j$BookieNLL
  j$Matchup <- paste0(j$HomeTeam, " v ", j$AwayTeam)
  j <- j[order(j$Delta), ]
  j$Matchup <- factor(j$Matchup, levels = j$Matchup)
  p <- plot_ly(j, x = ~Matchup, y = ~Delta, type = "bar",
               marker = list(color = ifelse(j$Delta <= 0, PAL$good, PAL$bad)),
               text = ~paste0("actual ", Outcome, "  ·  model ", sprintf("%.2f", NLL),
                              " vs ", bk_label, " ", sprintf("%.2f", BookieNLL)),
               hovertemplate = "%{x}<br>Δ %{y:+.3f}<br>%{text}<extra></extra>")
  plotly_base(p, ylab = paste0("model − ", bk_label, " NLL  (negative = model better)"),
              xlab = NULL, hovermode = "closest") |>
    plotly::layout(showlegend = FALSE, xaxis = list(tickangle = -45, automargin = TRUE))
}

# ── International: multiclass reliability diagram ─────────────────────────────
# Pools the 3 class probabilities; bins predicted prob, plots mean predicted vs
# observed frequency. On the diagonal = well calibrated.
intl_calibration_plot <- function(df, bins = 8) {
  if (is.null(df) || !nrow(df)) return(empty_plot("No international data"))
  long <- rbind(
    data.frame(p = df$WinProb,  hit = as.integer(df$Outcome == "H")),
    data.frame(p = df$DrawProb, hit = as.integer(df$Outcome == "D")),
    data.frame(p = df$LoseProb, hit = as.integer(df$Outcome == "A"))
  )
  long <- long[is.finite(long$p), ]
  if (!nrow(long)) return(empty_plot("No international data"))
  br <- seq(0, 1, length.out = bins + 1)
  long$bin <- cut(long$p, breaks = br, include.lowest = TRUE)
  agg <- long |>
    dplyr::group_by(bin) |>
    dplyr::summarise(pred = mean(p), obs = mean(hit), n = dplyr::n(), .groups = "drop")
  p <- plot_ly()
  p <- add_trace(p, x = c(0, 1), y = c(0, 1), type = "scatter", mode = "lines",
                 name = "perfect", line = list(color = PAL$bookie, dash = "dot", width = 1.5),
                 hoverinfo = "skip")
  p <- add_trace(p, data = agg, x = ~pred, y = ~obs, type = "scatter", mode = "lines+markers",
                 name = "model", line = list(color = PAL$model, width = 2),
                 marker = list(color = PAL$model, size = ~pmax(6, pmin(20, sqrt(n) * 2))),
                 text = ~paste0("n=", n),
                 hovertemplate = "pred %{x:.0%} -> obs %{y:.0%}<br>%{text}<extra></extra>")
  plotly_base(p, ylab = "Observed frequency", xlab = "Predicted probability", hovermode = "closest") |>
    plotly::layout(xaxis = list(tickformat = ".0%", range = c(0, 1), gridcolor = PAL$grid),
                   yaxis = list(tickformat = ".0%", range = c(0, 1), gridcolor = PAL$grid))
}
