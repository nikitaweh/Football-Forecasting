# ORAKEL Performance Dashboard (R Shiny)
# --------------------------------------
# Visualises Bundesliga backtest performance across matchdays AND every
# mode/finetuning variant, plus the International model, and auto-refreshes when
# new outcome data or new mode folders appear on disk.
#
# Launch:  shiny::runApp("dashboard", port = 4849, launch.browser = TRUE)
# Data is produced by Sports Api Data/Testruns/Code/build_dashboard_data.py.

suppressMessages({
  library(shiny)
  library(bslib)
  library(plotly)
  library(dplyr)
  library(DT)
})

source("R/theme.R", local = TRUE)
source("R/load_data.R", local = TRUE)
source("R/plots.R", local = TRUE)

# ── UI ───────────────────────────────────────────────────────────────────────
kpi <- function(title, id, sub = NULL) {
  value_box(
    title = title,
    value = textOutput(id, inline = TRUE),
    p(sub, class = "text-muted small mb-0"),
    class = "border"
  )
}

ui <- page_navbar(
  title = "ORAKEL · Performance",
  theme = app_theme(),
  fillable = TRUE,
  sidebar = sidebar(
    width = 270,
    title = "Controls",
    sliderInput("md_range", "Matchday range", min = 1, max = 34,
                value = c(1, 34), step = 1, sep = ""),
    hr(),
    input_switch("auto", "Auto-refresh on new data", value = TRUE),
    actionButton("refresh_now", "Refresh now", class = "btn-primary btn-sm w-100",
                 icon = icon("rotate")),
    div(class = "small text-muted mt-2", textOutput("last_updated")),
    hr(),
    div(class = "small text-muted", textOutput("coverage"))
  ),

  # ── Bundesliga: Season curve ──
  nav_panel(
    "Season curve",
    layout_columns(
      fill = FALSE, col_widths = c(3, 3, 3, 3),
      kpi("Mean baseline NLL", "kpi_nll", "deployable floor"),
      kpi("Mean baseline accuracy", "kpi_acc", "floor, per MD"),
      kpi("Beats bookie", "kpi_beats", "floor vs bookie"),
      kpi("Mean gap vs bookie", "kpi_gap", "floor - bookie (neg better)")
    ),
    layout_columns(
      col_widths = 12,
      card(
        card_header("Negative log-likelihood across matchdays",
                    div(class = "float-end", checkboxInput("rolling", "3-MD rolling avg", FALSE))),
        plotlyOutput("season_nll", height = 360)
      )
    ),
    card(
      card_header("Accuracy across matchdays"),
      plotlyOutput("season_acc", height = 300)
    )
  ),

  # ── Bundesliga: Mode comparison ──
  nav_panel(
    "Mode comparison",
    layout_columns(
      fill = FALSE, col_widths = c(4, 4),
      selectInput("mode_md", "Matchday with variants", choices = NULL, width = "100%"),
      radioButtons("mode_metric", "Bar metric", inline = TRUE,
                   choices = c("Floor NLL" = "FloorAvgNLL", "Floor accuracy" = "FloorAccuracy"))
    ),
    layout_columns(
      col_widths = c(6, 6),
      card(card_header("Baseline (floor) by variant"), plotlyOutput("mode_bar", height = 340)),
      card(card_header("Per-outcome NLL (H/D/A) guardrail"), plotlyOutput("mode_outcome", height = 340))
    ),
    card(card_header("Mode performance table"), DTOutput("mode_table"))
  ),

  # ── Bundesliga: Run spread ──
  nav_panel(
    "Run spread",
    layout_columns(
      fill = FALSE, col_widths = 4,
      radioButtons("run_metric", "Metric", inline = TRUE,
                   choices = c("NLL" = "AvgNLL", "Accuracy" = "Accuracy"))
    ),
    card(
      card_header("Per-run distribution by matchday (spread of finetuning)"),
      plotlyOutput("run_box", height = 460)
    )
  ),

  # ── Bundesliga: Mode explorer (compare every mode + bookie) ──
  nav_panel(
    "Mode explorer",
    layout_columns(
      fill = FALSE, col_widths = c(4, 8),
      radioButtons("mc_metric", "Metric", inline = TRUE,
                   choices = c("Floor NLL" = "NLL", "Accuracy" = "Acc")),
      div(class = "small text-muted mt-2",
          "Click a series in the legend to hide/show it; double-click to isolate one mode. Scroll down for the data.")
    ),
    card(
      card_header("All modes across matchdays (deployable floor)"),
      plotlyOutput("mc_plot", height = "82vh"),
      full_screen = TRUE
    ),
    card(card_header("Per-mode summary"), DTOutput("mc_summary")),
    card(card_header("All data by mode & matchday"), DTOutput("mc_detail"))
  ),

  # ── Bundesliga: Dixon-Coles (season-wide) ──
  nav_panel(
    "Dixon-Coles",
    layout_columns(
      fill = FALSE, col_widths = c(3, 3, 3, 3),
      kpi("Matchdays improved", "dx_improved", "Dixon beats base"),
      kpi("Mean delta NLL", "dx_delta", "Dixon - base"),
      kpi("Pooled NLL", "dx_pooled", "base -> dixon"),
      kpi("Dixon vs bookie", "dx_bookie", "pooled, neg = better")
    ),
    card(
      card_header("Base (normal) vs Dixon-Coles NLL across matchdays"),
      plotlyOutput("dx_nll", height = 340)
    ),
    layout_columns(
      col_widths = c(7, 5),
      card(card_header("Per-matchday delta (Dixon - base)"), plotlyOutput("dx_delta_plot", height = 320)),
      card(card_header("Pooled per-outcome NLL (H/D/A guardrail)"), plotlyOutput("dx_outcome", height = 320))
    ),
    card(card_header("Per-matchday Dixon-Coles table"), DTOutput("dx_table"))
  ),

  # ── International ──
  nav_panel(
    "International",
    layout_columns(
      fill = FALSE, col_widths = c(6, 3, 3),
      selectizeInput("intl_comp", "Competitions", choices = NULL, multiple = TRUE, width = "100%"),
      kpi("Matches", "intl_n", "validated"),
      kpi("Mean NLL / Acc", "intl_score", "on validation set")
    ),
    layout_columns(
      col_widths = c(7, 5),
      card(
        card_header("Performance by competition",
                    div(class = "float-end",
                        radioButtons("intl_metric", NULL, inline = TRUE,
                                     choices = c("NLL" = "NLL", "Accuracy" = "Accuracy")))),
        plotlyOutput("intl_comp_plot", height = 340)
      ),
      card(card_header("Actual outcome mix"), plotlyOutput("intl_outcome", height = 340))
    ),
    card(card_header("Probability calibration (reliability)"), plotlyOutput("intl_calib", height = 340))
  ),

  # ── International: per-game comparison vs bookmaker ──
  nav_panel(
    "Intl games",
    layout_columns(
      fill = FALSE, col_widths = c(6, 3, 3),
      selectizeInput("ig_comp", "Competitions", choices = NULL, multiple = TRUE, width = "100%"),
      selectInput("ig_book", "Bookmaker", choices = c("bet365", "betfair_exchange", "avg", "max")),
      div(class = "small text-muted mt-2",
          "Bars compare each game (with odds) to the bookmaker; the table below lists every game. Scroll down.")
    ),
    layout_columns(
      fill = FALSE, col_widths = c(3, 3, 3, 3),
      kpi("Games vs odds", "ig_n", "model & bookmaker"),
      kpi("Model NLL", "ig_mnll", "those games"),
      kpi("Bookmaker NLL", "ig_bnll", "same games"),
      kpi("Model beats book", "ig_beats", "per game")
    ),
    card(
      card_header("Model vs bookmaker · per-game NLL delta"),
      plotlyOutput("ig_delta", height = "60vh"),
      full_screen = TRUE
    ),
    card(card_header("All international games"), DTOutput("ig_table"))
  ),

  # ── Status ──
  nav_panel(
    "Status",
    layout_columns(
      col_widths = c(6, 6),
      card(card_header("Data manifest"), verbatimTextOutput("manifest_txt")),
      card(card_header("Refresh log"), verbatimTextOutput("refresh_txt"))
    )
  ),
  nav_spacer(),
  nav_item(tags$span(class = "navbar-text small text-muted", "Bundesliga + International"))
)

