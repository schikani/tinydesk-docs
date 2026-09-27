# Terminals and connections

The desktop is a stream of VT/xterm escape sequences, so any terminal with
xterm mouse reporting and UTF-8 shows it. This page covers the ways to reach
it: the board's USB or serial port, Telnet over the network, and the SSH/SFTP
shell.

## PuTTY settings

| Setting | Value |
| --- | --- |
| Connection type | *Serial*, `COMx`; speed: any value on the ESP32-C6 (USB), **921600** on the classic ESP32 (UART0) |
| Window | 80x25 or larger; resize freely (the desktop follows, up to the board's limit) |
| Window → Translation | remote character set **UTF-8** |
| Terminal → Features | leave "Disable xterm-style mouse reporting" **unticked** |

Keys PuTTY handles itself: **Alt+F4** closes PuTTY (use **Ctrl+Q** to close a
tinydesk window), **Shift+drag** is PuTTY's own text selection (copies to the
Windows clipboard), **Shift+Insert** and **Shift+right-click** paste. PuTTY
sends Ctrl+F4 as plain F4.

## Screen size

tinydesk asks the terminal for its size every second and redraws the whole
screen when it changes. The desktop uses at most the board's limit and the
top-left corner of a bigger window:

| Board | Limit | Why |
| --- | --- | --- |
| ESP32-C6 | 80x25 | the screen buffers are internal RAM, which SSH needs |
| ESP32 with PSRAM | 256x96 | buffers in PSRAM |
| Desktop hosts | 132x50 | default `TD_MAX_COLS` / `TD_MAX_ROWS` |

System Monitor shows "Screen: 80x25 of 120x40 (max)" when the window is
bigger than the limit. See [Core](../api/core.md) for the size polling and
[Configuration](../api/core.md#compile-time-configuration) for the limits.

## ESP32 boards without resets

On boards with a USB-UART chip (CP2102, CH340) the DTR and RTS lines drive
the ESP32's EN (reset) and IO0 pins so that esptool can flash it. PuTTY
raises both when it opens the port, so every connect reboots the board.
PuTTY has no option to leave the lines alone, and firmware cannot ignore a
reset. `tools/serial_bridge.py` avoids it: it opens the COM port with DTR
and RTS released, keeps it open, and lets PuTTY connect over Telnet on
`127.0.0.1`:

```bash
tools\tinydesk_putty.cmd COM10            # starts the bridge and PuTTY
python tools/serial_bridge.py COM10 --baud 921600 --listen 2310 --putty
```

or start the bridge alone and point PuTTY at *Telnet*, host `127.0.0.1`,
port `2310`. Closing and reopening PuTTY does not reset the board either:
the bridge sends the redraw request `ESC [ 5000 ~` (see
[Input](../api/input.md)) on every new connection, and the desktop comes
back as it was. Stop the bridge (Ctrl+C or close its window) before
flashing; esptool needs the port. The ESP32-C6's built-in USB port does not
have this problem.

## Remote desktop over Telnet (port 23)

After changing the root password with `passwd`, enable Telnet in Network.
With Wi-Fi up, choose *Telnet* in PuTTY, the board's address and port 23,
and log in as **root**. Non-root accounts use SSH shell sessions instead. The client then owns the desktop and the local screen shows
a notice until the session ends; the desktop switches to the user who
logged in and back afterwards. Telnet is plain text: use it on a trusted
network. The Network app has a switch to turn it off (saved in NVS).

## SSH and SFTP

`ssh start` (or the Network app) starts TinyDesk Shell's SSH/SFTP server on port 22.
This is a shell session, not the desktop. SFTP (e.g. FileZilla) is jailed to
the user's home, root sees the whole file system. Each board has its own
host key; compare the fingerprint from `ssh hostkey` with the one the
client shows the first time. See [Commands](../shell/commands.md#ssh).

## Other terminals

| Terminal | Notes |
| --- | --- |
| Windows Terminal | desktop builds; also `telnet <board>` / `ssh`. Supports OSC 52, so the Editor's Copy reaches the Windows clipboard |
| Tera Term | Serial or Telnet; Setup → General → language UTF-8 |
| Linux/macOS terminals | `picocom -b 921600 /dev/ttyUSB0`, `screen`, `telnet`; xterm, WezTerm and kitty support OSC 52 |
| `idf.py monitor` | not for interaction: the desktop owns the port and the ESP-IDF console is off (logs are in the Log Viewer app) |
