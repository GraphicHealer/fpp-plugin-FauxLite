<?php
/*
 * Plugin API for fpp-plugin-FauxLite — all endpoints sit under
 * /api/plugin/fpp-plugin-FauxLite/.  They proxy the FauxLite device's
 * REST API so the status page (and anything else on the LAN talking to
 * FPP) doesn't need to know the device address.
 *
 *   GET  version          plugin version
 *   GET  info             device /api/info + /api/messages
 *   POST send             {page,text,color,font,size,function,runPage}
 *   POST raw              {command}
 *   POST runpage          {page}
 *   POST blank            {page}
 *   POST time | date      {page}
 *   POST oneshot          {text,repeat,color,font,size,function,beep}
 *   POST beep             {count}
 *   POST queue            {action: start|stop}
 *   POST test             probe the saved device address
 */

require_once dirname(__FILE__) . '/lib/fauxlite.php';

function getEndpointsfpppluginFauxLite() {
    return array(
        array('method' => 'GET',  'endpoint' => 'version',
              'callback' => 'fpppluginFauxLiteVersion'),
        array('method' => 'GET',  'endpoint' => 'info',
              'callback' => 'fpppluginFauxLiteInfo'),
        array('method' => 'POST', 'endpoint' => 'send',
              'callback' => 'fpppluginFauxLiteSend'),
        array('method' => 'POST', 'endpoint' => 'raw',
              'callback' => 'fpppluginFauxLiteRaw'),
        array('method' => 'POST', 'endpoint' => 'runpage',
              'callback' => 'fpppluginFauxLiteRunPage'),
        array('method' => 'POST', 'endpoint' => 'blank',
              'callback' => 'fpppluginFauxLiteBlank'),
        array('method' => 'POST', 'endpoint' => 'time',
              'callback' => 'fpppluginFauxLiteTime'),
        array('method' => 'POST', 'endpoint' => 'date',
              'callback' => 'fpppluginFauxLiteDate'),
        array('method' => 'POST', 'endpoint' => 'oneshot',
              'callback' => 'fpppluginFauxLiteOneshot'),
        array('method' => 'POST', 'endpoint' => 'beep',
              'callback' => 'fpppluginFauxLiteBeep'),
        array('method' => 'POST', 'endpoint' => 'queue',
              'callback' => 'fpppluginFauxLiteQueue'),
        array('method' => 'POST', 'endpoint' => 'test',
              'callback' => 'fpppluginFauxLiteTest'),
    );
}

function _fauxliteBody() {
    $b = json_decode(file_get_contents('php://input'), true);
    return is_array($b) ? $b : array();
}

function _fauxliteSendResult($ok, $detail) {
    return json(array('ok' => $ok, 'detail' => $detail));
}

// GET /api/plugin/fpp-plugin-FauxLite/version
function fpppluginFauxLiteVersion() {
    return json(array('version' => 'fpp-plugin-FauxLite 1.0.0'));
}

// GET /api/plugin/fpp-plugin-FauxLite/info
function fpppluginFauxLiteInfo() {
    $cfg = fauxlite_cfg();
    $base = fauxlite_base($cfg);
    $out = array('enabled' => fauxlite_cfg_enabled($cfg),
                 'host' => isset($cfg['host']) ? $cfg['host'] : '',
                 'reachable' => false);
    if ($base === null) return json($out);
    list($code, $body, $err) = fauxlite_http('GET', $base . '/api/info');
    $out['reachable'] = ($code === 200);
    $out['info'] = $code === 200 ? json_decode($body, true) : null;
    $out['error'] = $err;
    list($qcode, $qbody) = fauxlite_http('GET', $base . '/api/messages');
    $out['queue'] = $qcode === 200 ? json_decode($qbody, true) : null;
    return json($out);
}

// POST /api/plugin/fpp-plugin-FauxLite/send
function fpppluginFauxLiteSend() {
    $in = _fauxliteBody();
    $cfg = fauxlite_cfg();
    $page = fauxlite_page(isset($in['page']) ? $in['page'] : 'A');
    $cmd = fauxlite_page_write($page,
        isset($in['text']) ? $in['text'] : '',
        isset($in['color']) ? $in['color'] : '',
        isset($in['font']) ? $in['font'] : '',
        isset($in['size']) ? $in['size'] : '',
        isset($in['function']) ? $in['function'] : '');
    list($ok, $d) = fauxlite_send($cfg, $cmd);
    // <RPx> is a standalone command — appending it to the page write
    // makes it literal text on the sign.
    if ($ok && !empty($in['runPage']))
        list($ok, $d) = fauxlite_send($cfg, '<RP' . $page . '>');
    return _fauxliteSendResult($ok, $d);
}

