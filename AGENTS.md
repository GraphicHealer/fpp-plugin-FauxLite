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
  Keys: `enabled`, `host`, `npEnabled`, `npPage`, `npFormat`,
  `npFunction`, `npColor`, `npFont`, `npSize`, `stopAction` (keep|blank|
  time|date|custom|queue), `stopPage`, `stopText`, `stopColor`,
  `stopFunction`.
- `commands/descriptions.json` + `commands/*.sh` — thin wrappers that
  exec `lib/fauxlite.py`; arg order in the .sh must match `args[]`.
- `content.php` (output menu), `status.php` (status menu), `about.php`
  (help) + `menu.inc`.
- `scripts/{fpp_install,fpp_uninstall}.sh` — chmod + mkdir only; **no
  restartFlag** (callbacks script → live reload per §2.8), uninstall
  removes only `config/plugin.<name>`.
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
- Colors `CA`–`CZ`, fonts `SA`–`SH`, sizes `SI`(5x7)/`SJ`(4x7),
  effects `FA`–`FW`,`FZ`,`F1`–`F6`; `FT`=clock, `FD`=date.
- Countdown: `<VddddhhmmP>` programs the timer (whole minutes — we round
  UP so zero lands late, not early) and the page to switch to at zero.
  Page text can embed live fields: `F3`–`F6` = days/hours/min/sec left,
  `F1` target, `F2` current — inject AFTER sanitize() so the `<Fx>`
  codes survive (page_write escape=False does exactly that).
- Pages A–X free; **Y and Z reserved** for one-shot/beep (blank Y +
  message Z + `<RPZ><NN><RPY>` restores what was showing).
- Trailing space after text keeps the sign out of demo mode.
- Text is sanitized to ASCII with `<>`/control chars stripped — song
  metadata must not inject protocol codes.

## Ops notes

- Config lives in `config/plugin.fpp-plugin-FauxLite` (key=value,
  written by SetPluginSetting). The plugin stores no state and needs no
  plugindata dir and no daemon — keep it that way.
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
