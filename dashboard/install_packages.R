# Installs the CRAN packages the ORAKEL dashboard needs, into a writable user
# library, using Windows binary packages (no compilation). Idempotent: skips
# anything already installed. Run once via run_dashboard.ps1 or manually.

user_lib <- Sys.getenv("R_LIBS_USER")
if (!nzchar(user_lib) || user_lib == "NA") {
  user_lib <- file.path(Sys.getenv("LOCALAPPDATA"), "R", "win-library",
                        paste(R.version$major, sub("\\..*", "", R.version$minor), sep = "."))
}
dir.create(user_lib, recursive = TRUE, showWarnings = FALSE)
.libPaths(c(user_lib, .libPaths()))

options(repos = c(CRAN = "https://cloud.r-project.org"))

needed <- c("shiny", "bslib", "plotly", "dplyr", "tidyr", "readr",
            "DT", "jsonlite", "ggplot2", "scales", "stringr")
missing <- needed[!vapply(needed, requireNamespace, logical(1), quietly = TRUE)]

if (length(missing)) {
  cat("Installing into", user_lib, ":\n  ", paste(missing, collapse = ", "), "\n")
  install.packages(missing, lib = user_lib, type = "binary", quiet = TRUE)
} else {
  cat("All packages already present in", user_lib, "\n")
}

# Verify everything loads
ok <- vapply(needed, requireNamespace, logical(1), quietly = TRUE)
if (all(ok)) {
  cat("OK: all", length(needed), "packages available.\n")
} else {
  cat("MISSING after install:", paste(needed[!ok], collapse = ", "), "\n")
  quit(status = 1)
}
