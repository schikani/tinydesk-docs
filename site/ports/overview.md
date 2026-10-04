# Architecture and porting

TinyDesk is a single-threaded core that turns a byte stream in (keys, mouse,
terminal replies) into a byte stream out (escape sequences). Everything a
platform must provide is a four-function HAL; everything else a platform
*may* provide (heap numbers, a file system, networking, firmware updates,
the system's task list) goes through one optional table,
[`td_sysinfo_t`](../api/sysinfo.md).

## Layers

```
 apps/          Terminal, Files, Editor, Network, MQTT, Modbus, Task Manager, ...
   |  td_apps.h: registry, sessions, clipboard, settings
 src/ (core)    window manager + widgets  ->  screen buffers  ->  renderer (diff)
   |            input parser -> event queue -> dispatch ; timers ; vterm
 proto/         sockets, MQTT, Modbus, TLS (polled from a 20 ms timer, no threads)
   |
 td_hal_t       read_byte / write / millis / sleep_ms          td_sysinfo_t (optional)
   |                                                                |
 ports/         esp32c6, esp32 (ESP-IDF), windows, posix, common (host start-up, TinyDesk Shell bridges)
```

The core never calls an operating-system or hardware API itself. It does
allocate screen buffers at `td_init()` and can grow a pasted-text buffer later; apps and protocols allocate only while they
are in use (a window open, a connection up), which is what keeps it inside
the ESP32-C6's RAM.

## One frame

1. `td_step()` reads every waiting input byte through `hal->read_byte` and
   feeds the parser ([Input](../api/input.md)), which queues events.
2. Events are dispatched: resizes change the screen size; keys, mouse and
   pastes go to the start menu, taskbar, focused window and its widgets
   ([Window manager](../api/wm.md)).
3. Due timers run (window ticks, the protocol poll, app timers).
4. If anything changed, the window manager composes the whole desktop into
   the back buffer, and the renderer sends only the cells that differ from
   what the terminal shows ([Screen](../api/screen.md)).
5. Every second the terminal is asked for its size; a changed answer causes
   a full redraw ([Core](../api/core.md)).

The loop then sleeps `TD_LOOP_SLEEP_MS` (5 ms) through `hal->sleep_ms`.

## Porting to a new platform

1. Implement [`td_hal_t`](../api/core.md#hardware-abstraction-layer): non-blocking `read_byte`
   (return -1 when nothing is waiting), `write` that may block briefly but
   never forever (return what was accepted; a short write counts as a
   dropped frame and the renderer retries a full redraw later), a
   millisecond clock and a sleep.
2. Call `td_init(hal)`, register apps (`td_apps_register_all()` or your
   own), optionally `td_set_sysinfo()`, then `td_run()` or your own loop
   calling `td_step()`.
3. Fill the parts of `td_sysinfo_t` you can support: heap numbers, a file
   system for the Files and Editor apps, network ops for the Network app,
   OTA ops, the clock, the task list. Everything is optional; apps show
   "n/a" or hide features that are missing.
4. For the Terminal app, give it a backend (`td_terminal_set_backend()`,
   see [Apps API](../api/apps.md)): a byte pipe to a shell.
5. Size the build with the `TD_*` macros in `td_config.h`
   ([Configuration](../api/core.md)): screen limit, widget pool, scrollback,
   output buffer.

Existing ports to copy from: [ESP-IDF](esp.md) (FreeRTOS, a Telnet mux on
top of the local link) and [desktop hosts](host.md) (raw console mode,
shell on a thread).

## Source layout

| Path | Contents |
| --- | --- |
| `include/tinydesk/` | public core headers (`td.h` includes all of them except `td_vterm.h`) |
| `src/` | core: `td.c` (loop), `screen.c`, `draw.c`, `render.c`, `utf8.c`, `input.c`, `event.c`, `timer.c`, `wm.c`, `widgets.c`, `theme.c`, `vterm.c` |
| `apps/` | built-in apps and `td_apps.h` |
| `proto/` | `td_sock`, `td_mqtt` (+ config file parser), `td_modbus`, `td_tls` |
| `ports/common/` | host start-up, stdio file system, TinyDesk Shell host bridge, `mqtt`/`modbus` shell commands |
| `ports/esp_idf/` | the ESP code shared by the ESP-IDF projects: the application (`app/`) and the TinyDesk component (`components/tinydesk/`) |
| `ports/esp32c6/`, `ports/esp32/`, `ports/esp32-4mb/` | the ESP-IDF projects for the ESP32-C6, the ESP32 with PSRAM and the 4 MB ESP32: link, partitions, `sdkconfig.defaults` |
| `ports/windows/`, `ports/posix/` | desktop `main.c` and console HALs |
| `third_party/tdsh/` | TinyDesk Shell, the git submodule (repository `tinydesk-shell`) |
| `tests/`, `tools/` | unit tests (ctest), [tools](../tools.md) |
| (separate) | these docs and the web installer, kept apart from the code |
