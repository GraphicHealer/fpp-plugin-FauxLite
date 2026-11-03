<?php
/*
 * Shared helpers for the FauxLite plugin pages and API endpoints:
 * settings file parsing, host validation, HTTP to the device, and
 * Pro-Lite command building. Mirrored by lib/fauxlite.py — keep the
 * command spelling in sync with that file and with the firmware's
 * /api/send handler (which adds the <IDxx> wrapper itself).
 */

$GLOBALS['fauxlite_plugin'] = 'fpp-plugin-FauxLite';

function fauxlite_cfg_path() {
    global $settings;
    $dir = isset($settings['configDirectory']) ? $settings['configDirectory']
                                             : '/home/fpp/media/config';
    return $dir . '/plugin.' . $GLOBALS['fauxlite_plugin'];
}

function fauxlite_cfg() {
    $cfg = array();
    $file = fauxlite_cfg_path();
    if (is_readable($file)) {
        foreach (file($file) as $line) {
            $line = trim($line);
            if ($line === '' || strpos($line, '=') === false) continue;
            list($k, $v) = explode('=', $line, 2);
            $cfg[trim($k)] = trim(trim($v), '"');
        }
    }
    return $cfg;
}

function fauxlite_cfg_enabled($cfg) {
    $e = isset($cfg['enabled']) ? strtolower(trim($cfg['enabled'])) : '';
    return in_array($e, array('1', 'true', 'yes', 'on'))
        && isset($cfg['host']) && trim($cfg['host']) !== '';
}

function fauxlite_host_valid($h) {
    return is_string($h) && preg_match('/^[A-Za-z0-9._-]+(:[0-9]{1,5})?$/', $h);
}

function fauxlite_base($cfg) {
    $host = isset($cfg['host']) ? rtrim(trim($cfg['host']), '/') : '';
    if (!fauxlite_host_valid($host)) return null;
    if (strpos($host, ':') !== false) {
        $port = intval(substr(strrchr($host, ':'), 1));
        if ($port < 1 || $port > 65535) return null;
    }
    return 'http://' . $host;
}

/**
 * Minimal HTTP request. Returns array(httpCode|0, bodyString, errorString).
 */
function fauxlite_http($method, $url, $payload = null, $timeout = 4) {
    $body = $payload !== null ? json_encode($payload) : null;
    if (function_exists('curl_init')) {
        $ch = curl_init($url);
        curl_setopt($ch, CURLOPT_CUSTOMREQUEST, $method);
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
        curl_setopt($ch, CURLOPT_TIMEOUT, $timeout);
        curl_setopt($ch, CURLOPT_CONNECTTIMEOUT, $timeout);
        if ($body !== null) {
            curl_setopt($ch, CURLOPT_POSTFIELDS, $body);
            curl_setopt($ch, CURLOPT_HTTPHEADER,
                array('Content-Type: application/json'));
        }
        $resp = curl_exec($ch);
        $code = curl_getinfo($ch, CURLINFO_RESPONSE_CODE);
        $err = curl_error($ch);
        curl_close($ch);
        if ($resp === false || $code === 0)
            return array(0, '', $err ?: 'connection failed');
        return array($code, $resp, '');
    }
    $ctx = stream_context_create(array('http' => array(
        'method' => $method,
        'header' => $body !== null ? "Content-Type: application/json\r\n" : '',
        'content' => $body,
        'timeout' => $timeout,
        'ignore_errors' => true,
    )));
    $resp = @file_get_contents($url, false, $ctx);
    if ($resp === false) return array(0, '', 'connection failed');
    $code = 0;
    if (isset($http_response_header[0])
        && preg_match('/\s(\d{3})\s/', $http_response_header[0], $m))
        $code = (int)$m[1];
    return array($code, $resp, '');
}

/** POST one Pro-Lite command to the device. Returns array(ok, detail). */
function fauxlite_send($cfg, $command) {
    $base = fauxlite_base($cfg);
    if ($base === null) return array(false, 'device address is not set/valid');
    list($code, $body, $err) = fauxlite_http('POST', $base . '/api/send',
        array('command' => $command));
    if ($code !== 200)
        return array(false, $err !== '' ? $err : 'HTTP ' . $code);
    return array(true, 'sent');
}

