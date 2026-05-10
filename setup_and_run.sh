#!/usr/bin/env bash
# Setup and launch the Ebook Reader.
# Run this once (or any time) — it installs dependencies into a local venv
# then starts the app.  Double-clicking it in Finder works too.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$SCRIPT_DIR/.venv"
PYTHON=""

# ── Find Python 3.9+ ──────────────────────────────────────────────────────────
find_python() {
    for candidate in python3 python3.12 python3.11 python3.10 python3.9; do
        if command -v "$candidate" &>/dev/null; then
            ver=$("$candidate" -c 'import sys; print(sys.version_info[:2])' 2>/dev/null)
            if "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3,9) else 1)' 2>/dev/null; then
                PYTHON="$candidate"
                return 0
            fi
        fi
    done
    return 1
}

if ! find_python; then
    osascript -e 'display dialog "Ebook Reader requires Python 3.9 or later.\n\nPlease install Python from python.org or via Homebrew:\n  brew install python3" buttons {"OK"} default button "OK" with icon stop' 2>/dev/null || true
    echo "ERROR: Python 3.9+ not found. Install from https://python.org or 'brew install python3'."
    exit 1
fi

echo "Using: $("$PYTHON" --version)"

# ── Create / update virtual environment ───────────────────────────────────────
if [ ! -d "$VENV" ]; then
    echo "Creating virtual environment…"
    "$PYTHON" -m venv "$VENV"
fi

PY="$VENV/bin/python"
PIP="$VENV/bin/pip"

echo "Installing / updating dependencies…"
"$PIP" install --quiet --upgrade pip
"$PIP" install --quiet -r "$SCRIPT_DIR/requirements.txt"

echo "Launching Ebook Reader…"
exec "$PY" "$SCRIPT_DIR/ebook_reader.py" "$@"
