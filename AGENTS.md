# fpp-plugin-FauxLite

FPP plugin: shows now-playing info and custom messages on a Pro-Lite
ASCII LED sign via a FauxLite ESP32 WiFi-to-serial bridge. Stdlib-only
Python + PHP — zero deps (FPP images ship python3 and php-curl).

## Layout

- `callbacks.py` — fppd entry point, keep it FAST (fppd waitpid()s on it);
  parses args, gates on settings, spawns `lib/fauxlite.py` DETACHED and
  exits. Never does network I/O itself.
- `lib/fauxlite.py` — worker: Pro-Lite command builder + bounded-HTTP
  client + CLI (`media`/`playlist`/`lifecycle` handlers plus
  `send/raw/run/blank/time/date/queue/oneshot/beep/countdown/info/
  stopaction`).
- `lib/fauxlite.php` — same command spelling for the PHP side (page
  writes, host validation, HTTP). Keep in sync with the .py.
- `api.php` — plugin API under `/api/plugin/fpp-plugin-FauxLite/*`
  (info/send/raw/runpage/blank/time/date/oneshot/beep/queue/test).
- `settings.json` — declarative fields (PrintSettingGroup, instant save).
  Keys: `enabled`, `host`, `npEnabled`, `npRotationPage`,
  `showName`/`showTagline`/`showHost`/`showLocation`/`showSchedule`/
  `showUrl` (the `{show*}` placeholders), `stopAction` (keep|blank|
  time|date|custom|queue), `stopPage`, `stopText`, `stopColor`,
  `stopFunction`. `npPages` = base64 JSON array of
  `{page,text,function,color,font,size,duration,enabled}` written by the
  content.php page editor (not a declared field — survives as a plain
  key=value line). Legacy `npPage`/`npFormat`/`npFunction`/`npColor`/
  `npFont`/`npSize` are still honored when `npPages` is empty.
- `commands/descriptions.json` + `commands/*.sh` — thin wrappers that
  exec `lib/fauxlite.py`; arg order in the .sh must match `args[]`.
- `content.php` (output menu), `status.php` (status menu), `about.php`
  (help) + `menu.inc`.
- `scripts/{fpp_install,fpp_uninstall}.sh` — chmod + config/plugindata
  cleanup + `setSetting restartFlag 1` (required while versions[] covers
  pre-10 FPP, which can't hot-load/unload; droppable on an FPP10-only
  branch).
- `pluginInfo.json` — strict JSON; `repoName` = repo dir name.

## FPP callback contract (verified in fpp src/Plugins.cpp)

- fppd probes `callbacks{,.sh,.pl,.php,.py}` — `callbacks.py` is used.
- `callbacks.py --list` → `media,playlist,lifecycle` (10s answer timeout).
- `--type media --data '<json>'` — blocking on fppd's main loop inside
  PreparePlay → the callback spawns the worker detached and exits.
  Media JSON: `{type: both|media|sequence|pause|video|event, Sequence,
  Media, title?, artist?, album?, year?, genre?, track?, length?,
  seconds?, minutes?, ...}` — tags are absent when missing.
- `--type playlist --data '<json>'` — `Playlist::GetInfo()` +
  `{Action: start|playing|query_next|stop, Section, Item}`; we act on
  `Action == "stop"` only (stop_action).
- `--type lifecycle startup|shutdown` — bare phase arg, max ~5s wait; we
  run stop_action on shutdown, nothing on startup.
- Gate: `enabled` + `host` must both be set (fresh install is inert);
  media also requires `npEnabled`.

## FauxLite / Pro-Lite protocol

Device: `POST http://<host>/api/send {"command": "<PA><CH>Hello "}` —
firmware prepends `<ID<signID>>` and appends CR/LF; commands here are
bare Pro-Lite strings (NO ID prefix). `GET /api/info` →
`{device:"faux-lite", version, chip_id, sign_id, baud_rate, ip, mac}`;
`GET/POST /api/messages` → on-device queue `{messages:[{command,
duration}], runOnBoot, queueActive, queueSize}`;
`POST /api/loop/start|stop` → queue control (start 400s if empty).

Pro-Lite spelling:
- `<P?>` write page, `<RP?>` run page, `<RP?><NN><RP?>` run N times then
  switch, `<DP?>`/`<DP*>` delete, `<D*>` delete all, `<RST>` reset.
