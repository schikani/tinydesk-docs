# Maintaining these docs

This site (the documentation and the web installer) lives in its own
folder, `tinydesk-site`, outside the code repositories, and is served from
a web server of your own. It is [Docsify](https://docsify.js.org):
`index.html` loads Docsify from a CDN and renders the Markdown files in the
browser; there is no build step. The folder's `README.md` explains the
server set-up, filling the installer and publishing.

```text
tinydesk-site/
  site/        the pages (this folder is what the server serves)
  tools/       check_links.py, fetch_release.py, publish.sh, publish.ps1
  deploy/      nginx.conf, Caddyfile
```

## Preview

```bash
python -m http.server 3000 --directory site     # in tinydesk-site/
```

Open <http://localhost:3000>. Pages reload on refresh. Before publishing:

```bash
python tools/check_links.py      # every link and #anchor between pages
```

## Where things go

Update the site in step with the code: a change that reaches users gets its
page updated before the release.

| Change in the code | Update in `site/` |
| --- | --- |
| a public function, struct, macro or callback in `include/tinydesk/`, `apps/td_apps.h`, `proto/` | the matching page in `api/` |
| a new `td_sysinfo_t` service or port hook | `api/sysinfo.md` and the port page |
| a new or changed shell command or option | `shell/commands.md` |
| a file format, settings byte, NVS key, partition | `shell/config-files.md` |
| keys, mouse actions, a new app, UI behaviour | `guide/using.md` (and `api/apps.md` for an app) |
| a new board or port change | `ports/`, `guide/install.md` and the installer (`install/index.html`) |
| a new board configuration key | `guide/board-config.md` (and, in the code, every `board.example.conf`) |
| a change in the shell (`third_party/tdsh`) | the shell repository's `CHANGELOG.md`, and the pages here that describe it |
| a new tool or tool option | `tools.md` |
| every release | `changelog.md`, the version in `_coverpage.md` |
| a new page | add it to `_sidebar.md` |

## Style

* Document what the code does, checked against the source. Copy
  prototypes exactly; say which task or thread may call a function, who
  owns returned memory, and the limits (sizes, timeouts, RAM).
* API pages: a short intro, `Header:` line, then groups of items. Each
  function: a `c` code block with the prototype, a description,
  parameters and return value, notes. Structs and enums: the definition,
  then a table of fields.
* Plain English, short sentences, tables for options.
* Links between pages are relative (`../api/wm.md`); sidebar links start
  with `/`. Link to a section with `page.md?id=heading-id`.

## Releases

Versions follow [Semantic Versioning](https://semver.org/); TinyDesk and
TinyDesk Shell have their own version numbers (both started at 0.1.0).

1. In the `tinydesk` repository set `PROJECT_VER` in
   `ports/esp32c6/CMakeLists.txt`, `ports/esp32/CMakeLists.txt` and
   `ports/esp32-4mb/CMakeLists.txt`, and `TD_VERSION` in
   `include/tinydesk/td.h`. A new shell version goes in the shell's
   `VERSION` and `TDSH_VERSION` (`include/tdsh.h`) with a `CHANGELOG.md`
   entry there.
2. Build the five firmware projects (`ports/esp32c6`, `ports/esp32`,
   `ports/esp32-4mb`, `third_party/tdsh`, `third_party/tdsh/projects/esp32`)
   and try the release locally:
   `python tools/make_release.py --site ../tinydesk-site/site`, then the
   installer on <http://localhost:3000/install/>.
3. If the shell changed, commit and push it in its own repository first,
   then commit the new submodule pointer in `tinydesk` (see
   [Contributing](contributing.md#working-on-the-shell)).
4. Tag `v<version>` in `tinydesk` (and `v<shell version>` in the shell
   repository): `.github/workflows/release.yml` builds both editions for
   every platform and attaches the images and PC programs to the GitHub
   Release.
5. Here: `python tools/fetch_release.py --repo <you>/tinydesk`, add the
   `changelog.md` entry, set the version in `_coverpage.md`, check the
   links and publish (`tools/publish.sh` or `tools/publish.ps1`).

## Generated reference (optional)

The headers carry the same information as comments. For a
symbol-by-symbol HTML index, Doxygen (installed with the MinGW toolchain)
can be run over `include/`, `apps/td_apps.h` and `proto/`; the hand-written
pages here stay the main reference because they also explain behaviour,
limits and board differences.
