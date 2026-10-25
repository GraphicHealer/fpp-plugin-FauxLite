#!/bin/bash
# FauxLite - Show Date
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec /usr/bin/python3 "$DIR/lib/fauxlite.py" date --page "${1:-A}"
