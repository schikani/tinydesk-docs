#!/usr/bin/env python3
"""fetch_release.py - put a TinyDesk release into the site's web installer.

    python tools/fetch_release.py --repo schikani/tinydesk            # the newest published release
    python tools/fetch_release.py --repo schikani/tinydesk --tag v0.1.0
    python tools/fetch_release.py --from ../tinydesk/dist/tinydesk-0.1.0   # a local make_release.py output

It downloads (or copies) the release files, checks them against
SHA256SUMS.txt and puts them where site/install/index.html expects them:

    site/install/manifest-<edition>-<board>.json   ESP Web Tools manifests
    site/install/firmware/*.bin                    the factory images they name
    site/install/downloads/*.tar.gz, *.zip         the PC programs
    site/install/SHA256SUMS.txt, README.txt

Files of the previous release there are replaced. Only the Python standard
library is needed. Set GITHUB_TOKEN if GitHub's rate limit gets in the way.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import urllib.error
import urllib.request

SITE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "site")


def http_get(url, accept="application/octet-stream"):
    req = urllib.request.Request(url, headers={"Accept": accept, "User-Agent": "tinydesk-fetch-release"})
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def get_json(url):
    return json.loads(http_get(url, "application/vnd.github+json"))


def find_release(repo, tag):
    """The release to install: the tagged one, else the one marked latest,
    else the newest published pre-release (GitHub's "latest" skips
    pre-releases, and every TinyDesk release starts as one). Drafts are
    never visible here."""
    base = "https://api.github.com/repos/%s/releases" % repo
    try:
        if tag:
            return get_json(base + "/tags/" + tag)
        try:
            return get_json(base + "/latest")
        except urllib.error.HTTPError as e:
            if e.code != 404:
                raise
        for release in get_json(base + "?per_page=20"):
            if not release.get("draft"):
                return release
        sys.exit("no published release in %s (a draft must be published first); nothing was changed" % repo)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            sys.exit("no published release %s in %s (a draft must be published first); nothing was changed"
                     % ("tagged " + tag if tag else "at all", repo))
        sys.exit("GitHub answered %d for %s; nothing was changed" % (e.code, e.url))


def download_release(repo, tag, into):
    release = find_release(repo, tag)
    print("release %s (%d files)" % (release.get("tag_name"), len(release.get("assets", []))))
    for asset in release.get("assets", []):
        name = asset["name"]
        print("  %s (%d KB)" % (name, asset.get("size", 0) // 1024))
        with open(os.path.join(into, name), "wb") as f:
            f.write(http_get(asset["browser_download_url"]))


def verify(folder):
    sums = os.path.join(folder, "SHA256SUMS.txt")
    if not os.path.exists(sums):
        sys.exit("no SHA256SUMS.txt in the release")
    bad = 0
    listed = set()
    with open(sums, encoding="utf-8") as checksum_file:
        checksum_lines = checksum_file.readlines()
    for line in checksum_lines:
        if not line.strip():
            continue
        digest, name = line.split(None, 1)
        name = name.strip()
        if not re.fullmatch(r"[0-9a-fA-F]{64}", digest) or not re.fullmatch(r"[A-Za-z0-9_.-]+", name) or name in listed:
            sys.exit("invalid or duplicate checksum entry; nothing was changed")
        listed.add(name)
        path = os.path.join(folder, name)
        if not os.path.exists(path):
            sys.exit("missing release asset: %s; nothing was changed" % name)
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for block in iter(lambda: f.read(65536), b""):
                h.update(block)
        if h.hexdigest() != digest:
            print("CHECKSUM MISMATCH: %s" % name.strip())
            bad += 1
    if bad:
        sys.exit("%d file(s) do not match SHA256SUMS.txt; nothing was changed" % bad)
    manifests = []
    for name in os.listdir(folder):
        if name.endswith((".bin", ".zip", ".tar.gz")) or name.startswith("manifest-"):
            if name not in listed:
                sys.exit("unchecked release asset: %s; nothing was changed" % name)
        if name.startswith("manifest-") and name.endswith(".json"):
            manifests.append(name)
            with open(os.path.join(folder, name), encoding="utf-8") as f:
                manifest = json.load(f)
            builds = manifest.get("builds", [])
            if not manifest.get("version") or not builds:
                sys.exit("empty manifest: %s; nothing was changed" % name)
            for build in builds:
                parts = build.get("parts", [])
                if build.get("chipFamily") not in ("ESP32", "ESP32-C6") or not parts:
                    sys.exit("invalid build: %s; nothing was changed" % name)
                for part in parts:
                    path = part.get("path", "")
                    if not re.fullmatch(r"firmware/[A-Za-z0-9_.-]+\.bin", path) or part.get("offset") != 0:
                        sys.exit("invalid firmware path/offset: %s; nothing was changed" % name)
                    binary = path.split("/")[-1]
                    if binary not in listed or os.path.getsize(os.path.join(folder, binary)) == 0:
                        sys.exit("missing/empty manifest firmware: %s; nothing was changed" % binary)
    if not manifests:
        sys.exit("no board manifests; nothing was changed")


def install(folder, site):
    dest = os.path.join(site, "install")
    if not os.path.exists(os.path.join(dest, "index.html")):
        sys.exit("%s is not the site folder (no install/index.html)" % site)
    for name in os.listdir(dest):
        p = os.path.join(dest, name)
        if name in ("firmware", "downloads") and os.path.isdir(p):
            shutil.rmtree(p)
        elif re.match(r"manifest.*\.json$|SHA256SUMS\.txt$|README\.txt$", name):
            os.remove(p)
    os.makedirs(os.path.join(dest, "firmware"))
    os.makedirs(os.path.join(dest, "downloads"))
    counts = {"firmware": 0, "downloads": 0, "manifests": 0}
    for name in sorted(os.listdir(folder)):
        src = os.path.join(folder, name)
        if name.endswith(".bin"):
            shutil.copy2(src, os.path.join(dest, "firmware", name))
            counts["firmware"] += 1
        elif name.endswith((".tar.gz", ".zip")):
            shutil.copy2(src, os.path.join(dest, "downloads", name))
            counts["downloads"] += 1
        elif name.startswith("manifest-") and name.endswith(".json"):
            shutil.copy2(src, os.path.join(dest, name))
            counts["manifests"] += 1
        elif name in ("SHA256SUMS.txt", "README.txt"):
            shutil.copy2(src, os.path.join(dest, name))
    print("installed into %s: %d images, %d manifests, %d downloads"
          % (os.path.normpath(dest), counts["firmware"], counts["manifests"], counts["downloads"]))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--repo", help="GitHub repository, e.g. schikani/tinydesk")
    src.add_argument("--from", dest="local", help="a folder made by make_release.py (dist/tinydesk-<version>)")
    ap.add_argument("--tag", help="release tag (default: the newest published release, pre-releases included)")
    ap.add_argument("--site", default=SITE, help="the site folder (default: ../site)")
    args = ap.parse_args()

    if args.local:
        verify(args.local)
        install(args.local, args.site)
        return
    with tempfile.TemporaryDirectory() as tmp:
        download_release(args.repo, args.tag, tmp)
        verify(tmp)
        install(tmp, args.site)


if __name__ == "__main__":
    main()
