# Changelog

Versions of the TinyDesk firmware and programs (`PROJECT_VER`, `TD_VERSION`),
newest first; TinyDesk Shell has its own `CHANGELOG.md`. Every board and PC
program of a release has the same version. Add an entry for every change
that reaches users or changes an API (see [Maintaining these docs](maintaining.md)).
Versions follow [Semantic Versioning](https://semver.org/): until 1.0.0 the
API may still change between minor versions.

## Unreleased

* **`ping` in the Terminal window** (TinyDesk Shell): the replies and the
  statistics now appear (only the `PING` line did), and `ping -c <count>`
  works on the boards as on the PC.
* **Documentation and web installer:**
  * The cover shows the current version and puts *Install / Download*
    (straight to the installer) right under the headline; `tools/fetch_release.py` writes the installed
    release's version into the cover and the installer.
  * Install: the Desktop edition's needs are given per board (the 4 MB
    ESP32 runs without PSRAM, with an 80x25 screen and no SSH server or
    OTA); updating is described per board, and the installer's advice
    follows the chosen board (no Software Update on the 4 MB ESP32 or in
    TinyDesk Shell).
  * Brighter small text on the cover and in the web terminal; the
    sidebar's section headings read like its links; "Installation" in the
    sidebar.
  * The installer shows the esptool command for the chosen board only (with
    the release's file name), and only for ESP boards.
  * First start and esptool: the SSH note and the erase advice follow the
    chosen board (no SSH server in the 4 MB Desktop build; no erase needed
    to switch editions on 4 MB boards). The cover's Shell picture is a new
    capture of TinyDesk Shell 0.1.1 on an ESP32.
  * Phones: wide tables scroll in their own box instead of being cut off,
    the text uses the full width, and the web terminal fits an 80x25 board
    screen without scrolling the page sideways.
  * Getting started and Troubleshooting: keep the checkout in a short
    folder on Windows (`ninja: error: mkdir(...)`).

## 0.1.1 (2026-09-28)

TinyDesk 0.1.1, with TinyDesk Shell 0.1.1.

* **PC programs: MQTT over TLS in the downloads.** The Windows and Linux
  programs of the 0.1.0 release were built without mbedTLS and refuse
  `mqtts` ("not available in this build"); programs built from source with
  ESP-IDF installed are not affected. CI and the release workflow now build
  against mbedTLS v3.6.7, stop without it (`TD_REQUIRE_TLS`) and test that
  TLS is built in.
* **TinyDesk Shell releases** in its own repository, from its own release
  workflow, with the same file names as the Shell edition here.
* **TinyDesk Shell for Windows: `tdsh.exe`.** A native Windows program of
  the Shell edition (`tinydesk-shell-windows-x64.zip`), for Windows
  Terminal: line editing, history and Tab completion, `ifconfig` and
  `ping`. Its files are in `%LOCALAPPDATA%\tdsh\rootfs`; the user is your
  Windows user name. The Desktop edition's Windows program now uses the same
  Windows port from TinyDesk Shell.
* **Documentation:** version numbers from before the first release removed
  from the troubleshooting page and the `ota` examples; "TinyDesk" written
  the same way everywhere.

## 0.1.0 (2026-09-28): first public release

TinyDesk 0.1.0, with TinyDesk Shell 0.1.0.

* **Desktop:** overlapping windows (move, resize, minimise, maximise, full
  screen), taskbar, start menu, desktop icons from each user's Desktop
  folder, mouse and keyboard, drag and drop, copy and paste with the PC,
  themes and UI sizes; the screen follows the terminal's size.
* **Apps:** Terminal (TinyDesk Shell), Files, Editor, Network, MQTT
  (TLS), Modbus TCP/RTU with a TCP server, System Monitor, Task Manager,
  Log Viewer, Settings, Software Update (OTA with rollback), Date & time.
* **Shell scripts:** `.tdsh` files have their own icon and a **Run** entry
  in their right-click menu.
* **Users:** per-user desktops, files, Wi-Fi networks and settings; Telnet
  remote desktop; factory root password `TinyDesk`.
* **Board configuration:** pins come from `board.conf` / `/etc/board.conf`,
  not from the code (`board` command).
* **Ports:** ESP32-C6, ESP32 with PSRAM, ESP32 with 4 MB flash and no
  PSRAM, Linux, Windows; macOS and other POSIX systems from source.
* **Editions:** TinyDesk Desktop and TinyDesk Shell, both with a web
  installer and PC downloads.
* **About** shows both source repositories (`tinydesk` and
  `tinydesk-shell`) and fits its content on every board; the name is
  spelled TinyDesk in About, Software Update, `ota status` and the welcome
  text, and free RAM is given in KB everywhere.
* **Windows:** the Terminal's shell now has `ifconfig`, `ping`, `date`,
  `cal`, `tz`, `write`, `hostpath` and `capabilities`, like the Linux
  program (`ifconfig` was "command not found").
* **Fix (Windows):** the desktop now follows the Windows Terminal window
  when it is maximised or resized. A resize now only repaints; the terminal
  setup it resent ("alternate screen on") made the Windows console fall
  back to its old size.
* **Docs:** [Shell scripts](shell/scripting.md), the `.tdsh` language
  reference (it was only shown by the shell's test scripts).
* **Web terminal** (`console/` on this site): opens a board's serial port in
  Chrome or Edge with a real terminal (xterm.js over Web Serial), presets for
  every board, no reset of ESP32 dev boards. The installer links to it; its
  own Logs & Console cannot show the desktop.
* **Dark theme by default** on every port, with a clearly visible teal
  desktop pattern (light shade). Classic stays available in Settings;
  saved settings keep their theme.
* **Windows and Linux programs:** the desktop follows the terminal up to
  400x150 (was 132x50), like the ESP32 with PSRAM does up to 256x96.
* **Build date:** the date and time shown by About, Software Update and
  `ota status` now come from the build that made the image. ESP-IDF compiled
  them only in a fresh build directory before, so incremental builds kept an
  old date (`ports/common/app_desc_stamp.cmake`).

## Development builds (before the first release)

These builds were never published; their notes are kept for reference.

### dev 0.2.17 (2026-09-26)

* **Board configuration**: pins and other hardware settings are no longer
  compiled in. RS-485 lines (`rs485.N.*`), W6100 Ethernet (`eth.*`), the
  SD card (`sd.*`) and the classic ESP32's console UART (`console.*`) come
  from `key = value` settings: the port's `board.conf` (not in git) or
  `board.example.conf` built into the firmware, overridden per device by
  `/etc/board.conf`. New shell command `board` (show, get, set, unset,
  init). API `tdsh_board.h`. See
  [Board configuration](guide/board-config.md).
* Ethernet stays off unless `eth.chip = w6100`; `lan hw set` and
  `lan poll` write the board configuration. The W6100 Kconfig pin
  defaults are now -1 (fallbacks only).
* `hwtest` runs on both ESP ports with the configured pins; unconfigured
  tests are skipped (`[SKIP]`).
* Modbus RTU on the classic ESP32 too, when RS-485 lines are configured.
* Factory root password **`TinyDesk`**, accepted everywhere (Telnet, SSH,
  FTP, Switch user). No forced change at the first start any more (the
  0.2.16 dialog and `td_sysinfo_t.root_password_is_default` /
  `set_root_password` are gone). `MicroPython` or `tinydesk` as root's
  password is switched to `TinyDesk` once.
* Shell scripts use the extension `.tdsh`; the boot script is
  `~/.tdshrc.tdsh`, history `~/.tdsh_history`, time zone `~/.tdsh_tz`, shebang
  `#!/bin/tdsh`, a directory runs `main.tdsh`.
* Fix: a board without Ethernet crashed at boot when the Telnet listener
  opened its socket before the TCP/IP stack existed (seen on the classic
  ESP32 as a reset loop). `app_main` now starts `esp_netif` and the
  default event loop first.
* ESP32: FreeRTOS functions in flash (`CONFIG_FREERTOS_PLACE_FUNCTIONS_INTO_FLASH`)
  to fit IRAM.
* The startup-file template no longer says "USB Serial/JTAG" on every board.
* The shell is now **TinyDesk Shell 0.7.0** (`tdsh`), MIT, in
  its own repository and included as the submodule `third_party/tdsh`.
  The Terminal window is titled `Terminal - tdsh`; About shows
  `Shell: TinyDesk Shell 0.7.0`.
* Docs: Board configuration, Contributing and repositories; README rewritten
  for GitHub; MIT licence for TinyDesk Shell.
* Everything that was named after the shell's origin is now `tdsh` /
  TinyDesk Shell: the submodule `third_party/tdsh`, the ESP-IDF component
  `tdsh`, `tdsh_*` functions and files, `CONFIG_TDSH_*`, `TD_WITH_TDSH`,
  the command `tdsh run`, the files `~/.tdsh_history` and `~/.tdsh_tz`, the
  SSH host key's NVS namespace `tdsh_ssh` (a board keeps a new host key).
* `.tdsh` scripts: **Right-click → Run** on the desktop and in Files runs
  the script in the Terminal (`td_terminal_run()`, `td_script_run()`); a
  green `#!` icon on the desktop (new optional `icon_fg` in
  `td_desktop_provider_t`), a green name with `#!` in Files.
* Two editions: **TinyDesk Desktop** and **TinyDesk Shell**. The installer
  page offers both for ESP32-C6, ESP32, Linux, Windows and macOS/other;
  `make_release.py` packages both editions and the PC programs
  (`--host-*`); the release workflow builds Linux and Windows programs.
* Docs search: results and the opened page highlight the searched words
  (`?highlight=`), with "Hide search matches".
* The tagline no longer says ESP32: "A windowed desktop for
  microcontrollers, drawn in any terminal" (About, docs, READMEs).
* Release builds (`-O3`) compile without warnings: a path that does not fit
  is refused instead of being cut (Files, `remove_tree`), and display texts
  are cut on purpose.
* The ESP32 port's libsmb2 MD5 shim moved into TinyDesk Shell
  (`tdsh_md5_rom.c`).

### dev 0.2.16 (2026-09-25)

* Factory root password `tinydesk` (was TinyDesk Shell's `MicroPython`; a board
  that still has that is switched to `tinydesk` once). It is accepted only
  on the board's own console; Telnet, SSH, FTP and Switch user refuse it.
* First start: the desktop asks for a new root password and cannot be used
  until one is set (`td_sysinfo_t.root_password_is_default`,
  `set_root_password`; TinyDesk Shell `tdsh_user_has_default_password()`,
  `tdsh_user_set_password()`).
* Prebuilt firmware: `tools/make_release.py` (parts, merged factory images,
  ESP Web Tools manifest, checksums), a browser installer page
  (`docs/install/`) and a GitHub Actions release workflow.
* Docs: Install, First login and users, Security, Troubleshooting; cover
  page, TinyDesk colours, light/dark switch, previous/next links, OS tabs;
  pinned CDN versions.
* `tdsim factory-root` simulates a fresh board.

### dev 0.2.15 (2026-09-25)

* `tools/serial_bridge.py` and `tools/tinydesk_putty.cmd`: PuTTY on an
  ESP32 dev board without resetting it.
* Input: `ESC [ 5000 ~` (`TD_SEQ_REDRAW`) asks for the terminal setup and a
  full redraw; the bridge sends it on every new connection.
* Documentation site (`docs/`, Docsify).
* `modbus` numbers and the Modbus app's fields are decimal unless they
  start with `0x` (a leading 0 was octal: `010` was 8).
* `modbus read -i`: the header says where Ctrl+C works; `-n 0` is refused
  where Ctrl+C cannot stop it (host builds).
* TinyDesk Shell patch: SSH messages say "PSRAM heap" on the classic ESP32.
* Header comments corrected (`td_wm_windows()` order, `td_update_register()`,
  `td_key_name()`, `td_config.h`, `td_mqtt.h`).

### dev 0.2.14 (2026-09-25)

* Task Manager app: open windows (switch to, end task) and FreeRTOS tasks
  with state, priority, core, CPU % and unused stack
  (`td_sysinfo_t.tasks`, `td_task_info_t`, `td_wm_windows()`).
* Bracketed paste: `TD_EV_PASTE`, `td_paste_text()`, `td_widgets_paste()`;
  the Editor, text boxes and the Terminal take pastes from the PC.
* OSC 52 on the Editor's Copy/Cut (`td_host_clipboard_set()`).
* Ctrl+Q (and Alt+F4) close the focused window.
* ESP32: UART RX buffer 8 KB. ESP32-C6: FreeRTOS kernel code in flash
  (`CONFIG_FREERTOS_PLACE_FUNCTIONS_INTO_FLASH`), about 14 KB more free RAM.
* TinyDesk Shell patch: a W6100 setup that fails half-way is undone (it leaked a
  task and an SPI device on every retry on boards without the chip).

### dev 0.2.13 (2026-09-24)

* The whole screen is redrawn whenever the terminal reports a new size,
  even if the size used stays the same (fixes a blank screen after resizing
  PuTTY past the C6's 80x25). Size poll every second.
* ESP32 screen limit 256x96; System Monitor shows the terminal's size when
  it is bigger than the limit (`td_stats_t.term_cols`, `term_rows`).

### dev 0.2.12 (2026-09-24)

* `modbus read ... -i ms -n times`: repeated reads with Ctrl+C
  (`td_proto_set_break_check()`, `tdsh_bridge_break_requested()`).
* Settings → Sizes: desktop icons, start menu and taskbar in Small /
  Medium / Large (`td_ui_size_t`, `td_wm_set_*_size()`), clock parts for the
  two-row taskbar (`td_clock_provider_t.parts`), window icons.
* Screen limits from `CONFIG_SPIRAM` (ESP32 160x60 at the time, C6 80x25).

### dev 0.2.11 (2026-09-24)

* Modbus app: repeat interval in ms (10 ms to 1 hour), faster polling and
  redraws only on change.

### dev 0.2.10 (2026-09-24)

* Per-device SSH host key (TinyDesk Shell patch; `ssh hostkey [new]`).
* The Modbus app's device hint matches the board's RTU lines.

### dev 0.2.9 (2026-09-24)

* TinyDesk Shell patch: `ssh stop` really stops the server (lwIP `accept()` needed
  a receive timeout).

### dev 0.2.8 (2026-09-24)

* Classic ESP32 port (`ports/esp32`, ESP32-WROVER-IE): UART0 link at
  921600, PSRAM for the static buffers, per-board `link.h`.
* Board-neutral shared ESP code (`hal_mux.c`), System Monitor shows
  internal RAM and PSRAM separately (`td_sysinfo_t.psram_free/total`).

### dev 0.2.0 - 0.2.7 (2026-09-24)

* OTA updates with rollback, Software Update app, `ota` command, new
  partition table with two app slots.
* MQTT client and app (config file, TLS 1.2 with CA/client certificates),
  Modbus TCP/RTU client, TCP server and app, `mqtt` and `modbus` commands.
* Two RS-485 channels on UART1/UART0 in RS-485 half-duplex mode; the
  ESP-IDF console is off, logs go to the Log Viewer.
* TLS memory: certificate files read at their size, dynamic mbedTLS buffers.

### dev 0.1.x (2026-09-23 - 2026-09-24)

* The core: screen buffers with diff rendering, input parser with SGR
  mouse, window manager, widgets, themes, terminal emulator, timers.
* Apps: Terminal (TinyDesk Shell), Files, Editor (undo/redo, selection,
  clipboard), Network, System Monitor, Log Viewer, Settings, Date & time,
  Counter, About; desktop icons and the Desktop folder, context menus,
  drag and drop, hover highlights, taskbar tray.
* Users: per-user desktops, settings, Wi-Fi networks, SSH/SFTP jail;
  Telnet remote desktop on port 23.
