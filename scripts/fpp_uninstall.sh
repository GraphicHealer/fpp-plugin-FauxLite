#!/bin/bash

# fpp-plugin-FauxLite uninstall script.
# This runs BEFORE the plugin directory is deleted — clean up everything
# we created outside the plugin directory (just our plugin settings file;
# the single plugin log is left for FPP to rotate/purge as usual).

. ${FPPDIR}/scripts/common

rm -f "${MEDIADIR}/config/plugin.fpp-plugin-FauxLite"
