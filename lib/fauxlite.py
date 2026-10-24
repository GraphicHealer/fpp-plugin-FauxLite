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
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

PLUGIN = "fpp-plugin-FauxLite"
MEDIADIR = os.environ.get("MEDIADIR", "/home/fpp/media")
LOGDIR = os.environ.get("LOGDIR", os.path.join(MEDIADIR, "logs"))
SETTINGS_PATH = os.path.join(MEDIADIR, "config", "plugin." + PLUGIN)
LOG_FILE = os.path.join(LOGDIR, "plugin-%s.log" % PLUGIN)

HTTP_TIMEOUT = 4
HOST_RE = re.compile(r"^[A-Za-z0-9._-]+(:[0-9]{1,5})?$")
PAGES_ALL = [chr(c) for c in range(ord("A"), ord("Z") + 1)]
PAGES_MSG = PAGES_ALL[:24]  # A-X: Y and Z are reserved for one-shot messages

# Pro-Lite protocol code tables (Faux-Lite-Addon custom_components/
# fauxlite_display/const.py).
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


def page_write(page, text, color="", font="", size="", function=""):
    """Build '<P?><F?><C?><S?>text ' — the trailing space keeps a short
    message from tripping the sign's demo mode (same trick the HA
    integration uses)."""
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
    return cmd + sanitize(text) + " "


class _Fields(dict):
    def __missing__(self, key):
        return ""


def _basename(name):
    n = re.sub(r"\.[A-Za-z0-9]+$", "", os.path.basename(str(name or "")))
    return n


def now_playing_text(data, fmt):
    """Render the configured format against the media callback payload.
    Placeholders: {title} {artist} {album} {sequence} {media} {filename}
    {type} {year} {genre} {track} {length} {seconds} {minutes}."""
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
        length=data.get("length", ""),
        seconds=data.get("seconds", ""),
        minutes=data.get("minutes", ""),
    )
    try:
        out = fmt.format_map(fields)
    except (KeyError, IndexError, ValueError):
        out = fmt
    # Collapse " - " separators and bracket pairs whose sides came out
    # empty (e.g. "{artist} - {title} [{album}]" with no album/artist).
    out = re.sub(r"(\s*-\s*){2,}", " - ", out)
    out = re.sub(r"[\[\(]\s*[\]\)]", "", out).strip(" -")
    if not out.strip():
        out = fields["filename"]
    return out


def blank(cfg, page):
    return send_command(cfg, "<P%s> <RP%s>" % (page, page))


def stop_action(cfg):
    """Apply the configured 'when the show stops' action."""
    action = (cfg.get("stopAction") or "keep").strip()
    page = page_letter(cfg.get("stopPage"), PAGES_MSG)
    if action == "blank":
        return blank(cfg, page)
    if action == "time":
        return send_command(cfg, "<P%s><FT><RP%s>" % (page, page))
    if action == "date":
        return send_command(cfg, "<P%s><FD><RP%s>" % (page, page))
    if action == "custom":
        text = cfg.get("stopText") or ""
        if not text.strip():
            return True
        cmd = page_write(page, text, cfg.get("stopColor", ""),
                         function=cfg.get("stopFunction", ""))
        return send_command(cfg, cmd + "<RP%s>" % page)
    if action == "queue":
        return loop_action(cfg, "start")
    return True  # "keep" — leave the sign as-is


# ---------------------------------------------------------------- events


def handle_media(cfg, data):
    """fppd media event -> now-playing text on the configured page."""
    if not truthy(cfg.get("npEnabled")):
        return 0
    etype = str(data.get("type") or "").lower()
    if etype in ("", "pause", "event"):
        return 0
    text = now_playing_text(data, cfg.get("npFormat") or "{title}")
    if not text.strip():
        return 0
    page = page_letter(cfg.get("npPage"), PAGES_MSG)
    cmd = page_write(page, text, cfg.get("npColor", ""),
                     cfg.get("npFont", ""), cfg.get("npSize", ""),
                     cfg.get("npFunction", ""))
    send_command(cfg, cmd + "<RP%s>" % page)
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
    """HA-style one-shot: blank Y, message on Z, run Z xN then back to Y."""
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
        cmd = page_write(page, args.text, args.color, args.font,
                         args.size, args.function)
        if args.display_mode == "display":
            cmd += "<RP%s>" % page
        return 0 if send_command(cfg, cmd) else 1

    if args.action == "raw":
        return 0 if send_command(cfg, args.command) else 1

    if args.action == "run":
        page = page_letter(args.page, PAGES_ALL)
        return 0 if send_command(cfg, "<RP%s>" % page) else 1

    if args.action == "blank":
        page = page_letter(args.page, PAGES_MSG)
        return 0 if blank(cfg, page) else 1

    if args.action == "time":
        page = page_letter(args.page, PAGES_MSG)
        return 0 if send_command(cfg, "<P%s><FT><RP%s>" % (page, page)) else 1

    if args.action == "date":
        page = page_letter(args.page, PAGES_MSG)
        return 0 if send_command(cfg, "<P%s><FD><RP%s>" % (page, page)) else 1

    if args.action == "queue":
        return 0 if loop_action(cfg, args.direction) else 1

    if args.action == "oneshot":
        ok = oneshot(cfg, args.text, args.repeat, args.color, args.font,
                     args.size, args.function, args.beep)
        return 0 if ok else 1

    if args.action == "beep":
        return 0 if beep(cfg, args.count) else 1

    if args.action == "stopaction":
        return 0 if stop_action(cfg) else 1

    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
