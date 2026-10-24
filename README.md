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
3. Optionally enable **Show Now Playing** and use the **Now Playing
   Pages** editor — see below.
4. Fill in **Show Info** if you want `{showName}`, `{showTagline}` and
   friends available in page text.
5. Optionally pick a **when the show stops** action — leave as-is, blank,
   show time, show date, custom message, or resume the device's own
   message queue.

**Test Connection** on the same page probes the device's `/api/info`.
**Status → FauxLite Status** shows live device state, the on-device
message queue, and quick-send controls.

## Now Playing pages

The page editor builds the sign's rotation: each row is one page with its
own text, effect, color, font, size and on-screen **seconds**. One row =
a single static page; two or more rows rotate seamlessly, driven by the
device's own message queue — the plugin loads `<RPx>` entries into the
queue and starts the loop, so the sign cycles on its own and mid-song
metadata updates just rewrite the page contents underneath.

Example — `Jones Light Show` → `Now Playing:` → artist → title:

| Page | Text | Secs |
| --- | --- | --- |
| A | `{showName}` | 8 |
| B | `Now Playing:` | 3 |
| C | `{artist}` | 6 |
| D | `{title}` | 6 |

Text placeholders: `{title}` `{artist}` `{album}` `{sequence}`
`{media}` `{filename}` `{type}` `{year}` `{genre}` `{track}` `{comment}`
`{length}` `{seconds}` `{minutes}` `{bitrate}` `{sampleRate}`
`{channels}` (TagLib fields from the media file), the Show Info fields
`{showName}` `{showTagline}` `{showHost}` `{showLocation}`
`{showSchedule}` `{showUrl}`, and `{hostname}` `{hostdesc}` from FPP.
A page whose text is just an **Effect** (e.g. Time or Date) shows that
function — no text needed.

The rotation borrows the device's message queue while the show runs.
**Restore Device Queue on Stop** (default on) puts back whatever was
queued before — the plugin snapshots it the first time it takes over.
With no pages configured at all, the plugin falls back to a single
`{title}` page (any pre-upgrade `npFormat`/`npPage`/etc. settings are
still honored).

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
| FauxLite - Countdown To Time | count down to a show start — programs the sign's countdown timer and writes a live `{hours}:{minutes}:{seconds}` page; at zero the sign switches to the end page |
| FauxLite - Beep | beep the sign's speaker |
| FauxLite - Start / Stop Message Queue | control the device's own message loop |
| FauxLite - Send Raw Command | send any bare Pro-Lite protocol string |

Pages **A–X** are yours. **Y and Z are reserved** for one-shot messages
and beep — don't keep content there.

## Countdowns

**FauxLite - Countdown To Time** takes the show's start time (and
optionally a date), computes the remaining duration, and sends it to the
sign's built-in countdown timer (`<VddddhhmmP>`). The countdown text is a
format string where `{days}`, `{hours}`, `{minutes}`, `{seconds}`,
`{target}` and `{current}` become live fields the sign renders itself —
e.g. `Show starts in {hours}:{minutes}:{seconds}` shows a ticking clock.
When the countdown reaches zero the sign switches to the **end page** —
fill that page beforehand (a "SHOWTIME!" message, for example) using
*Send Message* with "Just store it in the page".

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
