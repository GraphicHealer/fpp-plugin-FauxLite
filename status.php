<?php
/*
 * FauxLite status page (Status/Control menu).
 * Probes the device live (bounded 4s) and offers quick-send actions
 * through the plugin API.
 */

$pluginName = 'fpp-plugin-FauxLite';
require_once dirname(__FILE__) . '/lib/fauxlite.php';

$cfg = fl_cfg();
$enabled = fl_cfg_enabled($cfg);
$host = isset($cfg['host']) ? rtrim(trim($cfg['host']), '/') : '';
$base = fl_base($cfg);

$info = null;
$queue = null;
$reachable = false;
$err = '';
if ($base !== null) {
    list($code, $body, $e) = fl_http('GET', $base . '/api/info');
    $reachable = ($code === 200);
    if ($reachable) {
        $info = json_decode($body, true);
        list($qcode, $qbody) = fl_http('GET', $base . '/api/messages');
        if ($qcode === 200) $queue = json_decode($qbody, true);
    } else {
        $err = $e !== '' ? $e : 'HTTP ' . $code;
    }
}

function fl_h($s) { return htmlspecialchars((string)$s); }
$api = '/api/plugin/' . $GLOBALS['fl_plugin'];
?>

<h2>FauxLite Status</h2>

<table class="table table-striped" style="max-width: 50rem;">
<tr><td><b>Plugin</b></td>
    <td><?php echo $enabled ? '<span class="text-success">enabled</span>'
                            : '<span class="text-muted">disabled</span>'; ?>
        <small class="text-muted">(Input/Output Setup &rarr; FauxLite)</small></td></tr>
<tr><td><b>Device address</b></td><td><code><?php echo fl_h($host !== '' ? $host : 'not set'); ?></code></td></tr>
<tr><td><b>Device</b></td>
    <td><?php
        if ($base === null) echo '<span class="text-muted">no valid address configured</span>';
        elseif ($reachable) echo '<span class="text-success">reachable</span>';
        else echo '<span class="text-danger">not reachable</span>'
            . ' <small class="text-muted">' . fl_h($err) . '</small>';
    ?></td></tr>
<?php if ($info): ?>
<tr><td><b>Chip ID</b></td><td><?php echo fl_h(isset($info['chip_id']) ? $info['chip_id'] : ''); ?></td></tr>
<tr><td><b>Sign ID / baud</b></td><td><?php
    echo fl_h(isset($info['sign_id']) ? $info['sign_id'] : '');
    echo ' @ ' . fl_h(isset($info['baud_rate']) ? $info['baud_rate'] : '');
?></td></tr>
<tr><td><b>IP / MAC</b></td><td><?php
    echo fl_h(isset($info['ip']) ? $info['ip'] : '');
    if (isset($info['mac'])) echo ' / ' . fl_h($info['mac']);
?></td></tr>
<?php endif; ?>
<?php if (is_array($queue)): ?>
<tr><td><b>Message queues</b></td><td><?php
    $qs = isset($queue['queues']) && is_array($queue['queues'])
        ? $queue['queues'] : array();
    echo count($qs) . ' queue(s)';
    $aq = isset($queue['activeQueue']) ? intval($queue['activeQueue']) : -1;
    if ($aq >= 0 && $aq < count($qs)) {
        $nm = isset($qs[$aq]['name']) ? $qs[$aq]['name'] : '#' . $aq;
        echo ' &mdash; <span class="text-success">running: ' . fl_h($nm) . '</span>';
    } else {
        echo ' &mdash; <span class="text-muted">stopped</span>';
    }
    $bq = isset($queue['bootQueue']) ? intval($queue['bootQueue']) : -1;
    if ($bq >= 0 && $bq < count($qs))
        echo ' <small class="text-muted">(boot: '
            . fl_h(isset($qs[$bq]['name']) ? $qs[$bq]['name'] : '#' . $bq)
            . ')</small>';
?></td></tr>
<?php if (!empty($queue['timeSynced']) && isset($queue['time'])): ?>
<tr><td><b>Device clock</b></td><td><?php
    echo fl_h($queue['time']);
    if (isset($queue['timeZone'])) echo ' <small class="text-muted">(' . fl_h($queue['timeZone']) . ')</small>';
?></td></tr>
<?php endif; ?>
<?php endif; ?>
</table>

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
Log: <code>logs/plugin-<?php echo fl_h($pluginName); ?>.log</code>
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
