# Files and settings

This page lists the files TinyDesk reads or writes, the NVS keys it and TinyDesk Shell use, and the flash partition tables.

## Paths

Shell paths and real paths differ:

| User | Shell `~` | Real path on the ESP32 | Real path on a host |
|---|---|---|---|
| root | `/root` | `/fs/root` | `<cwd>/tinydesk_fs/root` |
| other users | `/home/<user>` | `/fs/home/<user>` | `<cwd>/tinydesk_fs/home/<user>` |

On the ESP32 the LittleFS partition `storage` is mounted at `/fs`. On Windows and Linux the files live in `tinydesk_fs` under the directory the program was started in. Root sees the whole filesystem; every other user is kept inside their home, in the shell, over SFTP and in the desktop apps.

## Overview

| File or key | Written by | Read by |
|---|---|---|
| [`~/mqtt.conf`](#mqttconf) | `mqtt config init`, the MQTT app's **Config...** button, the Editor | `mqtt connect`, `mqtt config show`, the MQTT app |
| [`~/.tinydesk_settings`](#tinydesk_settings) | the Settings app, the Date & time dialog | the desktop, at start-up and after every user switch |
| [`~/.tdshrc.tdsh`](#tdshrctdsh) | TinyDesk Shell (created with comments only), the user | TinyDesk Shell, when the local console starts a session |
| [`/etc/board.conf`](#etcboardconf) | `board set`, `board init`, the user | TinyDesk Shell and the ports, at start-up |
| [`~/Desktop`](#the-desktop-folder) | the desktop (created with `Welcome.txt`), the user | the desktop, every 3 s |
| [NVS keys](#nvs-keys) | TinyDesk, TinyDesk Shell | TinyDesk, TinyDesk Shell |
| [Partition tables](#partition-tables) | the build | the bootloader |

---

## ~/mqtt.conf

MQTT client settings, in the style of the Mosquitto tools. Used by:

- `mqtt connect` with no broker (reads `~/mqtt.conf`), and `mqtt connect -c <file>` (see [shell commands](commands.md#mqtt-connect)); options on the command line override the file;
- `mqtt config show [file]`, which prints what a file sets;
- the MQTT app, when its **Broker** field holds a file name: one ending in `.conf`, or starting with `~` or `/`. Its **Login...** user and password override the file's.

The parser is `td_mqtt_load_config()` in `proto/td_mqtt_conf.c` (API: [td_mqtt](../api/mqtt.md#td_mqtt_load_config)).

### Syntax

- One setting per line: a key, blanks, then the value (the rest of the line, inner spaces included).
- Keys are case-insensitive. Values are not (`on` works, `On` does not).
- Blank lines are ignored. A line whose first non-blank character is `#` is a comment.
- An inline comment starts at a `#` that has a blank (or the start of the value) before it and a blank or the line end after it: `keepalive 60   # seconds`. A `#` inside a word (`pass#1`) is kept.
- On `subscribe`, `sub` and `will_topic` lines `#` is the MQTT wildcard, so those lines have no inline comments.
- Trailing blanks and the CR of CRLF files are removed.
- A value in double quotes has the quotes removed: `password "secret with spaces"`. Quotes do not protect a ` # ` inside the value.
- Lines are applied in order; a later line overrides an earlier one. `host` with a port and `url` also set the port (to 0 when they have none), so put `port` after them.
- Booleans: `on`, `true`, `yes`, `1` or `off`, `false`, `no`, `0`.
- The file may be up to 8192 bytes. The first bad line stops parsing with `line N (key): <reason>`; an unknown key is `unknown setting`.

### Keys

| Key (aliases) | Value | Default | Error text |
|---|---|---|---|
| `host` (`broker`) | Host name or address. A value containing `:` is parsed like `url` (`host:port`, `mqtts://host`, ...). | `localhost` | `bad host` |
| `url` | `mqtt://host[:port]`, `mqtts://host[:port]`; also `tcp://`, `ssl://`, `tls://`, or a bare `host[:port]`. Sets host, port and TLS. | | `url must be mqtt://host[:port] or mqtts://host[:port]` |
| `port` | 1..65535 | 1883, or 8883 with TLS | `port must be 1..65535` |
| `username` (`user`) | Up to 31 characters. | none (no login) | `username too long` |
| `password` (`pass`) | Up to 63 characters. Sent only with a user name. | none | `password too long` |
| `client_id` (`id`) | Up to 31 characters. | `tinydesk-` and 8 hex digits | `client_id too long (31 at most)` |
| `keepalive` | 5..65535 seconds. | 60 | `keepalive must be 5..65535 seconds` |
| `reconnect` (`auto_reconnect`) | Boolean: retry every 5 s after a drop. | off | `use on or off` |
| `clean_session` | Boolean. `off`: the broker keeps the session (subscriptions, queued QoS 1 messages). | on | `use on or off` |
| `tls` (`ssl`) | Boolean. | off | `use on or off` |
| `tls_insecure` (`insecure`) | Boolean: do not check the server certificate. Does not turn TLS on by itself. | off | `use on or off` |
| `cafile` (`ca_file`, `ca`) | Path of the CA certificate. Turns TLS on. | the device's trusted roots | `cafile not allowed` |
| `certfile` (`cert`) | Path of the client certificate. Turns TLS on. | none | `certfile not allowed` |
| `keyfile` (`key`) | Path of its private key. Turns TLS on. | none | `keyfile not allowed` |
| `key_password` (`keypass`) | Password of an encrypted key, up to 63 characters. | none | `key_password too long` |
| `will_topic` | Up to 63 characters, no `+` or `#`. | none (no will) | `will_topic: up to 63 characters, no + or #` |
| `will_payload` (`will_message`) | Up to 127 characters. | empty | `will_payload too long (127 at most)` |
| `will_qos` | `0` or `1`. | 0 | `will_qos must be 0 or 1` |
| `will_retain` | Boolean. | off | `use on or off` |
| `subscribe` (`sub`) | `<topic> [qos]`, topic up to 63 characters, wildcards allowed. QoS above 0 becomes 1. Repeat the line for more topics, up to 8. | none | `bad topic`, `8 subscriptions at most` |

After the last line the parser also checks that `certfile` and `keyfile` come together (`certfile and keyfile go together`).

The trusted roots are the ESP-IDF certificate bundle on the ESP32, the Windows ROOT store, or the system bundle on Linux (see [TLS](../api/tls.md#ca-sources)).

### Certificate paths

`cafile`, `certfile` and `keyfile` accept:

- `~/...`: the user's home, for example `~/certs/ca.crt`;
- `/...`: a shell path, for example `/root/certs/ca.crt` (users other than root only inside their home);
- anything else: relative to the folder of the config file, for example `certs/client.crt` next to `~/mqtt.conf`.

A path the user may not use gives `cafile not allowed` (and so on) at load time. The files themselves are read when connecting: PEM or DER, up to 16384 bytes each. Copy them to the device with SFTP or FTP.

### Example

```
url mqtts://broker.example.com:8883
client_id tinydesk-kitchen
username bob
password "secret with spaces"
cafile ~/certs/ca.crt
certfile certs/client.crt          # relative: from this file's folder
keyfile ~/certs/client.key
keepalive 60
reconnect on
will_topic devices/kitchen/status
will_payload offline
will_qos 1
will_retain on
subscribe devices/+/status 1
subscribe kitchen/#
```

### The template

`mqtt config init [file]` and the MQTT app's **Config...** button write this text (`td_mqtt_config_template`) when the file does not exist yet:

```
# MQTT client settings (TinyDesk). One setting per line; '#' starts a comment.
# Used by 'mqtt connect' with no broker, 'mqtt connect -c <file>' and the
# MQTT app (type the file name, e.g. ~/mqtt.conf, as the broker).

# Where: host and port, or a URL (mqtt://host:1883, mqtts://host:8883).
host localhost
#port 1883
#url mqtts://broker.example.com:8883

# Who
#client_id tinydesk-kitchen
#username bob
#password secret

# TLS. Without cafile the device's trusted roots are used (ESP32: the
# ESP-IDF certificate bundle; Windows: the ROOT store; Linux: the system
# bundle). Paths: ~/..., /absolute, or relative to this file. PEM or DER.
#tls on
#cafile ~/certs/ca.crt
#certfile ~/certs/client.crt
#keyfile ~/certs/client.key
#key_password secret
#tls_insecure off          # on: do not check the server certificate

# Session
#keepalive 60
#reconnect on              # try again every 5 s after a drop
#clean_session on          # off: the broker keeps our subscriptions/messages

# Last will: published by the broker if this device disappears.
#will_topic devices/tinydesk/status
#will_payload offline
#will_qos 1
#will_retain on

# Topics to subscribe to after connecting: subscribe <topic> [qos]
#subscribe devices/+/status 1
#subscribe tinydesk/#
```

The file may hold passwords. The parser wipes its copy of the file after reading it.

---

## ~/.tinydesk_settings

The desktop settings of one user, written by `apps/settings.c` as soon as something changes in the Settings app or the Date & time dialog. It is a 16-byte binary blob:

```c
typedef struct {
    uint32_t magic;       /* 0x54445331 */
    uint8_t theme;
    uint8_t ascii;
    uint8_t pattern;
    uint8_t hide_icons;
    uint8_t clock_12h;
    uint8_t date_format;
    uint8_t hide_clock;
    uint8_t icon_size;
    uint8_t menu_size;
    uint8_t bar_size;
    uint8_t reserved[2];
} settings_blob_t;
```

| Offset | Size | Field | Values | Invalid value |
|---|---|---|---|---|
| 0 | 4 | `magic` | `0x54445331`, stored little-endian: bytes `31 53 44 54` | File ignored |
| 4 | 1 | `theme` | `0` Classic, `1` Dark | Classic |
| 5 | 1 | `ascii` | `0` UTF-8 drawing, non-zero ASCII-only drawing | |
| 6 | 1 | `pattern` | Desktop background: `0` light shade (U+2591), `1` medium shade (U+2592), `2` dark shade (U+2593), `3` dots (U+00B7), `4` plain | Pattern not changed |
| 7 | 1 | `hide_icons` | `0` desktop icons shown, non-zero hidden | |
| 8 | 1 | `clock_12h` | `0` 24-hour clock, non-zero 12-hour | |
| 9 | 1 | `date_format` | `0` day-month-year, `1` year-month-day, `2` month-day-year | day-month-year |
| 10 | 1 | `hide_clock` | `0` date and time in the taskbar, non-zero hidden | |
| 11 | 1 | `icon_size` | Desktop icons: `0` medium, `1` small, `2` large | medium |
| 12 | 1 | `menu_size` | Start menu: same codes | medium |
| 13 | 1 | `bar_size` | Taskbar: same codes | medium |
| 14 | 2 | `reserved` | Written as 0 | |

Older versions wrote only the first 8 bytes (magic to `hide_icons`). A file of 8 to 15 bytes with the right magic is accepted, and the missing fields read as 0. In every newer field, 0 means the default: 24-hour clock, day-month-year dates, clock shown, and medium icons, start menu and taskbar. In `hide_icons`, 0 (also in blobs saved before icons existed) means icons are shown.

### Where the settings come from

When a user's settings are applied (at start-up and after each user switch), the first of these that exists is used:

1. `~/.tinydesk_settings` of the current user;
2. the device defaults: the 8-byte blob stored by the port, which older versions saved for every user. On the ESP32 it is NVS namespace `tinydesk`, key `settings`, and must be exactly 8 bytes; on hosts it is `tinydesk_settings.bin` in the current directory (its first 8 bytes are read). Only the first 8 fields are taken from it, the rest are 0;
3. built-in defaults: Classic theme, the current ASCII mode, light-shade pattern, icons shown, and 0 for the rest.

The current code writes only the per-user file; nothing writes the device defaults any more.

---

## ~/.tdshrc.tdsh

The user's boot script, a shell script (extension `.tdsh`) with one command per line. The shell runs it when the **local console** starts a session for the user: in TinyDesk, the Terminal window's console, when it starts, after a login at its `login:` prompt, and after `login <user>` there. It is not run for SSH sessions, and not when the desktop switches the console to another user (for example after a Telnet desktop login).

Typical content:

```
#!/bin/tdsh
# Startup script of alice
wificonnect
```

`wificonnect` without an SSID connects to the first visible saved network the user may use (see [Wi-Fi networks](commands.md#wificonnect)). Without it, and with `network autowifi off` (the default), Wi-Fi does not connect at boot.

If the file is missing, the shell creates it with comment lines only. At start-up, for each user:

```
# Startup script of <user>: runs when <user>'s local shell starts
# (the console, or the desktop's Terminal window). One command per line,
# e.g. wificonnect to join the saved Wi-Fi network at boot.
```

and when a session starts and the file is still missing:

```
#!/bin/tdsh
# TinyDesk Shell per-user startup script (uScript <version>)
# Runs when the local shell starts (the console, or the desktop's Terminal).
```

Other scripts are run with `tdsh run <file.tdsh|directory>`; a directory runs its `main.tdsh`.

---

## /etc/board.conf

The device's own [board configuration](../guide/board-config.md): pins and other hardware settings (`rs485.*`, `eth.*`, `sd.*`, `console.*`). Real path `/fs/etc/board.conf`; only root may change it (`board set`, `board unset`, `board init`, or `nano`). Each key in it overrides the settings built into the firmware (the port's `board.conf` or `board.example.conf` at build time). It is read at start-up, so restart after a change. Reflashing the firmware keeps it.

```
# Board configuration: this file overrides the settings built into
# the firmware. Restart after a change. Keys: see board.example.conf
rs485.1.uart = 1
rs485.1.tx   = 16
rs485.1.rx   = 17
rs485.1.de   = 18
```

---

## The Desktop folder

Each user's `~/Desktop` holds the files shown as desktop icons (`apps/desktop.c`). The desktop:

- creates `~/Desktop` for the current user if missing (and `/home` and the home folder), and puts a `Welcome.txt` in a new folder;
- re-reads the folder every 3 s, so files made from the shell (`touch ~/Desktop/notes.txt`) appear on their own;
- shows up to 24 entries and hides names starting with `.`;
- saves new files from the Editor's **Save as** there, and moves dragged files into it.

After a user switch the desktop shows the new user's folder.

---

## NVS keys

Keys in the ESP32's `nvs` partition used by TinyDesk and TinyDesk Shell:

| Namespace | Key | Type | Owner | Content |
|---|---|---|---|---|
| `tinydesk` | `settings` | blob, 8 bytes | `ports/esp_idf/app/main.c` | Device-default desktop settings (legacy; read only). See [above](#where-the-settings-come-from). |
| `tinydesk` | `telnet` | u8 | `ports/esp_idf/app/telnet.c` | Telnet remote desktop on port 23: `1` enabled (default when missing), `0` disabled. |
| `tdsh_ssh` | `hostkey` | blob, up to 160 bytes | TinyDesk Shell patch (`tdsh_ssh.c`) | This device's SSH host key: ECDSA P-256, DER (SEC1 with the public key, 121 bytes). Made on the first `ssh start`; deleted by `ssh hostkey new`. |
| `ush_wifi` | `db` | blob | TinyDesk Shell (`tdsh_wifi.c`) | Saved Wi-Fi networks, version 2: magic `0x55535746`, version `2`, count, then 12 entries of `used`, SSID (33 bytes), password (65 bytes) and owner (32 bytes; empty = shared). A version 1 blob (no owners) is converted on first load. |
| `ush_time` | `auto` | u8 | TinyDesk Shell patch (`tdsh_time.c`) | Automatic (SNTP) time: `1` on (default when missing), `0` off. |
| `ush_net` | `wifi_auto` | u8 | TinyDesk Shell (unchanged) | `network autowifi`: `0` off (default), `1` on. |
| `ush_net` | `mode` | u8 | TinyDesk Shell (unchanged) | `network mode`: auto, lan, wifi or both. |

TinyDesk Shell keeps its user database and boot user in namespace `ush_users`; TinyDesk does not change those.

Wi-Fi passwords and the host key are stored in NVS in plain form: the ports' `sdkconfig` files enable neither flash encryption nor NVS encryption.

---

## Partition tables

Both ports have two OTA app slots for `ota install` (see [ota](commands.md#ota)).

### ESP32-C6 (`ports/esp32c6/partitions.csv`)

ESP32-C6-WROOM-1/1U-N8, 8 MB flash.

| Name | Type | SubType | Offset | Size |
|---|---|---|---|---|
| `nvs` | data | nvs | `0x9000` | `0x6000` (24 KB) |
| `phy_init` | data | phy | `0xF000` | `0x1000` (4 KB) |
| `ota_0` | app | ota_0 | `0x10000` | `0x280000` (2.5 MB) |
| `ota_1` | app | ota_1 | `0x290000` | `0x280000` (2.5 MB) |
| `otadata` | data | ota | `0x510000` | `0x2000` (8 KB) |
| `storage` | data | littlefs | `0x520000` | `0x2E0000` (2.9 MB) |

NVS stays where it was before OTA support, so users, Wi-Fi networks and settings survive. The `/fs` partition moved and shrank from 4.9 MB to 2.9 MB; the README section "Updating the firmware (OTA)" describes moving its files over with `tools/lfs_migrate.c`. `ports/esp32c6/partitions_single_app.csv` keeps the older single-app layout for reference.

### ESP32 (`ports/esp32/partitions.csv`)

ESP32-WROVER-IE, 16 MB flash.

| Name | Type | SubType | Offset | Size |
|---|---|---|---|---|
| `nvs` | data | nvs | `0x9000` | `0x6000` (24 KB) |
| `phy_init` | data | phy | `0xF000` | `0x1000` (4 KB) |
| `ota_0` | app | ota_0 | `0x10000` | `0x300000` (3 MB) |
| `ota_1` | app | ota_1 | `0x310000` | `0x300000` (3 MB) |
| `otadata` | data | ota | `0x610000` | `0x2000` (8 KB) |
| `storage` | data | littlefs | `0x620000` | `0x9E0000` (9.9 MB) |

In both tables `storage` is the LittleFS partition that TinyDesk Shell mounts at `/fs`.
