#!/usr/bin/env python3
"""Build a PEP 427-compliant wheel and an sdist for check-proxy-tax without external build tools.

Outputs:
  dist/check_proxy_tax-1.0.0-py3-none-any.whl
  dist/check_proxy_tax-1.0.0.tar.gz

Only the Python standard library is used, so the artifact is reproducible on any machine.
"""
import base64
import hashlib
import os
import shutil
import tarfile
import zipfile

NAME = "check_proxy_tax"
DIST = "check-proxy-tax"
VERSION = "1.0.0"
ROOT = os.path.dirname(os.path.abspath(__file__))
DIST_DIR = os.path.join(ROOT, "dist")
PKG_DIR = os.path.join(ROOT, "check_proxy_tax")

SUMMARY = ("Zero-dependency CLI that audits real proxy and anti-bot cost: usable rate, "
           "p50/p95 latency, bytes billed and effective price per 1,000 usable requests.")

CLASSIFIERS = [
    "Development Status :: 5 - Production/Stable",
    "Environment :: Console",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Operating System :: OS Independent",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3 :: Only",
    "Programming Language :: Python :: 3.8",
    "Programming Language :: Python :: 3.9",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Topic :: Internet :: WWW/HTTP",
    "Topic :: System :: Networking",
    "Topic :: Utilities",
]


def read(path):
    with open(os.path.join(ROOT, path), encoding="utf-8") as fh:
        return fh.read()


def metadata():
    readme = read("README.md")
    lines = [
        "Metadata-Version: 2.1",
        "Name: %s" % DIST,
        "Version: %s" % VERSION,
        "Summary: %s" % SUMMARY,
        "Home-page: https://github.com/600me/check-proxy-tax",
        "Author: Kais / 600me",
        "License: MIT",
        "Project-URL: Homepage, https://github.com/600me/check-proxy-tax",
        "Project-URL: Repository, https://github.com/600me/check-proxy-tax",
        "Project-URL: Issues, https://github.com/600me/check-proxy-tax/issues",
        "Project-URL: Benchmark, https://scrape.mybskm.top/?utm_source=cli&utm_content=check-proxy-tax",
        "Keywords: proxy,scraping,benchmark,http,cost,cli",
        "Requires-Python: >=3.8",
        "Description-Content-Type: text/markdown",
    ]
    lines += ["Classifier: %s" % c for c in CLASSIFIERS]
    lines.append("License-File: LICENSE")
    return "\n".join(lines) + "\n\n" + readme


WHEEL = """Wheel-Version: 1.0
Generator: check-proxy-tax-build (stdlib)
Root-Is-Purelib: true
Tag: py3-none-any
"""

ENTRY_POINTS = """[console_scripts]
check-proxy-tax = check_proxy_tax.cli:main
"""


def record_hash(data):
    digest = hashlib.sha256(data).digest()
    return "sha256=" + base64.urlsafe_b64encode(digest).decode().rstrip("=")


def build_wheel():
    os.makedirs(DIST_DIR, exist_ok=True)
    whl = os.path.join(DIST_DIR, "%s-%s-py3-none-any.whl" % (NAME, VERSION))
    distinfo = "%s-%s.dist-info" % (NAME, VERSION)
    entries = []
    for fname in sorted(os.listdir(PKG_DIR)):
        if fname.endswith(".py"):
            entries.append((NAME + "/" + fname, os.path.join(PKG_DIR, fname)))
    generated = {
        distinfo + "/METADATA": metadata().encode(),
        distinfo + "/WHEEL": WHEEL.encode(),
        distinfo + "/entry_points.txt": ENTRY_POINTS.encode(),
        distinfo + "/LICENSE": read("LICENSE").encode(),
    }
    payload = []
    for arc, src in entries:
        with open(src, "rb") as fh:
            payload.append((arc, fh.read()))
    payload += sorted(generated.items())

    lines = []
    for arc, data in payload:
        lines.append("%s,%s,%d" % (arc, record_hash(data), len(data)))
    lines.append("%s/RECORD,," % distinfo)
    record = ("\n".join(lines) + "\n").encode()

    with zipfile.ZipFile(whl, "w", zipfile.ZIP_DEFLATED) as zf:
        for arc, data in payload:
            info = zipfile.ZipInfo(arc, date_time=(2026, 10, 19, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, data)
        info = zipfile.ZipInfo(distinfo + "/RECORD", date_time=(2026, 10, 19, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = 0o644 << 16
        zf.writestr(info, record)
    return whl


def build_sdist():
    os.makedirs(DIST_DIR, exist_ok=True)
    tarball = os.path.join(DIST_DIR, "%s-%s.tar.gz" % (NAME, VERSION))
    base = "%s-%s" % (NAME, VERSION)
    pkg_info = metadata().replace("Metadata-Version: 2.1", "Metadata-Version: 2.1", 1)

    def add(tf, arc, data=None, path=None):
        info = tarfile.TarInfo(arc)
        info.mtime = 1792377600
        info.mode = 0o644
        info.uid = info.gid = 0
        info.uname = info.gname = "root"
        if path:
            info.size = os.path.getsize(path)
            with open(path, "rb") as src:
                tf.addfile(info, src)
        else:
            info.size = len(data)
            import io
            tf.addfile(info, io.BytesIO(data))

    with tarfile.open(tarball, "w:gz") as tf:
        add(tf, base + "/PKG-INFO", pkg_info.encode())
        add(tf, base + "/README.md", path=os.path.join(ROOT, "README.md"))
        add(tf, base + "/LICENSE", path=os.path.join(ROOT, "LICENSE"))
        add(tf, base + "/pyproject.toml", path=os.path.join(ROOT, "pyproject.toml"))
        for fname in sorted(os.listdir(PKG_DIR)):
            if fname.endswith(".py"):
                add(tf, base + "/check_proxy_tax/" + fname, path=os.path.join(PKG_DIR, fname))
        add(tf, base + "/setup.cfg", ("[metadata]\nname = %s\nversion = %s\n" % (DIST, VERSION)).encode())
    return tarball


def main():
    if os.path.isdir(DIST_DIR):
        shutil.rmtree(DIST_DIR)
    whl = build_wheel()
    sd = build_sdist()
    for path in (whl, sd):
        print("%s  %d bytes" % (path, os.path.getsize(path)))


if __name__ == "__main__":
    main()
