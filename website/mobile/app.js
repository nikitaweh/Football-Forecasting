/* ============================================================
   ORAKEL mobile — renders from window.ORAKEL_DATA (../data.js)
   ============================================================ */
(function () {
  "use strict";

  var DATA = window.ORAKEL_DATA;
  if (!DATA) { console.error("../data.js failed to load"); return; }

  var MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

  /* logos referenced in data.js are relative to website/; mobile sits one
     level deeper, so paths need a "../" prefix. */
  var ASSET_PREFIX = "../";

  // ── Helpers ───────────────────────────────────────────────

  function $(sel) { return document.querySelector(sel); }
  function $all(sel) { return Array.prototype.slice.call(document.querySelectorAll(sel)); }

  function el(tag, cls, html) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (html != null) node.innerHTML = html;
    return node;
  }

  function fmtDate(iso) {
    var p = String(iso).split("-");
    if (p.length !== 3) return iso;
    return parseInt(p[2], 10) + " " + MONTHS[parseInt(p[1], 10) - 1] + " " + p[0];
  }

  function teamMeta(name) {
    var t = DATA.teams[name];
    if (t) return t;
    var abbr = name.replace(/[^A-Za-zÀ-ÿ ]/g, "").split(/\s+/)
                   .map(function (w) { return w[0] || ""; }).join("").slice(0, 3).toUpperCase();
    return { abbr: abbr, color: "#3A3A42" };
  }

  function outcomeText(o) {
    return o === "HomeWin" ? "home win" : o === "AwayWin" ? "away win" : "draw";
  }

  function normPct(h, d, a) {
    var total = h + d + a || 1;
    var hp = Math.round((h / total) * 100);
    var ap = Math.round((a / total) * 100);
    return { home: hp, away: ap, draw: 100 - hp - ap };
  }

  function crest(name) {
    var m = teamMeta(name);
    var c = el("span", "crest");

    function useFallback() {
      c.className = "crest crest--fallback";
      c.style.background = m.color;
      c.textContent = m.abbr;
    }

    if (m.logo) {
      var img = el("img");
      img.alt = name;
      img.loading = "lazy";
      img.onerror = useFallback;
      img.src = ASSET_PREFIX + m.logo;
      c.appendChild(img);
    } else {
      useFallback();
    }
    return c;
  }

  // ── Hero, captions, top bar ───────────────────────────────

  var counted = false;

  function renderHero() {
    var m = DATA.meta;

    $("#topbar-md").textContent = "Matchday " + m.matchday;
    $("[data-eyebrow]").textContent = m.league + " · Matchday " + m.matchday;

    var played = DATA.matches.filter(function (x) { return x.result && x.result.outcome; });
    var correct = played.filter(function (x) {
      return x.prediction.outcome === x.result.outcome;
    }).length;
    var rate = played.length ? Math.round((correct / played.length) * 100) : 0;

    var top = DATA.matches[0];
    var topConf = Math.round(top.prediction.confidence * 100);
    var topSub;
    if (top.result) {
      var sc = top.result.homeGoals + "–" + top.result.awayGoals;
      topSub = (top.prediction.outcome === top.result.outcome)
        ? "Top pick landed " + sc : "Top pick · final " + sc;
    } else {
      topSub = "Highest-conviction call";
    }

    var stats = [
      { value: DATA.matches.length, label: "Matches called",
        sub: "Matchday " + m.matchday + " fixtures" },
      { value: rate, unit: "%", label: "Outcome hit rate",
        sub: correct + " of " + played.length + " correct" },
      { value: topConf, unit: "%", label: "Top-call confidence", sub: topSub },
      { value: m.signalsPerMatch, label: "Signals / match",
        sub: "form · H2H · weather" }
    ];

    var box = $("#stats");
    stats.forEach(function (s) {
      var card = el("div", "stat");
      var val = el("div", "stat__value");
      val.setAttribute("data-target", s.value);
      val.innerHTML = "0" + (s.unit ? '<span class="unit">' + s.unit + "</span>" : "");
      card.appendChild(val);
      card.appendChild(el("div", "stat__label", s.label));
      card.appendChild(el("div", "stat__sub", s.sub));
      box.appendChild(card);
    });

    $("#results-caption").textContent =
      "Matchday " + m.matchday + " · " + fmtDate(m.matchdayDate);
    $("#predictions-caption").textContent =
      "Every call ORAKEL published — before a ball was kicked.";
    $("#footer-note").textContent =
      m.model + " · Data " + fmtDate(m.generated);
  }

  // ── Cards ─────────────────────────────────────────────────

  function resultCard(match) {
    var r = match.result, p = match.prediction;
    var card = el("article", "card");
    var hit = p.outcome === r.outcome;
    var homeWin = r.outcome === "HomeWin", awayWin = r.outcome === "AwayWin";

    var top = el("div", "card__top");
    top.appendChild(el("span", "card__date", fmtDate(match.date)));
    top.appendChild(el("span", "chip " + (hit ? "chip--hit" : "chip--miss"),
      hit ? "✓ Called it" : "✗ Missed"));
    card.appendChild(top);

    [["home", homeWin, awayWin], ["away", awayWin, homeWin]].forEach(function (cfg) {
      var side = cfg[0];
      var row = el("div", "team" +
        (cfg[1] ? " team--winner" : "") + (cfg[2] ? " team--loser" : ""));
      row.appendChild(crest(match[side]));
      row.appendChild(el("span", "team__name", match[side]));
      var score = el("span", "team__score", String(r[side + "Goals"]));
      if (cfg[2]) score.classList.add("is-dim");
      row.appendChild(score);
      card.appendChild(row);
    });

    var foot = el("div", "card__foot");
    foot.appendChild(el("span", null,
      'AI predicted <span class="pred-score">' + p.homeGoals + "–" + p.awayGoals + "</span>"));
    foot.appendChild(el("span", null,
      Math.round(p.confidence * 100) + "% " + outcomeText(p.outcome)));
    card.appendChild(foot);
    return card;
  }

  function predictionCard(match) {
    var p = match.prediction;
    var card = el("article", "card");
    var pending = !match.result;

    var top = el("div", "card__top");
    top.appendChild(el("span", "card__date", fmtDate(match.date)));
    if (pending) {
      top.appendChild(el("span", "chip chip--upcoming", "Upcoming"));
    }
    card.appendChild(top);

    ["home", "away"].forEach(function (side) {
      var row = el("div", "team");
      row.appendChild(crest(match[side]));
      row.appendChild(el("span", "team__name", match[side]));
      card.appendChild(row);
    });

    var line = el("div", "predline");
    line.appendChild(el("span", "predline__label", "Predicted"));
    line.appendChild(el("span", "predline__score",
      p.homeGoals + '<span class="sep">–</span>' + p.awayGoals));
    card.appendChild(line);

    var pc = normPct(p.homeWinProb, p.drawProb, p.awayWinProb);

    var bar = el("div", "probar");
    [["home", pc.home], ["draw", pc.draw], ["away", pc.away]].forEach(function (s) {
      var seg = el("span", "probar__seg probar__seg--" + s[0]);
      seg.setAttribute("data-w", s[1]);
      bar.appendChild(seg);
    });
    card.appendChild(bar);

    var pick = { HomeWin: "home", Draw: "draw", AwayWin: "away" }[p.outcome];
    var legend = el("div", "problegend");
    [["home", "Home", pc.home], ["draw", "Draw", pc.draw], ["away", "Away", pc.away]]
      .forEach(function (s) {
        var item = el("div", "problegend__item" + (s[0] === pick ? " is-pick" : ""));
        item.appendChild(el("span", "dot dot--" + s[0]));
        item.appendChild(document.createTextNode(s[1] + " " + s[2] + "%"));
        legend.appendChild(item);
      });
    card.appendChild(legend);

    var xg = el("div", "xg");
    xg.appendChild(el("span", null, "Expected goals"));
    xg.appendChild(el("span", null,
      "<b>" + p.xgHome.toFixed(2) + "</b> – <b>" + p.xgAway.toFixed(2) + "</b>"));
    card.appendChild(xg);
    return card;
  }

  function renderFeeds() {
    var resultsFeed = $("#results-feed");
    var predFeed = $("#predictions-feed");
    var upcomingFeed = $("#upcoming-feed");

    var played = DATA.matches.filter(function (m) { return m.result && m.result.outcome; });
    var upcoming = DATA.matches.filter(function (m) { return !(m.result && m.result.outcome); });

    // Latest results
    if (played.length) {
      played.forEach(function (m) { resultsFeed.appendChild(resultCard(m)); });
    } else {
      resultsFeed.appendChild(el("p", "vhead__sub",
        "No settled matches yet — results appear here once played."));
    }

    // Upcoming fixtures — top of the Predictions tab, shown only when populated.
    if (upcoming.length) {
      upcoming.forEach(function (m) { upcomingFeed.appendChild(predictionCard(m)); });
      $("#upcoming-head").hidden = false;
      $("#upcoming-caption").textContent =
        "Still to be played — " + upcoming.length + " fixture" +
        (upcoming.length === 1 ? "" : "s") + ".";
    }

    // The predictions — calls for matches that have been played.
    if (played.length) {
      played.forEach(function (m) { predFeed.appendChild(predictionCard(m)); });
    } else {
      $("#predictions-head").hidden = true;
    }
  }

  // ── Animations ────────────────────────────────────────────

  function countUp(node) {
    var target = parseFloat(node.getAttribute("data-target")) || 0;
    var unit = node.querySelector(".unit");
    var unitHTML = unit ? unit.outerHTML : "";
    var start = null, dur = 1000;
    function step(ts) {
      if (start === null) start = ts;
      var t = Math.min((ts - start) / dur, 1);
      var eased = 1 - Math.pow(1 - t, 3);
      node.innerHTML = Math.round(target * eased) + unitHTML;
      if (t < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  }

  function fillBars(scope) {
    requestAnimationFrame(function () {
      requestAnimationFrame(function () {
        scope.querySelectorAll(".probar__seg").forEach(function (seg) {
          seg.style.width = (seg.getAttribute("data-w") || 0) + "%";
        });
      });
    });
  }

  // ── Tab navigation ────────────────────────────────────────

  function activate(name) {
    $all(".view").forEach(function (v) {
      v.classList.toggle("is-active", v.getAttribute("data-view") === name);
    });
    $all(".tab").forEach(function (t) {
      var on = t.getAttribute("data-tab") === name;
      t.classList.toggle("is-active", on);
      t.setAttribute("aria-current", on ? "page" : "false");
    });

    $("#scroll").scrollTop = 0;
    var view = $('.view[data-view="' + name + '"]');
    if (view) fillBars(view);
    if (name === "results" && !counted) {
      counted = true;
      $("#stats").querySelectorAll(".stat__value").forEach(countUp);
    }
  }

  function setupTabs() {
    $all(".tab").forEach(function (tab) {
      tab.addEventListener("click", function () {
        activate(tab.getAttribute("data-tab"));
      });
    });
  }

  // ── Boot ──────────────────────────────────────────────────

  renderHero();
  renderFeeds();
  setupTabs();
  activate("results");
})();
