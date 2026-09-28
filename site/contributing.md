# Contributing and repositories

## Three repositories

| Repository | Content | Licence |
| --- | --- | --- |
| [`tinydesk`](https://github.com/schikani/tinydesk) | the desktop core (`src/`, `include/`), apps, protocols, the ESP-IDF and host ports, tools | MIT |
| [`tinydesk-shell`](https://github.com/schikani/tinydesk-shell) | TinyDesk Shell (`tdsh`): the portable shell core, its ESP-IDF services (Wi-Fi, Ethernet, SSH, FTP, SMB, users, board configuration) and its POSIX host port | MIT; third-party parts (wolfSSH GPLv3, ...) keep their licences |
| [`tinydesk-docs`](https://github.com/schikani/tinydesk-docs) | these pages, the web installer and the web terminal (plain static files, published with GitHub Pages) | MIT; the scripts and styles it loads from CDNs (Docsify, xterm.js, ESP Web Tools) keep their licences |

`tinydesk` includes the shell as a **git submodule** at `third_party/tdsh`:
a pointer to one exact commit of `tinydesk-shell`. The ports use it as
the ESP-IDF component `tdsh` and, on the PC, as the library `tdsh`; its C
API has the prefix `tdsh_`.

The shell does not depend on the desktop. It builds and runs on its own
(its root is an ESP32-C6 ESP-IDF project, and `-DTDSH_BUILD_HOST=ON`
builds the host port and tests on Linux).

## Getting the code

```bash
git clone --recursive https://github.com/schikani/tinydesk.git
```

After a `git pull` that moved the submodule:

```bash
git submodule update --init
```

## Working on the shell

The submodule is a normal clone of `tinydesk-shell`, checked out at a
fixed commit (a "detached HEAD"). To change it:

```bash
cd third_party/tdsh
git switch main                      # leave the detached HEAD
# edit, build TinyDesk, test on a board
git commit -am "board: ..."          # commit in the shell repository
git push                             # publish the shell change first
cd ../..
git add third_party/tdsh           # record the new shell commit in tinydesk
git commit -m "Update TinyDesk Shell: ..."
git push
```

Push the shell before `tinydesk`: a `tinydesk` commit that points at an
unpublished shell commit cannot be cloned by anyone else.

The shell's changes are listed in its own `CHANGELOG.md`.

## Before a pull request

| Check | Command |
| --- | --- |
| Host build, warnings are errors | `cmake -B build -G Ninja && cmake --build build` |
| Unit tests | `ctest --test-dir build --output-on-failure` |
| Simulator smoke test | `build/tdsim wait=300 key=Enter wait=1500 'type=echo ok\r' wait=800 shot` |
| Shell tests (Linux, or Windows with MinGW: they build `tdsh.exe`) | `cmake -S third_party/tdsh -B build-shell -G Ninja -DTDSH_BUILD_HOST=ON && cmake --build build-shell && ctest --test-dir build-shell` |
| ESP32-C6 firmware | `cd ports/esp32c6 && idf.py build` |
| Classic ESP32 firmware | `cd ports/esp32 && idf.py build` |
| Docs | update the pages listed in [Maintaining these docs](maintaining.md) and the [changelog](changelog.md) |

GitHub Actions runs the host build, the tests and both firmware builds on
every push and pull request.

## Rules that keep the project portable

* **No board-specific pins in code, Kconfig defaults or docs examples.**
  Read them from the [board configuration](guide/board-config.md), and
  add new keys (commented out) to both `board.example.conf` files.
* Never commit `ports/*/board.conf`, `sdkconfig`, build folders, firmware
  images, or anything with a password, key, IP address or host name of
  your own network. `.gitignore` covers the usual files; check
  `git status` before committing.
* Core code (`src/`, `include/`) stays C11 with screen allocation at initialization and bounded paste-buffer growth at runtime and no platform headers; platform code lives in `ports/`.
* Match the style of the file you edit; `clang-format` with the repository's
  settings where present.

## Licence of contributions

By sending a pull request you agree that your contribution is released
under the repository's licence (MIT).
