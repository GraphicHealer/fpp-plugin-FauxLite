#!/usr/bin/env python3
"""
FPPD callback entry point for fpp-plugin-FauxLite.

FPPD calls this via scripts/eventScript:

    callbacks.py --list                        -> comma list of callback types
    callbacks.py --type media     --data '<json>'
    callbacks.py --type playlist  --data '<json>'
    callbacks.py --type lifecycle startup|shutdown

These calls are synchronous from fppd's point of view (it waitpid()s on the
media callback inside PreparePlay), so this script must return fast. It does
no I/O beyond reading the plugin settings file: the actual HTTP POST to the
FauxLite device is handed to lib/fauxlite.py in a DETACHED child, and this
script exits without waiting for it. A detached child with a bounded HTTP
timeout can never stall fppd's main loop, even when the sign is offline.
Python 3 stdlib only.
"""

import os
import subprocess
import sys
import time

PLUGIN = "fpp-plugin-FauxLite"
MEDIADIR = os.environ.get("MEDIADIR", "/home/fpp/media")
LOGDIR = os.environ.get("LOGDIR", os.path.join(MEDIADIR, "logs"))
PLUGINDIR = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(PLUGINDIR, "lib", "fauxlite.py")
SETTINGS_PATH = os.path.join(MEDIADIR, "config", "plugin." + PLUGIN)
LOG_FILE = os.path.join(LOGDIR, "plugin-%s.log" % PLUGIN)
PY = "/usr/bin/python3" if os.path.exists("/usr/bin/python3") else sys.executable


def _read_kv(path):
    out = {}
    try:
        with open(path) as f:
            for line in f:
                k, _, v = line.partition("=")
                out[k.strip()] = v.strip().strip('"')
    except OSError:
        pass
    return out


def _truthy(v):
    return str(v or "").strip().lower() not in ("", "0", "false", "no", "off")


def log(msg):
    try:
        os.makedirs(LOGDIR, exist_ok=True)
        with open(LOG_FILE, "a") as f:
            f.write("%s callbacks: %s\n"
                    % (time.strftime("%Y-%m-%dT%H:%M:%S"), msg))
    except OSError:
        pass


def plugin_ready(cfg):
    """Enabled + device address set — a fresh install is inert."""
    return _truthy(cfg.get("enabled")) \
        and bool((cfg.get("host") or "").strip())


def spawn(args):
    """Run lib/fauxlite.py detached and return IMMEDIATELY — fppd is
    waitpid()ing on this script, so we never wait on the child (or on the
    network). Output goes to /dev/null; the worker logs through the plugin
    log itself."""
    try:
        subprocess.Popen(
            [PY, LIB] + args,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            start_new_session=True, cwd=PLUGINDIR,
        )
    except OSError as e:
        log("spawn failed: %s" % e)


def main(argv):
    args = argv[1:]
    if "--list" in args:
        print("media,playlist,lifecycle")
        return 0

    cb_type = None
    data_arg = None
    for i, a in enumerate(args):
        if a == "--type" and i + 1 < len(args):
            cb_type = args[i + 1]
        elif a == "--data" and i + 1 < len(args):
            data_arg = args[i + 1]

    cfg = _read_kv(SETTINGS_PATH)

    if cb_type == "media":
        if plugin_ready(cfg) and _truthy(cfg.get("npEnabled")):
            spawn(["media", data_arg or "{}"])
        return 0

    if cb_type == "playlist":
        if plugin_ready(cfg):
            spawn(["playlist", data_arg or "{}"])
        return 0

    if cb_type == "lifecycle":
        # lifecycle passes the phase as a bare arg: --type lifecycle startup
        name = data_arg or (args[-1] if args else "")
        if name == "shutdown" and plugin_ready(cfg):
            spawn(["lifecycle", "shutdown"])
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
