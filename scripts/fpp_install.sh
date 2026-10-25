#!/bin/bash
set -e

# fpp-plugin-FauxLite install script

. ${FPPDIR}/scripts/common

PLUGIN_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# Executables FPP/fppd will run directly or via scripts/eventScript
chmod +x "${PLUGIN_DIR}/callbacks.py" "${PLUGIN_DIR}/lib/fauxlite.py"
chmod +x "${PLUGIN_DIR}/commands/"*.sh "${PLUGIN_DIR}/scripts/"*.sh

# Nothing else is created outside the plugin directory: config lives in
# FPP's plugin settings file, logs in FPP's logs dir.

# FPP 10+ hot-loads plugins with a callbacks script; older majors in our
# versions[] range have no plugin load/unload at all, so they need a
# full fppd restart to pick this up.
( set +u; source "${FPPDIR:-/opt/fpp}/scripts/common" && setSetting restartFlag 1 ) || true