# ── Server ───────────────────────────────────────────────────────────────────
server <- function(input, output, session) {

  # tidy-CSV readers (auto-reload when files change on disk)
  md_perf_r   <- make_reader(session, "matchday_performance.csv")
  mode_perf_r <- make_reader(session, "mode_performance.csv")
  per_out_r   <- make_reader(session, "per_outcome_nll.csv")
  runs_r      <- make_reader(session, "run_distributions.csv")
  intl_r      <- make_reader(session, "international_performance.csv")
  dixon_r     <- make_reader(session, "dixon_performance.csv")
  dixon_po_r  <- make_reader(session, "dixon_per_outcome.csv")
  mode_curve_r <- make_reader(session, "mode_curve.csv")
  intl_odds_r  <- make_reader(session, "international_odds.csv")
  manifest_r  <- reactiveFileReader(2000, session, file.path(DATA_DIR, "manifest.json"),
                                    function(p) if (file.exists(p)) jsonlite::read_json(p, simplifyVector = TRUE) else NULL)

  # ── auto-refresh: re-run the exporter when source files change ──
  fp <- reactivePoll(10000, session, source_fingerprint, source_fingerprint)
  last_seen    <- reactiveVal(isolate(source_fingerprint()))
  last_refresh <- reactiveVal(NULL)
  refresh_log  <- reactiveVal("Idle. Data is read live from dashboard/data/.")

  do_refresh <- function(reason) {
    refresh_log(paste0("[", format(Sys.time(), "%H:%M:%S"), "] ", reason, " - running exporter..."))
    res <- run_exporter()
    last_seen(source_fingerprint())
    last_refresh(Sys.time())
    refresh_log(paste0("[", format(Sys.time(), "%H:%M:%S"), "] ",
                       if (res$ok) "Refreshed OK." else "Exporter reported a problem.",
                       "\n\n", res$log))
  }

  observeEvent(fp(), {
    if (isTRUE(input$auto) && !identical(fp(), last_seen())) {
      do_refresh("New source data detected")
    }
  }, ignoreInit = TRUE)

  observeEvent(input$refresh_now, do_refresh("Manual refresh"))

  # ── typed views of the data ──
  md_perf <- reactive({
    d <- md_perf_r(); if (is.null(d) || !nrow(d)) return(NULL)
    d$BeatsBookie <- as_logical_str(d$BeatsBookie)
    d$FloorBeatsBookie <- as_logical_str(d$FloorBeatsBookie)
    dplyr::filter(d, Matchday >= input$md_range[1], Matchday <= input$md_range[2])
  })
  mode_perf <- reactive({
    d <- mode_perf_r(); if (is.null(d) || !nrow(d)) return(NULL)
    d$BeatsBookie <- as_logical_str(d$BeatsBookie)
    d$FloorBeatsBookie <- as_logical_str(d$FloorBeatsBookie); d
  })
  intl <- reactive({
    d <- intl_r(); if (is.null(d) || !nrow(d)) return(NULL)
    d$Correct <- as_logical_str(d$Correct); d
  })

  # ── populate dynamic input choices ──
  observeEvent(mode_perf(), {
    d <- mode_perf()
    mds <- sort(unique(d$Matchday[d$Mode != "baseline"]))
    choices <- stats::setNames(mds, paste0("MD", sprintf("%02d", mds)))
    sel <- if (!is.null(input$mode_md) && input$mode_md %in% mds) input$mode_md else (if (length(mds)) mds[1] else NULL)
    updateSelectInput(session, "mode_md", choices = choices, selected = sel)
  }, ignoreNULL = TRUE)

  observeEvent(intl(), {
    comps <- sort(unique(intl()$Competition))
    updateSelectizeInput(session, "intl_comp", choices = comps, selected = comps, server = FALSE)
  }, ignoreNULL = TRUE)

  # ── KPI cards (Season curve) ──
  output$kpi_nll <- renderText({ d <- md_perf(); if (is.null(d)) "-" else sprintf("%.3f", mean(d$FloorNLL, na.rm = TRUE)) })
  output$kpi_acc <- renderText({ d <- md_perf(); if (is.null(d)) "-" else sprintf("%.1f%%", 100 * mean(d$FloorAcc, na.rm = TRUE)) })
  output$kpi_beats <- renderText({
    d <- md_perf(); if (is.null(d)) return("-")
    sprintf("%d / %d", sum(d$FloorBeatsBookie, na.rm = TRUE), sum(!is.na(d$FloorBeatsBookie)))
  })
  output$kpi_gap <- renderText({ d <- md_perf(); if (is.null(d)) "-" else sprintf("%+.3f", mean(d$FloorGapVsBookie, na.rm = TRUE)) })

  # ── Season curve plots ──
  output$season_nll <- renderPlotly(season_nll_plot(md_perf(), rolling = isTRUE(input$rolling)))
  output$season_acc <- renderPlotly(season_acc_plot(md_perf()))

  # ── Mode comparison ──
  mode_md_sel <- reactive({ req(input$mode_md); as.integer(input$mode_md) })

  output$mode_bar <- renderPlotly({
    d <- mode_perf(); req(d); md <- mode_md_sel()
    sub <- dplyr::filter(d, Matchday == md)
    bookie <- suppressWarnings(stats::median(sub$BookieNLL, na.rm = TRUE))
    mode_metric_bar(sub, metric = input$mode_metric, bookie = bookie)
  })

  output$mode_outcome <- renderPlotly({
    d <- per_out_r(); req(d); md <- mode_md_sel()
    per_outcome_bar(dplyr::filter(d, Matchday == md))
  })

  output$mode_table <- renderDT({
    d <- mode_perf(); req(d); md <- mode_md_sel()
    sub <- d |>
      dplyr::filter(Matchday == md) |>
      dplyr::transmute(Variant, Mode, MatchStatsMode,
                       FloorNLL = round(FloorAvgNLL, 3), FloorAcc = round(FloorAccuracy, 3),
                       BestNLL = round(BestAvgNLL, 3), Runs = NumRuns,
                       Bookie = round(BookieNLL, 3), Gap = round(FloorGapVsBookie, 3),
                       BeatsBookie = FloorBeatsBookie)
    datatable(sub, rownames = FALSE, options = list(dom = "t", paging = FALSE, ordering = TRUE),
              selection = "none") |>
      formatStyle("Gap", color = styleInterval(0, c(PAL$good, PAL$bad)))
  })

  # ── Run spread ──
  output$run_box <- renderPlotly({
    d <- runs_r(); if (is.null(d) || !nrow(d)) return(empty_plot("No run data"))
    d <- dplyr::filter(d, Matchday >= input$md_range[1], Matchday <= input$md_range[2])
    run_box_plot(d, metric = input$run_metric)
  })

  # ── Mode explorer ──
  mode_curve <- reactive({
    d <- mode_curve_r(); if (is.null(d) || !nrow(d)) return(NULL)
    d$BeatsBookie <- as_logical_str(d$BeatsBookie)
    dplyr::filter(d, Matchday >= input$md_range[1], Matchday <= input$md_range[2])
  })
  output$mc_plot <- renderPlotly(mode_curve_plot(mode_curve(), input$mc_metric))
  output$mc_summary <- renderDT({
    d <- mode_curve(); req(d)
    s <- d |>
      dplyr::group_by(Mode) |>
      dplyr::summarise(Matchdays = dplyr::n(),
                       MeanNLL = round(mean(NLL, na.rm = TRUE), 3),
                       MeanAcc = round(mean(Acc, na.rm = TRUE), 3),
                       MeanGapVsBookie = round(mean(GapVsBookie, na.rm = TRUE), 3),
                       BeatsBookie = sum(BeatsBookie, na.rm = TRUE),
                       .groups = "drop") |>
      dplyr::arrange(MeanNLL)
    datatable(s, rownames = FALSE, options = list(dom = "t", paging = FALSE, ordering = TRUE),
              selection = "none") |>
      formatStyle("MeanGapVsBookie", color = styleInterval(0, c(PAL$good, PAL$bad)))
  })
  output$mc_detail <- renderDT({
    d <- mode_curve(); req(d)
    det <- d |>
      dplyr::transmute(Matchday, Mode, NLL = round(NLL, 3), Acc = round(Acc, 3),
                       N = round(N), GapVsBookie = round(GapVsBookie, 3), BeatsBookie) |>
      dplyr::arrange(Mode, Matchday)
    datatable(det, rownames = FALSE, filter = "top",
              options = list(pageLength = 15, order = list(list(1, "asc"), list(0, "asc"))),
              selection = "none") |>
      formatStyle("GapVsBookie", color = styleInterval(0, c(PAL$good, PAL$bad)))
  })

  # ── Dixon-Coles ──
  dixon <- reactive({
    d <- dixon_r(); if (is.null(d) || !nrow(d)) return(NULL)
    d$DixonImproves <- as_logical_str(d$DixonImproves)
    dplyr::filter(d, Matchday >= input$md_range[1], Matchday <= input$md_range[2])
  })
  output$dx_improved <- renderText({
    d <- dixon(); if (is.null(d)) return("-")
    sprintf("%d / %d", sum(d$DixonImproves, na.rm = TRUE), sum(!is.na(d$DixonImproves)))
  })
  output$dx_delta <- renderText({ d <- dixon(); if (is.null(d)) "-" else sprintf("%+.4f", mean(d$Delta, na.rm = TRUE)) })
  output$dx_pooled <- renderText({
    po <- dixon_po_r(); if (is.null(po)) return("-")
    a <- po[po$Outcome == "ALL", ]; if (!nrow(a)) return("-")
    sprintf("%.3f -> %.3f", a$Base[1], a$Dixon[1])
  })
  output$dx_bookie <- renderText({
    po <- dixon_po_r(); if (is.null(po)) return("-")
    a <- po[po$Outcome == "ALL", ]; if (!nrow(a)) return("-")
    sprintf("%+.4f", a$Dixon[1] - a$Bookie[1])
  })
  output$dx_nll        <- renderPlotly(dixon_nll_plot(dixon()))
  output$dx_delta_plot <- renderPlotly(dixon_delta_plot(dixon()))
  output$dx_outcome    <- renderPlotly(dixon_outcome_plot(dixon_po_r()))
  output$dx_table <- renderDT({
    d <- dixon(); req(d)
    sub <- d |>
      dplyr::transmute(MD = Matchday, N,
                       BaseNLL = round(BaseNLL, 3), DixonNLL = round(DixonNLL, 3),
                       Delta = round(Delta, 4), BaseAcc = round(BaseAcc, 3), DixonAcc = round(DixonAcc, 3),
                       BookieNLL = round(BookieNLL, 3), GapVsBookie = round(DixonGapVsBookie, 3),
                       Improves = DixonImproves)
    datatable(sub, rownames = FALSE, options = list(dom = "t", paging = FALSE, ordering = TRUE),
              selection = "none") |>
      formatStyle("Delta", color = styleInterval(0, c(PAL$good, PAL$bad)))
  })

  # ── International ──
  intl_f <- reactive({
    d <- intl(); if (is.null(d)) return(NULL)
    if (!is.null(input$intl_comp) && length(input$intl_comp)) d <- dplyr::filter(d, Competition %in% input$intl_comp)
    d
  })
  output$intl_n <- renderText({ d <- intl_f(); if (is.null(d)) "-" else as.character(nrow(d)) })
  output$intl_score <- renderText({
    d <- intl_f(); if (is.null(d) || !nrow(d)) return("-")
    sprintf("%.3f / %.0f%%", mean(d$NLL, na.rm = TRUE), 100 * mean(d$Correct, na.rm = TRUE))
  })
  output$intl_comp_plot <- renderPlotly(intl_competition_bar(intl_f(), metric = input$intl_metric))
  output$intl_outcome   <- renderPlotly(intl_outcome_bar(intl_f()))
  output$intl_calib     <- renderPlotly(intl_calibration_plot(intl_f()))

  # ── Intl games (per-game model vs bookmaker) ──
  observeEvent(intl(), {
    comps <- sort(unique(intl()$Competition))
    updateSelectizeInput(session, "ig_comp", choices = comps, selected = comps, server = FALSE)
  }, ignoreNULL = TRUE)

  ig_joined <- reactive({
    perf <- intl(); req(perf)
    if (!is.null(input$ig_comp) && length(input$ig_comp))
      perf <- dplyr::filter(perf, Competition %in% input$ig_comp)
    od <- intl_odds_r()
    if (is.null(od) || !nrow(od)) return(perf)
    ob <- od[od$Bookmaker == input$ig_book,
             c("MatchID", "BookieNLL", "BookiePick", "BookieWinProb", "BookieDrawProb", "BookieLoseProb")]
    dplyr::left_join(perf, ob, by = "MatchID")
  })
  ig_withodds <- reactive({ j <- ig_joined(); if (is.null(j) || !"BookieNLL" %in% names(j)) return(j[0, ]); j[is.finite(j$BookieNLL), ] })

  output$ig_n     <- renderText({ w <- ig_withodds(); as.character(nrow(w)) })
  output$ig_mnll  <- renderText({ w <- ig_withodds(); if (!nrow(w)) "-" else sprintf("%.3f", mean(w$NLL, na.rm = TRUE)) })
  output$ig_bnll  <- renderText({ w <- ig_withodds(); if (!nrow(w)) "-" else sprintf("%.3f", mean(w$BookieNLL, na.rm = TRUE)) })
  output$ig_beats <- renderText({ w <- ig_withodds(); if (!nrow(w)) "-" else sprintf("%d / %d", sum(w$NLL < w$BookieNLL, na.rm = TRUE), nrow(w)) })
  output$ig_delta <- renderPlotly(intl_games_delta_plot(ig_withodds(), input$ig_book))
  output$ig_table <- renderDT({
    j <- ig_joined(); req(j)
    has_odds <- "BookieNLL" %in% names(j)
    tab <- j |>
      dplyr::transmute(
        Date = MatchDate, Competition, Home = HomeTeam, Away = AwayTeam, Actual = Outcome,
        ModelPick = PredictedResult, ModelNLL = round(NLL, 3),
        BookiePick = if (has_odds) BookiePick else NA_character_,
        BookieNLL = if (has_odds) round(BookieNLL, 3) else NA_real_,
        Delta = if (has_odds) round(NLL - BookieNLL, 3) else NA_real_)
    datatable(tab, rownames = FALSE, filter = "top",
              options = list(pageLength = 15, order = list(list(0, "asc"))), selection = "none") |>
      formatStyle("Delta", color = styleInterval(0, c(PAL$good, PAL$bad)))
  })

  # ── sidebar status + Status tab ──
  output$last_updated <- renderText({
    lr <- last_refresh()
    if (is.null(lr)) "Live (no refresh yet this session)" else paste("Last refresh:", format(lr, "%H:%M:%S"))
  })
  output$coverage <- renderText({
    d <- md_perf_r(); if (is.null(d)) return("No data loaded.")
    present <- sort(unique(d$Matchday))
    miss <- setdiff(seq(min(present), max(present)), present)
    paste0("Matchdays: ", length(present), " (MD", min(present), "-", max(present), "). ",
           if (length(miss)) paste0("Missing: ", paste(miss, collapse = ", ")) else "No gaps.")
  })
  output$manifest_txt <- renderText({
    m <- manifest_r(); if (is.null(m)) return("manifest.json not found. Click 'Refresh now'.")
    up_to_date <- identical(source_fingerprint(), last_seen())
    paste0("Data generated:  ", m$generated_at, " (UTC)\n",
           "Status:          ", if (up_to_date) "up to date" else "new source data detected - refreshing...", "\n",
           "Odds source:     ", m$odds_source %||% "-", "\n\n",
           "counts:\n",
           "  matchdays:             ", m$counts$matchdays, "\n",
           "  mode_folders:          ", m$counts$mode_folders, "\n",
           "  run_rows:              ", m$counts$run_rows, "\n",
           "  per_outcome_rows:      ", m$counts$per_outcome_rows, "\n",
           "  international_matches:  ", m$counts$international_matches)
  })
  output$refresh_txt <- renderText(refresh_log())
}

shinyApp(ui, server)
