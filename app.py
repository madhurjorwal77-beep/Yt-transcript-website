#!/usr/bin/env python3
"""
YT Transcript — Free YouTube Transcript Generator
Backend: Python 3 standard library ONLY (no pip dependencies).

Routes
------
GET /api/health                       -> {"ok": true}
GET /api/tracks?url_or_id=<link|id>   -> video info + caption track list
GET /api/transcript?video_id=&lang=&translate=
                                      -> transcript segments (srv3/json3/vtt
                                         with format retries + mirror fallback)

Static files are served from ./public
Port: env PORT (default 8000)
"""

import json
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import html as html_lib
from collections import deque
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PUBLIC_DIR = os.path.join(BASE_DIR, "public")
PORT = int(os.environ.get("PORT", "8000"))

BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
HTTP_TIMEOUT = 22

# mirror fallback (used only when YouTube blocks the direct caption fetch)
MIRROR_BASE = "https://youtubetotranscript.com/transcript?v="

VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")

# --------------------------------------------------------------------------- #
# Small in-memory cache + per-IP rate limiting
# --------------------------------------------------------------------------- #
_cache = {}
_cache_lock = threading.Lock()


def cache_get(key):
    with _cache_lock:
        item = _cache.get(key)
        if item and item[0] > time.time():
            return item[1]
        if item:
            _cache.pop(key, None)
    return None


def cache_set(key, value, ttl):
    with _cache_lock:
        _cache[key] = (time.time() + ttl, value)


_rate = {}
_rate_lock = threading.Lock()
RATE_LIMIT = 90          # requests
RATE_WINDOW = 60         # seconds


def rate_limited(ip):
    now = time.time()
    with _rate_lock:
        dq = _rate.setdefault(ip, deque())
        while dq and dq[0] < now - RATE_WINDOW:
            dq.popleft()
        if len(dq) >= RATE_LIMIT:
            return True
        dq.append(now)
    return False


# --------------------------------------------------------------------------- #
# HTTP helpers
# --------------------------------------------------------------------------- #
def http_get(url, extra_headers=None, timeout=HTTP_TIMEOUT):
    headers = {
        "User-Agent": BROWSER_UA,
        "Accept-Language": "en-US,en;q=0.9,hi;q=0.7",
        "Accept-Encoding": "identity",
    }
    if extra_headers:
        headers.update(extra_headers)
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "ignore")


def clean_text(s):
    """Decode HTML entities, strip tags, collapse whitespace."""
    if not s:
        return ""
    s = re.sub(r"<[^>]+>", "", s)
    s = html_lib.unescape(s)
    s = s.replace("\u200b", "")
    return re.sub(r"\s+", " ", s).strip()


# --------------------------------------------------------------------------- #
# YouTube: video id parsing + player response
# --------------------------------------------------------------------------- #
def parse_video_id(raw):
    """Accept watch/youtu.be/shorts/live/embed/music URLs or a raw 11-char id."""
    if not raw:
        return None
    raw = raw.strip()
    if VIDEO_ID_RE.match(raw):
        return raw
    try:
        u = urllib.parse.urlparse(raw if "://" in raw else "https://" + raw)
    except Exception:
        return None
    host = (u.hostname or "").lower()
    path = u.path or ""
    qs = urllib.parse.parse_qs(u.query)
    if "youtu.be" in host:
        cand = path.lstrip("/").split("/")[0]
        return cand if VIDEO_ID_RE.match(cand) else None
    if "youtube" in host:
        if path == "/watch" and qs.get("v"):
            cand = qs["v"][0]
            return cand if VIDEO_ID_RE.match(cand) else None
        m = re.match(r"/(shorts|live|embed|v)/([A-Za-z0-9_-]{11})", path)
        if m:
            return m.group(2)
    m = re.search(r"(?:v=|/)([A-Za-z0-9_-]{11})(?:[&?#/]|$)", raw)
    return m.group(1) if m else None


def _extract_player_response(page):
    """Extract ytInitialPlayerResponse JSON via balanced-brace scan."""
    marker = "ytInitialPlayerResponse"
    i = page.find(marker)
    if i < 0:
        return None
    i = page.find("{", i)
    if i < 0:
        return None
    depth = 0
    in_str = False
    esc = False
    for j in range(i, len(page)):
        c = page[j]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
        else:
            if c == '"':
                in_str = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(page[i:j + 1])
                    except Exception:
                        return None
    return None


