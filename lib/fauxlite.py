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
DATADIR = os.path.join(MEDIADIR, "plugindata", PLUGIN)
STATE_PATH = os.path.join(DATADIR, "np-state.json")
FPP_API = os.environ.get("FPPAPI", "http://127.0.0.1")

HTTP_TIMEOUT = 4
HOST_RE = re.compile(r"^[A-Za-z0-9._-]+(:[0-9]{1,5})?$")
PAGES_ALL = [chr(c) for c in range(ord("A"), ord("Z") + 1)]
PAGES_MSG = PAGES_ALL[:24]  # A-X: Y and Z are reserved for one-shot messages

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


def loop_action(cfg, action):
    try:
        url = base_url(cfg)
    except ValueError as e:
        log("loop %s skipped: %s" % (action, e))
        return False
    status, _, err = http_json("POST", url + "/api/loop/" + action)
    if status != 200:
        log("loop %s failed: %s" % (action, err or status))
        return False
    log("queue %s" % action)
    return True


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


def page_write(page, text, color="", font="", size="", function="",
               escape=True):
    """Build '<P?><F?><C?><S?>text ' — the trailing space keeps a short
    message from tripping the sign's demo mode. escape=False is for
    text that already went through sanitize() + field injection (the
    countdown writer), which legitimately contains '<Fx>' codes."""
    cmd = "<P%s>" % page
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
    return cmd + (sanitize(text) if escape else text) + " "


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

    end_page = page_letter(args.end_page, PAGES_MSG)
    if not send_command(cfg, "<V%04d%02d%02d%s>"
                      % (days, hours, minutes, end_page)):
        return 1
    log("countdown armed: %dd %dh %dm -> page %s (target %s)"
        % (days, hours, minutes, end_page, target))

    text = countdown_text(args.format or "")
    if not text.strip():
        return 0  # timer set; user only wanted it programmed
    page = page_letter(args.page, PAGES_MSG)
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
                    "duration": max(1, min(300, dur)),
                })
            if pages:
                return pages
    return [{"page": page_letter(cfg.get("npPage"), PAGES_MSG),
             "text": cfg.get("npFormat") or "{title}",
             "function": cfg.get("npFunction", ""),
             "color": cfg.get("npColor", ""),
             "font": cfg.get("npFont", ""),
             "size": cfg.get("npSize", ""),
             "duration": 8, "legacy": True}]


def load_state():
    try:
        with open(STATE_PATH) as f:
            st = json.load(f)
        return st if isinstance(st, dict) else {}
    except (OSError, ValueError):
        return {}


def save_state(st):
    try:
        os.makedirs(DATADIR, exist_ok=True)
        with open(STATE_PATH, "w") as f:
            json.dump(st, f)
    except OSError as e:
        log("state save failed: %s" % e)


def _queue_entries(pages):
    return [{"command": "<RP%s>" % p["page"], "duration": p["duration"]}
            for p in pages]


def ensure_rotation(cfg, pages):
    """Program the device message queue to cycle <RPx> for each
    now-playing page — the sign-side engine that rotates seamlessly
    with zero plugin involvement between media events.

    The first takeover snapshots the user's queue (messages, runOnBoot,
    queueActive) into the state file; release_rotation() puts it back.
    Re-checked on every media event so a device reboot or an edited
    page list self-heals — but a matching signature means NO writes,
    which matters because /api/messages persists to the ESP32's flash."""
    sig = "|".join("%s:%d" % (p["page"], p["duration"]) for p in pages)
    st = load_state()
    try:
        url = base_url(cfg)
    except ValueError as e:
        log("rotation skipped: %s" % e)
        return

    want = _queue_entries(pages)
    code, cur, _ = http_json("GET", url + "/api/messages")
    if st.get("sig") == sig:
        # Already programmed once — verify the device still holds it.
        if code == 200 and isinstance(cur, dict):
            if (cur.get("queueActive")
                    and cur.get("messages") == want):
                return
        elif code == 0:
            return  # unreachable; the page writes already logged it

    if code != 200 or not isinstance(cur, dict):
        log("rotation: could not read device queue")
        return
    if not st.get("snapshot"):
        st["snapshot"] = {"messages": cur.get("messages") or [],
                          "runOnBoot": bool(cur.get("runOnBoot")),
                          "queueActive": bool(cur.get("queueActive"))}
    code, _, err = http_json("POST", url + "/api/messages",
                             {"messages": want,
                              "runOnBoot": bool(cur.get("runOnBoot"))})
    if code != 200:
        log("rotation: queue program failed (%s)" % (err or code))
        return
    loop_action(cfg, "start")
    st["sig"] = sig
    save_state(st)
    log("rotation: cycling %d pages (%s)"
        % (len(pages), ", ".join(p["page"] for p in pages)))


