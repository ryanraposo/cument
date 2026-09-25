"""Publish local Nautilus folder visits into cument's context stream."""
from gi import require_version

require_version('Nautilus', '4.1')
from gi.repository import Gio, GLib, GObject, Nautilus


class CumentContextProvider(GObject.GObject, Nautilus.MenuProvider):
    """Keep cument aligned with the most recently visited local Files folder."""

    def __init__(self):
        super().__init__()
        self._last_path = None

    def get_background_items(self, current_folder):
        location = current_folder.get_location()
        path = location.get_path() if location else None
        if not path or path == self._last_path:
            return []

        self._last_path = path
        executable = GLib.find_program_in_path('cument')
        if executable:
            try:
                Gio.Subprocess.new(
                    [executable, 'context', path, '--source', 'nautilus'],
                    Gio.SubprocessFlags.NONE,
                )
            except GLib.Error:
                pass
        return []
