# load_data.R - data layer for the Shiny app.
#
# Resolves all paths relative to the dashboard app directory, knows how to
# (re)run the Python exporter, computes a cheap "source fingerprint" used to
# detect new outcome data / new mode folders, and exposes reactiveFileReaders
# so the UI reloads automatically whenever the tidy CSVs change on disk.

suppressMessages({
  library(shiny)
  library(readr)
  library(jsonlite)
})

# ── Paths (app dir = working dir when launched via shiny::runApp('dashboard')) ─
APP_DIR   <- getwd()
DATA_DIR  <- file.path(APP_DIR, "data")
REPO_ROOT <- normalizePath(file.path(APP_DIR, ".."), winslash = "/", mustWork = FALSE)

# Python exporter + the interpreter that has pandas (ORAKEL_PYTHON, e.g. the
# VPS venv; else the Windows project venv; else python3/python on PATH).
EXPORTER  <- file.path(REPO_ROOT, "Sports Api Data", "Testruns", "Code", "build_dashboard_data.py")
PYTHON <- local({
  env  <- Sys.getenv("ORAKEL_PYTHON")
  venv <- file.path(REPO_ROOT, "Supportdateien", ".venv", "Scripts", "python.exe")
  if (nzchar(env)) env
  else if (file.exists(venv)) venv
  else if (nzchar(Sys.which("python3"))) unname(Sys.which("python3"))
  else unname(Sys.which("python"))
})

# Source inputs the exporter depends on (kept in sync with
# build_dashboard_data.py::source_fingerprint()).
BACKTEST_DIR      <- file.path(REPO_ROOT, "Sports Api Data", "Testruns", "Datacollection backtest")
REFERENCE_RESULTS <- file.path(REPO_ROOT, "Sports Api Data", "Testruns", "Datacollection reference", "match_results_references.csv")
STAMMDATEN        <- file.path(REPO_ROOT, "Sports Api Data", "Bundesliga", "Filtered", "Datacollection", "Stammdaten_78.csv")
STATS             <- file.path(REPO_ROOT, "Sports Api Data", "Bundesliga", "Filtered", "Datacollection", "match_statistics_filtered_78.csv")
INTL_VALIDATION   <- file.path(REPO_ROOT, "Sports Api Data", "International", "Model Output", "competitive", "international_competitive_validation.csv")
ODDS_DIR          <- file.path(REPO_ROOT, "Sports Api Data", "Testruns", "BWIN Odds", "Datacollection")

# ── Change detection ─────────────────────────────────────────────────────────
# (count of MD* folders) : (max integer mtime across all source inputs).
# We only ever compare this against our own previous value, so it just has to
# *change* when something new is uploaded - it need not match Python's exactly.
source_fingerprint <- function() {
  md_dirs <- list.dirs(BACKTEST_DIR, recursive = FALSE, full.names = TRUE)
  md_dirs <- md_dirs[grepl("[/\\\\]MD[0-9]+", md_dirs)]
  odds <- sort(list.files(ODDS_DIR, pattern = "^bwin_historical_odds_.*\\.csv$", full.names = TRUE))
  paths <- c(md_dirs, REFERENCE_RESULTS, STAMMDATEN, STATS, INTL_VALIDATION,
             if (length(odds)) utils::tail(odds, 1) else NULL)
  mt <- suppressWarnings(file.mtime(paths))
  mt <- as.numeric(mt[is.finite(as.numeric(mt))])
  max_mtime <- if (length(mt)) as.integer(max(mt)) else 0L
  paste0(length(md_dirs), ":", max_mtime)
}

# Run the exporter. Returns list(ok, log). Never throws.
run_exporter <- function() {
  if (!nzchar(PYTHON) || !file.exists(EXPORTER)) {
    return(list(ok = FALSE, log = "python or exporter not found"))
  }
  out <- tryCatch(
    system2(PYTHON, args = shQuote(EXPORTER), stdout = TRUE, stderr = TRUE),
    error = function(e) {
      attr(e$message, "status") <- 1L
      structure(conditionMessage(e), status = 1L)
    }
  )
  status <- attr(out, "status")
  list(ok = is.null(status) || identical(status, 0L), log = paste(out, collapse = "\n"))
}

# ── Tidy-CSV readers ─────────────────────────────────────────────────────────
# Each returns a reactive that re-reads its file ~1.5s after it changes on disk.
read_csv_quiet <- function(path) {
  if (!file.exists(path)) return(NULL)
  tryCatch(readr::read_csv(path, show_col_types = FALSE, progress = FALSE),
           error = function(e) NULL)
}

make_reader <- function(session, filename) {
  reactiveFileReader(1500, session, file.path(DATA_DIR, filename), read_csv_quiet)
}

read_manifest <- function() {
  p <- file.path(DATA_DIR, "manifest.json")
  if (!file.exists(p)) return(NULL)
  tryCatch(jsonlite::read_json(p, simplifyVector = TRUE), error = function(e) NULL)
}

# Coerce the exporter's "True"/"False" text columns to logical.
as_logical_str <- function(x) {
  x <- tolower(trimws(as.character(x)))
  out <- rep(NA, length(x))
  out[x %in% c("true", "t", "1")]  <- TRUE
  out[x %in% c("false", "f", "0")] <- FALSE
  out
}

# TRUE/FALSE mask that tolerates logical OR "True"/"False" text and maps NA->FALSE.
isTRUE_vec <- function(x) {
  if (is.logical(x)) return(!is.na(x) & x)
  tolower(trimws(as.character(x))) %in% c("true", "t", "1")
}
