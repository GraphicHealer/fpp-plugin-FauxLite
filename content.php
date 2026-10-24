<?php
/*
 * FauxLite configuration page (Input/Output Setup menu).
 *
 * Fields are declared in settings.json and rendered/saved by FPP's own
 * machinery: PrintSettingGroup draws the native rows and saves each field
 * instantly into config/plugin.fpp-plugin-FauxLite. There is no form and
 * no save loop. The connection test below posts back to this page and
 * probes the device's /api/info endpoint.
 */

$pluginName = 'fpp-plugin-FauxLite';
require_once dirname(__FILE__) . '/lib/fauxlite.php';

// Save the Now Playing page list. The UI posts a JSON array of
// {page,text,function,color,font,size,duration,enabled} rows which we
// sanitize, then base64 into the plugin config as npPages — base64
// keeps embedded quotes/newlines safe for the key=value file and for
// FPP's backup mechanism. The Python worker decodes it the same way.
$pagesSaved = null;
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['fl_pages'])) {
    $arr = json_decode(isset($_POST['fl_pages_json'])
                       ? $_POST['fl_pages_json'] : '', true);
    $clean = array();
    if (is_array($arr)) {
        foreach (array_slice($arr, 0, 24) as $p) {
            if (!is_array($p)) continue;
            $dur = isset($p['duration']) ? intval($p['duration']) : 8;
            $clean[] = array(
                'page' => fl_page(isset($p['page']) ? $p['page'] : 'A'),
                'text' => substr((string)(isset($p['text']) ? $p['text'] : ''),
                                 0, 200),
                'function' => substr((string)(isset($p['function'])
                                     ? $p['function'] : ''), 0, 2),
                'color' => substr((string)(isset($p['color'])
                                  ? $p['color'] : ''), 0, 2),
                'font' => substr((string)(isset($p['font'])
                                 ? $p['font'] : ''), 0, 2),
                'size' => substr((string)(isset($p['size'])
                                 ? $p['size'] : ''), 0, 2),
                'duration' => max(1, min(300, $dur)),
                'enabled' => !empty($p['enabled']) ? 1 : 0,
            );
        }
    }
    if (function_exists('WriteSettingToFile')) {
        WriteSettingToFile('npPages',
            base64_encode(json_encode($clean)), $pluginName);
        $pagesSaved = true;
    } else {
        $pagesSaved = false;
    }
    // Re-read below so the editor reflects what was actually stored.
}

$npPagesJson = '[]';
$cfgAll = fl_cfg();
if (isset($cfgAll['npPages']) && $cfgAll['npPages'] !== '') {
    $dec = json_decode(base64_decode($cfgAll['npPages']), true);
    if (is_array($dec)) $npPagesJson = json_encode($dec);
}

$testInfo = null;
$testError = null;
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['fl_test'])) {
    $cfg = fl_cfg();
    $host = isset($cfg['host']) ? rtrim(trim($cfg['host']), '/') : '';
    if ($host === '' || !fl_host_valid($host)) {
        $testError = 'Set a valid device address above first.';
    } else {
        list($code, $body, $err) = fl_http('GET', 'http://' . $host . '/api/info');
        if ($code === 200) {
            $testInfo = json_decode($body, true);
            if (!is_array($testInfo)
                || (isset($testInfo['device']) ? $testInfo['device'] : '') !== 'faux-lite') {
                $testInfo = null;
                $testError = 'Something answered, but it does not identify as a FauxLite device.';
            }
        } else {
            $testError = $err !== '' ? $err : 'HTTP ' . $code;
        }
    }
}
?>

<h2>FauxLite</h2>
<p>
Shows FPP playback info and custom messages on a Pro-Lite LED sign via a
FauxLite WiFi-to-serial bridge. Set the device address, enable the plugin,
then optionally turn on now-playing updates. Fields save as you change
them — changes take effect on the next media/playlist event. All traffic
is plain HTTP on your LAN.
</p>

<div id="global" class="settings">
<?php
if (function_exists('LoadPluginSettings')) LoadPluginSettings($pluginName);
PrintSettingGroup('FauxLiteDevice', '', '', 1, $pluginName);
PrintSettingGroup('FauxLiteNowPlaying', '', '', 1, $pluginName);
?>
</div>

