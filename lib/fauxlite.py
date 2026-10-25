#!/usr/bin/env python3
"""
fpp-plugin-FauxLite worker.

Builds Pro-Lite page commands and posts them to a FauxLite WiFi-to-serial
bridge over its HTTP API (see ../Faux-Lite-Firmware src/main.cpp):

    POST http://<host>/api/send      {"command": "<PA><CH>Hello "}
    GET  http://<host>/api/info      device/version/sign_id/baud/ip/mac
    POST http://<host>/api/loop/start|stop   device message queue

The firmware wraps every command in <ID<signID>> and appends CR/LF, so
commands here are the bare Pro-Lite strings (no ID prefix).

Run directly by the FPP command scripts (commands/*.sh) and by the detached
children callbacks.py spawns for media/playlist/lifecycle events. HTTP is
always bounded with a short timeout; failures are logged and non-fatal.
Python 3 stdlib only.
"""

import argparse
import base64
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta

PLUGIN = "fpp-plugin-FauxLite"
MEDIADIR = os.environ.get("MEDIADIR", "/home/fpp/media")
LOGDIR = os.environ.get("LOGDIR", os.path.join(MEDIADIR, "logs"))
SETTINGS_PATH = os.path.join(MEDIADIR, "config", "plugin." + PLUGIN)
LOG_FILE = os.path.join(LOGDIR, "plugin-%s.log" % PLUGIN)
FPP_API = os.environ.get("FPPAPI", "http://127.0.0.1")

HTTP_TIMEOUT = 4
HOST_RE = re.compile(r"^[A-Za-z0-9._-]+(:[0-9]{1,5})?$")
PAGES_ALL = [chr(c) for c in range(ord("A"), ord("Z") + 1)]
# C-X are the plugin's message pages. The firmware owns A (queue run
# page) and B (queue chain page); Y/Z stay reserved for one-shot/test/
# boot messages.
PAGES_MSG = PAGES_ALL[2:24]

# Pro-Lite protocol code tables.
COLORS = {
    "dim_red": "CA", "red": "CB", "bright_red": "CC", "orange": "CD",
    "bright_orange": "CE", "light_yellow": "CF", "yellow": "CG",
    "bright_yellow": "CH", "lime": "CI", "dim_lime": "CJ",
    "bright_lime": "CK", "bright_green": "CL", "green": "CM",
    "dim_green": "CN", "yel_grn_red": "CO", "rainbow": "CP",
    "red_grn_3d": "CQ", "red_yel_3d": "CR", "grn_red_3d": "CS",
    "grn_yel_3d": "CT", "grn_on_red": "CU", "red_on_grn": "CV",
    "org_on_grn_3d": "CW", "lime_on_red_3d": "CX", "grn_on_red_3d": "CY",
    "red_on_grn_3d": "CZ",
}
FONTS = {
    "normal": "SA", "bold": "SB", "italic": "SC", "bold_italic": "SD",
    "flash_normal": "SE", "flash_bold": "SF", "flash_italic": "SG",
    "flash_bold_italic": "SH",
}
SIZES = {"5x7": "SI", "4x7": "SJ"}
FUNCTIONS = {
    "auto": "FA", "open": "FB", "cover": "FC", "date": "FD",
    "cycling": "FE", "close_right": "FF", "close_left": "FG",
    "close_both": "FH", "scroll_up": "FI", "scroll_down": "FJ",
    "overlap": "FK", "stacking": "FL", "comic_1": "FM", "comic_2": "FN",
    "beep": "FO", "pause": "FP", "appear": "FQ", "random": "FR",
    "shift_left": "FS", "time": "FT", "magic": "FU", "thank_you": "FV",
    "welcome": "FW", "link_page": "FZ", "target": "F1", "current": "F2",
    "day_left": "F3", "hour_left": "F4", "minute_left": "F5",
    "second_left": "F6",
}


def log(msg):
    try:
        os.makedirs(LOGDIR, exist_ok=True)
        with open(LOG_FILE, "a") as f:
            f.write("%s %s\n" % (time.strftime("%Y-%m-%dT%H:%M:%S"), msg))
    except OSError:
        pass