def _classify_unplayable(pr):
    ps = pr.get("playabilityStatus") or {}
    status = str(ps.get("status", "")).upper()
    reason = str(ps.get("reason", "")).lower()
    if "private" in reason:
        return "private_video"
    # Real age gate: YouTube says the content itself is age-restricted.
    if "age-restricted" in reason or "age restricted" in reason or \
       "inappropriate for some users" in reason:
        return "age_restricted"
    # LOGIN_REQUIRED with "confirm you're not a bot / sign in" is a bot-check
    # against our server IP — retryable, NOT an age restriction.
    if status in ("LOGIN_REQUIRED", "UNPLAYABLE", "ERROR"):
        return "youtube_blocked" if "bot" in reason or "sign in" in reason else "video_unavailable"
    return "video_unavailable"


def fetch_player(video_id):
    """Return (player_response dict, None) or (None, error_code).

    Retries a couple of times: YouTube intermittently answers datacenter IPs
    with a bot-check player response even for public videos.
    """
    url = f"https://www.youtube.com/watch?v={video_id}"
    last_err = "youtube_blocked"
    for attempt in range(3):
        try:
            page = http_get(url)
        except urllib.error.HTTPError as e:
            last_err = "video_unavailable" if e.code in (404,) else "youtube_blocked"
            page = None
        except Exception:
            last_err = "youtube_blocked"
            page = None
        if page:
            pr = _extract_player_response(page)
            if pr:
                if (pr.get("playabilityStatus") or {}).get("status", "OK") == "OK":
                    return pr, None
                last_err = _classify_unplayable(pr)
                if last_err in ("age_restricted", "private_video", "video_unavailable"):
                    return None, last_err
        if attempt < 2:
            time.sleep(1.2)
    return None, last_err


def get_tracks_cached(video_id):
    """(tracks_with_baseUrls, video_info, error) — one player fetch, cached."""
    ck = f"player:{video_id}"
    hit = cache_get(ck)
    if hit:
        return hit["tracks"], hit["video"], None
    pr, err = fetch_player(video_id)
    if err:
        return None, None, err
    tracks = player_tracks(pr)
    video = player_video_info(pr, video_id)
    cache_set(ck, {"tracks": tracks, "video": video}, 1800)
    return tracks, video, None


def player_video_info(pr, video_id):
    vd = pr.get("videoDetails") or {}
    thumbs = ((vd.get("thumbnail") or {}).get("thumbnails") or [])
    thumb = thumbs[-1]["url"] if thumbs else f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
    return {
        "id": video_id,
        "title": vd.get("title", ""),
        "author": vd.get("author", ""),
        "thumbnail": thumb,
        "duration": int(vd.get("lengthSeconds", 0) or 0),
    }


def player_tracks(pr):
    tracks = (
        (pr.get("captions") or {})
        .get("playerCaptionsTracklistRenderer", {})
        .get("captionTracks", [])
    )
    out = []
    for t in tracks:
        name = t.get("name") or {}
        label = name.get("simpleText") or " ".join(
            r.get("text", "") for r in name.get("runs", [])
        ) or t.get("languageCode", "")
        out.append({
            "lang": t.get("languageCode", ""),
            "label": label,
            "kind": "asr" if t.get("kind") == "asr" else "manual",
            "baseUrl": t.get("baseUrl", ""),
        })
    # manual captions first, then ASR
    out.sort(key=lambda x: 0 if x["kind"] == "manual" else 1)
    return out


# --------------------------------------------------------------------------- #
# Caption body parsers (srv3 / json3 / vtt)
# --------------------------------------------------------------------------- #
def parse_srv3(body):
    segments = []
    for m in re.finditer(r'<p\s+t="(\d+)"(?:\s+d="(\d+)")?[^>]*>(.*?)</p>', body, re.S):
        start = int(m.group(1)) / 1000.0
        dur = int(m.group(2) or 0) / 1000.0
        inner = m.group(3)
        parts = re.findall(r"<s[^>]*>(.*?)</s>", inner, re.S)
        text = clean_text(" ".join(parts) if parts else inner)
        if text:
            segments.append({"start": round(start, 2), "duration": round(dur, 2), "text": text})
    return segments