- **`<RPx>` is a standalone command — never append it to a page write.**
  Everything after `<Px>` is page *text*; `<PA>text <RPA>` shows literal
  `<RPA>` on the sign. Write the page (`<Px>...text `), then send
  `<RPx>` as its own `/api/send`. `run_page()`/`write_and_run()` exist
  for exactly this; oneshot/beep's `<RPZ><NN><RPY>` is already a
  standalone command string.
- Colors `CA`–`CZ`, fonts `SA`–`SH`, sizes `SI`(5x7)/`SJ`(4x7),
  effects `FA`–`FW`,`FZ`,`F1`–`F6`; `FT`=clock, `FD`=date.
- Countdown: `<VddddhhmmP>` programs the timer (whole minutes — we round
  UP so zero lands late, not early) and the page to switch to at zero.
  Page text can embed live fields: `F3`–`F6` = days/hours/min/sec left,
  `F1` target, `F2` current — inject AFTER sanitize() so the `<Fx>`
  codes survive (page_write escape=False does exactly that).
- Pages **A and B are firmware-owned** (queue run page / queue chain
  page); **Y and Z reserved** for one-shot/test/boot. Plugin pages are
  C–X (`PAGES_MSG`; `page_letter`/`fl_page` default to C).
- Multi-page rotation = ONE sign page (`npRotationPage`, default C)
  holding every row as an `<FP>`-separated segment — exactly what the
  firmware's buildQueuePageCommand compiles its queues into. Each
  segment displays then each `<FP>` holds ~2s → row "secs" becomes
  (secs+1)//2 pause tags; the page loops back to the first segment.
  Rebuilt + `<RPx>` on every media event; the device queue is never
  touched (new firmware POST /api/messages REPLACES all
  queues+schedules+bootQueue — a partial payload wipes them).
- Blank needs an all-black graphic block: a visibly-empty page falls
  back to the sign's HELLO demo. We define block Z ourselves
  (`<GZ>`+126 B's, `ensure_black_graphic`) then show `<Px><FQ><BZ> `.
- Device queues (new firmware): GET /api/messages →
  `{queues:[{name,runTimes,nextQueue,messages:[{command,duration}]}],
  schedules,bootQueue,activeQueue,runPage,chainPage,timeSynced}`;
  `POST /api/loop/start?queue=N` (index required, 400 on empty);
  `/api/loop/stop`. `start_device_queue()` picks bootQueue else first
  non-empty. Firmware writes the whole queue to page A and chains to B
  via `<RPA><nn><RPB>` itself.
- /api/send now also saves `lastDisplay` in prefs (replayed on boot)
  and clears activeQueue bookkeeping on <P/<R/<D commands.
- New firmware endpoints not yet exposed by the plugin:
  `/api/graphics` GET/POST (user graphic blocks `<Gx>data`/`<DGx>`),
  `/api/wipe-sign` (`<D*>` + re-upload graphics — emergency only).
- `<FZ>` "Link Page" is listed in the Tru-Color II doc's function
  table but its operand syntax is undocumented — do NOT emit it
  without hardware verification.
- Text is sanitized to ASCII with `<>`/control chars stripped — song
  metadata must not inject protocol codes.

## Ops notes

- Config lives in `config/plugin.fpp-plugin-FauxLite` (key=value,
  written by SetPluginSetting/WriteSettingToFile). No daemon, no state
  files — the rotation is stateless (page rewritten per media event).
- Single plugin log `logs/plugin-fpp-plugin-FauxLite.log` (FPP rotates).
- HTTP timeouts: 4s total, always bounded; failures log + return, never
  stall fppd.
- No secrets, no auth — host is the only sensitive-ish value and it's
  in the plain plugin config intentionally.

## Dev/testing

```bash
python -m py_compile lib/fauxlite.py callbacks.py
python lib/fauxlite.py info            # probe a real device (set config first)
bash -n commands/*.sh scripts/*.sh
php -l api.php content.php status.php about.php lib/fauxlite.php
python -c "import json; [json.load(open(f)) for f in
    ('pluginInfo.json','settings.json','commands/descriptions.json')]"

# Simulate a media callback (needs config/plugin.fpp-plugin-FauxLite
# with enabled=1 + host set):
python lib/fauxlite.py media '{"type":"both","Sequence":"song.fseq",
  "Media":"song.mp3","title":"Carol","artist":"Choir"}'
python lib/fauxlite.py playlist '{"Action":"stop"}'
```
