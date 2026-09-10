#!/usr/bin/python3
"""Build a local binary package without needing root or debhelper."""
from pathlib import Path
import gzip
import os
import shutil
import subprocess
import tempfile

root = Path(__file__).resolve().parent.parent
output = root / 'dist'
output.mkdir(exist_ok=True)
version = '0.1.0-1ppa1'
with tempfile.TemporaryDirectory(prefix='cument-deb-') as temporary:
    stage = Path(temporary)
    subprocess.run(['make', 'install', f'DESTDIR={stage}', 'PREFIX=/usr'], cwd=root, check=True)
    control_dir = stage / 'DEBIAN'
    control_dir.mkdir()
    control = (root / 'debian/control').read_text().split('\n\nPackage: ', 1)[1]
    control = 'Package: ' + control
    control = control.replace('${misc:Depends}, ', '')
    control += f'Version: {version}\nMaintainer: Ryan Raposo <raposo.ryan@gmail.com>\nSection: gnome\nPriority: optional\n'
    (control_dir / 'control').write_text(control)
    docs = stage / 'usr/share/doc/cument'
    docs.mkdir(parents=True)
    shutil.copy(root / 'debian/copyright', docs)
    shutil.copy(root / 'README.md', docs)
    for source, target in [(root / 'debian/changelog', docs / 'changelog.Debian.gz'),
                           (stage / 'usr/share/man/man1/cument.1', stage / 'usr/share/man/man1/cument.1.gz')]:
        target.write_bytes(gzip.compress(source.read_bytes(), mtime=0))
    (stage / 'usr/share/man/man1/cument.1').unlink()
    epoch = int(os.environ.get('SOURCE_DATE_EPOCH', '1788998400'))
    for path in sorted(stage.rglob('*'), reverse=True):
        path.chmod(0o755 if path.is_dir() or path == stage / 'usr/bin/cument' else 0o644)
        os.utime(path, (epoch, epoch))
    os.utime(stage, (epoch, epoch))
    subprocess.run(['dpkg-deb', '--root-owner-group', '--build', str(stage),
                    str(output / f'cument_{version}_all.deb')], check=True,
                   env={**os.environ, 'SOURCE_DATE_EPOCH': str(epoch)})