def parse_json3(body):
    try:
        data = json.loads(body)
    except Exception:
        return []
    segments = []
    for ev in data.get("events", []):
        segs = ev.get("segs")
        if not segs:
            continue
        text = clean_text("".join(s.get("utf8", "") for s in segs))
        if text:
            segments.append({
                "start": round(ev.get("tStartMs", 0) / 1000.0, 2),
                "duration": round(ev.get("dDurationMs", 0) / 1000.0, 2),
                "text": text,
            })
    return segments


def _vtt_time(ts):
    parts = ts.strip().replace(",", ".").split(":")
    try:
        parts = [float(p) for p in parts]
    except Exception:
        return 0.0
    while len(parts) < 3:
        parts.insert(0, 0.0)
    return parts[0] * 3600 + parts[1] * 60 + parts[2]


def parse_vtt(body):
    segments = []
    blocks = re.split(r"\n\s*\n", body)
    prev_text = None
    for block in blocks:
        lines = [ln for ln in block.strip().splitlines() if ln.strip()]
        ts_idx = next((i for i, ln in enumerate(lines) if "-->" in ln), None)
        if ts_idx is None:
            continue
        m = re.match(r"([\d:.,]+)\s*-->\s*([\d:.,]+)", lines[ts_idx])
        if not m:
            continue
        start = _vtt_time(m.group(1))
        end = _vtt_time(m.group(2))
        text = clean_text(" ".join(lines[ts_idx + 1:]))
        text = re.sub(r"^\s*<[^>]+>\s*", "", text)
        if not text or text == prev_text:      # drop rolling-caption duplicates
            prev_text = text
            continue
        prev_text = text
        segments.append({
            "start": round(start, 2),
            "duration": round(max(end - start, 0), 2),
            "text": text,
        })
    return segments


def parse_any_caption_body(body):
    if not body or len(body) < 20:
        return []
    head = body.lstrip()[:200]
    if head.startswith("{"):
        return parse_json3(body)
    if "WEBVTT" in head:
        return parse_vtt(body)
    if "<p " in body or "<p>" in body or "<timedtext" in body:
        segs = parse_srv3(body)
        return segs if segs else parse_vtt(body)
    return []


def fetch_caption_direct(base_url, translate=None):
    """Try the track URL with every format variant. Returns segments or []."""
    if not base_url:
        return []
    urls = []
    sep = "&" if "?" in base_url else "?"
    for fmt in ("srv3", "json3", "vtt", None):
        u = base_url if fmt is None else f"{base_url}{sep}fmt={fmt}"
        if translate:
            u += f"&tlang={urllib.parse.quote(translate)}"
        urls.append(u)
    for u in urls:
        try:
            body = http_get(u, timeout=18)
        except Exception:
            continue
        segs = parse_any_caption_body(body)
        if segs:
            return segs
    return []


# --------------------------------------------------------------------------- #
# Mirror fallback (default language only) — used when YouTube blocks our IP
# --------------------------------------------------------------------------- #
def fetch_caption_mirror(video_id):
    try:
        body = http_get(MIRROR_BASE + video_id, timeout=25)
    except Exception:
        return []
    segments = []
    pat = re.compile(
        r'data-start="([\d.]+)"\s+data-duration="([\d.]+)"\s+'
        r'class="transcript-segment[^"]*">\s*(.*?)\s*</span>', re.S)
    for start, dur, text in pat.findall(body):
        text = clean_text(text).strip("♪ ").strip()
        if text:
            segments.append({
                "start": round(float(start), 2),
                "duration": round(float(dur), 2),
                "text": text,
            })
    return segments


# --------------------------------------------------------------------------- #
# API handlers
# --------------------------------------------------------------------------- #
ERROR_MESSAGES = {
    "invalid_input": "Please paste a valid YouTube link or video ID.",
    "video_unavailable": "This video is unavailable or does not exist.",
    "private_video": "This video is private, so its transcript can't be fetched.",
    "age_restricted": "This video is age-restricted and needs sign-in, so its transcript can't be fetched here.",
    "no_captions": "This video has no captions/subtitles, so there is no transcript to show.",
    "youtube_blocked": "YouTube blocked the caption fetch from our server right now. Please try again in a little while.",
    "rate_limited": "Too many requests — please wait a minute and try again.",
    "not_found": "Not found.",
}


