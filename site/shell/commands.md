# Shell commands

This page lists the shell commands that TinyDesk adds to TinyDesk Shell (`mqtt`, `modbus`, `ota`) and the shell commands that matter most on the desktop: `board`, `hwtest`, `lan`, `ssh`, `ftp` and the Wi-Fi commands. `help` in the Terminal lists all commands.

Commands run on the TinyDesk Shell task: in the desktop's Terminal window (the local console), or in an SSH or Telnet session. Their output goes to that session.

Examples use `$` as the prompt of any user and `#` for root.

"Local console" below means the desktop's Terminal window. On the ESP32 ports TinyDesk runs the TinyDesk Shell console loop in its own `tdsh` task and registers it as the local console, whether the desktop is shown on the local screen or over Telnet.

## Overview

| Command | Source | Ports | Who may run it |
|---|---|---|---|
| `mqtt` | `ports/common/td_proto_cmds.c` | all | any user |
| `modbus` | `ports/common/td_proto_cmds.c` | all (RTU where the board configuration has RS-485 lines) | any user |
| `ota` | `ports/esp_idf/app/ota_esp.c` | ESP32-C6, ESP32 | root |
| `ssh` | TinyDesk Shell | ESP32-C6, ESP32 | `status`, `hostkey`: any user; `hostkey new`: root; `start`, `stop`, `restart`: root, or any user on the local console |
| `ftp` | TinyDesk Shell | ESP32-C6, ESP32 | as `ssh` (no `hostkey`) |
| `board` | TinyDesk Shell (`tdsh_commands_espidf.c`) | ESP32-C6, ESP32 | `show`, `get`: any user; `set`, `unset`, `init`: root |
| `hwtest` | TinyDesk Shell | ESP32-C6, ESP32 (pins from the board configuration) | root |
| `lan` | TinyDesk Shell | ESP32-C6, ESP32 (only with `eth.chip = w6100`) | as in TinyDesk Shell |
| `networks`, `wifiadd`, `wifiremove`, `wificonnect` | TinyDesk Shell | ESP32-C6, ESP32 | any user, with per-user networks |
| `network autowifi` | TinyDesk Shell (unchanged) | ESP32-C6, ESP32 | any user |

Exit status, as the code returns it: 0 success, 1 failure, 2 usage error.

Commands can be combined into `.tdsh` scripts with variables, `if`, loops,
functions, pipes and redirection: see [Shell scripts](scripting.md).

---

## mqtt

MQTT client, TLS and `~/mqtt.conf` (shared with the MQTT app). The connection is the one [td_mqtt](../api/mqtt.md) keeps for the whole device, so a broker connected here shows up in the MQTT app and the other way round. It stays connected after the command ends.

Help line: `mqtt <connect|config|disconnect|status|sub|unsub|pub|log|listen> ...`

`mqtt` without arguments, or with a wrong one, prints:

```
usage:
  mqtt connect                     use ~/mqtt.conf
  mqtt connect -c <file>           use another config file
  mqtt connect <broker> [options]  broker: host[:port], mqtt://host[:port],
                                   mqtts://host[:port] (TLS, port 8883)
      -u user  -P password  -i client-id  -k keepalive  -r (reconnect)
      --tls  --cafile f  --cert f  --key f  --keypass p  --insecure
  mqtt config init | show [file]   write a template / show the settings
  mqtt disconnect | status
  mqtt sub [-q 0|1] <topic>        (wildcards + and # allowed)
  mqtt unsub <topic>
  mqtt pub [-q 0|1] [-r] <topic> <message...>   (-r: retain)
  mqtt log [count]                 last messages in and out
  mqtt listen [seconds]            print messages as they arrive (default 30)
```

Who: any user. File paths (`-c`, `--cafile`, `--cert`, `--key`, `config init|show`) follow the shell's path rules, so users other than root can only use files in their own home.

### mqtt connect

```
mqtt connect
mqtt connect -c <file> [options]
mqtt connect <broker> [options]
```

Settings are collected in this order:

