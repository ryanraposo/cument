import argparse
import json
import os
from pathlib import Path
import sys

from . import __version__
from .core import discover, project_root

BUS = 'org.gnome.Shell'
OBJECT = '/org/gnome/Shell/Extensions/Cument'
INTERFACE = 'org.gnome.Shell.Extensions.Cument'


def call(method, signature=None, values=()):
    from gi.repository import Gio, GLib
    connection = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    return connection.call_sync(BUS, OBJECT, INTERFACE, method,
                                GLib.Variant(signature, values) if signature else None,
                                None, Gio.DBusCallFlags.NONE, 1500, None)


def main(argv=None):
    parser = argparse.ArgumentParser(description='cument — your project’s margin. A GNOME Markdown drawer.')
    parser.add_argument('--version', action='version', version=__version__)
    sub = parser.add_subparsers(dest='command')
    for name in ('open', 'toggle'):
        p = sub.add_parser(name)
        p.add_argument('directory', nargs='?', default=os.getcwd())
    sub.add_parser('close')
    p = sub.add_parser('context', help='Publish shell context (used by shell integration)')
    p.add_argument('directory', nargs='?', default=os.getcwd())
    p.add_argument('--pid', type=int, default=os.getppid())
    p = sub.add_parser('list', help='List project Markdown files without opening a window')
    p.add_argument('directory', nargs='?', default=os.getcwd())
    p.add_argument('--json', action='store_true')
    p = sub.add_parser('shell-init', help='Print shell integration; eval the output in your shell rc')
    p.add_argument('shell', choices=('bash', 'zsh', 'fish'))
    sub.add_parser('doctor', help='Check desktop integration and editor dependencies')
    p = sub.add_parser('_editor', help=argparse.SUPPRESS)
    p.add_argument('--project', default=os.getcwd())
    p.add_argument('--hide', action='store_true')
    p.add_argument('--background', action='store_true')
    args = parser.parse_args(argv)
    if args.command == '_editor':
        from .app import run
        return run(args)
    if args.command == 'shell-init':
        base = Path(__file__).resolve().parent.parent
        source = base / 'shell' / f'cument.{args.shell}'
        if not source.exists():
            source = Path('/usr/share/cument/shell') / f'cument.{args.shell}'
        print(source.read_text(), end='')
        return 0
    if args.command == 'doctor':
        import subprocess
        checks = {}
        for namespace, version in [('Gtk', '4.0'), ('Adw', '1'), ('GtkSource', '5')]:
            try:
                import gi
                gi.require_version(namespace, version)
                checks[namespace] = 'available'
            except (ImportError, ValueError) as error:
                checks[namespace] = str(error)
        checks['session'] = os.environ.get('XDG_SESSION_TYPE', 'unknown')
        try:
            checks['drawer'] = call('Status').unpack()[0]
        except Exception:
            checks['drawer'] = 'unavailable — enable cument@ryanraposo.github.io; first install may need a login'
        checks['shell'] = subprocess.getoutput('gnome-shell --version')
        print(json.dumps(checks, indent=2))
        return 0 if not checks['drawer'].startswith('unavailable') else 1
    try:
        if args.command == 'list':
            notes = discover(project_root(args.directory))
            print(json.dumps([n.__dict__ for n in notes], indent=2) if args.json
                  else '\n'.join(n.path for n in notes))
            return 0
        if args.command == 'close':
            call('Close')
        elif args.command == 'context':
            call('Context', '(si)', (str(project_root(args.directory)), args.pid))
        else:
            directory = str(project_root(getattr(args, 'directory', os.getcwd())))
            call('Open' if args.command == 'open' else 'Toggle', '(s)', (directory,))
        return 0
    except Exception as error:
        if args.command != 'context':
            print(f'cument: {error}\nRun “cument doctor” to check the GNOME extension.', file=sys.stderr)
        return 1
