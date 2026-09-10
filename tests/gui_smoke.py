"""Run with dbus-run-session xvfb-run -a /usr/bin/python3 tests/gui_smoke.py."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cument.app import Cument, Drawer, GLib


def settle(seconds=.2):
    deadline = time.monotonic() + seconds
    context = GLib.MainContext.default()
    while time.monotonic() < deadline:
        while context.pending():
            context.iteration(False)
        time.sleep(.01)


with tempfile.TemporaryDirectory(prefix='cument-ui-') as directory:
    root = Path(directory)
    (root / 'README.md').write_text('# A little room to think\n\nEvery project deserves a margin.\n\n## The next good idea\n\n- [x] Follow the terminal\n- [x] Keep your notes nearby\n- [ ] Make something wonderful\n\n> Small notes. Clear thoughts.\n\n```python\ndef begin():\n    return "hello, cument"\n```\n')
    (root / 'notes').mkdir()
    (root / 'notes/ideas.md').write_text('# Ideas\n\nA quiet place for unfinished thoughts.\n')
    (root / 'notes/research.md').write_text('# Research\n')
    (root / 'docs').mkdir()
    (root / 'docs/design.md').write_text('# Design\n')
    (root / '.cument').touch()
    app = Cument()
    app.register(None)
    window = Drawer(app)
    app.window = window
    window.set_project(root)
    window.present()
    settle(1.2)
    assert len(window.notes) == 4, window.notes
    assert window.document.relative == 'README.md'
    window.select('notes/ideas.md')
    window.buffer.insert_at_cursor('Saved by the GUI test.\n')
    settle(1.2)
    assert 'Saved by the GUI test.' in (root / 'notes/ideas.md').read_text()
    assert not window.buffer.get_modified()
    window.buffer.insert_at_cursor('My conflicting edit.\n')
    (root / 'notes/ideas.md').write_text('External edit.\n')
    assert not window.save()
    assert (root / 'notes/ideas.md').read_text() == 'External edit.\n'
    assert window.message.get_visible()
    restored = Drawer(app)
    restored.set_project(root)
    settle(.4)
    restored.select('notes/ideas.md')
    assert 'My conflicting edit.' in restored.text()
    assert restored.buffer.get_modified()
    assert not restored.save()
    restored.pool.shutdown(wait=True)
    GLib.source_remove(restored.poll_source)
    restored.destroy()
    window.select('README.md')
    window.select('notes/ideas.md')
    assert 'My conflicting edit.' in window.text()
    assert window.buffer.get_modified()
    window.select('README.md')
    window.search.set_text('design')
    settle(.3)
    assert window.note_count.get_text().startswith('1 NOTES')
    window.search.set_text('')
    window.project_label.set_text('cument')
    window.path_label.set_text('~/repos/cument')
    settle(.4)
    output = Path(__file__).resolve().parents[1] / 'dist' / 'editor-light.png'
    output.parent.mkdir(exist_ok=True)
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'x11grab', '-video_size', '600x940',
                    '-i', os.environ['DISPLAY'], '-frames:v', '1', str(output)], check=True)
    print('GUI PASS: discovery, selection, autosave, conflicts, buffer retention, search, screenshot')
    window.pool.shutdown(wait=True)
    window.destroy()
