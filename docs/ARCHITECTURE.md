# Architecture

The CLI discovers project roots and publishes context over the current user's session bus. Shell hooks send a project path and shell PID at each prompt. A tiny Nautilus-Python provider publishes each local folder visit through the same path, and the newest terminal or Files event becomes the active project. Terminal titles carry the PID so focusing a known terminal can reassert that terminal's current project. No environment variables, command history, document content or credentials are transmitted.

The GNOME Shell extension owns a small chrome actor at one-third of the right edge, the Alt+bar binding and a D-Bus interface at `/org/gnome/Shell/Extensions/Cument`. It positions only the matching `io.github.ryanraposo.Cument` application window, applies compositor translations, and returns focus after closing. It does not reserve desktop space. GNOME controls session locking and extension lifetime.

The GTK application remains alive when hidden. GtkSourceView provides Markdown syntax highlighting and undo. A worker indexes the filesystem; generation IDs discard outdated results when projects change quickly. Files are opened only within the selected root. In-memory buffers retain conflicting edits across note and project changes. Atomic replacement preserves file permissions and CRLF, and checks content hashes before save; failed saves are also copied into private recovery files.

The extension targets GNOME 50. Its metadata and package dependency intentionally reject other major versions until tested. All GUI state stays outside the Shell except edge chrome and window positioning. This keeps document editing out of the compositor process.