def api_tracks(params):
    raw = (params.get("url_or_id") or [""])[0]
    video_id = parse_video_id(raw)
    if not video_id:
        return 400, {"error": "invalid_input", "message": ERROR_MESSAGES["invalid_input"]}
    tracks, video, err = get_tracks_cached(video_id)
    if err:
        return (404 if err in ("video_unavailable", "private_video") else 502), {
            "error": err, "message": ERROR_MESSAGES[err]}
    payload = {
        "video": video,
        "tracks": [{k: t[k] for k in ("lang", "label", "kind")} for t in tracks],
    }
    return 200, payload


def api_transcript(params):
    video_id = (params.get("video_id") or [""])[0].strip()
    lang = (params.get("lang") or [""])[0].strip()
    translate = (params.get("translate") or [""])[0].strip() or None
    if not VIDEO_ID_RE.match(video_id):
        return 400, {"error": "invalid_input", "message": ERROR_MESSAGES["invalid_input"]}

    ck = f"tr:{video_id}:{lang}:{translate or ''}"
    hit = cache_get(ck)
    if hit:
        return 200, hit

    tracks, _video, err = get_tracks_cached(video_id)
    if err == "youtube_blocked" and not translate and lang in ("", "en"):
        # Player page itself is bot-walled from this IP: the mirror still
        # serves the video's default (usually English) track.
        segments = fetch_caption_mirror(video_id)
        if segments:
            text_all = " ".join(s["text"] for s in segments)
            payload = {
                "video_id": video_id, "lang": "en", "trackLang": "en",
                "kind": "manual", "route": "mirror-fallback",
                "segments": segments,
                "wordCount": len(text_all.split()),
                "segmentCount": len(segments),
            }
            cache_set(ck, payload, 3600)
            return 200, payload
    if err:
        return (404 if err in ("video_unavailable", "private_video") else 502), {
            "error": err, "message": ERROR_MESSAGES[err]}
    if not tracks:
        return 404, {"error": "no_captions", "message": ERROR_MESSAGES["no_captions"]}

    track = None
    if lang:
        track = next((t for t in tracks if t["lang"] == lang), None) or \
                next((t for t in tracks if t["lang"].startswith(lang.split("-")[0])), None)
    if track is None:
        track = tracks[0]
        lang = track["lang"]

    segments = fetch_caption_direct(track["baseUrl"], translate=translate)
    route = "youtube-direct"

    # Fallback: the mirror serves the video's default track (English on the
    # videos we verified) — use it when the user asked for the first track or
    # for English, and no translation was requested.
    if not segments and not translate and (track is tracks[0] or lang == "en"):
        segments = fetch_caption_mirror(video_id)
        route = "mirror-fallback"

    if not segments:
        return 502, {"error": "youtube_blocked", "message": ERROR_MESSAGES["youtube_blocked"]}

    text_all = " ".join(s["text"] for s in segments)
    payload = {
        "video_id": video_id,
        "lang": translate or lang,
        "trackLang": lang,
        "kind": track["kind"],
        "route": route,
        "segments": segments,
        "wordCount": len(text_all.split()),
        "segmentCount": len(segments),
    }
    cache_set(ck, payload, 3600)
    return 200, payload


# --------------------------------------------------------------------------- #
# HTTP server
# --------------------------------------------------------------------------- #
class Handler(SimpleHTTPRequestHandler):
    server_version = "YTTranscript/1.0"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=PUBLIC_DIR, **kwargs)

    def log_message(self, fmt, *args):  # keep logs light; no full URLs beyond path
        pass

    def _json(self, code, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if path.startswith("/api/"):
            ip = self.client_address[0]
            if rate_limited(ip):
                return self._json(429, {"error": "rate_limited",
                                        "message": ERROR_MESSAGES["rate_limited"]})
            params = urllib.parse.parse_qs(parsed.query)
            try:
                if path == "/api/health":
                    return self._json(200, {"ok": True})
                if path == "/api/tracks":
                    code, payload = api_tracks(params)
                    return self._json(code, payload)
                if path == "/api/transcript":
                    code, payload = api_transcript(params)
                    return self._json(code, payload)
                return self._json(404, {"error": "not_found",
                                        "message": ERROR_MESSAGES["not_found"]})
            except Exception:
                return self._json(500, {"error": "server_error",
                                        "message": "Something went wrong on our side. Please try again."})
        if path == "/":
            self.path = "/index.html"
        return super().do_GET()


def main():
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"YT Transcript server running on port {PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()
