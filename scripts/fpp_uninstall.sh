#!/bin/bash

# fpp-plugin-FauxLite uninstall script.
# This runs BEFORE the plugin directory is deleted — clean up everything
# we created outside the plugin directory (the plugin settings file and
# the plugindata state file; the single plugin log is left for FPP to
# rotate/purge as usual).

. ${FPPDIR}/scripts/common

rm -f "${MEDIADIR}/config/plugin.fpp-plugin-FauxLite"
rm -rf "${MEDIADIR}/plugindata/fpp-plugin-FauxLite"

# Older FPP majors have no plugin unload — restart fppd there.
( set +u; source "${FPPDIR:-/opt/fpp}/scripts/common" && setSetting restartFlag 1 ) || true
