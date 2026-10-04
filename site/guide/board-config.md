# Board configuration

Which GPIO drives what — the RS-485 transceivers, a W6100 Ethernet chip, an
SD card, the classic ESP32's console UART — is **not compiled into the
code**. It comes from a small text file, the *board configuration*. So:

* one firmware runs on many boards; prebuilt releases are configured on
  the device, with no rebuild;
* your own wiring stays on your PC: `board.conf` is in `.gitignore`, and
  only the commented `board.example.conf` files are in the repository;
* new modules add their own keys the same way (see
  [Adding keys](#adding-keys-for-a-new-module)).

## Where the settings come from

For every key, the first of these that sets it wins:

| # | Source | Who writes it | Changes take effect |
| --- | --- | --- | --- |
| 1 | **`/etc/board.conf` on the device** (real path `/fs/etc/board.conf`) | `board set`, `board init`, `nano`, SFTP | at the next restart |
| 2 | **Built into the firmware**: `ports/<chip>/board.conf` if it exists when you build, otherwise `ports/<chip>/board.example.conf` | you, before `idf.py build` | after flashing |
| 3 | The code's default: usually "not connected" | — | — |

A key that is missing everywhere means "this board does not have it": no
RS-485 lines, no Ethernet, no SD card. With the example files as shipped
(everything commented out), a board is treated as a bare dev board with
Wi-Fi only.

Prebuilt release firmware contains only the example, so people who flash
a release configure their board with `board set` (layer 1). People who
build from source can use either layer.

## Configure your board

### From source (your own `board.conf`)

```bash
cd ports/esp32c6                       # or ports/esp32
cp board.example.conf board.conf       # Windows: copy board.example.conf board.conf
# edit board.conf: remove the '#' in front of the lines your board has
idf.py build flash
```

The build prints which file it used:

```text
-- tinydesk board configuration: .../ports/esp32c6/main/../board.conf
```

`board.conf` is ignored by git, so `git status` never offers it and a pull
request cannot include it by accident.

### On the device (`board` command)

In the Terminal, as root:

```text
# board set rs485.1.uart 1
# board set rs485.1.tx 16
# board set rs485.1.rx 17
# board set rs485.1.de 18
Saved in /etc/board.conf. Restart to apply.
# reboot
```

Or write a complete file and edit it:

```text
# board init              # copies the built-in settings, commented, to /etc/board.conf
# nano /etc/board.conf
# reboot
```

`board show` lists every setting and where it came from; anyone may run
it.

```text
$ board show
Board configuration: 4 settings (device file /etc/board.conf)
  rs485.1.uart           = 1                (file)
  rs485.1.tx             = 16               (file)
  rs485.1.rx             = 17               (file)
  rs485.1.de             = 18               (file)
```

| Command | Who | What it does |
| --- | --- | --- |
| `board` or `board show` | anyone | list the settings with their origin: `built-in` or `file` |
| `board get <key>` | anyone | one setting; exit status 1 if it is not set |
| `board set <key> <value>` | root | write the key to `/etc/board.conf` (other lines and comments stay as they are) |
| `board unset <key>` | root | remove the key from `/etc/board.conf`; the built-in value (if any) applies again |
| `board init` | root | create `/etc/board.conf` from the built-in settings; refuses to overwrite an existing file |

A line `eth.chip =` (empty value) in `/etc/board.conf` unsets a built-in
key for this device.

## File format

```text
# comment
rs485.1.uart = 1        # a comment after a value is fine
eth.chip     = w6100
sd.cs        =          # empty value: unset
```

* one `key = value` per line; spaces around `=` are optional;
* keys are lower case: `a-z 0-9 . _ -`, at most 39 characters;
* values are one word or number, at most 95 characters, no `#`;
* numbers are decimal or `0x` hex; GPIO and UART numbers use `-1` for
  "not connected";
* CRLF line ends (a file edited on Windows) are fine;
* a line that is not `key = value` is skipped, and the Log Viewer names
  the first one (`/etc/board.conf line N is not "key = value"; skipped`).

## Keys

### RS-485 lines (Modbus RTU `rtu1`, `rtu2`)

Read by `ports/esp_idf/app/rs485.c` (all ESP ports) and `hwtest rs485`.
A line exists when all four of its keys are set.

| Key | Meaning |
| --- | --- |
| `rs485.1.uart` | UART number for line 1. It must not be the console's UART. |
| `rs485.1.tx`, `rs485.1.rx` | TX and RX GPIO. |
| `rs485.1.de` | The transceiver's DE (and /RE) pin. The UART drives it through its RTS signal in RS-485 half-duplex mode. While the line is closed it is held low, so the board only listens. |
| `rs485.2.*` | The same for line 2. |

The Modbus app and `modbus` name the lines from these keys, for example
`rtu1 = RS485-1 (UART1: TX16 RX17 DE18)`. `hwtest rs485` (a loopback of
line 1 to line 2) needs both lines.

### W6100 Ethernet (SPI)

Read by TinyDesk Shell's Ethernet module (`lan`, `network`). `lan hw` shows the
values in use; `lan hw set` writes them here too.

| Key | Default | Meaning |
| --- | --- | --- |
| `eth.chip` | none | `w6100` switches Ethernet on. Without it, `lan` reports that the board has no Ethernet and nothing touches the pins. |
| `eth.spi_host` | 1 | SPI controller: 1 = SPI2_HOST (2 = SPI3_HOST on the classic ESP32). |
| `eth.miso`, `eth.mosi`, `eth.sclk`, `eth.cs` | -1 | SPI GPIOs; all four are needed. |
| `eth.int` | -1 | Interrupt GPIO; -1 polls the chip every `eth.poll_ms`. |
| `eth.rst` | -1 | Reset GPIO; -1 if not connected. |
| `eth.spi_mhz` | 10 | SPI clock in MHz. |
| `eth.poll_ms` | 100 | Poll period when `eth.int` is -1 (`lan poll` writes it). |

### SD card (SPI)

For [`sd`](../shell/commands.md#sd) (the card at `/sd`) and `hwtest sd`.
The firmware of a release has no pins built in: on a board with a card slot
set them once and restart, for example `board set sd.cs 22` when the card
shares the W6100's bus (the `eth.*` keys), otherwise also `sd.miso`,
`sd.mosi` and `sd.sclk`.

| Key | Default | Meaning |
| --- | --- | --- |
| `sd.cs` | -1 | Chip select; the card needs it. |
| `sd.miso`, `sd.mosi`, `sd.sclk`, `sd.spi_host` | the `eth.*` values | Only needed when the card is not on the Ethernet chip's bus. |
| `sd.automount` | 0 | 1: mount the card at `/sd` at boot. |

### Updates

| Key | Default | Meaning |
| --- | --- | --- |
| `update.url` | the official feed | The update feed *Check for official updates* and the daily check read (`http://` or `https://`, a full URL to an `update-desktop-<board>.json`), for example your own server. |

### Console (classic ESP32 only)

Read by `ports/esp_idf/app/link_uart.c` at start-up. The ESP32-C6 uses its
built-in USB Serial/JTAG port and has no such keys.

| Key | Default | Meaning |
| --- | --- | --- |
| `console.uart` | 0 | UART that serves the desktop. |
| `console.tx`, `console.rx` | the UART's usual pins (GPIO1 / GPIO3 on UART0) | TX and RX GPIO. |
| `console.baud` | 921600 | Line speed; set the same in the terminal. |

!> A wrong console setting leaves the serial port silent. Fix it over
Telnet or SSH if the board is on the network (`board unset console.baud`,
then `reboot`). Reflashing does **not** remove `/etc/board.conf`, because
the file system is kept. The last resort is erasing the file system, which
deletes all files on the board:
`esptool.py --chip esp32 erase_region 0x620000 0x9E0000`.

## Choosing pins

| Chip | Avoid | Notes |
| --- | --- | --- |
| ESP32-C6 | GPIO12/13 (USB D-/D+, the desktop's port), GPIO24-30 (flash on most modules) | UART0 and UART1 are free for RS-485: the console is USB Serial/JTAG. GPIO4/5 are used by `hwtest uart` (LP UART loopback). |
| ESP32 | GPIO6-11 (flash), GPIO16/17 (PSRAM on WROVER modules), GPIO1/3 (UART0, the desktop) | Use UART1 and UART2 for RS-485. GPIO34-39 are inputs only: fine for `eth.int` or RX, not for TX, DE or CS. Strapping pins (0, 2, 5, 12, 15) need care at boot. |

The examples in `board.example.conf` are illustrations, not a tested
product. Check them against your board's schematic.

## Adding keys for a new module

A module reads its wiring when it starts. The configuration is loaded
before the shell and the desktop start, so any later code can use it:

```c
#include "tdsh_board.h"

int cs   = tdsh_board_int("lcd.cs", -1);          /* -1: not connected */
int mhz  = tdsh_board_int("lcd.spi_mhz", 20);
bool inv = tdsh_board_bool("lcd.invert", false);  /* 1/0, yes/no, on/off, true/false */
const char *chip = tdsh_board_get("lcd.chip");    /* NULL if not set */
if (!chip) return ESP_ERR_NOT_SUPPORTED;            /* the board has no LCD */
```

Conventions:

1. Name keys `<module>.<item>`, or `<module>.<n>.<item>` for numbered
   units (`rs485.2.tx`). Lower case.
2. A missing key means "not fitted": do nothing and touch no pin. Use -1
   for "not connected" on a single pin.
3. Read the values once at start-up. Changes apply after a restart, and
   the docs say so.
4. Add the keys, commented out, to **both** `board.example.conf` files,
   with a short explanation, and to the tables on this page.
5. Never put a real board's pins in code or in Kconfig defaults.

The API is declared in `third_party/tdsh/include/tdsh_board.h`:

| Function | Purpose |
| --- | --- |
| `tdsh_board_get(key)` | The value as text, or `NULL`. |
| `tdsh_board_int(key, def)` | The value as a number (decimal or `0x`), or `def` if it is missing or not a number. |
| `tdsh_board_bool(key, def)` | `1/0`, `yes/no`, `on/off`, `true/false`, else `def`. |
| `tdsh_board_origin(key)` | `TDSH_BOARD_BUILTIN`, `TDSH_BOARD_FILE` or `TDSH_BOARD_UNSET`. |
| `tdsh_board_count()`, `tdsh_board_at(i, ...)` | Iterate over all settings (as `board show` does). |
| `tdsh_board_set(key, value)` | Write or remove (`value` NULL) a key in the device file, keeping its other lines, then reload. |
| `tdsh_board_load(builtin, path)` | Load the configuration (the shell's ESP-IDF start-up does this with `tdsh_espidf_config_t.board_config`). |
| `tdsh_board_parse(text, fn, user)` | Parse text and call `fn` for each setting (no storage). |

The ESP ports pass the built-in text to the shell like this
(`ports/esp_idf/app/main.c`):

```c
extern const char s_board_builtin[] asm("_binary_board_builtin_conf_start");
cfg.board_config = s_board_builtin;   /* board.conf or board.example.conf, embedded by main/CMakeLists.txt */
```