def release_rotation(cfg):
    """Stop the rotation queue and (default) restore whatever the
    device's message queue held before we borrowed it."""
    st = load_state()
    if not st.get("sig"):
        return
    loop_action(cfg, "stop")
    snap = st.get("snapshot") or {}
    msgs = snap.get("messages")
    try:
        url = base_url(cfg)
    except ValueError:
        url = None
    if url and truthy(cfg.get("npRestoreQueue", "1")) \
            and isinstance(msgs, list):
        code, _, err = http_json("POST", url + "/api/messages",
                                 {"messages": msgs,
                                  "runOnBoot": bool(snap.get("runOnBoot"))})
        if code != 200:
            log("rotation: queue restore failed (%s)" % (err or code))
        elif snap.get("queueActive"):
            loop_action(cfg, "start")
    elif url:
        # Not restoring — still clear our <RPx> entries out of the
        # device's saved queue so they don't come back on boot.
        http_json("POST", url + "/api/messages",
                  {"messages": [],
                   "runOnBoot": bool(snap.get("runOnBoot"))})
    save_state({})
    log("rotation: released")


def blank(cfg, page):
    if not send_command(cfg, "<P%s> " % page):
        return False
    return run_page(cfg, page)


def stop_action(cfg):
    """Apply the configured 'when the show stops' action."""
    action = (cfg.get("stopAction") or "keep").strip()
    page = page_letter(cfg.get("stopPage"), PAGES_MSG)
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
        return loop_action(cfg, "start")
    return True  # "keep" — leave the sign as-is


# ---------------------------------------------------------------- events


def handle_media(cfg, data):
    """fppd media event -> render every configured page, then keep the
    sign cycling them via the device queue (multi-page) or just run the
    one page."""
    if not truthy(cfg.get("npEnabled")):
        return 0
    etype = str(data.get("type") or "").lower()
    if etype in ("", "pause", "event"):
        return 0
    pages = np_pages(cfg)
    fields = np_field_map(cfg, data)

    if len(pages) == 1:
        p = pages[0]
        text = render_template(p["text"], fields)
        if p.get("legacy") and not text.strip():
            text = fields["filename"]
        # A stale rotation signature means a previous multi-page setup
        # still owns the queue — hand it back first.
        if load_state().get("sig"):
            release_rotation(cfg)
        write_and_run(cfg, p["page"], text, p["color"], p["font"],
                      p["size"], p["function"])
        return 0

    for p in pages:
        text = render_template(p["text"], fields)
        # Function-only pages (clock/date) need no text at all; a blank
        # template on a plain page just holds its slot in the rotation.
        send_command(cfg, page_write(p["page"], text, p["color"],
                                     p["font"], p["size"],
                                     p["function"]))
    ensure_rotation(cfg, pages)
    return 0


def handle_playlist(cfg, data):
    """Playlist stop -> release the rotation, then the configured stop
    action (time/blank/...)."""
    if str(data.get("Action") or "").lower() != "stop":
        return 0
    release_rotation(cfg)
    stop_action(cfg)
    return 0


def handle_lifecycle(cfg, phase):
    if phase == "shutdown":
        release_rotation(cfg)
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
    """One-shot: blank Y, message on Z, run Z xN then back to Y."""
    page_y = page_write("Y", " ", function=function)
    page_z = page_write("Z", text, color, font, size, function)
    repeat = max(1, min(99, int(repeat or 1)))
    if beep:
        if not send_command(cfg, "<PX><FO> "):
            return False
    if not send_command(cfg, page_y):
        return False
    if not send_command(cfg, page_z):
        return False
    return send_command(cfg, "<RPZ><%02d><RPY>" % repeat)


def beep(cfg, count):
    count = max(1, min(99, int(count or 1)))
    if not send_command(cfg, page_write("Y", " ")):
        return False
    if not send_command(cfg, "<PZ><FO> "):
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
    s.add_argument("--page", default="A")
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
    s.add_argument("--page", default="A")

    s = sub.add_parser("time", help="show the sign's clock")
    s.add_argument("--page", default="A")
    s = sub.add_parser("date", help="show the sign's date")
    s.add_argument("--page", default="A")

    s = sub.add_parser("queue", help="start/stop the device message queue")
    s.add_argument("direction", choices=["start", "stop"])

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
    s.add_argument("--page", default="A")
    s.add_argument("--end-page", default="A",
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
        page = page_letter(args.page, PAGES_MSG)
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
        page = page_letter(args.page, PAGES_MSG)
        return 0 if blank(cfg, page) else 1

    if args.action == "time":
        page = page_letter(args.page, PAGES_MSG)
        ok = send_command(cfg, "<P%s><FT>" % page) and run_page(cfg, page)
        return 0 if ok else 1

    if args.action == "date":
        page = page_letter(args.page, PAGES_MSG)
        ok = send_command(cfg, "<P%s><FD>" % page) and run_page(cfg, page)
        return 0 if ok else 1

    if args.action == "queue":
        return 0 if loop_action(cfg, args.direction) else 1

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
