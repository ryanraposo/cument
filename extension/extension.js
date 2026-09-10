import Clutter from 'gi://Clutter';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import Meta from 'gi://Meta';
import Shell from 'gi://Shell';
import St from 'gi://St';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';

const APP_ID = 'io.github.ryanraposo.Cument';
const XML = `<node><interface name="org.gnome.Shell.Extensions.Cument">
 <method name="Toggle"><arg type="s" direction="in" name="directory"/></method>
 <method name="Open"><arg type="s" direction="in" name="directory"/></method>
 <method name="Close"/>
 <method name="Context"><arg type="s" direction="in" name="directory"/><arg type="i" direction="in" name="pid"/></method>
 <method name="Status"><arg type="s" direction="out" name="status"/></method>
</interface></node>`;

export default class Cument extends Extension {
    enable() {
        this._settings = this.getSettings();
        this._interface = new Gio.Settings({schema_id: 'org.gnome.desktop.interface'});
        this._contexts = new Map();
        this._sources = new Set();
        this._signals = [];
        this._open = false;
        this._project = this._settings.get_string('project') || GLib.get_home_dir();
        this._earmark = new St.Button({style_class: 'cument-earmark', reactive: true,
            can_focus: true, track_hover: true, accessible_name: 'Toggle cument drawer'});
        this._label = new St.Label({text: 'cument'});
        this._earmark.set_child(this._label);
        this._earmark.connect('clicked', () => this.Toggle(''));
        Main.layoutManager.addChrome(this._earmark, {affectsStruts: false, trackFullscreen: true});
        this._signals.push([this._interface, this._interface.connect('changed', () => this._theme())]);
        this._signals.push([this._settings, this._settings.connect('changed::drawer-width', () => this._layout())]);
        this._signals.push([Main.layoutManager, Main.layoutManager.connect('monitors-changed', () => this._layout())]);
        this._signals.push([global.display, global.display.connect('workareas-changed', () => this._layout())]);
        this._signals.push([global.display, global.display.connect('notify::focus-window', () => this._focus())]);
        this._signals.push([global.display, global.display.connect('window-created', (_display, window) => {
            if (this._isEditor(window)) {
                const actor = window.get_compositor_private();
                if (actor) Main.wm.skipNextEffect(actor);
                this._signals.push([window, window.connect('unmanaged', () => {
                    if (this._window === window) this._window = null;
                })]);
            }
        })]);
        this._signals.push([global.window_manager, global.window_manager.connect('map', (_wm, actor) => {
            if (this._isEditor(actor.meta_window)) {
                this._window = actor.meta_window;
                this._layout();
                if (this._open) this._animate(true);
                else this._launch(true);
            }
        })]);
        this._signals.push([Main.overview, Main.overview.connect('showing', () => this._earmark.hide())]);
        this._signals.push([Main.overview, Main.overview.connect('hidden', () => this._earmark.show())]);
        this._dbus = Gio.DBusExportedObject.wrapJSObject(XML, this);
        this._dbus.export(Gio.DBus.session, '/org/gnome/Shell/Extensions/Cument');
        Main.wm.addKeybinding('toggle-shortcut', this._settings, Meta.KeyBindingFlags.NONE,
            Shell.ActionMode.NORMAL, () => this.Toggle(''));
        this._theme();
        this._layout();
        this._focus();
        console.log('cument: drawer enabled');
    }

    _isEditor(window) {
        return window && window.get_window_type() === Meta.WindowType.NORMAL &&
            (window.get_gtk_application_id() === APP_ID || window.get_wm_class() === APP_ID);
    }

    _later(delay, callback) {
        const id = GLib.timeout_add(GLib.PRIORITY_DEFAULT, delay, () => {
            this._sources.delete(id);
            callback();
            return GLib.SOURCE_REMOVE;
        });
        this._sources.add(id);
        return id;
    }

    _theme() {
        const dark = this._interface.get_string('color-scheme') === 'prefer-dark';
        // Shell inherits GNOME's UI font. Semantic light/dark follows the interface setting.
        this._earmark.set_style(`background-color: ${dark ? '#242424' : '#fafafa'}; color: ${dark ? '#eeeeec' : '#303030'};`);
    }

    _layout() {
        const monitor = this._monitor ?? Main.layoutManager.primaryIndex;
        const index = Main.layoutManager.monitors[monitor] ? monitor : Main.layoutManager.primaryIndex;
        if (index < 0) return;
        const area = Main.layoutManager.getWorkAreaForMonitor(index);
        const width = Math.min(this._settings.get_int('drawer-width'), Math.floor(area.width * .65));
        this._width = width;
        const name = GLib.path_get_basename(this._project);
        this._label.set_text(name.length > 24 ? `${name.slice(0, 23)}…` : name);
        // Rotate the entire hit target: its text reads bottom to top.
        const length = Math.max(110, Math.min(220, name.length * 8 + 38));
        this._earmark.set_size(length, 32);
        this._earmark.set_pivot_point(.5, .5);
        this._earmark.rotation_angle_z = -90;
        const edge = area.x + area.width - (this._open ? width : 0);
        const x = edge - 16 - length / 2;
        const y = area.y + Math.round(area.height / 3) + length / 2 - 16;
        if (this._positioned && this._interface.get_boolean('enable-animations'))
            this._earmark.ease({x, y, duration: 280, mode: Clutter.AnimationMode.EASE_OUT_CUBIC});
        else this._earmark.set_position(x, y);
        this._positioned = true;
        if (this._window && this._window.get_compositor_private()) {
            this._window.unmaximize();
            this._window.move_to_monitor(index);
            this._window.move_resize_frame(false, area.x + area.width - width, area.y, width, area.height);
            if (this._open) this._window.make_above();
        }
    }