1. A config file: the one given with `-c`, or `~/mqtt.conf` when no broker is given. See [config files](config-files.md#mqttconf).
2. The command-line options, which override the file.

| Option | Sets |
|---|---|
| `<broker>` | `host`, `host:port`, `mqtt://host[:port]`, `mqtts://host[:port]` (also `tcp://`, `ssl://`, `tls://`). |
| `-u user` | User name. |
| `-P password` | Password. |
| `-i client-id` | Client id (default `tinydesk-` plus 8 hex digits). |
| `-k keepalive` | Keep-alive in seconds (0: 60). |
| `-r` | Reconnect every 5 s after a drop. |
| `--tls` | Use TLS (default port 8883). |
| `--cafile f` | CA certificate; turns TLS on. Without it the device's trusted roots are used. |
| `--cert f`, `--key f` | Client certificate and key (both or neither); turn TLS on. |
| `--keypass p` | Password of an encrypted key. |
| `--insecure` | Do not verify the server certificate; turns TLS on. |

The command prints what it connects to, waits up to 15 s, then prints the outcome. It returns 0 only when connected. With reconnect on, a failed attempt keeps retrying in the background after the command returns.

```
$ mqtt connect 192.168.1.10 -u bob -P secret
Connecting to mqtt://192.168.1.10:1883...
Connected to 192.168.1.10:1883
```

```
$ mqtt connect
Connecting to mqtts://test.mosquitto.org:8886 (settings from the config file)...
Connected to test.mosquitto.org:8886 (TLS)
Security: TLSv1.2 TLS-ECDHE-RSA-WITH-AES-256-GCM-SHA384
```

Errors:

```
mqtt: no broker given and no ~/mqtt.conf (create one with: mqtt config init)
mqtt: ~/mqtt.conf: line 7 (port): port must be 1..65535
mqtt: bad broker ws://host
mqtt: certs/ca.crt is not allowed
mqtt: cannot resolve broker.example.com
Refused: bad user name or password
server certificate rejected:The certificate validity has expired (is the clock set?)
```

A running connection is replaced by the new one. Subscriptions made before are kept and sent again (use `mqtt disconnect` first to forget them).

### mqtt config

```
mqtt config init [file]
mqtt config show [file]
mqtt config
```

`file` defaults to `~/mqtt.conf`. `mqtt config` alone is `mqtt config show`.

`init` writes the commented template (text in [config files](config-files.md#the-template)) and refuses to overwrite:

```
$ mqtt config init
Wrote ~/mqtt.conf. Edit it (nano ~/mqtt.conf), then run: mqtt connect
$ mqtt config init
mqtt: ~/mqtt.conf already exists (edit it with nano)
```

`show` parses the file and prints the result, without passwords:

```
$ mqtt config show
broker     mqtts://broker.example.com:8883
client_id  tinydesk-kitchen
username   bob  (password set)
cafile     /root/certs/ca.crt
keepalive  60 s, reconnect on, clean_session on
will       devices/kitchen/status = offline (qos 1, retained)
subscribe  devices/+/status (qos 1)
subscribe  kitchen/# (qos 0)
```

With TLS and no `cafile` the line reads `cafile     (the device's trusted roots)`. With `tls_insecure on` a line `WARNING    tls_insecure: the server certificate is not checked` is added. A file error is printed as `mqtt: <file>: <error>`.

### mqtt disconnect, mqtt status

```
mqtt disconnect
mqtt status
```

`disconnect` closes the connection, forgets subscriptions and the message log, and prints `Disconnected`.

```
$ mqtt status
MQTT: connected
Broker: test.mosquitto.org:8886
Connected to test.mosquitto.org:8886 (TLS)
Security: TLSv1.2 TLS-ECDHE-RSA-WITH-AES-256-GCM-SHA384
Messages: 12 received, 3 published
Subscribed: devices/+/status (qos 1)
```

The first line is `not connected`, `connecting`, `logging in`, `connected` or `reconnecting`. The third line is the last status text or error. During the TLS handshake the first line also reads `not connected` (the state has no name in the command), while the third line says `TLS handshake with ...`.

### mqtt sub, mqtt unsub

```
mqtt sub [-q 0|1] <topic>
mqtt unsub <topic>
```

`-q` must come before the topic. Topics are up to 63 characters; `+` and `#` are allowed. Up to 8 subscriptions are remembered and sent again after a reconnect.

```
$ mqtt sub -q 1 devices/+/status
Subscribed to devices/+/status
$ mqtt unsub devices/+/status
Unsubscribed from devices/+/status
```

While the client exists but is not connected (after a drop), `sub` prints `Will subscribe to <topic> once connected` and `unsub` prints `Forgot <topic> once connected`. Errors: `mqtt: too many subscriptions (8 at most)`, `mqtt: connect first (mqtt connect), topic up to 63 characters`, `mqtt: not subscribed to that topic`.

### mqtt pub

```
mqtt pub [-q 0|1] [-r] <topic> <message...>
```

The words after the topic are joined with single spaces (up to 511 bytes). A message is required. `-r` sets the retain flag. The topic must not contain `+` or `#`.

```
$ mqtt pub -q 1 -r devices/kitchen/status online
Published 6 bytes to devices/kitchen/status
```

Errors: `mqtt: connect first; topic without + or #, up to 63 characters`, `mqtt: message too big or connection busy`.

### mqtt log

```
mqtt log [count]
```

Prints the last `count` messages (default 10) in and out, oldest first. Only the last 20 are kept, and each payload is cut to 120 bytes (`...` marks a cut).

```
$ mqtt log 3
<- devices/kitchen/status (retained) qos1  online
<- devices/garage/status (retained)  offline
-> devices/kitchen/temp  21.5
```

`<-` is received, `->` published. `No messages yet` when the log is empty.

### mqtt listen

```
mqtt listen [seconds]
```

Prints incoming messages as they arrive, for `seconds` (1..3600, default 30; other values give 30). It needs a connection (`mqtt: not connected`). It runs for the full time; Ctrl+C does not stop it.

```
$ mqtt listen 10
Listening for 10 s...
<- devices/garage/status  online
1 message
```

---

## modbus

Modbus TCP/RTU client and TCP server (shared with the Modbus app). See [td_modbus](../api/modbus.md).

Help line: `modbus <read|write|server> ...`

Usage text, as printed on the ESP32-C6:

```
usage:
  modbus read  <device> <unit> <co|di|hr|ir> <addr> [count] [-i ms] [-n times]
  modbus write <device> <unit> <co|hr> <addr> <value> [value...]
  modbus server start [port] | stop | status
  modbus server get <co|di|hr|ir> <addr> [count]
  modbus server set <co|di|hr|ir> <addr> <value> [value...]
device: host[:port] for Modbus TCP (port 502), or rtu[N][:baud[:8N1|8E1|8O1]]
for Modbus RTU: rtu1 = RS485-1 (UART1: TX16 RX17 DE18), rtu2 = RS485-2 (UART0: TX21 RX22 DE23).
co coils, di discrete inputs, hr holding registers, ir input registers;
addresses start at 0; values in decimal or 0x hex.
-i ms repeats the read every ms milliseconds (10..3600000, start to start),
-n times reads that often (default 10; 0 = until Ctrl+C in the Terminal window).
```

On a device without RS-485 lines (classic ESP32, Windows, Linux) the second device line reads `for Modbus RTU (not available here).`

Who: any user.

### Arguments

| Argument | Values |
|---|---|
| `device` | `host`, `host:port`, `rtu`, `rtuN`, `rtu[N]:baud`, `rtu[N]:baud:8N1` / `8E1` / `8O1` (see [targets](../api/modbus.md#targets)). |
| `unit` | 0..255. |
| table | `co`, `di`, `hr`, `ir` (also `coils`, `discrete`, `holding`, `input`, `0x`, `1x`, `4x`, `3x`). |
| `addr` | 0-based address. |
| `count` | 1..125 (default 1). |
| `value` | -32768..65535; negative values are sent as their 16-bit two's complement. For coils, any non-zero value is ON. |

Numbers are decimal, or hex with a `0x` prefix (`0x10` is 16). A leading `0` is still decimal (`010` is 10).

### modbus read

```
modbus read <device> <unit> <co|di|hr|ir> <addr> [count] [-i ms] [-n times]
```

Reads with FC 01, 02, 03 or 04 and prints one line per value: address, unsigned, hex and signed (registers), or address and 0/1 (bits).

```
$ modbus read 192.168.1.50 1 hr 0 3
Read 3 holding registers (14 ms)
      0     230  0x00E6     230
      1   65535  0xFFFF      -1
      2    1200  0x04B0    1200
```

```
$ modbus read rtu1:19200:8E1 17 co 0 4
Read 4 coils (31 ms)
      0  1
      1  0
      2  0
      3  1
```

A device exception or timeout is printed as the result and returns 1:

```
$ modbus read 192.168.1.50 1 hr 500 2
Exception 2: illegal data address (12 ms)
$ modbus read rtu2 5 ir 0
No answer (timeout) (1001 ms)
```

Other errors are printed as `modbus: <message>`, for example `modbus: Busy with another request` or `modbus: There is no RTU line 3 here (rtu1..rtu2)`.

### Repeat mode: -i and -n

`-i ms` repeats the read every `ms` milliseconds (10..3600000), measured from the start of one read to the start of the next. `-n times` sets how many reads (0..1000000, default 10); `0` means until Ctrl+C. `-n` needs `-i`. Both may stand anywhere after `read`. If a read takes longer than the interval, the next one starts right after it.

Each read prints one line: number, time since the first read, answer time, and the values. A summary follows.

```
$ modbus read 192.168.1.50 1 hr 0 2 -i 1000 -n 5
Reading every 1000 ms, 5 times (Ctrl+C in the desktop's Terminal stops it)
    #  time ms  answer  values from address 0
    1        0   12 ms  230 1200
    2     1000   11 ms  231 1200
    3     2000   --  No answer (timeout)
    4     3000   14 ms  231 1201
    5     4000   12 ms  232 1201
5 reads, 4 ok, 1 failed; one every 1000 ms; answer 11/12/14 ms (min/avg/max)
```

Ctrl+C:

- Works for a command typed in the desktop's Terminal window on the ESP32 ports. The loop checks for it while waiting between reads, prints `^C` and the summary. Other keys typed during the run are kept as type-ahead for the prompt, and dropped when Ctrl+C is pressed.
- Does not work in an SSH session: the check only reads the local console's input (the header says so). Use `-n` there.
- On Windows and Linux hosts no check is installed, and `-n 0` is refused: `modbus: -n 0 needs Ctrl+C, which is not available here: give a count`.

The command returns 0 when every read succeeded, else 1.

Errors: `modbus: -i needs a number`, `modbus: -i must be 10..3600000 ms`, `modbus: -n must be 0..1000000`, `modbus: -n goes with -i (the interval)`.

### modbus write

```
modbus write <device> <unit> <co|hr> <addr> <value> [value...]
```

Writes 1..64 values. One value uses FC 05 (coil) or FC 06 (register); more use FC 15 or FC 16.

```
$ modbus write 192.168.1.50 1 hr 10 1500 0x00FF
Wrote 2 values (9 ms)
$ modbus write rtu1 17 co 3 1
Wrote 1 value (27 ms)
```

Errors: `modbus: only coils (co) and holding registers (hr) can be written`, `modbus: bad value <v> (up to 64 values)`.

### modbus server

```
modbus server start [port]
modbus server stop
modbus server status
modbus server get <co|di|hr|ir> <addr> [count]
modbus server set <co|di|hr|ir> <addr> <value> [value...]
```

A Modbus TCP server with four tables of 128 entries, answering every unit id. `modbus server` alone is `status`. `get` and `set` need a running server (`modbus: start the server first (modbus server start)`). `set` may write the read-only tables (`di`, `ir`), which is how the device offers data. `get` reads 1..64 entries.

```
$ modbus server start
Modbus TCP server listening on port 502 (any unit id; 128 of each table)
$ modbus server set ir 0 215 1
Set 2 input registers from address 0
$ modbus server get ir 0 2
      0     215  0x00D7     215
      1       1  0x0001       1
$ modbus server status
Modbus TCP server: running on port 502, 1 client, 57 requests
$ modbus server stop
Modbus TCP server stopped
```

Errors: `modbus: bad port`, `modbus: bind: ...` (port in use), `modbus: count must be 1..64`, `modbus: addresses go up to 127`. `set` returns 1 when it hit the end of the table before writing every value.

---

## ota

Firmware update (OTA). Available on the ESP32-C6 and the classic ESP32 ports (both build `ports/esp_idf/app/ota_esp.c`). Who: **root only** (`TDSH_CMD_ROOT_ONLY`).

Help line: `ota <status|official|notify|check|install|cancel|restart|rollback> ...`

```
usage:
  ota status                    installed version, slots, last result
  ota official                  look up the newest official release
  ota notify [on|off]           daily check and notice (on: tell again)
  ota check <url|file>          show the version of an update
  ota install <url|file>        install it (then: ota restart)
  ota cancel | restart | rollback
url: http://... or https://... to a TinyDesk .bin; file: a .bin on this device.
```

`ota` alone is `ota status`. A file is a shell path (for example `~/tinydesk.bin`, copied with SFTP, FTP or SMB). HTTPS is checked against the ESP-IDF certificate bundle; plain HTTP is allowed.

The flash has two app slots, `ota_0` and `ota_1` (see [partition tables](config-files.md#partition-tables)). An update is written to the slot that is not running, checked (image format, chip, SHA-256) and made the boot slot. The next start runs it on trial: it confirms itself 30 s after start-up, or at a requested restart (`reboot`, `ota restart`, Start > Exit) after at least 5 s of uptime. If it crashes or resets before that, the bootloader goes back to the previous version.

### ota official, ota notify

`ota official` reads the update feed of the official releases, next to the
web installer (`https://schikani.github.io/tinydesk-docs/install/update-desktop-<board>.json`,
`<board>` `esp32c6` or `esp32`), and prints the newest release and the URL
of its app image; `ota install <that URL>` installs it:

```
# ota official
TinyDesk 0.1.4 is available (installed: 0.1.3). Install it?
Newest:    TinyDesk 0.1.4 of 2026-10-02, 1864 KB
Image:     https://schikani.github.io/tinydesk-docs/install/firmware/tinydesk-desktop-0.1.4-esp32c6-app.bin
Notes:     https://github.com/schikani/tinydesk/releases/tag/v0.1.4
Install:   ota install https://schikani.github.io/tinydesk-docs/install/firmware/tinydesk-desktop-0.1.4-esp32c6-app.bin
```

Other answers: `TinyDesk 0.1.3, the newest release, is installed.`, `No
update information for this board on the server (404).`, `Cannot reach the
update server: <esp error>`. The board key `update.url` (a full feed URL)
reads another feed instead, for example your own server.

`ota notify` shows whether the daily check is on (the default); `ota notify
off` turns it off, `ota notify on` turns it on and forgets which version you
were told about, so the newest one is announced again. The setting is the
Software Update app's *Check for official updates daily and notify me*
(NVS namespace `td_update`).

### ota status

```
# ota status
Firmware:  TinyDesk 0.1.0, built Sep 28 2026 00:45:54, ESP-IDF v5.3.1
Running:   ota_0
Other slot: ota_1 has version 0.1.0 (ota rollback)
Last:      Version 0.1.1 is installed. Restart to use it.
```

`Running:` adds ` (on trial: confirms itself 30 s after start-up)` for an unconfirmed update. `Other slot: ota_1 is empty` when it holds no app. `Last:` appears after a check or install in this boot.

### ota check, ota install

```
# ota check https://example.com/tinydesk.bin
Version 0.1.1 is available (installed: 0.1.0).
# ota install https://example.com/tinydesk.bin
    0%  0 of 1284 KB  0 KB/s
   10%  129 of 1284 KB  92 KB/s
   ...
  100%  1284 of 1284 KB  95 KB/s
Version 0.1.1 is installed. Restart to use it.
# ota restart
```

The command waits until the job ends, printing progress every 10 %. The job runs in its own task (`td_ota`), so `ota cancel` from another session or the Software Update app stops it (`Cancelled. The installed version is unchanged.`); Ctrl+C does not.

Messages: `That is version X, the one installed.`, `ota: an update is already running`, `ota: <file> is not allowed`, `Cannot download it: <esp error>`, `Download failed: <esp error>`, `The image is damaged or not for this chip.`, `Could not finish: <esp error>`, `Cannot open the file.`, `That is not an ESP32 firmware image (.bin).`, `That is not an application image.`, `The image (N KB) does not fit the update slot.`, `Writing failed: <esp error>`, `Not enough memory to start.`

### ota cancel, restart, rollback

- `ota cancel` asks a running job to stop and prints `Cancelling...`.
- `ota restart` restarts the device after 200 ms.
- `ota rollback` goes back to the other slot and restarts: `Going back to 0.1.0 and restarting...`, or, for a firmware still on trial, `Going back to the previous version and restarting...` (it marks itself invalid). Without a usable other version: `ota: there is no previous version to go back to`.

---

## ssh

Control the SSH/SFTP server. ESP32 ports only.

Help line: `ssh <start|stop|restart|status> [port] | ssh hostkey [new]`

```
ssh start [port]
ssh stop
ssh restart [port]
ssh status
ssh hostkey
ssh hostkey new
```

Without arguments it prints `usage: ssh <start|stop|restart|status> [port] | ssh hostkey [new]`. An unknown subcommand prints `usage: ssh <start|stop|restart|status> [port]`.

Who:

| Subcommand | Who |
|---|---|
| `status`, `hostkey` | any user |
| `hostkey new` | root (`ssh: permission denied: root required`) |
| `start`, `stop`, `restart` | root anywhere, or any user on the local console (`ssh: permission denied: root, or any user on the local console/desktop`) |

Before the patch, `ssh` was root-only. Remote shells of non-root users still cannot change the server. The permission check comes before the subcommand check, so such a user also gets "permission denied" for a mistyped subcommand.

The default port is 22; a port given to `start` or `restart` is remembered for later starts. One client at a time. SFTP is allowed for every user; users other than root are confined to their home (`/fs/home/<user>`), root starts in `/fs/root` and is not confined.

```
$ ssh start
SSH/SFTP server started on port 22.
wolfSSL/wolfSSH allocations use a private 64 KiB internal heap.
Login with a tdsh username/password.
$ ssh status
SSH/SFTP server: running
Port: 22
Host key: per-device ECDSA P-256, SHA256:0ABP/uQzdEWl2ES2m2RBZ1AJxfxZTODdlN+PhDKuGyc
Active clients: 0 / 1
wolfSSL allocator: private internal heap
Private SSH heap: 65536 bytes
Allocator guard errors: 0
Internal RAM free: 118340 bytes
$ ssh stop
SSH/SFTP server stopped.
```

The heap is in internal RAM on the ESP32-C6; on the classic ESP32 it is in PSRAM and the two lines say `private 64 KiB PSRAM heap` and `private PSRAM heap`.

`ssh stop` now works reliably (the listening socket wakes every 0.5 s to see the stop). Before, it could print `ssh: server shutdown timed out.` and block the next `ssh start`.

Start errors: `SSH server already running on port 22.`, `ssh: previous server is still shutting down.`, `ssh: no network interface is connected.`, `ssh: insufficient internal RAM (N bytes free; need at least M before start).`, `ssh: cannot create SSH server task.`, `ssh: server initialization failed. Check tdsh-ssh log above.`, `ssh: invalid port`. The RAM check needs 96 KiB free on the ESP32-C6 and 64 KiB on the classic ESP32, whose 64 KB SSH heap lives in PSRAM (the start message still says "internal heap").

### ssh hostkey

Each device makes its own ECDSA P-256 host key the first time the server starts and stores it in NVS (`tdsh_ssh` / `hostkey`, see [NVS keys](config-files.md#nvs-keys)). The development key built into TinyDesk Shell is only a fallback; `ssh status` then shows `Host key: built-in development key (not unique!), ...`.

```
$ ssh hostkey
Host key: per-device ECDSA P-256
Fingerprint: SHA256:q7Qm0x3cH1v9yWbKZr2pLx8TnE4sUaJd6fGhVkYtR0c
```

Before the server has started once in this boot: `Host key: not loaded yet (the server makes or loads it when it starts)`. The fingerprint is the one OpenSSH clients show.

```
# ssh hostkey new
Host key deleted. The server makes a new one when it next starts (ssh restart).
SSH and SFTP clients will then warn that the host key changed.
```

` (ssh restart)` appears only while the server is running. `ssh hostkey new` does not restart the server.

## ftp

Control the FTP server. Same permission rules as `ssh start|stop|restart`. `status` works for everyone.

```
usage: ftp <start|stop|restart|status> [port]
```

Default port 21. Errors include `ftp: permission denied: root, or any user on the local console/desktop` and `ftp: invalid port`.

## sd

The SD card as `/sd`: a card with a FAT file system (FAT12, FAT16 or FAT32;
not exFAT, which large SDXC cards often come with: `sd format --yes` makes
FAT32 on cards above about 1 GB) on the SPI bus, with the pins of the [board
configuration](../guide/board-config.md#sd-card-spi) (`sd.cs`, and
`sd.miso`/`sd.mosi`/`sd.sclk` or the W6100's `eth.*` bus, which the card
then shares with Ethernet). Root only.

```
usage: sd [status] | sd mount | sd umount | sd format --yes
```

```
# sd mount
SD card SB16G mounted at /sd.
# sd
SD card:   mounted at /sd
Pins:      SPI2 MISO 18 MOSI 23 SCLK 19 CS 22, 10000 kHz
At boot:   not mounted (board set sd.automount 1)
Card:      SB16G, SDHC/SDXC
Size:      14 GB
Free:      14 GB
```

While it is mounted the card is `/sd` everywhere: in the shell (`ls /sd`,
`cd /sd`, `nano`, `cp`), over FTP and, for root, SFTP, and in the desktop's
**Files** app as the folder `sd` at the top. Long file names work. The `sd`
folder itself cannot be deleted or renamed in Files.

- `sd mount` never formats; a card that has no FAT file system says so.
- `sd umount` before removing the card (close files on it first).
- `sd format --yes` erases the whole card and makes a new FAT file system,
  then mounts it.
- `board set sd.automount 1` mounts the card at every boot (a missing card
  is logged, not an error).

The mounted card uses a few KB of internal RAM (FAT buffers for up to five
open files).

## hwtest

Loopback tests for the board's SD card, TTL UART and RS-485 pair. Root only. The pins come from the [board configuration](../guide/board-config.md) (`sd.*`, `eth.*` for the shared SPI bus, `rs485.1.*`, `rs485.2.*`); a test whose pins are not configured is skipped. The TTL UART test uses the ESP32-C6's LP UART (GPIO5 TX, GPIO4 RX) and is skipped on other chips.

```
usage: hwtest <sd|uart|rs485> [count] | hwtest <status|all>
```

`hwtest` or `hwtest status` prints the map it would use:

```
# hwtest status
Hardware test map (board configuration)
-----------------------------------------------
SD card   : SPI MISO MOSI SCLK CS: 2 7 6 19
TTL UART  : LP_UART0 TX5 RX4 @ 115200
RS485-1   : UART TX RX DE: 1 16 17 18
RS485-2   : not configured
-----------------------------------------------
```

`hwtest sd` mounts the card for the test and unmounts it afterwards; when
it is already mounted (`sd mount`) it tests on it and leaves it mounted.
A skipped test prints `[SKIP] <name>` and does not count as a failure in `hwtest all`. `hwtest rs485` needs both RS-485 UARTs: `modbus` RTU releases a line 15 s after its last request, until then the Modbus side holds the UART.

## lan

TinyDesk Shell's W6100 Ethernet command. TinyDesk changes where the hardware settings live: `lan hw` shows the `eth.*` keys of the [board configuration](../guide/board-config.md), `lan hw set ...` and `lan poll <ms>` write them to `/etc/board.conf`, and a board without `eth.chip = w6100` has no Ethernet (`lan enable` says so and touches no pin). The IP settings (`lan dhcp`, `lan static`, `lan dns`) stay in NVS as before.

```
$ lan hw
W6100 hardware (board configuration, keys eth.*):
  chip:      none (set eth.chip = w6100)
  ...
```

## board

Show or change the [board configuration](../guide/board-config.md): the pins and other hardware settings the firmware reads at start-up.

```
usage:
  board [show]            every setting and where it comes from
  board get <key>
  board set <key> <value> (root) write it to /etc/board.conf
  board unset <key>       (root) remove it from /etc/board.conf
  board init              (root) start /etc/board.conf from the built-in settings
Settings are read at start-up: restart after a change.
```

```
$ board show
Board configuration: 2 settings (device file /etc/board.conf)
  rs485.1.uart           = 1                (built-in)
  rs485.1.tx             = 16               (file)
$ board get eth.chip
eth.chip is not set
# board set eth.chip w6100
Saved in /etc/board.conf. Restart to apply.
```

Errors: `board: permission denied: root required`, `board: keys are a-z 0-9 . _ - and values one line without #`, `board: /etc/board.conf already exists (edit it with nano)`. Exit status 0, 1 on an error, 2 for usage.

---

## Wi-Fi networks

The saved-network database (NVS `ush_wifi` / `db`, up to 12 networks) records an owner per network. A database from development builds, saved before owners existed, is converted on first load; its networks become shared.

| Network | Added by | Who may use it | Who may change or remove it |
|---|---|---|---|
| shared | root (or saved before owners existed) | everyone | root |
| own | another user | that user and root | that user and root |

The Network app uses the same database and rules.

### networks

```
networks
```

Lists the networks the current user may use. The label is `shared`, `yours`, or, for root, the owner's name.

```
$ networks
[1] "HomeNet"  (shared)
[2] "Workshop"  (yours)
```

`No saved networks. Use 'wifiadd <ssid>' to add one.` when there are none.

### wifiadd

```
usage: wifiadd <ssid> [password]
```

Saves a network, or updates the password of one you manage. Without a password it asks `Network password (Enter for open network): ` (in a background script: `wifiadd needs a password argument in a background script`). SSID up to 32 characters, password up to 63.

```
# wifiadd HomeNet s3cret-pass
Network HomeNet added successfully (shared with all users).
$ wifiadd Workshop
Network password (Enter for open network):
Network Workshop added successfully.
```

`Saved network database is full.` when 12 are saved.

### wifiremove

```
usage: wifiremove <ssid ...>
```

Removes networks you manage. A shared network, for a user other than root: `Network 'HomeNet' is shared; only root can remove it.` Unknown: `Network 'X' not found in database.`

### wificonnect

```
usage: wificonnect [saved_ssid]
```

With an SSID, connects to that saved network (the user's own entry first, then a shared one). Without, scans and connects to the first visible network the user may use. Waits up to 20 s, then starts network time sync.

```
$ wificonnect
Scanning for available saved networks ...
found: HomeNet (-58 dBm)
Connecting to network: HomeNet
Connected to HomeNet
IP address: 192.168.1.23
```

Errors: `Network 'X' not found in database.`, `No saved networks. Use 'wifiadd <ssid>' first.`, `No saved Wi-Fi network is currently visible.`, `Unable to connect to HomeNet.`

`wificonnect` is the usual line in a user's [boot script](config-files.md#tdshrctdsh). The boot-time automatic connection (`network autowifi on`) acts as the system and may use every saved network.

### network autowifi

This part of `network` is plain TinyDesk Shell, listed here because it decides whether Wi-Fi connects at boot without `wificonnect` in the boot script.

```
network [status] | network mode [auto|lan|wifi|both] | network autowifi [on|off]
```

```
$ network autowifi
off
$ network autowifi on
Wi-Fi auto-connect set to on.
$ network autowifi off
Wi-Fi auto-connect set to off.
Existing Wi-Fi connection is unchanged; future automatic reconnects are suppressed.
```

A wrong value prints `usage: network autowifi <on|off>`. The setting is stored in NVS (`ush_net` / `wifi_auto`, default off). Any user may change it.
