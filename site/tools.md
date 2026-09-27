# Tools

Helpers in `tools/` (and two in `ports/esp32c6/`) for driving real boards
from a script, checking screens without a terminal, and testing the
protocols. The C tools are built with the host build (`cmake --build build`).

| Tool | What it is for |
| --- | --- |
| `tools/serial_bridge.py`, `tools/tinydesk_putty.cmd` | PuTTY on an ESP32 dev board without resetting it |
| `tools/serial_probe.py` | send keys/clicks to a board over its serial port and capture the output |
| `build/vtshot` (`tools/vtshot.c`) | render a capture as a text screenshot or an SVG picture |
| `build/tdsim` (`tools/tdsim.c`) | run the whole host desktop against a simulated terminal |
| `tools/rtu_slave.py` | a Modbus RTU slave on PC serial ports (USB-RS485 adapters) |
| `build/lfs_migrate` (`tools/lfs_migrate.c`) | copy a LittleFS image into an image of another size |
| `tools/make_release.py` | package a release: factory images, web installer manifests, PC programs, checksums |
| `tools/make_source_zip.py` | the whole project (code, shell, site) in one zip |
| `ports/esp32c6/serve_bin.py` | serve a firmware `.bin` over HTTP for OTA updates |
| `ports/esp32c6/build.ps1` | build and flash the C6 with the right ESP-IDF on Windows |

## serial_bridge.py

```bash
python tools/serial_bridge.py COM10 [--baud 921600] [--listen 2310] [--putty]
tools\tinydesk_putty.cmd [COM10] [921600]
```

