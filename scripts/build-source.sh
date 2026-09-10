#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p dist
stage=$(mktemp -d)
trap 'rm -rf "$stage"' EXIT
destination="$PWD/dist"
mkdir "$stage/cument-0.1.0"
tar --exclude='./.git' --exclude='./dist' --exclude='./build' --exclude='./debian/cument' --exclude='./debian/.debhelper' --exclude='./debian/files' --exclude='./debian/debhelper-build-stamp' --exclude='*.substvars' --exclude='*.debhelper*' --exclude='__pycache__' --exclude='*.pyc' --exclude='gschemas.compiled' -cf - . | tar -xf - -C "$stage/cument-0.1.0"
tar --sort=name --mtime='2026-09-10 00:00:00Z' --owner=0 --group=0 --numeric-owner --exclude='cument-0.1.0/debian' -czf "$stage/cument_0.1.0.orig.tar.gz" -C "$stage" cument-0.1.0
cd "$stage"
dpkg-source -b cument-0.1.0
cp cument_*.tar.* cument_*.dsc "$destination/"
