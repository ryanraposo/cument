# Release validation — 0.1.0

Test environment: Ubuntu 26.04.1 LTS, GNOME Shell 50.1, native Wayland compositor; GTK 4 / libadwaita / GtkSourceView 5.

- Ten filesystem tests: Git ignores and directory clustering, project roots, CRLF and mode preservation, conflicts, externally deleted files, refusal to replace an existing note, nested creation, traversal/symlink rejection, binary/oversize rejection, Unicode paths.
- GTK interaction test: initial discovery and selection, autosave to disk, externally modified file conflict, retention across note switches, recovery in a fresh editor window, file map search, rendered screenshot inspection.
- Isolated GNOME Wayland test: extension ACTIVE, exact 580 × 968 drawer at x=860/y=32 on a 1440 × 1000 monitor, Alt+Shift+backslash, earmark click, close and reopen, two terminal contexts, newest terminal-or-Nautilus context wins, terminal focus can reassert its known context, focus restoration, extension INACTIVE after cleanup.
- Standard `dpkg-buildpackage -us -uc -b` succeeds. Lintian on the generated binary `.changes` reports no errors or warnings.

The terminal test uses native GTK fixture windows carrying shell IDs and the real context CLI; it verifies compositor routing rather than a particular terminal emulator. Bash syntax is checked. Zsh, Fish, terminal multiplexers and SSH remain manual compatibility checks. Only GNOME 50 is declared supported. PPA publication and official Ubuntu archive admission are separate from these local checks.
