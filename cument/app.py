"""Native GTK editor; all compositor policy lives in the companion extension."""
import json
import hashlib
import os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
gi.require_version('GtkSource', '5')
from gi.repository import Adw, Gdk, Gio, GLib, Gtk, GtkSource, Pango

from .core import Document, discover, project_root

APP_ID = 'io.github.ryanraposo.Cument'
STYLE = '''
window.cument { border-radius: 18px 0 0 18px; }
.brand { font-size: 23px; font-weight: 800; letter-spacing: -1px; }
.eyebrow { font-size: 10px; font-weight: 700; letter-spacing: 1.8px; opacity: .55; }
.project-title { font-size: 28px; font-weight: 700; letter-spacing: -.7px; }
.map { padding: 8px 0 12px; }
.cluster { padding: 12px; border-radius: 14px; background: alpha(@window_fg_color, .035); }
.cluster-path { font-size: 10px; opacity: .55; }
.note { border-radius: 9px; padding: 4px 8px; min-height: 24px; background: transparent; box-shadow: none; }
.note:hover { background: alpha(@accent_bg_color, .13); }
.note.selected { background: alpha(@accent_bg_color, .18); color: @accent_color; }
.weight-3 { font-size: 19px; font-weight: 700; }
.weight-2 { font-size: 15px; font-weight: 600; }
.weight-1 { font-size: 12px; }
.editor-title { font-size: 16px; font-weight: 650; }
.footer { font-size: 11px; opacity: .65; }
.document-surface { background: @view_bg_color; border-radius: 14px; }
.error-message { color: @error_color; }
textview { background: transparent; }
'''


def label(text, css=None, **kwargs):
    widget = Gtk.Label(label=text, **kwargs)
    if css:
        widget.add_css_class(css)
    return widget


def button(icon, tooltip, callback):
    widget = Gtk.Button(icon_name=icon, tooltip_text=tooltip)
    widget.add_css_class('flat')
    widget.connect('clicked', callback)
    return widget


