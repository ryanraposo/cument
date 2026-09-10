"""Filesystem operations, deliberately independent of GTK and the session bus."""
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile

EXCLUDED = {'.git', '.hg', '.svn', 'node_modules', 'vendor', '.venv', 'venv',
            '__pycache__', 'dist', 'build', '.cache', '.tox'}
MAX_BYTES = 4 * 1024 * 1024


def project_root(directory):
    path = Path(directory).expanduser().resolve(strict=True)
    if path.is_file():
        path = path.parent
    try:
        result = subprocess.run(['git', '-C', str(path), 'rev-parse', '--show-toplevel'],
                                capture_output=True, text=True, timeout=2)
        if result.returncode == 0:
            return Path(result.stdout.strip()).resolve()
    except (OSError, subprocess.TimeoutExpired):
        pass
    for parent in (path, *path.parents):
        if any((parent / marker).exists() for marker in
               ('pyproject.toml', 'package.json', 'Cargo.toml', 'meson.build', '.cument')):
            return parent
    return path


def confined(root, relative):
    """Reject escapes, including symlinks, before reading or writing a document."""
    root = Path(root).resolve()
    candidate = root / relative
    resolved = candidate.resolve()
    resolved.relative_to(root)
    if any(p.is_symlink() for p in (candidate, *candidate.parents) if p != root and root in p.parents):
        raise ValueError('Symbolic links are not editable in cument')
    if resolved.suffix.lower() not in ('.md', '.markdown'):
        raise ValueError('Choose a .md or .markdown file')
    return resolved


@dataclass(frozen=True)
class Note:
    path: str
    title: str
    group: str
    weight: int


def discover(root, limit=500):
    root = Path(root).resolve()
    candidates = None
    try:
        result = subprocess.run(['git', '-C', str(root), 'ls-files', '-z', '--cached',
                                 '--others', '--exclude-standard'], capture_output=True, timeout=5)
        if result.returncode == 0:
            candidates = [os.fsdecode(p) for p in result.stdout.split(b'\0') if p]
    except (OSError, subprocess.TimeoutExpired):
        pass
    if candidates is None:
        candidates = []
        for parent, directories, files in os.walk(root, followlinks=False):
            directories[:] = sorted(d for d in directories if d not in EXCLUDED and not d.startswith('.')
                                    and not (Path(parent) / d).is_symlink())
            candidates.extend(str((Path(parent) / f).relative_to(root)) for f in files
                              if Path(f).suffix.lower() in ('.md', '.markdown'))
            if len(candidates) >= limit * 4:
                break
    notes = []
    for relative in sorted(set(candidates), key=lambda p: (p.count('/'), p.casefold())):
        if Path(relative).suffix.lower() not in ('.md', '.markdown'):
            continue
        if any(part in EXCLUDED for part in Path(relative).parts):
            continue
        try:
            path = confined(root, relative)
            if not path.is_file() or path.stat().st_size > MAX_BYTES:
                continue
            with path.open(encoding='utf-8') as stream:
                start = stream.read(4096)
            title = next((line.lstrip('#').strip() for line in start.splitlines()
                          if line.startswith('# ')), path.stem.replace('-', ' '))
            group = str(Path(relative).parent)
            weight = 3 if path.name.lower() == 'readme.md' else (2 if group == '.' else 1)
            notes.append(Note(relative, title[:90], group, weight))
        except (OSError, UnicodeError, ValueError):
            continue
        if len(notes) >= limit:
            break
    return notes


class ConflictError(OSError):
    pass


class Document:
    def __init__(self, root, relative):
        self.root, self.relative = Path(root).resolve(), relative
        self.path = confined(root, relative)
        self.digest = None
        self.newline = '\n'

    def load(self):
        self.path = confined(self.root, self.relative)
        with self.path.open('rb') as stream:
            raw = stream.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError('This file exceeds the 4 MiB editor limit')
        text = raw.decode('utf-8')
        if '\x00' in text:
            raise ValueError('This file contains binary data')
        self.digest = hashlib.sha256(raw).digest()
        self.newline = '\r\n' if b'\r\n' in raw else '\n'
        return text.replace('\r\n', '\n')

    def save(self, text):
        path = confined(self.root, self.relative)
        try:
            current = path.read_bytes()
        except FileNotFoundError:
            current = None
        if self.digest is None:
            if current is not None:
                raise ConflictError('A file already exists at this path')
        elif current is None or hashlib.sha256(current).digest() != self.digest:
            raise ConflictError('Changed on disk. Your edits are kept here; reload or save a copy.')
        raw = text.replace('\n', self.newline).encode('utf-8')
        if len(raw) > MAX_BYTES:
            raise ValueError('This document exceeds the 4 MiB editor limit')
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix='.cument-', dir=path.parent)
        try:
            with os.fdopen(descriptor, 'wb') as stream:
                if current is not None:
                    os.fchmod(stream.fileno(), path.stat().st_mode & 0o777)
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            # Recheck after writing the temporary file to narrow the conflict window.
            now = path.read_bytes() if path.exists() else None
            if now != current:
                raise ConflictError('Changed on disk while saving; your edits are kept here')
            os.replace(temporary, path)
            directory = os.open(path.parent, os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
            self.digest = hashlib.sha256(raw).digest()
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
