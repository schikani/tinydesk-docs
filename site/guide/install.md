# Install

Every release has ready-made firmware and programs, so trying TinyDesk
needs no toolchain. The **<a href="install/index.html">installer page</a>**
walks through the choices below. Building from source is on
[Getting started](getting-started.md).

## Editions

Like the desktop and server installs of an operating system, TinyDesk comes
in two editions:

| | TinyDesk Desktop | TinyDesk Shell |
| --- | --- | --- |
| What you get | windows, taskbar, start menu, mouse and the apps (Files, Editor, Network, MQTT, Modbus, Task Manager, ...), with the shell in the Terminal window | the shell alone on the console |
| Shell features | all of them | all of them: users, files, `.tdsh` scripts, Wi-Fi, Ethernet, SSH/SFTP, FTP, SMB, `board`, `hwtest` |
| Terminal | a VT terminal with mouse support (PuTTY, Windows Terminal, ...) | any serial terminal |
| Resources | more flash and RAM (the ESP32 needs PSRAM) | less; runs on more boards |
| Repository | [`tinydesk`](https://github.com/schikani/tinydesk) | [`tinydesk-shell`](https://github.com/schikani/tinydesk-shell) |

## Platforms

| Platform | TinyDesk Desktop | TinyDesk Shell |
| --- | --- | --- |
| ESP32-C6, 8 MB flash (e.g. ESP32-C6-DevKitC-1-N8) | web installer or esptool; built-in USB port, any speed | web installer or esptool; built-in USB port |
| ESP32 with PSRAM and 16 MB flash (e.g. ESP32-WROVER-IE N16R8) | web installer or esptool; USB-UART at 921600 baud, screens up to 256x96 | web installer or esptool; USB-UART at 115200 baud |
| ESP32 with 4 MB flash, no PSRAM (e.g. ESP32-WROOM-32 DevKitC) | web installer or esptool; 921600 baud; screen at most 80x25, no OTA updates, no SSH server | the same firmware as above; SSH works |
| Linux x86_64 | `tinydesk-desktop-linux-x86_64.tar.gz` | `tinydesk-shell-linux-x86_64.tar.gz` |
| Windows x64 | `tinydesk-desktop-windows-x64.zip` (run it in Windows Terminal) | not yet: use the Linux program in WSL, or the Desktop edition |
| macOS, other CPUs, other systems | build from source ([Getting started](getting-started.md)) | build from source (`cmake -DTDSH_BUILD_HOST=ON`) |
| Another microcontroller | [port it](../ports/overview.md): four functions | port the shell's platform API |

The PC programs are built without mbedTLS, so MQTT over TLS is not in them;
build from source with ESP-IDF's mbedTLS for that ([TLS](../api/tls.md)).

## ESP boards from the browser

Open the **<a href="install/index.html">installer page</a>** in Chrome or
Edge on a computer, choose the edition and the board, plug the board in,
press **Install** and pick its port.
[ESP Web Tools](https://esphome.github.io/esp-web-tools/) checks the chip
and writes the firmware. Choose **Erase device** for a first install and
whenever you switch a board between the two editions: users, Wi-Fi
networks and files then start fresh. On 4 MB ESP32 boards both editions use
the same flash layout, so there the files survive a switch without erasing.

The installer needs a browser with Web Serial (Chrome or Edge on a PC).

After installing, close the installer dialog and press **Open the web
terminal** (or use PuTTY): see
[Web terminal](terminals.md#web-terminal-in-the-browser). The installer's own
**Logs & Console** cannot show the desktop: it prints the escape sequences
as symbols.

If the board is not detected: install its USB driver (CP210x or CH340 on
ESP32 boards), use a data cable, and on some boards hold **BOOT** while
pressing **RESET** to enter the download mode.

## ESP boards with esptool

A release has one image per board and edition, written at offset 0:

```bash
pip install esptool
esptool.py --chip esp32c6 write_flash 0x0 tinydesk-desktop-0.1.0-esp32c6-factory.bin
esptool.py --chip esp32 -b 921600 write_flash 0x0 tinydesk-desktop-0.1.0-esp32-factory.bin
esptool.py --chip esp32 -b 921600 write_flash 0x0 tinydesk-desktop-0.1.0-esp32-4mb-factory.bin
esptool.py --chip esp32c6 write_flash 0x0 tinydesk-shell-0.1.0-esp32c6-factory.bin
esptool.py --chip esp32 write_flash 0x0 tinydesk-shell-0.1.0-esp32-factory.bin
```

Add `-p <port>` if esptool picks the wrong one. The image covers everything
below the file system (bootloader, partition table, NVS, the apps), so NVS
starts fresh: users, Wi-Fi networks and the SSH host key are recreated.
Files in `/fs` are kept when the edition stays the same. Run
`esptool.py erase_flash` first for a completely clean board, and always
when switching editions. Compare the files with `SHA256SUMS.txt`.

## Linux and Windows

Download the archive for your edition from the
[releases page](https://github.com/schikani/tinydesk/releases),
unpack it and start the program from a terminal:

<!-- tabs:start -->

#### **Linux**

```bash
tar xzf tinydesk-desktop-linux-x86_64.tar.gz
cd tinydesk-desktop-linux-x86_64
./tinydesk                      # or: ./tdsh from tinydesk-shell-linux-x86_64
```

#### **Windows**

```powershell
Expand-Archive tinydesk-desktop-windows-x64.zip .
cd tinydesk-desktop-windows-x64
.\tinydesk.exe                  # inside Windows Terminal
```

<!-- tabs:end -->

The desktop keeps its files in `./tinydesk_fs` (where you start it); the
shell program in `~/.local/share/tdsh/rootfs`, apart from your real home.

## Updating

A Desktop board that is set up updates itself: **Software Update** on the
board, or `ota install <url>` ([Shell commands](../shell/commands.md#ota)),
keeps users, networks and files. The web installer and the factory images
are for new installs.

## What is in a release

`tools/make_release.py` builds it ([Tools](../tools.md#make_releasepy)); a
release is a flat set of files:

| File | Contents |
| --- | --- |
| `tinydesk-<edition>-<version>-<board>-factory.bin` | the whole firmware in one image, for `write_flash 0x0` |
| `manifest-<edition>-<board>.json` | the ESP Web Tools manifest of that board (it names `firmware/<image>`) |
| `tinydesk-desktop-linux-x86_64.tar.gz`, `tinydesk-desktop-windows-x64.zip`, `tinydesk-shell-linux-x86_64.tar.gz` | the PC programs, with a README and the licences |
| `SHA256SUMS.txt`, `README.txt` | checksums and short instructions |

Boards: `esp32c6`, `esp32` (PSRAM, 16 MB) and `esp32-4mb` for the Desktop
edition; `esp32c6` and `esp32` (every ESP32) for the Shell edition.

The GitHub Actions workflow `.github/workflows/release.yml` of the
`tinydesk` repository builds all of it on every `v*` tag (firmware with
ESP-IDF 5.3.1 in the `espressif/idf` container, the Linux programs on
Ubuntu 22.04, the Windows program with MinGW) and attaches it to the GitHub
Release. The site's `tools/fetch_release.py` copies a release into the
installer: manifests next to it, images in `install/firmware/`, programs in
`install/downloads/`.

After installing: [First login and users](first-login.md).
