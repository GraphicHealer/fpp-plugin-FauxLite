# fpp-plugin-FauxLite

An FPP (Falcon Player) plugin that drives a **Pro-Lite ASCII-Series LED
sign** through a **FauxLite** ESP32 WiFi-to-serial bridge.

Put your show's *now playing* info on the sign while songs play, show the
time/date or a custom message when the show stops, and trigger sign
messages from playlist entries, scheduler presets, GPIO inputs or the FPP
command UI.

## How it works

The FauxLite bridge exposes a small HTTP API on your LAN
(`POST /api/send`, `GET /api/info`, `GET/POST /api/messages`,
`POST /api/loop/start|stop`). Every Pro-Lite command posted to it is
wrapped in `<IDxx>` and sent to the sign over serial — this plugin builds
the Pro-Lite strings and posts them over plain HTTP. No daemon, no
dependencies beyond Python 3 (bundled with FPP).

FPP's media/playlist callbacks fire the plugin's `callbacks.py`, which
hands the event to a detached worker (`lib/fauxlite.py`) and returns
immediately, so a powered-off or unreachable sign can never stall FPP.

## Install

In FPP, go to **Content Setup → Plugin Manager → Install a new plugin**
and use this repo's URL, or copy the folder into FPP's plugin directory.

## Configure

**Input/Output Setup → FauxLite**

1. **Device Address** — IP or mDNS name of the bridge, e.g.
   `192.168.1.120` or `faux-lite-AB12CD.local`.
2. **Enabled** — master switch; nothing is sent until this is on.
3. Optionally enable **Show Now Playing** and tune the page, format
   (`{title}`, `{artist}`, `{album}`, `{sequence}`, `{media}`,
   `{filename}`, `{type}`), effect, color, font and size.
4. Optionally pick a **when the show stops** action — leave as-is, blank,
   show time, show date, custom message, or resume the device's own
   message queue.

**Test Connection** on the same page probes the device's `/api/info`.
**Status → FauxLite Status** shows live device state, the on-device
message queue, and quick-send controls.

## FPP commands

Available anywhere FPP commands can run (playlist entries, scheduler,
GPIO scripts, command editor):

| Command | What it does |
| --- | --- |
| FauxLite - Send Message | write text to a page, show it now or just store it |
| FauxLite - One-Shot Message | flash a temporary message, then restore the display (pages Y/Z) |
| FauxLite - Run Page | switch the display to page A–Z |
| FauxLite - Blank Display | show an empty page |
| FauxLite - Show Time / Date | show the sign's built-in clock/date |
| FauxLite - Beep | beep the sign's speaker |
| FauxLite - Start / Stop Message Queue | control the device's own message loop |
| FauxLite - Send Raw Command | send any bare Pro-Lite protocol string |

Pages **A–X** are yours. **Y and Z are reserved** for one-shot messages
and beep — don't keep content there.

## Notes

- The sign has no auth — keep it on a trusted LAN.
- A trailing space is appended to every message to keep the sign out of
  demo mode.
- Non-ASCII characters and `<`/`>` are stripped from message text so
  metadata can't inject protocol commands.
- Logs: **File Manager → Logs → `plugin-fpp-plugin-FauxLite.log`**.

## Related projects

- [Faux-Lite-Firmware](https://github.com/GraphicHealer/Faux-Lite-Firmware)
  — the ESP32 bridge firmware this plugin talks to
- [Faux-Lite-Addon](https://github.com/GraphicHealer/Faux-Lite-Addon) —
  Home Assistant integration for the same device