<fieldset>
<legend>Now Playing Pages</legend>
<p class="text-muted">
Each row is one entry in the rotation. With one row the sign just shows
that page; with two or more, the device's own message queue cycles the
rendered messages — each displayed for its <b>Secs</b> — which is how the
device natively rotates content (the queue writes each entry to page A
when it fires, just like entries added on the device's Messages page).
The <b>Page</b> column picks which sign page the content is also stored
on — useful for Run Page commands and one-shot restores. Mid-song tag
changes refresh the next queue update. Leave the list empty for the
simple default ("{title}" on page A). Text placeholders:
<b>{title} {artist} {album} {sequence} {filename} {type} {year} {genre}
{track} {length} {seconds} {minutes} {bitrate}</b>, plus the Show Info
fields <b>{showName} {showTagline} {showHost} {showLocation}
{showSchedule} {showUrl}</b> and <b>{hostname} {hostdesc}</b> from FPP
itself. Example rotation: <i>{showName}</i> &rarr; <i>Now Playing:</i>
&rarr; <i>{artist}</i> &rarr; <i>{title}</i>. Pages Y/Z stay reserved
for one-shot messages.
</p>
<table class="table table-striped" id="flPagesTable" style="max-width: 72rem;">
<thead><tr>
<th style="width:4rem;">Page</th><th>Text / template</th>
<th>Effect</th><th>Color</th><th>Font</th><th>Size</th>
<th style="width:5rem;">Secs</th><th>On</th><th style="width:7rem;"></th>
</tr></thead>
<tbody id="flPagesBody"></tbody>
</table>
<button type="button" class="buttons" onclick="flAddPage()">Add Page</button>
<button type="button" class="buttons" onclick="flSavePages()">Save Pages</button>
<span id="flPagesMsg" class="text-muted" style="margin-left:0.5rem;"></span>
<form method="post" action="" id="flPagesForm" style="display:none;">
<input type="hidden" name="fl_pages" value="1">
<input type="hidden" name="fl_pages_json" id="flPagesJson" value="">
</form>
<?php if ($pagesSaved === true): ?>
<p class="text-success" style="margin-top:0.5rem;">Page list saved.</p>
<?php elseif ($pagesSaved === false): ?>
<p class="text-danger" style="margin-top:0.5rem;">Save failed — WriteSettingToFile unavailable.</p>
<?php endif; ?>
</fieldset>

<script>
var FL_PAGES = <?php echo $npPagesJson; ?>;
var FL_PAGES_SAVED = <?php echo $npPagesJson !== '[]' ? 'true' : 'false'; ?>;
var FL_EFFECTS = {'':'device default','FA':'Auto','FB':'Open','FC':'Cover',
  'FD':'Date','FE':'Cycling','FF':'Close right','FG':'Close left',
  'FH':'Close both','FI':'Scroll up','FJ':'Scroll down','FK':'Overlap',
  'FL':'Stacking','FM':'Comic 1','FN':'Comic 2','FP':'Pause','FQ':'Appear',
  'FR':'Random','FS':'Shift left','FT':'Time','FU':'Magic',
  'FV':'Thank you','FW':'Welcome'};
var FL_COLORS = {'':'device default','CA':'Dim red','CB':'Red',
  'CC':'Bright red','CD':'Orange','CE':'Bright orange',
  'CF':'Light yellow','CG':'Yellow','CH':'Bright yellow','CI':'Lime',
  'CJ':'Dim lime','CK':'Bright lime','CL':'Bright green','CM':'Green',
  'CN':'Dim green','CO':'Yel/grn/red','CP':'Rainbow','CQ':'Red/grn 3D',
  'CR':'Red/yel 3D','CS':'Grn/red 3D','CT':'Grn/yel 3D',
  'CU':'Grn on red','CV':'Red on grn','CW':'Org on grn 3D',
  'CX':'Lime on red 3D','CY':'Grn on red 3D','CZ':'Red on grn 3D'};
var FL_FONTS = {'':'device default','SA':'Normal','SB':'Bold',
  'SC':'Italic','SD':'Bold italic','SE':'Flash normal','SF':'Flash bold',
  'SG':'Flash italic','SH':'Flash bold italic'};
var FL_SIZES = {'':'device default','SI':'5x7','SJ':'4x7 (smaller)'};
var FL_LETTERS = 'ABCDEFGHIJKLMNOPQRSTUVWX'.split('');

function flSelect(opts, val, cls) {
    var h = '<select' + (cls ? ' class="' + cls + '"' : '') + '>';
    for (var k in opts)
        h += '<option value="' + k + '"' + (k === val ? ' selected' : '')
             + '>' + opts[k] + '</option>';
    return h + '</select>';
}
function flEsc(s) {
    return String(s == null ? '' : s)
        .replace(/&/g, '&amp;').replace(/</g, '&lt;')
        .replace(/"/g, '&quot;').replace(/>/g, '&gt;');
}
function flRenderPages() {
    var body = document.getElementById('flPagesBody');
    var h = '';
    for (var i = 0; i < FL_PAGES.length; i++) {
        var p = FL_PAGES[i];
        h += '<tr>'
          + '<td>' + flSelect(FL_LETTERS.reduce(function(o,l){o[l]=l;return o;},{}),
                              p.page || 'A', 'fl-page') + '</td>'
          + '<td><input class="fl-text" type="text" size="28" maxlength="200" '
          + 'value="' + flEsc(p.text) + '" placeholder="{artist} - {title}"></td>'
          + '<td>' + flSelect(FL_EFFECTS, p.function || '', 'fl-function') + '</td>'
          + '<td>' + flSelect(FL_COLORS, p.color || '', 'fl-color') + '</td>'
          + '<td>' + flSelect(FL_FONTS, p.font || '', 'fl-font') + '</td>'
          + '<td>' + flSelect(FL_SIZES, p.size || '', 'fl-size') + '</td>'
          + '<td><input class="fl-duration" type="number" min="1" max="300" '
          + 'value="' + (p.duration || 8) + '" style="width:4rem;"></td>'
          + '<td><input class="fl-enabled" type="checkbox"'
          + (p.enabled ? ' checked' : '') + '></td>'
          + '<td>'
          + '<button type="button" onclick="flMovePage(' + i + ',-1)" title="Move up">&#8593;</button>'
          + '<button type="button" onclick="flMovePage(' + i + ',1)" title="Move down">&#8595;</button>'
          + '<button type="button" onclick="flDelPage(' + i + ')" title="Delete">&#10005;</button>'
          + '</td></tr>';
    }
    body.innerHTML = h;
}
function flPullRows() {
    var rows = document.querySelectorAll('#flPagesBody tr');
    for (var i = 0; i < rows.length; i++) {
        var q = function(sel) { return rows[i].querySelector(sel).value; };
        FL_PAGES[i] = {
            page: q('.fl-page'),
            text: q('.fl-text'),
            function: q('.fl-function'),
            color: q('.fl-color'),
            font: q('.fl-font'),
            size: q('.fl-size'),
            duration: Math.max(1, Math.min(300,
                parseInt(q('.fl-duration'), 10) || 8)),
            enabled: rows[i].querySelector('.fl-enabled').checked ? 1 : 0
        };
    }
}
function flAddPage() {
    flPullRows();
    var used = {};
    FL_PAGES.forEach(function(p) { used[p.page] = 1; });
    var letter = 'A';
    for (var i = 0; i < FL_LETTERS.length; i++)
        if (!used[FL_LETTERS[i]]) { letter = FL_LETTERS[i]; break; }
    FL_PAGES.push({page: letter, text: '', function: 'FA', color: '',
                   font: '', size: '', duration: 8, enabled: 1});
    flRenderPages();
}
function flDelPage(i) { flPullRows(); FL_PAGES.splice(i, 1); flRenderPages(); }
function flMovePage(i, d) {
    flPullRows();
    var j = i + d;
    if (j < 0 || j >= FL_PAGES.length) return;
    var t = FL_PAGES[i]; FL_PAGES[i] = FL_PAGES[j]; FL_PAGES[j] = t;
    flRenderPages();
}
function flSavePages() {
    flPullRows();
    document.getElementById('flPagesJson').value = JSON.stringify(FL_PAGES);
    document.getElementById('flPagesForm').submit();
}
// Seed one sensible default row so the editor isn't empty on first use
// (it only persists once Save Pages is clicked).
if (!FL_PAGES_SAVED && FL_PAGES.length === 0)
    FL_PAGES = [{page: 'A', text: '{artist} - {title}', function: 'FA',
                 color: '', font: '', size: '', duration: 8, enabled: 1}];
flRenderPages();
</script>

<div id="global2" class="settings">
<?php
PrintSettingGroup('FauxLiteShowInfo', '', '', 1, $pluginName);
PrintSettingGroup('FauxLiteShowStopped', '', '', 1, $pluginName);
?>
</div>

<fieldset>
<legend>Connection test</legend>
<p class="text-muted">Probes the saved device address (GET /api/info).</p>
<form method="post" action="">
<button type="submit" name="fl_test" value="1" class="buttons">Test Connection</button>
</form>
<?php if ($testInfo !== null): ?>
<table class="table table-striped" style="max-width: 40rem; margin-top: 0.5rem;">
<tr><td><b>Device</b></td><td><span class="text-success">&#10003; reachable</span>
    <small class="text-muted">(<?php echo htmlspecialchars($testInfo['device']); ?>)</small></td></tr>
<tr><td><b>Chip ID</b></td><td><?php echo htmlspecialchars(isset($testInfo['chip_id']) ? $testInfo['chip_id'] : ''); ?></td></tr>
<tr><td><b>Sign ID</b></td><td><?php echo htmlspecialchars(isset($testInfo['sign_id']) ? $testInfo['sign_id'] : ''); ?></td></tr>
<tr><td><b>Baud rate</b></td><td><?php echo htmlspecialchars(isset($testInfo['baud_rate']) ? $testInfo['baud_rate'] : ''); ?></td></tr>
<tr><td><b>IP / MAC</b></td><td><?php
    echo htmlspecialchars(isset($testInfo['ip']) ? $testInfo['ip'] : '');
    if (isset($testInfo['mac'])) echo ' / ' . htmlspecialchars($testInfo['mac']);
?></td></tr>
</table>
<?php elseif ($testError !== null): ?>
<p style="margin-top:0.5rem;"><span class="text-danger">&#10007; not reachable</span>
<small class="text-muted"><?php echo htmlspecialchars($testError); ?></small></p>
<?php endif; ?>
</fieldset>

<p class="text-muted">
Commands for playlists and scheduler triggers are under
<b>Commands</b> &rarr; look for the <i>FauxLite -</i> entries.
See Status &rarr; FauxLite Status for live device state, and
FauxLite - Help for the Pro-Lite command reference.
</p>
