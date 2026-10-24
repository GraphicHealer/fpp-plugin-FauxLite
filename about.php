<h2>FauxLite — Help</h2>

<p>
Drives a Pro-Lite ASCII-Series LED sign through a
<b>FauxLite</b> ESP32 WiFi-to-serial bridge. The bridge exposes a small
HTTP API on your LAN (<code>/api/send</code>, <code>/api/info</code>,
<code>/api/messages</code>, <code>/api/loop/*</code>) and wraps every
command in <code>&lt;IDxx&gt;</code> before sending it to the sign — so
commands sent by this plugin are the bare Pro-Lite strings.
</p>

<h4>What it does</h4>
<ul>
<li><b>Now playing</b> — when enabled, each playlist media entry writes its
title/artist/etc. to a sign page and shows it. The format string supports
<code>{title}</code>, <code>{artist}</code>, <code>{album}</code>,
<code>{sequence}</code>, <code>{media}</code>, <code>{filename}</code>,
<code>{type}</code>.</li>
<li><b>When the show stops</b> — blank the sign, show the sign's clock or
date, show a custom message, or resume the device's own message queue.</li>
<li><b>FPP commands</b> — use the <i>FauxLite -</i> commands from playlist
entries, scheduler presets, GPIO scripts or the command UI: send a message,
one-shot message, run page, blank, show time/date, beep, queue start/stop,
or send a raw Pro-Lite command.</li>
</ul>

<h4>Configuration</h4>
<p>
Input/Output Setup &rarr; FauxLite. You need only the device address (IP
or <code>faux-lite-XXXXXX.local</code>) — the FauxLite API has no auth.
Test Connection probes <code>/api/info</code> on the saved address.
</p>

<h4>Pages</h4>
<p>
Pages A&ndash;X are free for your use. Pages Y and Z are reserved: the
one-shot message and beep commands use them to flash temporary content and
then restore what was showing.
</p>

<h4>Pro-Lite cheat sheet</h4>
<ul>
<li><code>&lt;PA&gt;text </code> write page A &middot;
<code>&lt;RPA&gt;</code> run page A &middot;
<code>&lt;DPA&gt;</code> / <code>&lt;DP*&gt;</code> delete page/all</li>
<li>Colors <code>&lt;CA&gt;</code>&ndash;<code>&lt;CZ&gt;</code>,
fonts <code>&lt;SA&gt;</code>&ndash;<code>&lt;SH&gt;</code>,
sizes <code>&lt;SI&gt;</code>/<code>&lt;SJ&gt;</code>,
effects <code>&lt;FA&gt;</code>&ndash;<code>&lt;FW&gt;</code></li>
<li>A trailing space in a page keeps the sign out of its demo mode —
the plugin appends one automatically.</li>
</ul>

<h4>Troubleshooting</h4>
<ul>
<li>Status &rarr; FauxLite Status shows reachability, device info and the
device's message queue.</li>
<li>Log file: <code>File Manager &rarr; Logs &rarr; plugin-fpp-plugin-FauxLite.log</code></li>
<li>Nothing sent? Check <b>Enabled</b> and the device address — a fresh
install deliberately sends nothing.</li>
<li>One-shot messages/beep overwrite pages Y and Z — don't use those for
your own content.</li>
</ul>
