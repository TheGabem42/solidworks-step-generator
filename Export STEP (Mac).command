#!/bin/bash
cd -- "$(dirname -- "$0")" || exit 1
printf 'STEP exporter — using this project folder\n\n'
if command -v python3 >/dev/null 2>&1; then
    python3 exporter/mac_client.py --root "$PWD"
    result=$?
else
    printf 'Python 3 is required. Install it from https://www.python.org/downloads/macos/ and try again.\n'
    result=1
fi
printf '\nPress Return to close.'
read -r _
exit "$result"
