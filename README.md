# TinyDesk documentation site and web installer

This repository is the TinyDesk website: the documentation and the web
installer, as plain static files. It is **kept apart from the code
repositories** (`tinydesk`, `tinydesk-shell`). GitHub Pages publishes it
(`.github/workflows/pages.yml`); any other static HTTPS host works too.

```text
tinydesk-site/
  site/                   everything the web server serves
    index.html            Docsify: renders the Markdown pages in the browser
    _coverpage.md, _sidebar.md, *.md, guide/, api/, shell/, ports/
    images/               the cover pictures (desktop.png, terminal.png)
    install/index.html    the web installer (editions x platforms)
    install/manifest-*.json, firmware/, downloads/    filled from a release
  .github/workflows/
    pages.yml             publishes site/ with GitHub Pages, release files included
    checks.yml            link check and tool tests on every push
  tools/
    check_links.py        checks every link and #anchor between the pages
    fetch_release.py      puts a release (GitHub or local) into site/install/
    publish.sh            copies site/ to the server with rsync (Linux, macOS, WSL)
    publish.ps1           the same from Windows with scp
  deploy/
    nginx.conf            server block with HTTPS, cache and MIME settings
    Caddyfile             the same for Caddy (automatic HTTPS)
```

Nothing is built: the server only hands out files. The pages load Docsify,
its plugins, fonts and ESP Web Tools from public CDNs (pinned versions, see
`site/index.html` and `site/install/index.html`).

The screenshots and the demo are real terminal captures from TinyDesk
boards.

Links that leave the Docsify pages (the installer, the web terminal, media
files) are plain HTML links relative to the site root, such as
`<a href="install/index.html">`, so the site works both at a domain root
and under a GitHub project path (`/tinydesk-docs/`).

## 1. Preview on your PC

```bash
python -m http.server 3000 --directory site
```

Open <http://localhost:3000> for the documentation and
<http://localhost:3000/install/> for the installer. The installer also
flashes boards from `localhost` (browsers allow Web Serial on `https://`
and `localhost` only).

## 2. Fill the installer with a release

The installer shows a board's **Install** button only when its firmware is
on the site, and serves the PC programs from `site/install/downloads/`
(falling back to the GitHub release when a file is missing).

From a GitHub release (the `tinydesk` repository's release workflow makes
a draft prerelease for every `v*` tag, after CI succeeds):

```bash
python tools/fetch_release.py --repo schikani/tinydesk            # the newest published release
python tools/fetch_release.py --repo schikani/tinydesk --tag v0.1.0
```

Or from a release built on your PC (in the `tinydesk` repository, after
building the firmware):

```bash
python tools/make_release.py --site ../tinydesk-site/site           # run inside tinydesk/
# or, with an existing dist/ folder:
python tools/fetch_release.py --from ../tinydesk/dist/tinydesk-0.1.0
```

Both check the files against `SHA256SUMS.txt` and replace the previous
release in `site/install/`.

!> A local build that embedded a private `board.conf` is refused by
`make_release.py` unless you pass `--allow-board-conf`; do not publish such
images.

## 3. Publish with GitHub Pages

1. Settings → Pages → *Build and deployment* → Source: **GitHub Actions**.
2. Push to `main`, or run Actions → *GitHub Pages* → **Run workflow**. The
   workflow checks the links, copies the latest published TinyDesk release
   into `site/install/` (with `fetch_release.py`) and deploys `site/`.
3. The site is at `https://<owner>.github.io/tinydesk-docs/`.

After publishing a TinyDesk release, run the workflow again. It takes the
newest published release, pre-releases included; to pin one (for example
to roll back), enter its tag in the *Run workflow* form or set the
repository variable `INSTALLER_TAG`. Drafts are never used: publish the
release first. Without any release the site still deploys; the installer
then shows its "not available yet" notes.

A custom domain: Settings → Pages → *Custom domain*, plus a `CNAME` DNS
record pointing at `<owner>.github.io`; tick *Enforce HTTPS* (the installer
needs HTTPS).

## 4. Or: your own web server

Any static web server works. Requirements:

* **HTTPS.** Without it the installer cannot reach the serial port.
* `.json` served as `application/json`, `.bin` as `application/octet-stream`
  (both are the defaults of nginx and Caddy); `.md` any text type.
* No server-side code, no database, no directory listings.

### nginx (with Let's Encrypt)

```bash
sudo apt install nginx certbot python3-certbot-nginx
sudo mkdir -p /var/www/tinydesk && sudo chown "$USER" /var/www/tinydesk
sudo cp deploy/nginx.conf /etc/nginx/sites-available/tinydesk   # edit the name and paths first
sudo ln -s /etc/nginx/sites-available/tinydesk /etc/nginx/sites-enabled/
sudo certbot --nginx -d tinydesk.example.com
sudo nginx -t && sudo systemctl reload nginx
```

### Caddy

```bash
sudo apt install caddy
sudo cp deploy/Caddyfile /etc/caddy/Caddyfile                   # edit the name and path first
sudo systemctl reload caddy                                      # certificates are automatic
```

Point a DNS name at the server first (an `A`/`AAAA` record for
`tinydesk.example.com`), and open ports 80 and 443.

### Publish to it

```bash
SERVER=me@myserver DEST=/var/www/tinydesk tools/publish.sh       # Linux, macOS, WSL
```

```powershell
.\tools\publish.ps1 -Server me@myserver -Dest /var/www/tinydesk  # Windows
```

Both run `check_links.py` first and stop on a broken link. `publish.sh`
mirrors the folder (files removed locally are removed on the server);
`publish.ps1` only copies.

## 5. Day-to-day

| Task | What to do |
| --- | --- |
| Edit a page | change the Markdown in `site/`, preview, `python tools/check_links.py`, push (Pages redeploys) |
| Add a page | create the `.md` file and add it to `site/_sidebar.md` |
| New release | bump the version in `site/_coverpage.md`, add the entry to `site/changelog.md`, push, then run the *GitHub Pages* workflow (with the tag for a pre-release); on your own server: `fetch_release.py` and publish |
| New cover pictures | replace `site/images/desktop.png` and `terminal.png` (the `tinydesk` repository's `tools/vtshot --svg` renders a capture as SVG) |
| Roll back a release | run the *GitHub Pages* workflow with the older tag (own server: `fetch_release.py --tag <older tag>`, publish) |

## Notes

* `tinydesk.example.com` in `deploy/` is an example domain for your own
  server, not a running service.
* The installer points to `schikani/tinydesk` for release assets
  (`site/release-config.js`; the Pages workflow's `RELEASE_REPO`).
* Release firmware and PC archives stay out of git. The Pages workflow and
  `tools/fetch_release.py` check them against the release's
  `SHA256SUMS.txt` before they reach the site.

## Checks

```sh
python tools/check_links.py
python -m unittest discover -s tools -p "test_*.py"
```

## Licence

MIT (see `LICENSE`), like the `tinydesk` and `tinydesk-shell` repositories.
The pages load Docsify, its plugins, xterm.js, ESP Web Tools and fonts from
public CDNs; those keep their own licences. The firmware and programs that
the installer serves come from the `tinydesk` releases (MIT; third-party
parts such as wolfSSH keep theirs, see that repository).