    _focus() {
        if (this._watched && this._titleSignal) {
            try { this._watched.disconnect(this._titleSignal); } catch (_) { /* window gone */ }
        }
        this._watched = global.display.focus_window;
        this._titleSignal = 0;
        if (!this._watched || this._watched.get_gtk_application_id() === APP_ID) return;
        this._lastWindow = this._watched;
        this._titleSignal = this._watched.connect('notify::title', () => this._followTitle());
        this._followTitle();
    }

    _followTitle() {
        const title = this._watched?.get_title() ?? '';
        const match = title.match(/cument:(\d+)/);
        if (match && this._contexts.has(Number(match[1]))) {
            this._setProject(this._contexts.get(Number(match[1])));
        }
    }

    _setProject(directory) {
        if (!directory || !GLib.file_test(directory, GLib.FileTest.IS_DIR)) return;
        const changed = directory !== this._project;
        this._project = directory;
        this._settings.set_string('project', directory);
        this._layout();
        if (changed && this._open) this._launch(false, true);
    }

    Context(directory, pid) {
        if (!GLib.file_test(directory, GLib.FileTest.IS_DIR) || pid <= 0) return;
        this._contexts.delete(pid);
        this._contexts.set(pid, directory);
        if (this._contexts.size > 128) this._contexts.delete(this._contexts.keys().next().value);
        const title = global.display.focus_window?.get_title() ?? '';
        if (title.match(/cument:(\d+)/)?.[1] === String(pid) || this._contexts.size === 1)
            this._setProject(directory);
    }

    _launch(hide = false, background = false) {
        // Development checkout and packaged install share exactly the same entrypoint.
        const local = GLib.build_filenamev([this.path, '..', 'bin', 'cument']);
        const executable = GLib.file_test(local, GLib.FileTest.IS_EXECUTABLE) ? local : 'cument';
        const args = [executable, '_editor', '--project', this._project];
        if (hide) args.push('--hide');
        if (background) args.push('--background');
        try {
            const process = Gio.Subprocess.new(args, Gio.SubprocessFlags.NONE);
            process.wait_check_async(null, (proc, result) => {
                try { proc.wait_check_finish(result); }
                catch (error) { console.error(`cument: ${error.message}`); }
            });
        } catch (error) {
            Main.notify('cument', `Could not start the editor: ${error.message}`);
            this._open = false;
            this._layout();
        }
    }

    Toggle(directory) { this._open ? this.Close() : this.Open(directory); }

    Open(directory) {
        this._monitor = this._lastWindow?.get_monitor() ?? Main.layoutManager.primaryIndex;
        this._setProject(directory);
        this._open = true;
        this._launch();
        this._layout();
        if (this._window?.get_compositor_private()) this._animate(true);
    }

    _animate(open) {
        const actor = this._window?.get_compositor_private();
        if (!actor) return;
        actor.remove_all_transitions();
        const duration = this._interface.get_boolean('enable-animations') ? 280 : 0;
        if (open) {
            actor.translation_x = this._width;
            actor.opacity = 0;
            actor.ease({translation_x: 0, opacity: 255, duration, mode: Clutter.AnimationMode.EASE_OUT_CUBIC});
            this._window.activate(global.get_current_time());
        } else {
            actor.ease({translation_x: this._width, opacity: 0, duration,
                mode: Clutter.AnimationMode.EASE_IN_CUBIC,
                onComplete: () => {
                    if (this._open) return;
                    this._launch(true);
                    this._window?.unmake_above();
                    if (this._lastWindow?.get_compositor_private())
                        this._lastWindow.activate(global.get_current_time());
                }});
        }
    }

    Close() {
        if (!this._open) return;
        this._open = false;
        this._animate(false);
        this._layout();
    }

    Status() {
        return JSON.stringify({open: this._open, project: this._project, contexts: this._contexts.size});
    }

    disable() {
        Main.wm.removeKeybinding('toggle-shortcut');
        this._dbus?.unexport();
        this._dbus = null;
        if (this._watched && this._titleSignal) {
            try { this._watched.disconnect(this._titleSignal); } catch (_) { /* window gone */ }
        }
        for (const [object, id] of this._signals ?? []) {
            try { object.disconnect(id); } catch (_) { /* window already gone */ }
        }
        for (const id of this._sources ?? []) GLib.source_remove(id);
        const actor = this._window?.get_compositor_private();
        if (actor) {
            actor.remove_all_transitions();
            actor.translation_x = 0;
            actor.opacity = 255;
            this._window.unmake_above();
        }
        if (this._open) this._launch(true);
        this._earmark?.destroy();
        this._earmark = null;
        this._window = null;
        this._contexts = null;
        this._signals = [];
        this._settings = null;
        this._interface = null;
        console.log('cument: drawer disabled');
    }
}
