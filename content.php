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
