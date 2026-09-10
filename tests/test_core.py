import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from cument.core import ConflictError, Document, discover, project_root


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.addCleanup(self.temporary.cleanup)

    def write(self, path, text):
        file = self.root / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(text)
        return file

    def test_discovery_clusters_and_ignores(self):
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        self.write('.gitignore', 'private/\n')
        self.write('README.md', '# Hello\n')
        self.write('docs/design.md', '# Design\n')
        self.write('private/secret.md', '# Hidden\n')
        self.write('node_modules/ignored.md', '# Hidden\n')
        notes = discover(self.root)
        self.assertEqual([n.path for n in notes], ['README.md', 'docs/design.md'])
        self.assertEqual(notes[1].group, 'docs')
        self.assertGreater(notes[0].weight, notes[1].weight)

    def test_root_from_subdirectory(self):
        self.write('pyproject.toml', '')
        path = self.root / 'src/deep'
        path.mkdir(parents=True)
        self.assertEqual(project_root(path), self.root)

    def test_atomic_save_preserves_mode_and_newlines(self):
        file = self.write('note.md', '')
        file.write_bytes(b'# Note\r\nHello\r\n')
        file.chmod(0o640)
        doc = Document(self.root, 'note.md')
        self.assertEqual(doc.load(), '# Note\nHello\n')
        doc.save('# Note\nUpdated\n')
        self.assertEqual(file.read_bytes(), b'# Note\r\nUpdated\r\n')
        self.assertEqual(file.stat().st_mode & 0o777, 0o640)
        self.assertFalse(list(self.root.glob('.cument-*')))

    def test_conflict_never_overwrites(self):
        file = self.write('note.md', 'before')
        doc = Document(self.root, 'note.md')
        doc.load()
        file.write_text('external')
        with self.assertRaises(ConflictError):
            doc.save('mine')
        self.assertEqual(file.read_text(), 'external')

    def test_deleted_file_is_conflict(self):
        file = self.write('note.md', 'before')
        doc = Document(self.root, 'note.md')
        doc.load()
        file.unlink()
        with self.assertRaises(ConflictError):
            doc.save('mine')

    def test_new_document_does_not_replace_existing(self):
        self.write('note.md', 'existing')
        with self.assertRaises(ConflictError):
            Document(self.root, 'note.md').save('replacement')

    def test_new_nested_document(self):
        Document(self.root, 'notes/new.md').save('# New\n')
        self.assertEqual((self.root / 'notes/new.md').read_text(), '# New\n')

    def test_reject_escape_and_symlink(self):
        with self.assertRaises(ValueError):
            Document(self.root, '../escape.md')
        self.write('real.md', 'text')
        (self.root / 'link.md').symlink_to(self.root / 'real.md')
        with self.assertRaises(ValueError):
            Document(self.root, 'link.md')
        self.assertEqual([n.path for n in discover(self.root)], ['real.md'])

    def test_binary_and_oversize(self):
        file = self.write('note.md', '\x00')
        with self.assertRaises(ValueError):
            Document(self.root, 'note.md').load()
        file.write_bytes(b'x' * (4 * 1024 * 1024 + 1))
        with self.assertRaises(ValueError):
            Document(self.root, 'note.md').load()

    def test_unicode_paths(self):
        self.write('notes/考え.md', '# pensée')
        doc = Document(self.root, 'notes/考え.md')
        self.assertEqual(doc.load(), '# pensée')
        doc.save('café ☕')
        self.assertEqual(doc.load(), 'café ☕')