function fauxlite_sanitize($text) {
    $t = preg_replace('/[\x00-\x1f\x7f<>]/', '', (string)$text);
    $t = preg_replace('/[^\x20-\x7e]/', '', $t);
    return trim(preg_replace('/[ \t]+/', ' ', $t));
}

$GLOBALS['fauxlite_tables'] = array(
    'color' => array(
        'dim_red' => 'CA', 'red' => 'CB', 'bright_red' => 'CC',
        'orange' => 'CD', 'bright_orange' => 'CE', 'light_yellow' => 'CF',
        'yellow' => 'CG', 'bright_yellow' => 'CH', 'lime' => 'CI',
        'dim_lime' => 'CJ', 'bright_lime' => 'CK', 'bright_green' => 'CL',
        'green' => 'CM', 'dim_green' => 'CN', 'yel_grn_red' => 'CO',
        'rainbow' => 'CP', 'red_grn_3d' => 'CQ', 'red_yel_3d' => 'CR',
        'grn_red_3d' => 'CS', 'grn_yel_3d' => 'CT', 'grn_on_red' => 'CU',
        'red_on_grn' => 'CV', 'org_on_grn_3d' => 'CW',
        'lime_on_red_3d' => 'CX', 'grn_on_red_3d' => 'CY',
        'red_on_grn_3d' => 'CZ'),
    'font' => array(
        'normal' => 'SA', 'bold' => 'SB', 'italic' => 'SC',
        'bold_italic' => 'SD', 'flash_normal' => 'SE',
        'flash_bold' => 'SF', 'flash_italic' => 'SG',
        'flash_bold_italic' => 'SH'),
    'size' => array('5x7' => 'SI', '4x7' => 'SJ'),
    'function' => array(
        'auto' => 'FA', 'open' => 'FB', 'cover' => 'FC', 'date' => 'FD',
        'cycling' => 'FE', 'close_right' => 'FF', 'close_left' => 'FG',
        'close_both' => 'FH', 'scroll_up' => 'FI', 'scroll_down' => 'FJ',
        'overlap' => 'FK', 'stacking' => 'FL', 'comic_1' => 'FM',
        'comic_2' => 'FN', 'beep' => 'FO', 'pause' => 'FP',
        'appear' => 'FQ', 'random' => 'FR', 'shift_left' => 'FS',
        'time' => 'FT', 'magic' => 'FU', 'thank_you' => 'FV',
        'welcome' => 'FW', 'link_page' => 'FZ', 'target' => 'F1',
        'current' => 'F2', 'day_left' => 'F3', 'hour_left' => 'F4',
        'minute_left' => 'F5', 'second_left' => 'F6'),
);

/** Mirror of lib/fauxlite.py's resolve(): a table name
 * ('bright_yellow'), a raw code ('CH'), or '' — anything else is
 * dropped rather than mangled into a protocol byte. */
function fauxlite_resolve($value, $kind) {
    $table = $GLOBALS['fauxlite_tables'][$kind];
    $v = trim((string)$value);
    if ($v === '') return '';
    $key = str_replace(array(' ', '-'), '_', strtolower($v));
    if (isset($table[$key])) return $table[$key];
    if (isset($table[$v])) return $table[$v];
    if (strlen($v) === 2 && in_array(strtoupper($v), $table))
        return strtoupper($v);
    return '';
}

/** Clamp a page letter. Default range C-X: the firmware owns pages A
 * (queue run page) and B (queue chain page), and Y/Z stay reserved for
 * one-shot/test/boot messages. Pass $min='A' for commands like Run
 * Page where reaching an owned page is legitimate. */
function fauxlite_page($v, $max = 'X', $min = 'C') {
    $p = strtoupper(substr(trim((string)$v), 0, 1));
    return ($p >= $min && $p <= $max) ? $p : $min;
}

/** '<P?><F?><C?><S?>text' — same arg order as lib/fauxlite.py's
 *  page_write(page, text, color, font, size, function). */
function fauxlite_page_write($page, $text, $color = '', $font = '',
                       $size = '', $function = '') {
    $cmd = '<P' . $page . '>';
    $codes = array(
        fauxlite_resolve($function, 'function'),
        fauxlite_resolve($color, 'color'),
        fauxlite_resolve($font, 'font'),
        fauxlite_resolve($size, 'size'));
    foreach ($codes as $code)
        if ($code !== '') $cmd .= '<' . $code . '>';
    return $cmd . fauxlite_sanitize($text);
}
?>
