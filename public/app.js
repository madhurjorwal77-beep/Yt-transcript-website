/* YT Transcript — frontend logic (vanilla JS, talks to /api on same origin) */
(function () {
  "use strict";
  var $ = function (id) { return document.getElementById(id); };
  var form = $("tool-form"), input = $("url-input"), btn = $("get-btn");
  var loadingEl = $("state-loading"), errorEl = $("state-error"), errorMsg = $("error-msg");
  var resultEl = $("result"), langRow = $("lang-row"), langSel = $("lang-select"), trSel = $("translate-select");
  var segBox = $("segments"), searchInput = $("search-input");
  var current = null;        // last transcript payload
  var currentVideo = null;   // last tracks payload .video
  var lastQuery = "";        // for retry

  function fmtTime(s) {
    s = Math.max(0, Math.floor(s));
    var h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60;
    var mm = (h > 0 && m < 10) ? "0" + m : "" + m;
    var ss = sec < 10 ? "0" + sec : "" + sec;
    return (h > 0 ? h + ":" : "") + mm + ":" + ss;
  }
  function showLoading(on) {
    loadingEl.classList.toggle("show", on);
    btn.disabled = on;
  }
  function showError(msg) {
    errorMsg.textContent = msg;
    errorEl.classList.add("show");
  }
  function hideStates() {
    errorEl.classList.remove("show");
    resultEl.classList.remove("show");
  }

  async function fetchJSON(url) {
    var r = await fetch(url);
    var data = {};
    try { data = await r.json(); } catch (e) {}
    if (!r.ok) throw new Error(data.message || "Request failed (" + r.status + ")");
    return data;
  }

  async function run(raw) {
    lastQuery = raw;
    hideStates(); showLoading(true);
    try {
      var tracks = await fetchJSON("/api/tracks?url_or_id=" + encodeURIComponent(raw));
      currentVideo = tracks.video;
      fillLanguages(tracks.tracks);
      langRow.style.display = tracks.tracks.length ? "flex" : "none";
      await loadTranscript();
    } catch (e) {
      showLoading(false);
      showError(e.message);
    }
  }

  function fillLanguages(tracks) {
    langSel.innerHTML = "";
    tracks.forEach(function (t) {
      var o = document.createElement("option");
      o.value = t.lang;
      o.textContent = t.label + " (" + t.lang + (t.kind === "asr" ? ", auto" : "") + ")";
      langSel.appendChild(o);
    });
  }

  async function loadTranscript() {
    if (!currentVideo) return;
    showLoading(true); errorEl.classList.remove("show");
    var q = "/api/transcript?video_id=" + encodeURIComponent(currentVideo.id) +
            "&lang=" + encodeURIComponent(langSel.value || "");
    if (trSel.value) q += "&translate=" + encodeURIComponent(trSel.value);
    try {
      current = await fetchJSON(q);
      render();
    } catch (e) {
      showError(e.message);
    } finally {
      showLoading(false);
    }
  }

  function render() {
    var v = currentVideo, t = current;
    $("video-thumb").src = v.thumbnail;
    $("video-thumb").alt = v.title;
    $("video-title").textContent = v.title;
    $("video-meta").textContent = (v.author ? "by " + v.author + " · " : "") +
      "Language: " + t.lang + (t.kind === "asr" ? " (auto-generated)" : "");
    $("counts").textContent = t.wordCount.toLocaleString() + " words · " +
      t.segmentCount + " lines · video length " + fmtTime(v.duration || 0);
    searchInput.value = "";
    drawSegments("");
    resultEl.classList.add("show");
    resultEl.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function drawSegments(filter) {
    var segs = current.segments;
    segBox.innerHTML = "";
    var hits = 0;
    var frag = document.createDocumentFragment();
    segs.forEach(function (s) {
      var row = document.createElement("div");
      row.className = "seg";
      var b = document.createElement("button");
      b.className = "ts"; b.type = "button"; b.textContent = fmtTime(s.start);
      b.title = "Play video from here";
      b.addEventListener("click", function () {
        window.open("https://www.youtube.com/watch?v=" + currentVideo.id +
                    "&t=" + Math.floor(s.start) + "s", "_blank", "noopener");
      });
      var span = document.createElement("span");
      span.className = "tx";
      if (filter) {
        var idx = s.text.toLowerCase().indexOf(filter.toLowerCase());
        if (idx >= 0) {
          hits++;
          span.textContent = s.text.slice(0, idx);
          var mk = document.createElement("mark");
          mk.textContent = s.text.slice(idx, idx + filter.length);
          span.appendChild(mk);
          span.appendChild(document.createTextNode(s.text.slice(idx + filter.length)));
        } else {
          span.textContent = s.text;
          row.style.display = "none";
        }
      } else {
        span.textContent = s.text;
      }
      row.appendChild(b); row.appendChild(span);
      frag.appendChild(row);
    });
    segBox.appendChild(frag);
    $("search-count").textContent = filter ? (hits + " match" + (hits === 1 ? "" : "es")) : "";
  }

  function plainText(withTs) {
    return current.segments.map(function (s) {
      return (withTs ? "[" + fmtTime(s.start) + "] " : "") + s.text;
    }).join("\n");
  }
  function srtText() {
    function ts(s) {
      var ms = Math.round((s % 1) * 1000), sec = Math.floor(s);
      var h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), ss = sec % 60;
      function p(n, l) { return String(n).padStart(l, "0"); }
      return p(h, 2) + ":" + p(m, 2) + ":" + p(ss, 2) + "," + p(ms, 3);
    }
    return current.segments.map(function (s, i) {
      var end = s.start + (s.duration || 2);
      return (i + 1) + "\n" + ts(s.start) + " --> " + ts(end) + "\n" + s.text + "\n";
    }).join("\n");
  }
  function download(name, text) {
    var a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([text], { type: "text/plain;charset=utf-8" }));
    a.download = name;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(function () { URL.revokeObjectURL(a.href); }, 4000);
  }
  function copyText(text, btnEl) {
    function done() {
      var old = btnEl.textContent;
      btnEl.textContent = "✓ Copied";
      setTimeout(function () { btnEl.textContent = old; }, 1600);
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(done, function () { fallback(); });
    } else fallback();
    function fallback() {
      var ta = document.createElement("textarea");
      ta.value = text; document.body.appendChild(ta); ta.select();
      try { document.execCommand("copy"); done(); } catch (e) {}
      ta.remove();
    }
  }

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var raw = input.value.trim();
    if (raw) run(raw);
  });
  document.querySelectorAll(".chip").forEach(function (chip) {
    chip.addEventListener("click", function () {
      input.value = chip.getAttribute("data-url");
      run(input.value);
    });
  });
  $("retry-btn").addEventListener("click", function () { if (lastQuery) run(lastQuery); });
  langSel.addEventListener("change", loadTranscript);
  trSel.addEventListener("change", loadTranscript);
  searchInput.addEventListener("input", function () { drawSegments(searchInput.value.trim()); });
  $("ts-toggle").addEventListener("change", function () {
    segBox.classList.toggle("no-ts", !this.checked);
  });
  $("copy-btn").addEventListener("click", function () { copyText(plainText(false), this); });
  $("copy-ts-btn").addEventListener("click", function () { copyText(plainText(true), this); });
  $("dl-txt-btn").addEventListener("click", function () {
    download("transcript-" + currentVideo.id + ".txt",
      currentVideo.title + "\n" + "https://www.youtube.com/watch?v=" + currentVideo.id + "\n\n" + plainText(true));
  });
  $("dl-srt-btn").addEventListener("click", function () {
    download("transcript-" + currentVideo.id + ".srt", srtText());
  });
})();
