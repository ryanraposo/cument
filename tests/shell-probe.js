// Test-only extension, staged solely inside the disposable test compositor.
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import Shell from 'gi://Shell';
import Clutter from 'gi://Clutter';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
const XML = `<node><interface name="io.github.ryanraposo.Cument.Test">
 <method name="Inspect"><arg type="s" direction="out"/></method>
 <method name="Capture"><arg type="s" direction="in"/><arg type="b" direction="out"/></method>
 <method name="Prepare"/>
 <method name="Shortcut"/>
 <method name="Click"/>
 <method name="Focus"><arg type="i" direction="in"/></method>
</interface></node>`;
export default class Probe extends Extension {
    enable() {
        this.object = Gio.DBusExportedObject.wrapJSObject(XML, this);
        this.object.export(Gio.DBus.session, '/io/github/ryanraposo/Cument/Test');
    }
    Prepare() { Main.overview.hide(); }
    Shortcut() {
        this.keyboard ??= Clutter.get_default_backend().get_default_seat().create_virtual_device(Clutter.InputDeviceType.KEYBOARD_DEVICE);
        for (const key of [Clutter.KEY_Alt_L, Clutter.KEY_Shift_L, Clutter.KEY_backslash])
            this.keyboard.notify_keyval(GLib.get_monotonic_time(), key, Clutter.KeyState.PRESSED);
        for (const key of [Clutter.KEY_backslash, Clutter.KEY_Shift_L, Clutter.KEY_Alt_L])
            this.keyboard.notify_keyval(GLib.get_monotonic_time(), key, Clutter.KeyState.RELEASED);
    }
    Click() { Extension.lookupByUUID('cument@ryanraposo.github.io')._earmark.emit('clicked', 1); }
    Focus(pid) {
        const window = global.get_window_actors().map(a => a.meta_window).find(w => w.get_title().endsWith(`cument:${pid}`));
        window.activate(global.get_current_time());
    }
    Inspect() {
        const extension = Extension.lookupByUUID('cument@ryanraposo.github.io');
        return JSON.stringify({status: extension?.Status(),
            earmark: extension?._earmark?.get_transformed_position(),
            focus: global.display.focus_window?.get_title(),
            windows: global.get_window_actors().filter(a => a.meta_window.get_gtk_application_id() === 'io.github.ryanraposo.Cument')
                .map(a => { const r = a.meta_window.get_frame_rect(); return {title:a.meta_window.get_title(), rect:[r.x,r.y,r.width,r.height],
                    visible:a.visible, opacity:a.opacity, translation:a.translation_x, scale:a.scale_x}; })});
    }
    async CaptureAsync([filename], invocation) {
        try {
            const stream = Gio.File.new_for_path(filename).replace(null, false, Gio.FileCreateFlags.NONE, null);
            await new Shell.Screenshot().screenshot(false, stream);
            stream.close(null);
            invocation.return_value(new GLib.Variant('(b)', [true]));
        } catch (error) { invocation.return_dbus_error('io.github.ryanraposo.Cument.Test.Error', error.message); }
    }
    disable() { this.object.unexport(); }
}
