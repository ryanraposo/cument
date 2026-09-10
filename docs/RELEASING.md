# Release cument

Maintainer: Ryan Raposo <raposo.ryan@gmail.com>
GitHub: https://github.com/ryanraposo/cument
Launchpad owner: https://launchpad.net/~ryanraposo
Planned PPA: `ppa:ryanraposo/cument`
Initial target: Ubuntu **resolute (26.04)**, GNOME 50, architecture `all`.

## Local artifacts

`make test && make deb` creates `dist/cument_0.1.0-1ppa1_all.deb` without root or network. `make source` creates the upstream tarball, Debian delta and unsigned `.dsc`. The local builder uses the same `make install` payload as debhelper.

For the full Launchpad upload set:

```sh
sudo apt install build-essential debhelper devscripts dput lintian
make source
cd dist
dpkg-source -x cument_0.1.0-1ppa1.dsc cument-0.1.0
cd cument-0.1.0
debuild -S -sa -kYOUR_REGISTERED_GPG_FINGERPRINT
lintian ../cument_0.1.0-1ppa1_source.changes
```

Use a GPG signing key registered to Ryan's Launchpad account. Unlock it locally through the GPG agent; never paste private keys or passwords into chat, source control or CI logs. If no suitable key exists, create one locally with `gpg --full-generate-key`, register its **public** fingerprint with Launchpad, and complete the email verification.

## Publish

Create the public `cument` PPA under the `ryanraposo` Launchpad account. Review the package metadata, GPL license and upload artifact checksums, then upload the signed **source** changes (not the local binary):

```sh
dput ppa:ryanraposo/cument dist/cument_0.1.0-1ppa1_source.changes
```

Launchpad builds binaries and signs the repository. Wait for a successful build and published package before advertising the apt install command. Every accepted upload needs a new version, including packaging-only fixes. GitHub should contain the matching source tag and checksum-listed `.deb` release asset.

Official Ubuntu archive inclusion requires a new-package review and sponsorship; a PPA does not automatically enter the official archive. No archive submission or reviewer email is sent by the build scripts.

References: [Ubuntu PPA upload guide](https://documentation.ubuntu.com/project/contributors/new-package/upload-packages-to-a-ppa/), [Launchpad PPA requirements](https://documentation.ubuntu.com/launchpad/user/reference/packaging/ppas/ppa/), [Debian maintainer introduction](https://mentors.debian.net/intro-maintainers/).