// POST /api/plugin/fpp-plugin-FauxLite/raw
function fpppluginFauxLiteRaw() {
    $in = _fauxliteBody();
    $cmd = isset($in['command']) ? trim($in['command']) : '';
    if ($cmd === '') return _fauxliteSendResult(false, 'empty command');
    list($ok, $d) = fauxlite_send(fauxlite_cfg(), $cmd);
    return _fauxliteSendResult($ok, $d);
}

// POST /api/plugin/fpp-plugin-FauxLite/runpage
function fpppluginFauxLiteRunPage() {
    $in = _fauxliteBody();
    $page = fauxlite_page(isset($in['page']) ? $in['page'] : 'A', 'Z', 'A');
    list($ok, $d) = fauxlite_send(fauxlite_cfg(), '<RP' . $page . '>');
    return _fauxliteSendResult($ok, $d);
}

// POST /api/plugin/fpp-plugin-FauxLite/blank
function fpppluginFauxLiteBlank() {
    $in = _fauxliteBody();
    $cfg = fauxlite_cfg();
    $page = fauxlite_page(isset($in['page']) ? $in['page'] : 'C');
    // A visibly-empty page falls back to the sign's HELLO demo — real
    // blanking needs an all-black graphic block (we define block Z).
    list($ok, $d) = fauxlite_send($cfg, '<GZ>' . str_repeat('B', 126));
    if ($ok) list($ok, $d) = fauxlite_send($cfg, '<P' . $page . '><FQ><BZ>');
    if ($ok) list($ok, $d) = fauxlite_send($cfg, '<RP' . $page . '>');
    return _fauxliteSendResult($ok, $d);
}

// POST /api/plugin/fpp-plugin-FauxLite/time
function fpppluginFauxLiteTime() {
    $in = _fauxliteBody();
    $page = fauxlite_page(isset($in['page']) ? $in['page'] : 'C');
    list($ok, $d) = fauxlite_send(fauxlite_cfg(), '<P' . $page . '><FT>');
    if ($ok) list($ok, $d) = fauxlite_send(fauxlite_cfg(), '<RP' . $page . '>');
    return _fauxliteSendResult($ok, $d);
}

// POST /api/plugin/fpp-plugin-FauxLite/date
function fpppluginFauxLiteDate() {
    $in = _fauxliteBody();
    $page = fauxlite_page(isset($in['page']) ? $in['page'] : 'C');
    list($ok, $d) = fauxlite_send(fauxlite_cfg(), '<P' . $page . '><FD>');
    if ($ok) list($ok, $d) = fauxlite_send(fauxlite_cfg(), '<RP' . $page . '>');
    return _fauxliteSendResult($ok, $d);
}

// POST /api/plugin/fpp-plugin-FauxLite/oneshot
function fpppluginFauxLiteOneshot() {
    $in = _fauxliteBody();
    $cfg = fauxlite_cfg();
    $repeat = isset($in['repeat']) ? max(1, min(99, intval($in['repeat']))) : 1;
    $color = isset($in['color']) ? $in['color'] : '';
    $font = isset($in['font']) ? $in['font'] : '';
    $size = isset($in['size']) ? $in['size'] : '';
    $func = isset($in['function']) ? $in['function'] : '';
    if (!empty($in['beep'])) {
        list($ok, $d) = fauxlite_send($cfg, '<PX><FO>');
        if (!$ok) return _fauxliteSendResult(false, $d);
    }
    // Black graphic on Y — a space page would show the HELLO demo.
    list($ok, $d) = fauxlite_send($cfg, '<GZ>' . str_repeat('B', 126));
    if (!$ok) return _fauxliteSendResult(false, $d);
    list($ok, $d) = fauxlite_send($cfg,
        '<PY><' . (fauxlite_resolve($func, 'function') !== '' ? fauxlite_resolve($func, 'function') : 'FQ') . '><BZ>');
    if (!$ok) return _fauxliteSendResult(false, $d);
    list($ok, $d) = fauxlite_send($cfg,
        fauxlite_page_write('Z', isset($in['text']) ? $in['text'] : '',
                      $color, $font, $size, $func));
    if (!$ok) return _fauxliteSendResult(false, $d);
    list($ok, $d) = fauxlite_send($cfg, sprintf('<RPZ><%02d><RPY>', $repeat));
    return _fauxliteSendResult($ok, $d);
}

