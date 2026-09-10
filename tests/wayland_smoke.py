"""Assertions against the actual compositor, invoked inside test-shell.sh."""
import json
import subprocess
import sys
import time
from pathlib import Path
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gio, GLib, Gtk

bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
def probe(method, signature=None, values=()):
    result = bus.call_sync('org.gnome.Shell', '/io/github/ryanraposo/Cument/Test',
                           'io.github.ryanraposo.Cument.Test', method,
                           GLib.Variant(signature, values) if signature else None,
                           None, Gio.DBusCallFlags.NONE, 5000, None)
    return result.unpack()

def state():
    return json.loads(probe('Inspect')[0])

def settle(seconds=.7):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        while GLib.MainContext.default().pending():
            GLib.MainContext.default().iteration(False)
        time.sleep(.01)

def cli(*args):
    subprocess.run(['bin/cument', *args], check=True)

root = str(Path.cwd())
cli('open', root)
settle(1.2)
s = state()
assert len(s['windows']) == 1, s
assert s['windows'][0]['rect'] == [860, 32, 580, 968], s
assert s['windows'][0]['translation'] == 0 and s['windows'][0]['scale'] == 1, s
probe('Shortcut')
settle()
assert not json.loads(state()['status'])['open'], state()
assert not state()['windows'], state()
probe('Click')
settle()
assert json.loads(state()['status'])['open'], state()
assert len(state()['windows']) == 1, state()

app = Gtk.Application(application_id='io.github.ryanraposo.Cument.TestTerminal')
app.register(None)
windows = [Gtk.ApplicationWindow(application=app, title=f'Terminal — cument:{pid}',
                                 default_width=500, default_height=400) for pid in (10001, 10002)]
for window in windows:
    window.present()
settle()
cli('context', '--pid', '10001', root)
cli('context', '--pid', '10002', '/tmp')
probe('Focus', '(i)', (10001,))
settle()
assert json.loads(state()['status'])['project'] == root, state()
probe('Focus', '(i)', (10002,))
settle()
assert json.loads(state()['status'])['project'] == '/tmp', state()
assert state()['focus'].endswith('cument:10002'), state()
cli('context', '--pid', '10001', '/home/ryan/repos')
assert json.loads(state()['status'])['project'] == '/tmp', state()
probe('Focus', '(i)', (10001,))
settle()
assert json.loads(state()['status'])['project'] == '/home/ryan/repos', state()
cli('close')
settle()
assert state()['focus'].endswith('cument:10001'), state()
for window in windows:
    window.destroy()
cli('open', root)
settle()
print('WAYLAND PASS: exact geometry, Alt+|, earmark click, close/reopen, two terminal contexts, background update without focus theft, focus restoration')