def read_kv(path):
    out = {}
    try:
        with open(path) as f:
            for line in f:
                k, _, v = line.partition("=")
                out[k.strip()] = v.strip().strip('"')
    except OSError:
        pass
    return out


def load_cfg():
    return read_kv(SETTINGS_PATH)


def truthy(v):
    return str(v or "").strip().lower() not in ("", "0", "false", "no", "off")


def configured(cfg):
    """Master switch + device address both set — until then nothing runs.
    Defaults deliberately fail closed: a fresh install is inert."""
    return truthy(cfg.get("enabled")) and bool((cfg.get("host") or "").strip())


def base_url(cfg):
    host = (cfg.get("host") or "").strip().rstrip("/")
    if not host or not HOST_RE.match(host):
        raise ValueError("invalid FauxLite host: %r" % host)
    if "://" in host:
        # HOST_RE disallows schemes, but be safe anyway
        host = host.split("://", 1)[1]
    if ":" in host:
        h, p = host.rsplit(":", 1)
        port = int(p)
        if not (1 <= port <= 65535):
            raise ValueError("invalid port: %s" % p)
    return "http://" + host


def http_json(method, url, payload=None, timeout=HTTP_TIMEOUT):
    """Returns (status, parsed-json-or-None, error-string)."""
    req = urllib.request.Request(url, method=method)
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, data=data, timeout=timeout) as r:
            body = r.read(65536)
            try:
                return r.status, json.loads(body), ""
            except ValueError:
                return r.status, None, ""
    except urllib.error.HTTPError as e:
        return e.code, None, "HTTP %s" % e.code
    except (urllib.error.URLError, OSError) as e:
        return 0, None, str(e.reason if hasattr(e, "reason") else e)


def send_command(cfg, command):
    """Post one Pro-Lite command string to the device. Returns ok bool."""
    try:
        url = base_url(cfg)
    except ValueError as e:
        log("send skipped: %s" % e)
        return False
    status, _, err = http_json("POST", url + "/api/send",
                               {"command": command})
    if status != 200:
        log("send failed (%s): %r" % (err or status, command[:80]))
        return False
    log("sent: %s" % command)
    return True


def run_page(cfg, page):
    """Run a page. <RPx> is a standalone command: it must go over the
    wire on its own — appended to a page write it becomes literal text
    on the sign."""
    return send_command(cfg, "<RP%s>" % page)


def write_and_run(cfg, page, text, color="", font="", size="",
                  function="", escape=True):
    """Page write then separate run — the only correct way to show text."""
    if not send_command(cfg, page_write(page, text, color, font, size,
                                        function, escape=escape)):
        return False
    return run_page(cfg, page)


def loop_action(cfg, action, index=None):
    """POST /api/loop/start|stop. 'start' takes ?queue=N on current
    firmware (an index into the queues array); 'stop' takes no index."""
    try:
        url = base_url(cfg)
    except ValueError as e:
        log("loop %s skipped: %s" % (action, e))
        return False
    ep = url + "/api/loop/" + action
    if action == "start" and index is not None:
        ep += "?queue=%d" % index
    status, _, err = http_json("POST", ep)
    if status != 200:
        log("loop %s failed: %s" % (action, err or status))
        return False
    log("queue %s%s" % (action,
                        " #%d" % index if index is not None else ""))
    return True


def start_device_queue(cfg, index=None):
    """Start the device's own message queue. With no index, prefer the
    boot queue, then the first queue that has messages."""
    if index is not None:
        return loop_action(cfg, "start", index)
    try:
        url = base_url(cfg)
    except ValueError as e:
        log("queue start skipped: %s" % e)
        return False
    code, cur, err = http_json("GET", url + "/api/messages")
    if code != 200 or not isinstance(cur, dict):
        log("queue start: could not read queues (%s)" % (err or code))
        return False
    qs = cur.get("queues") or []
    pick = -1
    bq = cur.get("bootQueue")
    if isinstance(bq, int) and 0 <= bq < len(qs) \
            and isinstance(qs[bq], dict) and qs[bq].get("messages"):
        pick = bq
    else:
        for i, q in enumerate(qs):
            if isinstance(q, dict) and q.get("messages"):
                pick = i
                break
    if pick < 0:
        log("queue start: device has no queues to run")
        return False
    return loop_action(cfg, "start", pick)


