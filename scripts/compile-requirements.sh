#!/usr/bin/env bash
# Regenerate requirements.txt and requirements-dev.txt from the .in files, hash-pinned.
# Needs uv (pip install uv, in a throwaway venv). Run from the repo root: scripts/compile-requirements.sh
set -euo pipefail
cd "$(dirname "$0")/.."

read -r -d '' EXPLANATION <<'TEXT' || true
#
# HOW TO READ THIS FILE (for reviewers)
#
# Generated lockfile: do not edit by hand. Change the .in file next to it and run scripts/compile-requirements.sh.
#
# Every package, direct or transitive, is pinned to one version with ==.
#
# Why several --hash lines per package: PyPI holds many files for one version (one wheel per operating system,
# CPU type and Python version, plus the source archive), and each file has its own SHA-256 hash. The file lists the
# hash of every one of them, so it works on CI (Linux, Python 3.12) and on a laptop (for example macOS, Python 3.13)
# alike. When installing, pip picks the one file that fits the machine and refuses to install it unless its hash is
# in this list. The other hashes stay unused on that machine. Pure-Python packages have few hashes; packages with
# compiled code (pydantic-core, jiter, lxml) have many.
#
# What the hashes do and do not prove: a changed or swapped file is rejected. They do not show a package is safe;
# they show it is the same file that PyPI served when this file was generated. Review the diff of this file in
# every pull request that regenerates it.
#
TEXT

compile() {  # compile <input .in> <output .txt>
    local tmp
    tmp="$(mktemp)"
    uv pip compile "$1" --universal --python-version 3.12 --generate-hashes \
        --custom-compile-command "scripts/compile-requirements.sh" -o "$tmp" >/dev/null
    { printf '%s\n' "$EXPLANATION"; cat "$tmp"; } > "$2"
    rm -f "$tmp"
}

compile requirements.in requirements.txt
compile requirements-dev.in requirements-dev.txt
