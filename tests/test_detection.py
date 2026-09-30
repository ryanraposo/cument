"""Detection/responsiveness contract for terminal (Guake) + Nautilus follow.

RED phase: these assert the improved behavior. They must fail on the
old title-only implementation and pass after the extension/shell fix.
"""
import re
import unittest
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
EXT = BASE / 'extension' / 'extension.js'


def read(name):
    return (BASE / 'shell' / name).read_text()


class ShellTitleTests(unittest.TestCase):
    def test_bash_emits_both_osc_sequences(self):
        text = read('cument.bash')
        self.assertIn('cument:', text)
        # OSC 0 (window title) and OSC 2 (icon title) so Guake/VTE variants propagate.
        self.assertTrue(']0;' in text and ']2;' in text, 'bash must emit OSC 0 and OSC 2')

    def test_zsh_emits_both_osc_sequences(self):
        text = read('cument.zsh')
        self.assertIn('cument:', text)
        self.assertTrue(']0;' in text and ']2;' in text, 'zsh must emit OSC 0 and OSC 2')

    def test_fish_title_carries_pid(self):
        text = read('cument.fish')
        self.assertIn('cument:', text)
        self.assertIn('fish_title', text)


class ExtensionFollowTests(unittest.TestCase):
    def setUp(self):
        self.js = EXT.read_text()

    def test_contexts_track_recency(self):
        # _contexts values must carry recency for PID-fallback disambiguation.
        self.assertTrue(re.search(r'seen|timestamp|Date\.now|monotonic', self.js),
                        'contexts must track recency')

    def test_pid_descendant_fallback(self):
        # Must not rely solely on title regex; use window pid -> descendant shells.
        self.assertIn('get_pid', self.js)
        self.assertTrue(re.search(r'/proc|descendant|ancestor|ppid|get_ppid|_descendant',
                                  self.js, re.IGNORECASE),
                        'must resolve focused window pid to known shell pids')

    def test_debounced_retry(self):
        # Title-before-Context race needs a deferred re-check.
        self.assertTrue(re.search(r'_scheduleFollow', self.js),
                        'must debounce/retry follow after focus/title/context')

    def test_guake_show_hide_triggers(self):
        # Guake dropdown toggles via map/unmap without focus change.
        self.assertTrue(re.search(r"'map'|\"map\"|map.*unmap|unmap|notify::mapped|visible",
                                  self.js),
                        'must listen for map/unmap for dropdown terminals')
        self.assertTrue(re.search(r'guake', self.js, re.IGNORECASE),
                        'must handle Guake explicitly')

    def test_nautilus_heuristic(self):
        self.assertTrue(re.search(r'Nautilus|org\.gnome\.Nautilus', self.js),
                        'must detect Nautilus windows')
        # In-window navigation updates title; must use it for folder changes.
        self.assertIn('notify::title', self.js)


if __name__ == '__main__':
    unittest.main()
