#!/bin/bash
# Start a fresh headless Wayland compositor on a private session bus.
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ ${1:-} != --inside ]]; then
    sandbox=$(mktemp -d /tmp/cument-shell.XXXXXX)
    mkdir -p "$sandbox/data/gnome-shell/extensions" "$sandbox/config" "$sandbox/state"
    ln -s "$PWD/extension" "$sandbox/data/gnome-shell/extensions/cument@ryanraposo.github.io"
    probe="$sandbox/data/gnome-shell/extensions/cument-test@local"
    mkdir -p "$probe"
    cp tests/shell-probe.js "$probe/extension.js"
    printf '%s\n' '{"uuid":"cument-test@local","name":"Test probe","description":"Isolated test only","shell-version":["50"]}' > "$probe/metadata.json"
    export CUMENT_TEST_ROOT="$sandbox"
    export XDG_DATA_HOME="$sandbox/data" XDG_CONFIG_HOME="$sandbox/config" XDG_STATE_HOME="$sandbox/state"
    exec dbus-run-session "$0" --inside
fi
export GSETTINGS_BACKEND=dconf
gsettings set org.gnome.shell enabled-extensions "['cument@ryanraposo.github.io', 'cument-test@local']"
gsettings set org.gnome.shell welcome-dialog-last-shown-version '50'
gnome-shell --headless --wayland --virtual-monitor 1440x1000 --wayland-display cument-test --debug-control >"$CUMENT_TEST_ROOT/shell.log" 2>&1 &
compositor=$!
trap 'kill "$compositor" 2>/dev/null || true' EXIT
export WAYLAND_DISPLAY=cument-test
for attempt in $(seq 1 100); do
    if gnome-extensions info cument@ryanraposo.github.io 2>/dev/null | grep -q ACTIVE; then break; fi
    if ! kill -0 "$compositor" 2>/dev/null; then cat "$CUMENT_TEST_ROOT/shell.log"; exit 1; fi
    sleep .1
done
gnome-extensions info cument@ryanraposo.github.io
gdbus call --session --dest org.gnome.Shell --object-path /io/github/ryanraposo/Cument/Test --method io.github.ryanraposo.Cument.Test.Prepare
bin/cument open "$PWD"
sleep 2
bin/cument doctor
gdbus call --session --dest org.gnome.Shell --object-path /io/github/ryanraposo/Cument/Test --method io.github.ryanraposo.Cument.Test.Inspect
sleep .5
gdbus call --session --dest org.gnome.Shell --object-path /io/github/ryanraposo/Cument/Test --method io.github.ryanraposo.Cument.Test.Capture "$PWD/dist/drawer-wayland.png"
bin/cument close
sleep .6
bin/cument doctor
bin/cument open "$PWD"
sleep .6
bin/cument doctor
 /usr/bin/python3 tests/wayland_smoke.py
gnome-extensions disable cument@ryanraposo.github.io
sleep .3
gnome-extensions info cument@ryanraposo.github.io
cat "$CUMENT_TEST_ROOT/shell.log"
echo "Shell test diagnostics: $CUMENT_TEST_ROOT"
