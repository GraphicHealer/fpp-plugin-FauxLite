#!/bin/bash
# FauxLite - Stop Message Queue
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
setsid /usr/bin/python3 "$DIR/lib/fauxlite.py" queue stop </dev/null >/dev/null 2>&1 &
