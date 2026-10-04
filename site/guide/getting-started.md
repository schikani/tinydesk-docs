# Getting started

This page builds TinyDesk from source for a desktop terminal, an ESP32-C6
and a classic ESP32. To try it on a board without installing anything, use
the [prebuilt firmware](install.md) instead. The terminal side
(PuTTY settings, Telnet, SSH) is on [Terminals and connections](terminals.md).

## Requirements

| For | You need |
| --- | --- |
| Desktop build | CMake 3.16+, a C11 compiler (GCC/MinGW-w64, Clang, MSVC), Ninja or Make |
| ESP32 boards | ESP-IDF **5.3.1** (other versions are untested) |
| Tools | Python 3 with `pyserial` (the ESP-IDF Python environment has it) |

## Get the source

The shell, [TinyDesk Shell](https://github.com/schikani/tinydesk-shell),
is a git submodule in `third_party/tdsh`, so clone with `--recursive`:

```bash
git clone --recursive https://github.com/schikani/tinydesk.git
cd tinydesk
git submodule update --init      # only if you cloned without --recursive
```

## Desktop (Windows, Linux, macOS)

<!-- tabs:start -->

#### **Windows**

```powershell
cmake -B build -G Ninja      # MinGW-w64 or MSVC
cmake --build build
build\tinydesk.exe           # inside Windows Terminal
```

#### **Linux / macOS**

```bash
cmake -B build -G Ninja      # or leave out -G for Make
cmake --build build
./build/tinydesk
```

<!-- tabs:end -->

The shell's files live in `./tinydesk_fs`; the Files app browses the same
tree. For MQTT over TLS the host build needs mbedTLS 3.x sources: it finds
the copy inside ESP-IDF, or give it one with
`-DTD_MBEDTLS_DIR=<path>` (for example a clone of
[mbedTLS](https://github.com/Mbed-TLS/mbedtls) v3.6.7 with its submodules).
See [TLS](../api/tls.md).

Tests:

```bash
cd build && ctest
```

## Your board's wiring

Before building for a board with RS-485 transceivers, a W6100 Ethernet
chip or an SD card, give the firmware your pins. Copy the example and
remove the `#` from the lines your board has:

```bash
cp ports/esp32c6/board.example.conf ports/esp32c6/board.conf   # or ports/esp32/...
```

`board.conf` stays on your PC (it is in `.gitignore`). A bare dev board
needs nothing. The pins can also be set later on the running board with
`board set`. See [Board configuration](board-config.md).

## ESP32-C6

<!-- tabs:start -->

#### **Windows**

```powershell
cd ports\esp32c6
idf.py set-target esp32c6        # once
idf.py build
idf.py -p COM3 flash             # close any terminal on COM3 first
```

#### **Linux / macOS**

```bash
cd ports/esp32c6
idf.py set-target esp32c6        # once
idf.py build
idf.py -p /dev/ttyACM0 flash     # macOS: /dev/cu.usbmodem*
```

<!-- tabs:end -->

`app-flash` writes only the application and keeps the file system, users,
Wi-Fi networks and settings. On Windows, `ports\esp32c6\build.ps1 -Port COM3`
finds the ESP-IDF 5.3.1 installation itself.

On Windows, keep the checkout in a short folder such as `C:\src\tinydesk`.
ESP-IDF's build folders nest deeply, and a checkout far down a long path
(for example inside `%TEMP%` or a deep profile folder) runs past Windows'
260-character path limit: the build stops with `ninja: error: mkdir(...):
No such file or directory`.

Open the board's USB port (it shows up as "USB JTAG/serial debug unit") in
a terminal and press a key: the desktop appears. The baud rate does not
matter on USB Serial/JTAG.

## Classic ESP32

Two projects, the same application:

| Board | Project |
| --- | --- |
| ESP32 with PSRAM and 16 MB flash (e.g. ESP32-WROVER-IE N16R8) | `ports/esp32` |
| ESP32 with 4 MB flash and no PSRAM (e.g. ESP32-WROOM-32 DevKitC) | `ports/esp32-4mb`: screen at most 80x25, no OTA updates, no SSH server |

The commands are the same; use `ports\esp32-4mb` instead of `ports\esp32`
for a 4 MB board.

<!-- tabs:start -->

#### **Windows**

```powershell
cd ports\esp32
idf.py set-target esp32            # once
idf.py build
idf.py -p COM10 -b 921600 flash
```

#### **Linux / macOS**

```bash
cd ports/esp32
idf.py set-target esp32            # once
idf.py build
idf.py -p /dev/ttyUSB0 -b 921600 flash
```

<!-- tabs:end -->

The shell's third-party components (LittleFS, wolfSSL, libsmb2, W6100)
come from the ESP-IDF component manager: the first build of each project
downloads them into its `managed_components` folder, at the versions
pinned in TinyDesk Shell's `idf_component.yml`.

The desktop runs on UART0 (the board's USB-UART chip) at **921600 baud
8N1**. Opening the COM port in PuTTY resets these boards (the chip's
DTR/RTS lines drive EN and IO0); use the [serial bridge](terminals.md#esp32-boards-without-resets)
to avoid that.

## First steps on the desktop

1. **F10** or a click on **[Start]** opens the start menu; double-click an
   icon to open an app.
2. Open the **Terminal** and try `help`, `ls /`, `heap`, `ifconfig`.
3. **Network** connects Wi-Fi (double-click a network). The board then
   serves the desktop over Telnet (port 23) and SSH/SFTP when started.
4. **Settings** sets the theme, icon/start menu/taskbar sizes and the
   desktop pattern; **Task Manager** shows windows and system tasks.
5. **Ctrl+Q** closes the focused window.

More: [Using the desktop](using.md).
