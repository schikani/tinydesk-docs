# Troubleshooting

Problems met while building and using tinydesk, and what fixed them.

## The screen

**Nothing appears after connecting.** Press a key or Ctrl+L: the desktop
redraws for a terminal it has not heard from. On the ESP32 check the speed
(921600); garbage characters mean a wrong baud rate.

**A burst of junk characters when an ESP32 board starts.** The ESP32 ROM
prints its boot messages at 115200 before tinydesk starts; the desktop then
clears the screen. Only an eFuse removes them.

**Borders show as `â”€` or other odd characters.** The terminal is not in
UTF-8. PuTTY: *Window → Translation → Remote character set: UTF-8*. Or turn
on *ASCII-only drawing* in Settings.

**The screen goes blank after resizing the window** (only the parts under
the mouse come back). Fixed in 0.2.13; on older firmware press Ctrl+L or
use Start → Redraw screen. The desktop uses at most 80x25 on the ESP32-C6
and 256x96 on the ESP32; a bigger window keeps the rest blank.

**Mouse clicks do nothing.** PuTTY: leave *Terminal → Features → Disable
xterm-style mouse reporting* unticked. With Shift held, clicks go to
PuTTY's own text selection.

**Alt+F4 closes PuTTY.** Use Ctrl+Q to close a tinydesk window.

## Connecting

**The ESP32 resets every time PuTTY opens the COM port.** The USB-UART
chip's DTR/RTS lines drive the reset. Use `tools\tinydesk_putty.cmd COM10`
(the [serial bridge](guide/terminals.md#esp32-boards-without-resets)).

**"Access is denied" / port busy when flashing or connecting.** Another
program has the port: PuTTY, the serial bridge, `idf.py monitor`, or a
Modbus tool. Only one program can open a COM port.

**A USB-RS485 adapter stops with Windows error 31.** A flaky adapter or
hub (seen with CH340 adapters): replug it, try another port or adapter.

**The PC cannot reach the board over Telnet, SSH or HTTP, or the board
cannot reach the PC.** Check that both are on the same network (the Network
app shows the board's address; `ipconfig` the PC's). For connections from
the board to the PC (an MQTT broker, `serve_bin.py` for OTA), Windows
Firewall blocks incoming connections by default: allow the program (Python,
Mosquitto) for private networks, or mark the Wi-Fi network as *Private*.

**Wi-Fi sees networks at -90 dBm or worse and cannot join.** On modules
with an antenna connector (ESP32-WROVER-IE, `-IE`/`-U` variants) an external
antenna is needed.

**Root cannot log in over Telnet, SSH or FTP.** The factory password is
`TinyDesk` (capital T and D) unless someone changed it. If nobody knows
it, run `rootrecover` on the board's own console
([First login](guide/first-login.md)).

**A pin, UART or the Ethernet chip is wrong, or `rtu1` says "not
configured".** The wiring comes from the board configuration: `board show`
lists it, `board set` changes it (restart afterwards). See
[Board configuration](guide/board-config.md).

## SSH and memory

**`ssh start` says "insufficient internal RAM".** TinyDesk Shell's SSH server wants
96 KB of free internal RAM on the ESP32-C6 (64 KB on the ESP32). Close
windows (each app allocates while open), disconnect MQTT over TLS (about
17 KB), or start SSH right after boot; `heap` shows the free RAM. From 0.2.14
the C6 boots with about 109 KB free.

**`ssh stop` says "server shutdown timed out"** and a later start fails.
Fixed in 0.2.9.

**SSH/SFTP clients warn that the host key changed.** From 0.2.10 every
board has its own key: compare the fingerprint with `ssh hostkey`, then
remove the old entry (`ssh-keygen -R <ip>`, or accept in PuTTY/FileZilla).

**FileZilla says "Could not open directory".** Fixed in TinyDesk Shell's SFTP start
folder; update the firmware.

## MQTT, Modbus, updates

**MQTT: "not enough memory for ca.crt" or "SSL - Memory allocation failed".**
Fixed in 0.2.7 (certificate files are read at their size). With little RAM
left, close windows before connecting over TLS.

**MQTT over TLS: "certificate verify failed".** The broker's certificate is
not signed by a CA the board knows: set `cafile` in `mqtt.conf` to the
broker's CA certificate ([config files](shell/config-files.md)).

**Modbus RTU: no answer.** Check the line (`rtu1` / `rtu2`), baud rate and
parity (`rtu1:19200:8E1`), the unit id, and the A/B wiring; test with
`tools/rtu_slave.py` on a PC adapter.

**`modbus` reads the wrong address.** Before 0.2.15 a leading zero meant
octal (`010` was 8).

**An update goes back to the old version after a restart.** A new image
runs on trial for 30 s; a crash, a watchdog reset or a power cut before
that rolls back. Restart it on purpose after at least 5 s, or leave it
running for 30 s.

**The web installer does not find the board.** Use Chrome or Edge, install
the USB driver, try another cable, or hold BOOT while pressing RESET.

## Building

**`region dram0_0_seg overflowed` on the ESP32.** Build the desktop from
`ports/esp32`: it moves static buffers to PSRAM (`main/extram.lf`). The
classic ESP32's `undefined reference to MD5Init` (libsmb2) is handled by
TinyDesk Shell's `tdsh_md5_rom.c`; if you see it, the shell submodule is
out of date (`git submodule update --init`).

**`export.ps1` picks the wrong Python.** Activate ESP-IDF with
`C:\Espressif\Initialize-Idf.ps1 -IdfId <id>` (the ESP-IDF shortcut does the
same).
