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
 *   POST test             {host?}  probe a device (defaults to saved host)
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

function _flBody() {
    $b = json_decode(file_get_contents('php://input'), true);
    return is_array($b) ? $b : array();
}

function _flSendResult($ok, $detail) {
    return json(array('ok' => $ok, 'detail' => $detail));
}

// GET /api/plugin/fpp-plugin-FauxLite/version
function fpppluginFauxLiteVersion() {
    return json(array('version' => 'fpp-plugin-FauxLite 1.0.0'));
}

// GET /api/plugin/fpp-plugin-FauxLite/info
function fpppluginFauxLiteInfo() {
    $cfg = fl_cfg();
    $base = fl_base($cfg);
    $out = array('enabled' => fl_cfg_enabled($cfg),
                 'host' => isset($cfg['host']) ? $cfg['host'] : '',
                 'reachable' => false);
    if ($base === null) return json($out);
    list($code, $body, $err) = fl_http('GET', $base . '/api/info');
    $out['reachable'] = ($code === 200);
    $out['info'] = $code === 200 ? json_decode($body, true) : null;
    $out['error'] = $err;
    list($qcode, $qbody) = fl_http('GET', $base . '/api/messages');
    $out['queue'] = $qcode === 200 ? json_decode($qbody, true) : null;
    return json($out);
}

// POST /api/plugin/fpp-plugin-FauxLite/send
function fpppluginFauxLiteSend() {
    $in = _flBody();
    $cfg = fl_cfg();
    $page = fl_page(isset($in['page']) ? $in['page'] : 'A');
    $cmd = fl_page_write($page,
        isset($in['text']) ? $in['text'] : '',
        isset($in['color']) ? $in['color'] : '',
        isset($in['font']) ? $in['font'] : '',
        isset($in['size']) ? $in['size'] : '',
        isset($in['function']) ? $in['function'] : '');
    if (!empty($in['runPage'])) $cmd .= '<RP' . $page . '>';
    list($ok, $d) = fl_send($cfg, $cmd);
    return _flSendResult($ok, $d);
}

// POST /api/plugin/fpp-plugin-FauxLite/raw
function fpppluginFauxLiteRaw() {
    $in = _flBody();
    $cmd = isset($in['command']) ? trim($in['command']) : '';
    if ($cmd === '') return _flSendResult(false, 'empty command');
    list($ok, $d) = fl_send(fl_cfg(), $cmd);
    return _flSendResult($ok, $d);
}

// POST /api/plugin/fpp-plugin-FauxLite/runpage
function fpppluginFauxLiteRunPage() {
    $in = _flBody();
    $page = fl_page(isset($in['page']) ? $in['page'] : 'A', 'Z');
    list($ok, $d) = fl_send(fl_cfg(), '<RP' . $page . '>');
    return _flSendResult($ok, $d);
}

// POST /api/plugin/fpp-plugin-FauxLite/blank
function fpppluginFauxLiteBlank() {
    $in = _flBody();
    $page = fl_page(isset($in['page']) ? $in['page'] : 'A');
    list($ok, $d) = fl_send(fl_cfg(), '<P' . $page . '> <RP' . $page . '>');
    return _flSendResult($ok, $d);
}

// POST /api/plugin/fpp-plugin-FauxLite/time
function fpppluginFauxLiteTime() {
    $in = _flBody();
    $page = fl_page(isset($in['page']) ? $in['page'] : 'A');
    list($ok, $d) = fl_send(fl_cfg(), '<P' . $page . '><FT><RP' . $page . '>');
    return _flSendResult($ok, $d);
}

// POST /api/plugin/fpp-plugin-FauxLite/date
function fpppluginFauxLiteDate() {
    $in = _flBody();
    $page = fl_page(isset($in['page']) ? $in['page'] : 'A');
    list($ok, $d) = fl_send(fl_cfg(), '<P' . $page . '><FD><RP' . $page . '>');
    return _flSendResult($ok, $d);
}

// POST /api/plugin/fpp-plugin-FauxLite/oneshot
function fpppluginFauxLiteOneshot() {
    $in = _flBody();
    $cfg = fl_cfg();
    $repeat = isset($in['repeat']) ? max(1, min(99, intval($in['repeat']))) : 1;
    $color = isset($in['color']) ? $in['color'] : '';
    $font = isset($in['font']) ? $in['font'] : '';
    $size = isset($in['size']) ? $in['size'] : '';
    $func = isset($in['function']) ? $in['function'] : '';
    if (!empty($in['beep'])) {
        list($ok, $d) = fl_send($cfg, '<PX><FO> ');
        if (!$ok) return _flSendResult(false, $d);
    }
    list($ok, $d) = fl_send($cfg,
        fl_page_write('Y', ' ', '', '', '', $func));
    if (!$ok) return _flSendResult(false, $d);
    list($ok, $d) = fl_send($cfg,
        fl_page_write('Z', isset($in['text']) ? $in['text'] : '',
                      $color, $font, $size, $func));
    if (!$ok) return _flSendResult(false, $d);
    list($ok, $d) = fl_send($cfg, sprintf('<RPZ><%02d><RPY>', $repeat));
    return _flSendResult($ok, $d);
}

// POST /api/plugin/fpp-plugin-FauxLite/beep
function fpppluginFauxLiteBeep() {
    $in = _flBody();
    $cfg = fl_cfg();
    $count = isset($in['count']) ? max(1, min(99, intval($in['count']))) : 1;
    list($ok, $d) = fl_send($cfg, fl_page_write('Y', ' '));
    if (!$ok) return _flSendResult(false, $d);
    list($ok, $d) = fl_send($cfg, '<PZ><FO> ');
    if (!$ok) return _flSendResult(false, $d);
    list($ok, $d) = fl_send($cfg, sprintf('<RPZ><%02d><RPY>', $count));
    return _flSendResult($ok, $d);
}

// POST /api/plugin/fpp-plugin-FauxLite/queue
function fpppluginFauxLiteQueue() {
    $in = _flBody();
    $action = isset($in['action']) ? $in['action'] : '';
    if ($action !== 'start' && $action !== 'stop')
        return _flSendResult(false, 'action must be start or stop');
    $base = fl_base(fl_cfg());
    if ($base === null)
        return _flSendResult(false, 'device address is not set/valid');
    list($code, $body, $err) = fl_http('POST', $base . '/api/loop/' . $action);
    if ($code !== 200) {
        $msg = $err !== '' ? $err : 'HTTP ' . $code;
        $b = json_decode($body, true);
        if (is_array($b) && isset($b['error'])) $msg = $b['error'];
        return _flSendResult(false, $msg);
    }
    return _flSendResult(true, 'queue ' . $action);
}

// POST /api/plugin/fpp-plugin-FauxLite/test
function fpppluginFauxLiteTest() {
    $in = _flBody();
    $host = isset($in['host']) && fl_host_valid(trim($in['host']))
        ? rtrim(trim($in['host']), '/')
        : (isset(fl_cfg()['host']) ? rtrim(trim(fl_cfg()['host']), '/') : '');
    if ($host === '' || !fl_host_valid($host))
        return json(array('ok' => false, 'detail' => 'no device address'));
    list($code, $body, $err) = fl_http('GET', 'http://' . $host . '/api/info');
    $out = array('ok' => $code === 200, 'detail' => $err);
    $info = json_decode($body, true);
    $out['info'] = is_array($info) ? $info : null;
    if ($code === 200 && is_array($info)
        && (isset($info['device']) ? $info['device'] : '') !== 'faux-lite')
        $out['detail'] = 'device answered, but does not identify as FauxLite';
    return json($out);
}
?>
