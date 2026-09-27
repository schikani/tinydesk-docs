# TinyDesk

TinyDesk is a windowed text desktop for microcontrollers that draws itself
in a compatible UTF-8 terminal with ANSI/VT cursor control and xterm mouse reporting: windows, a taskbar, a start menu, desktop icons, mouse
support and a set of apps, all sent as ANSI/VT escape sequences over a
serial line or a network connection. No display hardware is needed.

The core is portable C11 with no dependencies. A platform supplies four
functions (read a byte, write bytes, a millisecond clock, sleep) and,
optionally, services such as a file system or networking. Ports exist for
**ESP32-C6** and the **classic ESP32** (ESP-IDF), and for **Linux** and
**Windows**, where the desktop runs in a console window.

[TinyDesk Shell](shell/commands.md) (`tdsh`) is built in as the Terminal
app. It also runs on its own, without the desktop: see the two
[editions](guide/install.md#editions).

<pre class="td-art">
+--------------------------------------------------------------------------+
| [>_]      [((]      [▄█]      ╔ Task Manager ═══════════════════[-][x]╗  |
| Terminal  Network   System    ║ CPU 6.1 %   RAM 105 KB free           ║  |
|                     Monitor   ║ Windows (2)                           ║  |
| [[]]      [MQ]      [▐▌]      ║  >_ Terminal - tdsh        open       ║  |
| Files     MQTT      Task Man. ║ System tasks (10, busiest first)      ║  |
|                               ╚═══════════════════════════════════════╝  |
| [Start]  >_ Terminal  ▐▌ Task Manager         alice  Wi-Fi ███  2:18 PM  |
+--------------------------------------------------------------------------+
</pre>

## What is in it

| Part | Where | Docs |
| --- | --- | --- |
| Core: screen buffers, renderer, input parser, event queue, timers, window manager, widgets, themes | `src/`, `include/tinydesk/` | [Core](api/core.md), [Screen](api/screen.md), [Input](api/input.md), [Window manager](api/wm.md), [Widgets](api/widgets.md) |
| Apps: Terminal, Files, Editor, Network, MQTT, Modbus, System Monitor, Task Manager, Log Viewer, Settings, Software Update, Counter, About | `apps/` | [Apps API](api/apps.md), [Writing an app](guide/writing-an-app.md) |
| Protocols: sockets, MQTT 3.1.1 (TLS), Modbus TCP/RTU client and TCP server | `proto/` | [Sockets](api/sock.md), [MQTT](api/mqtt.md), [Modbus](api/modbus.md), [TLS](api/tls.md) |
| Ports: ESP32-C6 (USB Serial/JTAG), classic ESP32 with PSRAM and with 4 MB flash (UART0), Windows, Linux | `ports/` | [Architecture](ports/overview.md), [ESP-IDF](ports/esp.md), [Hosts](ports/host.md) |
| Shell: TinyDesk Shell (`tdsh`, the git submodule `third_party/tdsh`) plus `mqtt`, `modbus`, `ota` commands | `third_party/tdsh/`, `ports/common/td_proto_cmds.c` | [Commands](shell/commands.md), [Config files](shell/config-files.md) |
| Tools: serial probe, screen renderer, simulator, serial bridge, Modbus slave, LittleFS migration | `tools/` | [Tools](tools.md) |

## Boards

| | ESP32-C6 | ESP32 with PSRAM (e.g. WROVER-IE) | ESP32, 4 MB (e.g. WROOM-32) |
| --- | --- | --- | --- |
| Project | `ports/esp32c6` | `ports/esp32` | `ports/esp32-4mb` |
| Desktop link | built-in USB Serial/JTAG | UART0 (USB-UART chip), 921600 baud | UART0 (USB-UART chip), 921600 baud |
| Screen limit | 80x25 | 256x96 (buffers in PSRAM) | 80x25 |
| Flash | 8 MB, two OTA slots | 16 MB, two OTA slots | 4 MB, one app (update by flashing) |
| SSH/SFTP server | yes | yes | no (too little RAM; the Shell edition has it) |
| Everywhere | Wi-Fi, FTP, Telnet remote desktop, MQTT (TLS), Modbus TCP and RTU, users, board configuration | | |

Wiring (RS-485 lines, W6100 Ethernet, SD card) is set in the
[board configuration](guide/board-config.md) on every board.

**Try it:** [install the prebuilt firmware](guide/install.md) from the
browser, no toolchain needed, then read [First login](guide/first-login.md).
To build from source: [Getting started](guide/getting-started.md).

Current version: see [Changelog](changelog.md). Before putting a board on
a network, read [Security](security.md).
