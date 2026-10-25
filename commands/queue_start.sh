#!/bin/bash
# FauxLite - Start Message Queue
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec /usr/bin/python3 "$DIR/lib/fauxlite.py" queue start
