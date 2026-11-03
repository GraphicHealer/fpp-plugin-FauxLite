#!/bin/bash
# FauxLite - Start Message Queue
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
setsid /usr/bin/python3 "$DIR/lib/fauxlite.py" queue start </dev/null >/dev/null 2>&1 &
