<?php
/*
 * FauxLite status page (Status/Control menu).
 * Probes the device live (bounded 4s) and offers quick-send actions
 * through the plugin API.
 */

$pluginName = 'fpp-plugin-FauxLite';
require_once dirname(__FILE__) . '/lib/fauxlite.php';

$cfg = fauxlite_cfg();
$enabled = fauxlite_cfg_enabled($cfg);
$host = isset($cfg['host']) ? rtrim(trim($cfg['host']), '/') : '';
$base = fauxlite_base($cfg);

$infoRows = '';   // filled in by the async probe below

function fauxlite_h($s) { return htmlspecialchars((string)$s); }
$api = '/api/plugin/' . $GLOBALS['fauxlite_plugin'];
?>

<h2>FauxLite Status</h2>

<table class="table table-striped" style="max-width: 50rem;">
<tr><td><b>Plugin</b></td>
    <td><?php echo $enabled ? '<span class="text-success">enabled</span>'
                            : '<span class="text-muted">disabled</span>'; ?>
        <small class="text-muted">(Input/Output Setup &rarr; FauxLite)</small></td></tr>
<tr><td><b>Device address</b></td><td><code><?php echo fauxlite_h($host !== '' ? $host : 'not set'); ?></code></td></tr>
<tbody id="flDevice">
<tr><td><b>Device</b></td><td id="flReach"><span class="text-muted"><?php
    echo $base === null ? 'no valid address configured' : 'probing…';
?></span></td></tr>
</tbody>
</table>

<script>
// The page renders first; the device probe comes back through the
// plugin API so an offline sign can't hold this page open (4-5s).
(function () {
    var api = <?php echo json_encode($api); ?>;
    function esc(s) {
        return String(s == null ? '' : s)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    }
    function row(k, v) {
        return '<tr><td><b>' + k + '</b></td><td>' + v + '</td></tr>';
    }
    fetch(api + '/info').then(function (r) { return r.json(); }).then(function (d) {
        var dev = document.getElementById('flDevice');
        var reach = document.getElementById('flReach');
        if (!d.host) { reach.innerHTML = '<span class="text-muted">no valid address configured</span>'; return; }
        if (!d.reachable) {
            reach.innerHTML = '<span class="text-danger">not reachable</span> <small class="text-muted">' + esc(d.error || '') + '</small>';
            return;
        }
        reach.innerHTML = '<span class="text-success">reachable</span>';
        var info = d.info || {};
        var html = '';
        html += row('Chip ID', esc(info.chip_id || ''));
        html += row('Sign ID / baud', esc(info.sign_id != null ? info.sign_id : '') + ' @ ' + esc(info.baud_rate || ''));
        html += row('IP / MAC', esc(info.ip || '') + (info.mac ? ' / ' + esc(info.mac) : ''));
        var q = d.queue;
        if (q && q.queues) {
            var qs = q.queues;
            var qtxt = qs.length + ' queue(s)';
            var aq = typeof q.activeQueue === 'number' ? q.activeQueue : -1;
            if (aq >= 0 && aq < qs.length)
                qtxt += ' — <span class="text-success">running: ' + esc(qs[aq].name || ('#' + aq)) + '</span>';
            else
                qtxt += ' — <span class="text-muted">stopped</span>';
            var bq = typeof q.bootQueue === 'number' ? q.bootQueue : -1;
            if (bq >= 0 && bq < qs.length)
                qtxt += ' <small class="text-muted">(boot: ' + esc(qs[bq].name || ('#' + bq)) + ')</small>';
            html += row('Message queues', qtxt);
            if (q.timeSynced && q.time)
                html += row('Device clock', esc(q.time) + (q.timeZone ? ' <small class="text-muted">(' + esc(q.timeZone) + ')</small>' : ''));
        }
        dev.insertAdjacentHTML('beforeend', html);
    }).catch(function () {
        document.getElementById('flReach').innerHTML = '<span class="text-danger">probe failed</span>';
    });
})();
</script>

<fieldset>
<legend>Quick send</legend>
<div class="row" style="align-items:flex-end; flex-wrap:wrap; gap:0.5rem;">
    <div class="col-md-4">
        <label for="flText">Text</label>
        <input id="flText" type="text" class="form-control" maxlength="200"
               placeholder="Message to display">
    </div>
    <div class="col-md-2">
        <label for="flPage">Page</label>
        <select id="flPage" class="form-control">
<?php foreach (range('C', 'X') as $p): ?>
            <option value="<?php echo $p; ?>"><?php echo $p; ?></option>
<?php endforeach; ?>
        </select>
    </div>
    <div class="col-md-2">
        <label for="flColor">Color</label>
        <select id="flColor" class="form-control">
            <option value="">Device default</option>
            <option value="CC">Bright red</option>
            <option value="CG">Yellow</option>
            <option value="CH">Bright yellow</option>
            <option value="CL">Bright green</option>
            <option value="CM">Green</option>
            <option value="CP">Rainbow</option>
        </select>
    </div>
    <div class="col-md-2">
        <button class="buttons" onclick="flSend()">Send &amp; show</button>
    </div>
</div>
<div id="flResult" class="text-muted" style="margin-top:0.5rem;"></div>
</fieldset>

<fieldset>
<legend>Display controls</legend>
<button class="buttons" onclick="flPost('blank', {page: 'C'})">Blank</button>
<button class="buttons" onclick="flPost('time', {page: 'C'})">Show time</button>
<button class="buttons" onclick="flPost('date', {page: 'C'})">Show date</button>
<button class="buttons" onclick="flPost('queue', {action: 'start'})">Queue start</button>
<button class="buttons" onclick="flPost('queue', {action: 'stop'})">Queue stop</button>
</fieldset>

<p class="text-muted">
Log: <code>logs/plugin-<?php echo fauxlite_h($pluginName); ?>.log</code>
</p>

<script>
function flPost(ep, body) {
    return fetch('<?php echo $api; ?>/' + ep, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(body)
    }).then(function (r) { return r.json(); })
      .then(function (d) {
          var el = document.getElementById('flResult');
          if (el) el.textContent = d.ok ? 'OK — ' + (d.detail || '')
                                        : 'Failed — ' + (d.detail || '');
          if (window.$ && $.jGrowl)
              $.jGrowl(d.ok ? 'Sent' : 'Failed: ' + (d.detail || ''));
      })
      .catch(function (e) {
          var el = document.getElementById('flResult');
          if (el) el.textContent = 'Request failed — ' + e;
      });
}
function flSend() {
    flPost('send', {
        page: document.getElementById('flPage').value,
        text: document.getElementById('flText').value,
        color: document.getElementById('flColor').value,
        runPage: true
    });
}
</script>