def resolve(value, table):
    """Accept a code ('CH'), a table key ('bright_yellow'), or '' (omit)."""
    v = (value or "").strip()
    if not v:
        return ""
    if v in table:
        return table[v]
    # tolerate labels with spaces / case
    key = v.lower().replace(" ", "_").replace("-", "_")
    if key in table:
        return table[key]
    if len(v) == 2 and v[0].isalpha() and v.upper() in table.values():
        return v.upper()
    return ""


def page_letter(value, allowed=None, default="A"):
    v = (value or "").strip()[:1].upper()
    allowed = allowed if allowed is not None else PAGES_ALL
    return v if v in allowed else default


def sanitize(text):
    """ASCII-only text with no protocol metacharacters — a stray '<PA>'
    inside a song title must not turn into a page command."""
    t = re.sub(r"[\x00-\x1f\x7f<>]", "", str(text or ""))
    t = t.encode("ascii", "ignore").decode("ascii")
    t = re.sub(r"[ \t]+", " ", t).strip()
    return t


def page_attrs(function="", color="", font="", size=""):
    """'<F?><C?><S?><S?>' — the attribute codes that lead page content,
    in effect/color/font/size order."""
    cmd = ""
    f = resolve(function, FUNCTIONS)
    c = resolve(color, COLORS)
    fo = resolve(font, FONTS)
    s = resolve(size, SIZES)
    if f:
        cmd += "<%s>" % f
    if c:
        cmd += "<%s>" % c
    if fo:
        cmd += "<%s>" % fo
    if s:
        cmd += "<%s>" % s
    return cmd


def page_write(page, text, color="", font="", size="", function="",
               escape=True):
    """Build '<P?><F?><C?><S?>text'. escape=False is for text that
    already went through sanitize() + field injection (the countdown
    writer), which legitimately contains '<Fx>' codes."""
    cmd = "<P%s>" % page + page_attrs(function, color, font, size)
    return cmd + (sanitize(text) if escape else text)


# Live countdown fields the sign renders itself inside page text.
COUNTDOWN_FIELDS = {
    "target": "F1", "current": "F2", "days": "F3",
    "hours": "F4", "minutes": "F5", "seconds": "F6",
}


def countdown_text(fmt):
    """Turn '{days} {hours}:{minutes}:{seconds}' style placeholders into
    the sign's live countdown fields (<F3>..<F6>, <F1> target, <F2>
    current). sanitize() runs first so user '<>' can't inject codes, then
    the real fields are injected."""
    t = sanitize(fmt)
    for name, code in COUNTDOWN_FIELDS.items():
        t = t.replace("{%s}" % name, "<%s>" % code)
    return t


