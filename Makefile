PREFIX ?= /usr
DESTDIR ?=
UUID = cument@ryanraposo.github.io

.PHONY: all test install clean deb source
all:
	glib-compile-schemas --strict extension/schemas

test: all
	/usr/bin/python3 -m unittest discover -s tests -v
	/usr/bin/python3 -m py_compile nautilus/cument_context.py

install: all
	install -d $(DESTDIR)$(PREFIX)/lib/cument/cument $(DESTDIR)$(PREFIX)/bin
	install -m644 cument/*.py $(DESTDIR)$(PREFIX)/lib/cument/cument/
	install -m755 bin/cument $(DESTDIR)$(PREFIX)/bin/cument
	install -d $(DESTDIR)$(PREFIX)/share/gnome-shell/extensions/$(UUID)/schemas
	install -m644 extension/extension.js extension/metadata.json extension/stylesheet.css $(DESTDIR)$(PREFIX)/share/gnome-shell/extensions/$(UUID)/
	install -m644 extension/schemas/*xml extension/schemas/gschemas.compiled $(DESTDIR)$(PREFIX)/share/gnome-shell/extensions/$(UUID)/schemas/
	install -d $(DESTDIR)$(PREFIX)/share/cument/shell $(DESTDIR)$(PREFIX)/share/applications $(DESTDIR)$(PREFIX)/share/icons/hicolor/scalable/apps
	install -m644 shell/* $(DESTDIR)$(PREFIX)/share/cument/shell/
	install -d $(DESTDIR)$(PREFIX)/share/nautilus-python/extensions
	install -m644 nautilus/cument_context.py $(DESTDIR)$(PREFIX)/share/nautilus-python/extensions/cument_context.py
	install -m644 data/io.github.ryanraposo.Cument.desktop $(DESTDIR)$(PREFIX)/share/applications/
	install -m644 data/io.github.ryanraposo.Cument.svg $(DESTDIR)$(PREFIX)/share/icons/hicolor/scalable/apps/
	install -d $(DESTDIR)$(PREFIX)/share/man/man1
	install -m644 data/cument.1 $(DESTDIR)$(PREFIX)/share/man/man1/

deb:
	/usr/bin/python3 scripts/build-deb.py

source:
	./scripts/build-source.sh

clean:
	find cument nautilus tests -type d -name __pycache__ -exec rm -rf {} +
	rm -f extension/schemas/gschemas.compiled