Opens the COM port with DTR and RTS released (so the board's auto-reset
circuit never fires), listens on `127.0.0.1:<listen>` and bridges one
Telnet client (PuTTY in Telnet mode) at a time. It asks the client for
character-at-a-time, no local echo and binary mode, strips Telnet commands
and CR NUL / CR LF from the client, doubles 0xFF bytes towards it, and
sends `ESC [ 5000 ~` to the board on every new connection so the desktop is
redrawn. The port stays open between clients. Stop it before flashing.
See [Terminals](guide/terminals.md#esp32-boards-without-resets).

## serial_probe.py and vtshot

```bash
python tools/serial_probe.py [--baud=N] [--size=COLSxROWS] COM3 out ACTIONS...
build/vtshot out_1.bin 80 25
build/vtshot out_1.bin 80 25 --svg screen.svg [--rows 0-20] [--title "caption"]
```

`serial_probe.py` opens the port like a terminal (DTR/RTS released),
answers the size query as a `COLSxROWS` terminal (80x25 by default), runs
the actions in order and writes captures:

| Action | Meaning |
| --- | --- |
| `wait=MS` | read for MS milliseconds |
| `type=TEXT` | send text (`\r \n \t \e \xHH` escapes) |
| `key=NAME` | Enter Esc Tab Up Down Left Right F4 F6 F10 F11 Bksp Del CtrlL CtrlC CtrlQ |
| `click=X,Y` | left click at a 0-based cell |
| `reset` | pulse the chip reset through RTS/DTR |
| `shot` | write `out_<n>.bin` with everything received so far |

`vtshot` replays a capture through the [terminal emulator](api/vterm.md)
and prints the screen (at most 400x150). With `--svg` it renders the
screen as an SVG picture instead, with its colours (the 16 basic colours as
Windows Terminal's Campbell scheme shows them); `--rows A-B` keeps only
those rows and `--title` adds a window frame with a caption. The cover
pictures of this site are made that way. A capture contains only what
the board sent during that run, so send `key=CtrlL` before `shot` for a full
screen (but not while a Terminal window has the focus: Ctrl+L also clears
the shell's screen).

## tdsim

```bash
build/tdsim size=80x25 wait=500 shot key=Enter wait=800 type="ls\r" wait=300 shot
```

Runs the complete host desktop (apps and TinyDesk Shell) against a simulated
terminal and prints text screenshots. Actions: `size=COLSxROWS` (first
only), `wait=MS`, `type=TEXT`, `key=NAME` (Enter Esc Tab BTab arrows Home
End PgUp PgDn Del Bksp F1..F12 CtrlA..CtrlZ), `click=X,Y`, `rclick=X,Y`,
`drag=X1,Y1,X2,Y2`, `move=X,Y`, `wheel=X,Y,up|down`, `shot`, `stats`, and
`save=FILE`, which writes everything the desktop sent so far, for
`vtshot FILE COLS ROWS --svg out.svg`.
Screen rows in its output start one line down (the first line is a border).
Settings it changes are saved in `build/tinydesk_fs/root/.tinydesk_settings`.
A bracketed paste can be simulated with `type="\e[200~text\e[201~"`.

## make_release.py

```bash
python tools/make_release.py [--site ../tinydesk-site/site] [--out dist] [--allow-board-conf]
    [--host-linux-desktop build/tinydesk] [--host-linux-shell build-shell/tdsh_host]
    [--host-windows-desktop build/tinydesk.exe]
```

Packages both [editions](guide/install.md#editions) for people without a
toolchain. Run it after building the ESP-IDF projects: `ports/esp32c6`,
`ports/esp32` and `ports/esp32-4mb` (TinyDesk Desktop, required),
`third_party/tdsh` and `third_party/tdsh/projects/esp32` (TinyDesk Shell,
left out with a note when not built). For each board it merges what
`idf.py flash` writes (`build/flash_args`) into one factory image and
writes `dist/tinydesk-<version>/`:

| Output | Contents |
| --- | --- |
| `tinydesk-<edition>-<version>-<board>-factory.bin` | one merged image for `esptool write_flash 0x0` |
| `manifest-<edition>-<board>.json` | [ESP Web Tools](https://esphome.github.io/esp-web-tools/) manifest for that board, `new_install_prompt_erase` on; it names the image as `firmware/<image>`. One per board because ESP Web Tools picks a build by chip family only, and two ESP32 builds could not share a manifest. |
| `tinydesk-desktop-linux-x86_64.tar.gz`, `tinydesk-shell-linux-x86_64.tar.gz`, `tinydesk-desktop-windows-x64.zip` | with `--host-*`: the PC program, a README and the licences, in a folder of the same name |
| `SHA256SUMS.txt`, `README.txt` | checksums of everything, short instructions |

`--site DIR` also puts the release into the web installer of a local copy
of this site (`DIR/install/`: the manifests, `firmware/`, `downloads/`),
like the site's `tools/fetch_release.py` does with a GitHub release.

It stops when the boards of one edition were built from different
versions, and refuses images whose built-in
[board configuration](guide/board-config.md) sets any key: that happens
when a private `board.conf` was present at build time, and published
images must carry only the example. Remove the file and rebuild, or pass
`--allow-board-conf` for an image you keep to yourself. The release
workflow builds from git, where no `board.conf` exists.

## make_source_zip.py

```bash
python tools/make_source_zip.py [--site ../tinydesk-site] [--out ..]
```

Packs the whole project into `TinyDesk-<version>-source.zip`: the
`tinydesk` repository with TinyDesk Shell (`third_party/tdsh`), this site
(`tinydesk-site`, when found next to it) and a short guide at the top.
Build output, downloaded components, `sdkconfig` files, logs, run-time
data, release images and every private `board.conf` are left out. Useful
for a review, or to hand the project to someone without git.

## rtu_slave.py

```bash
python tools/rtu_slave.py COM6 COM7 [--baud 9600] [--parity N] [--unit 1] [--seconds 60]
```

Each port gets its own tables: holding and input registers start at
`<port number> * 1000` (COM6: 6000, 6001, ...), coils alternate 1,0,1,0.
Writes are applied and every request is logged. Use it with
`modbus read rtu1 ...` on the board ([Modbus](api/modbus.md)).

## lfs_migrate

```bash
lfs_migrate old.img new.img 0x2E0000
```

Copies every file and folder of a raw LittleFS image into a new image of a
different size and compares them afterwards. It was used to move `/fs` when
the OTA partition table shrank the storage partition; see the top of
`tools/lfs_migrate.c` for building it with ESP-IDF's LittleFS sources.

## serve_bin.py

```bash
python ports/esp32c6/serve_bin.py [build/tinydesk.bin] [-p 8000]
```

Serves a firmware image on the local network (standard library only) and
re-reads it on every request, so a rebuild is served at once. On the board:
Software Update, URL `http://<pc>:8000/tinydesk.bin`, or
`ota install http://<pc>:8000/tinydesk.bin`.