class Drawer(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title='cument', default_width=580, default_height=900)
        self.add_css_class('cument')
        self.set_decorated(False)
        self.root = None
        self.document = None
        self.notes = []
        self.buffers = {}
        self.loading = False
        self.save_source = 0
        self.scan_generation = 0
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='cument-index')
        self.connect('close-request', self.close_requested)
        self.interface = Gio.Settings.new('org.gnome.desktop.interface')
        self.interface.connect('changed', self.theme_changed)

        self.toast = Adw.ToastOverlay()
        self.set_content(self.toast)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        for side in ('top', 'bottom', 'start', 'end'):
            getattr(box, 'set_margin_' + side)(20 if side in ('start', 'end') else 12)
        self.toast.set_child(box)
        masthead = Gtk.Box(spacing=8)
        masthead.append(label('cument', 'brand', xalign=0, hexpand=True))
        masthead.append(label('YOUR PROJECT’S MARGIN', 'eyebrow'))
        masthead.append(button('go-next-symbolic', 'Close drawer · Esc', lambda _: self.close_requested()))
        box.append(masthead)

        intro = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, margin_top=24, margin_bottom=14)
        intro.append(label('IN CONTEXT', 'eyebrow', xalign=0))
        self.project_label = label('Your project', 'project-title', xalign=0, ellipsize=Pango.EllipsizeMode.END)
        intro.append(self.project_label)
        self.path_label = label('', 'dim-label', xalign=0, ellipsize=Pango.EllipsizeMode.MIDDLE)
        intro.append(self.path_label)
        box.append(intro)

        search_row = Gtk.Box(spacing=6)
        self.search = Gtk.SearchEntry(placeholder_text='Find a note…', hexpand=True)
        self.search.connect('search-changed', lambda _: self.render_map())
        search_row.append(self.search)
        search_row.append(button('view-refresh-symbolic', 'Refresh file map', lambda _: self.refresh()))
        search_row.append(button('document-new-symbolic', 'New Markdown file · Ctrl+N', lambda _: self.new_note()))
        box.append(search_row)

        self.map_scroll = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER,
                                             min_content_height=130, max_content_height=240,
                                             propagate_natural_height=True)
        self.map_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.map_box.add_css_class('map')
        self.map_scroll.set_child(self.map_box)
        box.append(self.map_scroll)
        self.note_count = label('', 'eyebrow', xalign=0, margin_bottom=14)
        box.append(self.note_count)
        box.append(Gtk.Separator())

        toolbar = Gtk.Box(spacing=8, margin_top=10, margin_bottom=10)
        self.file_label = label('Choose a note', 'editor-title', xalign=0, hexpand=True,
                                ellipsize=Pango.EllipsizeMode.MIDDLE)
        toolbar.append(self.file_label)
        toolbar.append(button('edit-undo-symbolic', 'Undo · Ctrl+Z', lambda _: self.undo()))
        toolbar.append(button('edit-redo-symbolic', 'Redo · Ctrl+Shift+Z', lambda _: self.redo()))
        toolbar.append(button('document-save-symbolic', 'Save · Ctrl+S', lambda _: self.save()))
        toolbar.append(button('document-save-as-symbolic', 'Save a copy', lambda _: self.new_note(copy=True)))
        toolbar.append(button('document-revert-symbolic', 'Reload from disk', lambda _: self.reload_note()))
        box.append(toolbar)
        self.buffer = GtkSource.Buffer()
        self.buffer.set_language(GtkSource.LanguageManager.get_default().get_language('markdown'))
        self.buffer.connect('changed', self.changed)
        self.buffer.connect('notify::cursor-position', lambda *_: self.update_footer())
        self.view = GtkSource.View(buffer=self.buffer, wrap_mode=Gtk.WrapMode.WORD_CHAR,
                                   show_line_numbers=False, auto_indent=True,
                                   indent_on_tab=False, tab_width=4,
                                   left_margin=20, right_margin=20, top_margin=20, bottom_margin=60,
                                   vexpand=True)
        self.view.add_css_class('cument-editor')
        self.view.set_editable(False)
        self.editor_scroll = Gtk.ScrolledWindow(vexpand=True, child=self.view,
                                                hscrollbar_policy=Gtk.PolicyType.NEVER)
        self.editor_scroll.add_css_class('document-surface')
        box.append(self.editor_scroll)
        self.message = label('', xalign=0, wrap=True, selectable=True, margin_top=6)
        self.message.add_css_class('error-message')
        self.message.set_visible(False)
        box.append(self.message)
        footer = Gtk.Box(spacing=10, margin_top=10)
        self.status = label('Ready', 'footer', xalign=0, hexpand=True)
        self.metrics = label('', 'footer')
        footer.append(self.status)
        footer.append(self.metrics)
        box.append(footer)
        self.font_css = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_display(self.get_display(), self.font_css,
                                                  Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1)
        Adw.StyleManager.get_default().connect('notify::dark', self.theme_changed)
        self.theme_changed()
        keys = Gtk.EventControllerKey()
        keys.connect('key-pressed', self.key_pressed)
        self.add_controller(keys)
        self.poll_source = GLib.timeout_add_seconds(3, self.check_disk)

    def theme_changed(self, *_):
        font = Pango.FontDescription.from_string(self.interface.get_string('monospace-font-name'))
        family = json.dumps(font.get_family())
        size = font.get_size() / Pango.SCALE or 11
        self.font_css.load_from_data(f'.cument-editor {{ font-family: {family}; font-size: {size}pt; }}'.encode())
        dark = Adw.StyleManager.get_default().get_dark()
        schemes = GtkSource.StyleSchemeManager.get_default()
        self.buffer.set_style_scheme(schemes.get_scheme('Adwaita-dark' if dark else 'Adwaita'))

    def key_pressed(self, _controller, key, _code, state):
        control = bool(state & Gdk.ModifierType.CONTROL_MASK)
        shift = bool(state & Gdk.ModifierType.SHIFT_MASK)
        if key == Gdk.KEY_Escape:
            self.close_requested()
        elif control and key in (Gdk.KEY_s, Gdk.KEY_S):
            self.save()
        elif control and key in (Gdk.KEY_p, Gdk.KEY_f):
            self.search.grab_focus()
        elif control and key == Gdk.KEY_n:
            self.new_note()
        elif control and key in (Gdk.KEY_z, Gdk.KEY_Z):
            self.redo() if shift else self.undo()
        else:
            return False
        return True

    def undo(self):
        if self.buffer.get_can_undo():
            self.buffer.undo()

    def redo(self):
        if self.buffer.get_can_redo():
            self.buffer.redo()

    def text(self):
        return self.buffer.get_text(*self.buffer.get_bounds(), True)

    def stash(self):
        if self.document:
            self.buffers[str(self.document.path)] = (self.document, self.text(), self.buffer.get_modified())

    def set_project(self, directory):
        root = project_root(directory)
        if root == self.root:
            return
        self.save()
        self.stash()
        self.root = root
        self.document = None
        self.loading = True
        self.buffer.set_text('')
        self.buffer.set_modified(False)
        self.loading = False
        self.view.set_editable(False)
        self.project_label.set_text(root.name)
        self.path_label.set_text(str(root).replace(str(Path.home()), '~', 1))
        self.set_title(f'cument · {root.name}')
        self.file_label.set_text('Choose a note')
        self.search.set_text('')
        self.refresh()

    def refresh(self):
        if self.root is None:
            return
        self.scan_generation += 1
        generation, root = self.scan_generation, self.root
        future = self.pool.submit(discover, root)
        def completed(future):
            try:
                notes = future.result()
            except Exception as error:
                GLib.idle_add(self.error, str(error))
                return
            GLib.idle_add(self.accept_scan, generation, notes)
        future.add_done_callback(completed)

    def accept_scan(self, generation, notes):
        if generation != self.scan_generation:
            return GLib.SOURCE_REMOVE
        self.notes = notes
        self.render_map()
        if self.document is None and notes:
            preferred = next((n for n in notes if n.path.lower() == 'readme.md'), notes[0])
            self.select(preferred.path)
        return GLib.SOURCE_REMOVE

    def render_map(self):
        child = self.map_box.get_first_child()
        while child:
            following = child.get_next_sibling()
            self.map_box.remove(child)
            child = following
        query = self.search.get_text().casefold()
        groups = {}
        for note in self.notes:
            if query in f'{note.path} {note.title}'.casefold():
                groups.setdefault(note.group, []).append(note)
        for group, notes in groups.items():
            cluster = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            cluster.add_css_class('cluster')
            breadcrumb = self.root.name + (' / ' + group.replace('/', ' / ') if group != '.' else ' /')
            cluster.append(label(breadcrumb, 'cluster-path', xalign=0, ellipsize=Pango.EllipsizeMode.MIDDLE))
            flow = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, column_spacing=4, row_spacing=3,
                               max_children_per_line=5, min_children_per_line=1, homogeneous=False)
            for note in notes:
                item = Gtk.Button(label=Path(note.path).stem, tooltip_text=f'{note.path}\n{note.title}')
                item.add_css_class('note')
                item.add_css_class(f'weight-{note.weight}')
                item.get_child().set_ellipsize(Pango.EllipsizeMode.END)
                item.get_child().set_max_width_chars(28)
                if self.document and self.document.relative == note.path:
                    item.add_css_class('selected')
                item.connect('clicked', lambda _, path=note.path: self.select(path))
                flow.append(item)
            cluster.append(flow)
            self.map_box.append(cluster)
        if not groups:
            self.map_box.append(label('No matching notes' if query else 'A little room to think.\nCreate your first Markdown note.',
                                      'dim-label', wrap=True, margin_top=20, margin_bottom=20))
        count = sum(len(group) for group in groups.values())
        self.note_count.set_text(f'{count} NOTES  ·  {len(groups)} CLUSTERS' + ('  ·  FIRST 500' if len(self.notes) == 500 else ''))

    def select(self, relative):
        if self.document and self.document.relative == relative:
            return
        self.save()
        self.stash()
        try:
            doc = Document(self.root, relative)
            cached = self.buffers.get(str(doc.path))
            doc, text, dirty = cached if cached and cached[2] else (doc, doc.load(), False)
            recovery = self.recovery_path(doc.path)
            if not dirty and recovery.exists():
                try:
                    saved = json.loads(recovery.read_text())
                    if saved['path'] == str(doc.path) and saved['text'] != text:
                        text, dirty = saved['text'], True
                        doc.digest = bytes.fromhex(saved.get('digest', '00'))
                except (OSError, ValueError, KeyError, TypeError):
                    pass
        except (OSError, ValueError, UnicodeError) as error:
            self.error(str(error))
            return
        self.document = doc
        self.loading = True
        self.buffer.set_text(text)
        self.buffer.set_modified(dirty)
        self.loading = False
        self.view.set_editable(True)
        self.file_label.set_text(relative.replace('/', ' / '))
        self.message.set_visible(False)
        self.status.set_text('Unsaved edits restored' if dirty else 'All changes saved')
        self.update_footer()
        self.render_map()

    def changed(self, *_):
        if self.loading or self.document is None:
            return
        self.buffer.set_modified(True)
        self.status.set_text('Editing…')
        self.update_footer()
        if self.save_source:
            GLib.source_remove(self.save_source)
        self.save_source = GLib.timeout_add(900, self.autosave)

    def autosave(self):
        self.save_source = 0
        self.save()
        return GLib.SOURCE_REMOVE

    def save(self):
        if self.save_source:
            GLib.source_remove(self.save_source)
            self.save_source = 0
        if self.document and self.buffer.get_modified():
            try:
                self.document.save(self.text())
                self.buffer.set_modified(False)
                self.buffers.pop(str(self.document.path), None)
                self.recovery_path(self.document.path).unlink(missing_ok=True)
                self.status.set_text('All changes saved')
                self.message.set_visible(False)
            except (OSError, ValueError) as error:
                self.error(str(error))
                self.stash()
                try:
                    self.persist_recovery()
                except OSError as recovery_error:
                    self.error(f'{error}\nRecovery copy failed: {recovery_error}. Keep this window open and save a copy.')
                return False
        return True

    def recovery_path(self, path):
        return Path(GLib.get_user_state_dir()) / 'cument' / 'recovery' / (hashlib.sha256(str(path).encode()).hexdigest() + '.json')

    def persist_recovery(self):
        directory = Path(GLib.get_user_state_dir()) / 'cument' / 'recovery'
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        for path, (document, text, dirty) in self.buffers.items():
            if dirty:
                target = self.recovery_path(path)
                descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
                with os.fdopen(descriptor, 'w') as stream:
                    json.dump({'path': path, 'text': text, 'digest': document.digest.hex() if document.digest else '00'}, stream)

    def error(self, text):
        self.message.set_text(text)
        self.message.set_visible(True)
        self.status.set_text('Needs attention · edits retained')
        return GLib.SOURCE_REMOVE

    def update_footer(self):
        iterator = self.buffer.get_iter_at_mark(self.buffer.get_insert())
        self.metrics.set_text(f'{len(self.text().split())} words   ·   {iterator.get_line()+1}:{iterator.get_line_offset()+1}   ·   Markdown')

    def check_disk(self):
        if self.get_visible() and self.document and not self.buffer.get_modified():
            try:
                fresh = Document(self.root, self.document.relative)
                text = fresh.load()
                if fresh.digest != self.document.digest:
                    cursor = self.buffer.get_property('cursor-position')
                    self.document = fresh
                    self.loading = True
                    self.buffer.set_text(text)
                    self.buffer.place_cursor(self.buffer.get_iter_at_offset(min(cursor, len(text))))
                    self.buffer.set_modified(False)
                    self.loading = False
                    self.status.set_text('Updated from disk')
            except (OSError, ValueError, UnicodeError) as error:
                self.error(str(error))
        return GLib.SOURCE_CONTINUE

    def new_note(self, copy=False):
        dialog = Adw.MessageDialog(transient_for=self, heading='Save a copy' if copy else 'New note',
                                   body='Give this note a path within your project.')
        entry = Gtk.Entry(placeholder_text='notes/idea.md', activates_default=True)
        dialog.set_extra_child(entry)
        dialog.add_response('cancel', 'Cancel')
        dialog.add_response('create', 'Create')
        dialog.set_response_appearance('create', Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response('create')
        def response(_, selected):
            if selected != 'create':
                return
            try:
                relative = entry.get_text().strip()
                if not relative:
                    raise ValueError('Enter a file name')
                if not Path(relative).suffix:
                    relative += '.md'
                doc = Document(self.root, relative)
                doc.save(self.text() if copy else '# ' + Path(relative).stem.replace('-', ' ').title() + '\n\n')
                self.select(relative)
                self.refresh()
            except (OSError, ValueError) as error:
                self.error(str(error))
        dialog.connect('response', response)
        dialog.present()

    def reload_note(self):
        if not self.document:
            return
        relative = self.document.relative
        def reload():
            self.buffers.pop(str(self.document.path), None)
            self.recovery_path(self.document.path).unlink(missing_ok=True)
            self.buffer.set_modified(False)
            self.document = None
            self.select(relative)
        if not self.buffer.get_modified():
            reload()
            return
        dialog = Adw.MessageDialog(transient_for=self, heading='Reload from disk?',
                                   body='This discards the unsaved edits in this note. You can save a copy first.')
        dialog.add_response('cancel', 'Keep editing')
        dialog.add_response('reload', 'Reload')
        dialog.set_response_appearance('reload', Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.connect('response', lambda _, answer: reload() if answer == 'reload' else None)
        dialog.present()

    def close_requested(self, *_):
        self.save()
        try:
            from .cli import call
            call('Close')
        except Exception:
            self.set_visible(False)
        return True


class Cument(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.window = None

    def do_startup(self):
        Adw.Application.do_startup(self)
        provider = Gtk.CssProvider()
        provider.load_from_data(STYLE.encode())
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), provider,
                                                  Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self.hold()

    def do_command_line(self, command):
        arguments = command.get_arguments()[1:]
        if '--hide' in arguments:
            if self.window:
                self.window.save()
                self.window.set_visible(False)
            return 0
        if self.window is None:
            self.window = Drawer(self)
        directory = arguments[arguments.index('--project') + 1] if '--project' in arguments else os.getcwd()
        try:
            self.window.set_project(directory)
            if '--background' not in arguments:
                self.window.present()
        except (OSError, ValueError) as error:
            self.window.error(str(error))
        return 0

    def do_shutdown(self):
        if self.window:
            self.window.save()
            self.window.stash()
            try:
                self.window.persist_recovery()
            except OSError as error:
                print(f'cument: recovery save failed: {error}', file=__import__('sys').stderr)
            self.window.pool.shutdown(wait=False, cancel_futures=True)
        Adw.Application.do_shutdown(self)


def run(args):
    return Cument().run(['cument-editor', '--project', args.project] +
                       (['--hide'] if args.hide else []) + (['--background'] if args.background else []))