def countdown(cfg, args):
    """Program the sign's countdown timer to a wall-clock target and
    (optionally) write a live countdown page.

    <VddddhhmmP> sets the remaining duration and the page to switch to at
    zero; it takes whole minutes so we round UP — hitting zero a few
    seconds late beats hitting it early."""
    m = re.match(r"^(\d{1,2}):(\d{2})(?::(\d{2}))?$", (args.time or "").strip())
    if not m:
        log("countdown: bad --time %r (want HH:MM[:SS])" % args.time)
        return 1
    hh, mm, ss = int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)
    if hh > 23 or mm > 59 or ss > 59:
        log("countdown: --time out of range %r" % args.time)
        return 1

    now = datetime.now()
    dstr = (args.date or "").strip()
    if dstr:
        try:
            d = datetime.strptime(dstr, "%Y-%m-%d").date()
        except ValueError:
            log("countdown: bad --date %r (want YYYY-MM-DD)" % dstr)
            return 1
        target = datetime(d.year, d.month, d.day, hh, mm, ss)
    else:
        target = now.replace(hour=hh, minute=mm, second=ss, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
    if target <= now:
        log("countdown: target %s is in the past" % target)
        return 1

    total_min = (int((target - now).total_seconds()) + 59) // 60
    days, rem = divmod(total_min, 1440)
    hours, minutes = divmod(rem, 60)
    if days > 9999:
        log("countdown: %d days out is too far" % days)
        return 1

    end_page = page_letter(args.end_page, PAGES_MSG, default="C")
    if not send_command(cfg, "<V%04d%02d%02d%s>"
                      % (days, hours, minutes, end_page)):
        return 1
    log("countdown armed: %dd %dh %dm -> page %s (target %s)"
        % (days, hours, minutes, end_page, target))

    text = countdown_text(args.format or "")
    if not text.strip():
        return 0  # timer set; user only wanted it programmed
    page = page_letter(args.page, PAGES_MSG, default="C")
    if args.display_mode == "display":
        ok = write_and_run(cfg, page, text, args.color, args.font,
                           args.size, args.function, escape=False)
    else:
        ok = send_command(cfg, page_write(page, text, args.color,
                                          args.font, args.size,
                                          args.function, escape=False))
    return 0 if ok else 1


class _Fields(dict):
    def __missing__(self, key):
        return ""


def _basename(name):
    n = re.sub(r"\.[A-Za-z0-9]+$", "", os.path.basename(str(name or "")))
    return n


def fpp_system_info():
    """Best-effort HostName/HostDescription from the local fppd API —
    used by the {hostname}/{hostdesc} placeholders. 1.5s budget; empty
    on any failure."""
    st, info, _ = http_json("GET", FPP_API + "/api/system/info",
                          timeout=1.5)
    return info if st == 200 and isinstance(info, dict) else {}


def np_field_map(cfg, data):
    """All placeholders available in page text: the media callback's
    TagLib fields, the plugin's Show Info settings, and FPP's host
    identity."""
    fields = _Fields(
        title=data.get("title", ""),
        artist=data.get("artist", ""),
        album=data.get("album", ""),
        sequence=_basename(data.get("Sequence", "")),
        media=_basename(data.get("Media", "")),
        filename=_basename(data.get("Media", "") or data.get("Sequence", "")),
        type=data.get("type", ""),
        year=data.get("year", ""),
        genre=data.get("genre", ""),
        track=data.get("track", ""),
        comment=data.get("comment", ""),
        length=data.get("length", ""),
        seconds=data.get("seconds", ""),
        minutes=data.get("minutes", ""),
        bitrate=data.get("bitrate", ""),
        sampleRate=data.get("sampleRate", ""),
        channels=data.get("channels", ""),
        showName=cfg.get("showName", ""),
        showTagline=cfg.get("showTagline", ""),
        showHost=cfg.get("showHost", ""),
        showLocation=cfg.get("showLocation", ""),
        showSchedule=cfg.get("showSchedule", ""),
        showUrl=cfg.get("showUrl", ""),
    )
    sysinfo = fpp_system_info()
    fields["hostname"] = sysinfo.get("HostName", "")
    fields["hostdesc"] = sysinfo.get("HostDescription", "")
    return fields


def render_template(fmt, fields):
    """Substitute {placeholders}; collapse separators/brackets left
    empty by missing fields. Never raises on a bad template."""
    try:
        out = fmt.format_map(fields)
    except (KeyError, IndexError, ValueError):
        out = fmt
    out = re.sub(r"(\s*-\s*){2,}", " - ", out)
    return re.sub(r"[\[\(]\s*[\]\)]", "", out).strip(" -")


def now_playing_text(data, fmt):
    """Legacy single-format renderer (kept for callers/tests)."""
    fields = np_field_map({}, data)
    out = render_template(fmt, fields)
    return out if out.strip() else fields["filename"]


def np_pages(cfg):
    """Ordered list of enabled now-playing page dicts.

    npPages is a base64-encoded JSON array saved by the config page:
      [{page,text,function,color,font,size,duration,enabled}, ...]
    duration is the number of seconds the device queue holds that page
    while rotating. Falls back to the legacy single-page np* settings
    when npPages is unset or malformed."""
    raw = (cfg.get("npPages") or "").strip()
    if raw:
        arr = None
        try:
            arr = json.loads(base64.b64decode(raw).decode("utf-8",
                                                         "replace"))
        except Exception:
            log("npPages is not valid base64 JSON — ignoring")
        if isinstance(arr, list):
            pages, used = [], set()
            for p in arr[:len(PAGES_MSG)]:
                if not isinstance(p, dict) or not truthy(p.get("enabled", 1)):
                    continue
                letter = str(p.get("page") or "").strip()[:1].upper()
                if letter not in PAGES_MSG or letter in used:
                    continue  # reserved/invalid letter, or duplicate row
                used.add(letter)
                try:
                    dur = int(p.get("duration") or 8)
                except (TypeError, ValueError):
                    dur = 8
                pages.append({
                    "page": letter,
                    "text": str(p.get("text") or "")[:200],
                    "function": str(p.get("function") or ""),
                    "color": str(p.get("color") or ""),
                    "font": str(p.get("font") or ""),
                    "size": str(p.get("size") or ""),
                    "duration": max(0, min(300, dur)),
                })
            if pages:
                return pages
    return [{"page": page_letter(cfg.get("npPage"), PAGES_MSG, default="C"),
             "text": cfg.get("npFormat") or "{title}",
             "function": cfg.get("npFunction", ""),
             "color": cfg.get("npColor", ""),
             "font": cfg.get("npFont", ""),
             "size": cfg.get("npSize", ""),
             "duration": 8, "legacy": True}]


def combined_page(page, rendered):
    """One sign page holding every row's message, separated by <FP>
    pause tags — the same layout the firmware's own queue compiler
    (buildQueuePageCommand) produces: each segment displays, then each
    <FP> holds it for ~2s, so a row's hold seconds becomes
    (secs+1)//2 pause tags. After the last segment the page loops back
    to the first, giving a seamless multi-message rotation on a single
    page with no device-queue involvement at all."""
    cmd = "<P%s>" % page
    for p, text in rendered:
        cmd += page_attrs(p["function"], p["color"], p["font"], p["size"])
        cmd += sanitize(text)
        cmd += "<FP>" * ((p["duration"] + 1) // 2)
    return cmd


def rotation_page(cfg):
    return page_letter(cfg.get("npRotationPage"), PAGES_MSG, default="C")


# 18x7 all-black bitmap (one R/G/Y/B char per dot). A page with no
# visible content falls back to the sign's built-in HELLO demo, so real
# blanking needs a black graphic block — a space doesn't cut it. We
# define our own on block Z rather than relying on the firmware's
# block-B upload.
BLACK_GRAPHIC = "B" * 126


def ensure_black_graphic(cfg):
    return send_command(cfg, "<GZ>" + BLACK_GRAPHIC)


def blank_page_cmd(page, function="FQ"):
    """'<Px><F?><BZ>' — an all-black graphic page (a truly blank
    display, unlike a space which shows HELLO)."""
    return "<P%s>%s<BZ>" % (page, page_attrs(function))


def blank(cfg, page):
    if not ensure_black_graphic(cfg):
        return False
    if not send_command(cfg, blank_page_cmd(page)):
        return False
    return run_page(cfg, page)


def stop_action(cfg):
    """Apply the configured 'when the show stops' action."""
    action = (cfg.get("stopAction") or "keep").strip()
    page = page_letter(cfg.get("stopPage"), PAGES_MSG, default="C")
    if action == "blank":
        return blank(cfg, page)
    if action == "time":
        if not send_command(cfg, "<P%s><FT>" % page):
            return False
        return run_page(cfg, page)
    if action == "date":
        if not send_command(cfg, "<P%s><FD>" % page):
            return False
        return run_page(cfg, page)
    if action == "custom":
        text = cfg.get("stopText") or ""
        if not text.strip():
            return True
        return write_and_run(cfg, page, text, cfg.get("stopColor", ""),
                             function=cfg.get("stopFunction", ""))
    if action == "queue":
        return start_device_queue(cfg)
    return True  # "keep" — leave the sign as-is


# ---------------------------------------------------------------- events


def handle_media(cfg, data):
    """fppd media event -> render every configured row, then either run
    the one page (single row) or rebuild the combined rotation page
    (multi-row)."""
    if not truthy(cfg.get("npEnabled")):
        return 0
    etype = str(data.get("type") or "").lower()
    if etype in ("", "pause", "event"):
        return 0
    pages = np_pages(cfg)
    fields = np_field_map(cfg, data)
    rendered = [(p, render_template(p["text"], fields)) for p in pages]

    if len(pages) == 1:
        p, text = rendered[0]
        if p.get("legacy") and not text.strip():
            text = fields["filename"]
        write_and_run(cfg, p["page"], text, p["color"], p["font"],
                      p["size"], p["function"])
        return 0

    # Each row's content also lands on its own sign page (reachable via
    # Run Page / countdown end-pages / one-shot restores), then the
    # combined <FP>-separated page on npRotationPage drives the visible
    # rotation — written last so it wins if a row shares its letter.
    rot = rotation_page(cfg)
    for p, text in rendered:
        send_command(cfg, page_write(p["page"], text, p["color"],
                                     p["font"], p["size"],
                                     p["function"]))
    send_command(cfg, combined_page(rot, rendered))
    run_page(cfg, rot)
    return 0


def handle_playlist(cfg, data):
    """Playlist stop -> the configured stop action (time/blank/...)."""
    if str(data.get("Action") or "").lower() != "stop":
        return 0
    stop_action(cfg)
    return 0


def handle_lifecycle(cfg, phase):
    if phase == "shutdown":
        stop_action(cfg)
    return 0


def do_info(cfg):
    try:
        url = base_url(cfg)
    except ValueError as e:
        print(json.dumps({"reachable": False, "error": str(e)}))
        return 1
    st, info, err = http_json("GET", url + "/api/info")
    out = {"reachable": st == 200, "info": info, "error": err}
    st2, msgs, _ = http_json("GET", url + "/api/messages")
    out["queue"] = msgs if st2 == 200 else None
    print(json.dumps(out))
    return 0 if out["reachable"] else 1


def oneshot(cfg, text, repeat, color, font, size, function, beep):
    """One-shot: black page Y, message on Z, run Z xN then back to Y.
    Y must hold the black graphic, not a space — a visibly-empty page
    makes the sign fall back to its HELLO demo."""
    repeat = max(1, min(99, int(repeat or 1)))
    if beep:
        if not send_command(cfg, "<PX><FO>"):
            return False
    if not ensure_black_graphic(cfg):
        return False
    if not send_command(cfg, blank_page_cmd("Y", function)):
        return False
    if not send_command(cfg, page_write("Z", text, color, font, size,
                                        function)):
        return False
    return send_command(cfg, "<RPZ><%02d><RPY>" % repeat)


def beep(cfg, count):
    count = max(1, min(99, int(count or 1)))
    if not ensure_black_graphic(cfg):
        return False
    if not send_command(cfg, blank_page_cmd("Y")):
        return False
    if not send_command(cfg, "<PZ><FO>"):
        return False
    return send_command(cfg, "<RPZ><%02d><RPY>" % count)


# ------------------------------------------------------------------- CLI


def build_parser():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="action", required=True)

    sub.add_parser("media").add_argument("data", help="fppd media JSON")
    sub.add_parser("playlist").add_argument("data", help="fppd playlist JSON")
    sub.add_parser("lifecycle").add_argument("phase")

    s = sub.add_parser("send", help="write text to a page")
    s.add_argument("--text", required=True)
    s.add_argument("--page", default="C")
    s.add_argument("--color", default="")
    s.add_argument("--font", default="")
    s.add_argument("--size", default="")
    s.add_argument("--function", default="")
    s.add_argument("--display-mode", default="display",
                   choices=["display", "store"],
                   help="display = also run the page now")

    s = sub.add_parser("raw", help="send a bare Pro-Lite command")
    s.add_argument("command")

    s = sub.add_parser("run", help="run a page")
    s.add_argument("--page", default="A")

    s = sub.add_parser("blank")
    s.add_argument("--page", default="C")

    s = sub.add_parser("time", help="show the sign's clock")
    s.add_argument("--page", default="C")
    s = sub.add_parser("date", help="show the sign's date")
    s.add_argument("--page", default="C")

    s = sub.add_parser("queue", help="start/stop a device message queue")
    s.add_argument("direction", choices=["start", "stop"])
    s.add_argument("--queue", type=int, default=None,
                   help="queue index for start (default: boot queue, "
                        "else first non-empty)")

    s = sub.add_parser("oneshot",
                       help="temporary message on reserved pages Y/Z")
    s.add_argument("--text", required=True)
    s.add_argument("--repeat", type=int, default=1)
    s.add_argument("--color", default="")
    s.add_argument("--font", default="")
    s.add_argument("--size", default="")
    s.add_argument("--function", default="")
    s.add_argument("--beep", action="store_true")

    s = sub.add_parser("beep")
    s.add_argument("--count", type=int, default=1)

    s = sub.add_parser("countdown",
                       help="count down to a wall-clock time on the sign")
    s.add_argument("--time", required=True,
                   help="target clock time HH:MM[:SS]")
    s.add_argument("--date", default="",
                   help="YYYY-MM-DD; blank = today, or tomorrow if past")
    s.add_argument("--format", default="{hours}:{minutes}:{seconds}",
                   help="text with {days} {hours} {minutes} {seconds} "
                        "{target} {current} live fields; blank = only "
                        "program the timer")
    s.add_argument("--page", default="C")
    s.add_argument("--end-page", default="C",
                   help="page shown when the countdown reaches zero")
    s.add_argument("--color", default="")
    s.add_argument("--font", default="")
    s.add_argument("--size", default="")
    s.add_argument("--function", default="")
    s.add_argument("--display-mode", default="display",
                   choices=["display", "store"])

    sub.add_parser("info", help="print device info/queue as JSON")
    sub.add_parser("stopaction", help="run the configured stop action")
    return p


def main(argv):
    args = build_parser().parse_args(argv)
    cfg = load_cfg()

    if args.action == "info":
        return do_info(cfg)

    if not configured(cfg):
        log("%s ignored: plugin disabled or no device configured"
            % args.action)
        return 0

    if args.action == "media":
        try:
            data = json.loads(args.data)
        except ValueError:
            data = {}
        return handle_media(cfg, data)

    if args.action == "playlist":
        try:
            data = json.loads(args.data)
        except ValueError:
            data = {}
        return handle_playlist(cfg, data)

    if args.action == "lifecycle":
        return handle_lifecycle(cfg, args.phase)

    if args.action == "send":
        page = page_letter(args.page, PAGES_MSG, default="C")
        if args.display_mode == "display":
            ok = write_and_run(cfg, page, args.text, args.color,
                               args.font, args.size, args.function)
        else:
            ok = send_command(cfg, page_write(page, args.text,
                                              args.color, args.font,
                                              args.size, args.function))
        return 0 if ok else 1

    if args.action == "raw":
        return 0 if send_command(cfg, args.command) else 1

    if args.action == "run":
        page = page_letter(args.page, PAGES_ALL)
        return 0 if run_page(cfg, page) else 1

    if args.action == "blank":
        page = page_letter(args.page, PAGES_MSG, default="C")
        return 0 if blank(cfg, page) else 1

    if args.action == "time":
        page = page_letter(args.page, PAGES_MSG, default="C")
        ok = send_command(cfg, "<P%s><FT>" % page) and run_page(cfg, page)
        return 0 if ok else 1

    if args.action == "date":
        page = page_letter(args.page, PAGES_MSG, default="C")
        ok = send_command(cfg, "<P%s><FD>" % page) and run_page(cfg, page)
        return 0 if ok else 1

    if args.action == "queue":
        if args.direction == "start":
            return 0 if start_device_queue(cfg, args.queue) else 1
        return 0 if loop_action(cfg, "stop") else 1

    if args.action == "oneshot":
        ok = oneshot(cfg, args.text, args.repeat, args.color, args.font,
                     args.size, args.function, args.beep)
        return 0 if ok else 1

    if args.action == "beep":
        return 0 if beep(cfg, args.count) else 1

    if args.action == "countdown":
        return countdown(cfg, args)

    if args.action == "stopaction":
        return 0 if stop_action(cfg) else 1

    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