// POST /api/plugin/fpp-plugin-FauxLite/beep
function fpppluginFauxLiteBeep() {
    $in = _fauxliteBody();
    $cfg = fauxlite_cfg();
    $count = isset($in['count']) ? max(1, min(99, intval($in['count']))) : 1;
    list($ok, $d) = fauxlite_send($cfg, '<GZ>' . str_repeat('B', 126));
    if (!$ok) return _fauxliteSendResult(false, $d);
    list($ok, $d) = fauxlite_send($cfg, '<PY><FQ><BZ>');
    if (!$ok) return _fauxliteSendResult(false, $d);
    list($ok, $d) = fauxlite_send($cfg, '<PZ><FO>');
    if (!$ok) return _fauxliteSendResult(false, $d);
    list($ok, $d) = fauxlite_send($cfg, sprintf('<RPZ><%02d><RPY>', $count));
    return _fauxliteSendResult($ok, $d);
}

// POST /api/plugin/fpp-plugin-FauxLite/queue
function fpppluginFauxLiteQueue() {
    $in = _fauxliteBody();
    $action = isset($in['action']) ? $in['action'] : '';
    if ($action !== 'start' && $action !== 'stop')
        return _fauxliteSendResult(false, 'action must be start or stop');
    $base = fauxlite_base(fauxlite_cfg());
    if ($base === null)
        return _fauxliteSendResult(false, 'device address is not set/valid');
    $ep = $base . '/api/loop/' . $action;
    if ($action === 'start') {
        // Firmware takes ?queue=N; pick one: explicit index, else the
        // boot queue, else the first queue with messages.
        $idx = isset($in['queue']) ? intval($in['queue']) : -1;
        if ($idx < 0) {
            list($qc, $qb) = fauxlite_http('GET', $base . '/api/messages');
            $cur = json_decode($qb, true);
            $qs = ($qc === 200 && is_array($cur) && isset($cur['queues']))
                ? $cur['queues'] : array();
            $bq = isset($cur['bootQueue']) ? intval($cur['bootQueue']) : -1;
            if ($bq >= 0 && $bq < count($qs)
                && !empty($qs[$bq]['messages'])) {
                $idx = $bq;
            } else {
                foreach ($qs as $i => $q) {
                    if (!empty($q['messages'])) { $idx = $i; break; }
                }
            }
        }
        if ($idx < 0)
            return _fauxliteSendResult(false, 'device has no queues to run');
        $ep .= '?queue=' . $idx;
    }
    list($code, $body, $err) = fauxlite_http('POST', $ep);
    if ($code !== 200) {
        $msg = $err !== '' ? $err : 'HTTP ' . $code;
        $b = json_decode($body, true);
        if (is_array($b) && isset($b['error'])) $msg = $b['error'];
        return _fauxliteSendResult(false, $msg);
    }
    return _fauxliteSendResult(true, 'queue ' . $action);
}

// POST /api/plugin/fpp-plugin-FauxLite/test
// Probes the SAVED device address only — the request body must never be
// able to aim FPP's HTTP at an arbitrary host:port (SSRF).
// POST /api/plugin/fpp-plugin-FauxLite/test
// Probes the SAVED device address only — the request body must never be
// able to aim FPP's HTTP at an arbitrary host:port (SSRF).
function fpppluginFauxLiteTest() {
    $cfg = fauxlite_cfg();
    $host = isset($cfg['host']) ? rtrim(trim($cfg['host']), '/') : '';
    if ($host === '' || !fauxlite_host_valid($host))
        return json(array('ok' => false, 'detail' => 'no device address'));
    list($code, $body, $err) = fauxlite_http('GET', 'http://' . $host . '/api/info');
    $out = array('ok' => $code === 200, 'detail' => $err);
    $info = json_decode($body, true);
    $out['info'] = is_array($info) ? $info : null;
    if ($code === 200 && is_array($info)
        && (isset($info['device']) ? $info['device'] : '') !== 'faux-lite')
        $out['detail'] = 'device answered, but does not identify as FauxLite';
    return json($out);
}
?>
