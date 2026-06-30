# theme.R - minimalistic / clean / modern look for the ORAKEL dashboard.
# A restrained palette, one accent colour, system fonts (no network calls),
# and a shared plotly layout so every chart matches.

suppressMessages({
  library(bslib)
  library(plotly)
})

# Single accent + a small, consistent palette reused across every chart.
PAL <- list(
  model    = "#2563eb",  # accent blue  - the model's headline series
  mean     = "#9db8e8",  # muted blue   - secondary / mean series
  ensemble = "#7c3aed",  # violet       - ensemble series
  bookie   = "#9aa3b2",  # grey         - bookmaker baseline (dashed)
  good     = "#16a34a",  # green        - beats bookie
  bad      = "#dc2626",  # red          - worse than bookie
  H        = "#2563eb",  # home
  D        = "#f59e0b",  # draw (amber)
  A        = "#dc2626",  # away
  grid     = "#eef1f5",
  ink      = "#1f2430"
)

FONT <- "system-ui, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"

app_theme <- function() {
  bslib::bs_theme(
    version     = 5,
    bg          = "#ffffff",
    fg          = PAL$ink,
    primary     = PAL$model,
    base_font   = FONT,
    heading_font = FONT,
    "border-radius" = "0.6rem",
    "card-border-color" = "#e8ebf0",
    "card-cap-bg" = "#ffffff"
  )
}

# Shared plotly styling so all charts feel like one product.
plotly_base <- function(p, ylab = NULL, xlab = NULL, hovermode = "x unified") {
  p |>
    plotly::layout(
      paper_bgcolor = "white",
      plot_bgcolor  = "white",
      font   = list(family = FONT, color = PAL$ink, size = 13),
      xaxis  = list(title = xlab, gridcolor = PAL$grid, zeroline = FALSE,
                    showline = FALSE, ticks = "outside", tickcolor = PAL$grid),
      yaxis  = list(title = ylab, gridcolor = PAL$grid, zeroline = FALSE),
      legend = list(orientation = "h", x = 0, y = 1.12, bgcolor = "rgba(0,0,0,0)"),
      margin = list(l = 58, r = 18, t = 46, b = 46),
      hovermode = hovermode
    ) |>
    plotly::config(displayModeBar = FALSE, responsive = TRUE)
}

empty_plot <- function(msg = "No data") {
  plotly::plot_ly() |>
    plotly::layout(
      paper_bgcolor = "white", plot_bgcolor = "white",
      xaxis = list(visible = FALSE), yaxis = list(visible = FALSE),
      annotations = list(list(text = msg, showarrow = FALSE,
                              font = list(family = FONT, size = 14, color = "#9aa3b2"),
                              xref = "paper", yref = "paper", x = 0.5, y = 0.5))
    ) |>
    plotly::config(displayModeBar = FALSE)
}
