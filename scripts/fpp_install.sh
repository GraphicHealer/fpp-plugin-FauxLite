#!/bin/bash
set -e

# fpp-plugin-FauxLite install script

. ${FPPDIR}/scripts/common

PLUGIN_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# Executables FPP/fppd will run directly or via scripts/eventScript
chmod +x "${PLUGIN_DIR}/callbacks.py" "${PLUGIN_DIR}/lib/fauxlite.py"
chmod +x "${PLUGIN_DIR}/commands/"*.sh "${PLUGIN_DIR}/scripts/"*.sh

# No restartFlag: install live-loads our commands/descriptions.json and
# callbacks.py via POST /api/fppd/plugin/<name>/load (PLUGIN_GUIDELINES
# §2.8 — the flag is only needed when a plugin ships commands with no
# callbacks script at all). Nothing else is created outside the plugin
# directory: config lives in FPP's plugin settings file, logs in FPP's
# logs dir.
