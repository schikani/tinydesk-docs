# Core

The core ties tinydesk together: it owns the two screen buffers, the renderer and the input parser, and runs the cooperative main loop that reads input, dispatches events, runs timers and sends the changed cells to the terminal. A port supplies only a small hardware abstraction layer (`td_hal_t`); everything else is portable C11. This page also lists every compile-time limit in `td_config.h`.

Header: `include/tinydesk/td.h` (umbrella), `include/tinydesk/td_hal.h`, `include/tinydesk/td_config.h`
Source: `src/td.c`

`td.h` includes `td_config.h`, `td_hal.h`, `td_input.h`, `td_screen.h`, `td_sysinfo.h`, `td_widgets.h` and `td_wm.h`. It does **not** include `td_vterm.h`; include that one yourself when you use the [Terminal emulator](vterm.md).

## Threading model

The UI core is single-threaded. Every function on this page and on the [Screen](screen.md), [Input](input.md), [Window manager](wm.md) and [Widgets](widgets.md) pages uses static state without locks and must be called from the task that runs `td_step()` / `td_run()` (the "UI task"). Other tasks must hand data to the UI task through their own queue or buffer, polled from a timer or `on_tick` callback. The HAL callbacks are also only called from the UI task.

## Hardware abstraction layer

```c
typedef struct td_hal {
    int (*read_byte)(void *ctx);
    int (*write)(void *ctx, const uint8_t *buf, int len);
    uint32_t (*millis)(void *ctx);
    void (*sleep_ms)(void *ctx, uint32_t ms);
    void *ctx;
} td_hal_t;
```

This is the only thing a port has to provide. The core never calls operating-system or hardware APIs directly.

| Field | Meaning |
|---|---|
| `read_byte` | Return the next input byte (0..255), or -1 if none is waiting. Must never block. The main loop calls it repeatedly until it returns -1 on every pass. |
| `write` | Write up to `len` bytes; return the number accepted. May block briefly (a few tens of ms) but must never block forever. A return value `<= 0` is taken to mean "the link is not draining" and the rest of the frame is dropped (see [Link supervision](#link-supervision)). A partial write (`0 < n < len`) is fine; the renderer retries with the remainder. |
| `millis` | Milliseconds since an arbitrary start point. It may wrap after about 49 days; all core comparisons use unsigned or signed differences and survive the wrap. |
| `sleep_ms` | Sleep or yield the CPU for about `ms` milliseconds. `td_run()` calls it between passes; `td_init()` calls it while waiting for the size answer. |
| `ctx` | Port-private pointer passed back to every callback. |

The HAL structure must stay valid (and unchanged) from `td_init()` until after `td_shutdown()`; the core keeps the pointer, not a copy.

Example of a HAL for a byte-stream link. The `uart_*` / `board_*` functions stand for your own driver:

```c
#include "tinydesk/td.h"

/* Your driver (not part of tinydesk). */
int uart_getc_nonblocking(void);                     /* -1 if empty */
int uart_write_timeout(const uint8_t *buf, int len, uint32_t timeout_ms);
uint32_t board_millis(void);
void board_delay_ms(uint32_t ms);

static int hal_read(void *ctx) { (void)ctx; return uart_getc_nonblocking(); }
static int hal_write(void *ctx, const uint8_t *buf, int len)
{
    (void)ctx;
    return uart_write_timeout(buf, len, 20);          /* never block forever */
}
static uint32_t hal_millis(void *ctx) { (void)ctx; return board_millis(); }
static void hal_sleep(void *ctx, uint32_t ms) { (void)ctx; board_delay_ms(ms); }

static const td_hal_t s_hal = { hal_read, hal_write, hal_millis, hal_sleep, NULL };

void ui_main(void)
{
    td_init(&s_hal);
    /* register apps, open windows ... */
    td_run();
    td_shutdown();
}
```

The host ports (`ports/windows/hal_win.c`, `ports/posix/hal_posix.c`) and the ESP-IDF ports (`ports/esp32c6/main/hal_mux.c`, which multiplexes the USB/UART link and Telnet) are complete working examples.

## Lifecycle

### td_init

```c
int td_init(const td_hal_t *hal);
```

Initialises the core and connects it to the terminal. In order it:

1. Stores `hal` and records the start time for `td_uptime_ms()`.
2. Clears the statistics, initialises the renderer and the input parser, empties the event queue and stops all timers (`td_timers_reset()`).
3. Sets up both screen buffers and the window manager at `TD_DEFAULT_COLS` x `TD_DEFAULT_ROWS`.
4. Sends the terminal setup sequence (alternate screen, hidden cursor, auto-wrap off, mouse reporting, bracketed paste, clear screen) and a size query, and marks everything for a full redraw.
5. Waits up to `TD_SIZE_QUERY_TIMEOUT_MS` for the size answer, sleeping 5 ms between polls. Input other than the size answer that arrives during the wait (up to `TD_EVENT_QUEUE_SIZE` events) is kept and delivered by the first `td_step()`.

Returns 0 (there is no failure path). `hal` must not be NULL. After `td_init()` returns, `td_stats()->cols/rows` hold the size in use: the terminal's answer clamped to the limits, or the defaults if it did not answer in time.

Call `td_init()` before registering apps, opening windows or starting timers: it resets the timer pool and the window manager. It may be called again after `td_shutdown()`; it resets the same state.

### td_run

```c
void td_run(void);
```

Runs the main loop: calls `td_step()` and then `hal->sleep_ms(ctx, TD_LOOP_SLEEP_MS)` until `td_step()` returns false, i.e. until `td_quit()` has been called. It does not call `td_shutdown()`.

### td_step

```c
bool td_step(void);
```

One pass of the main loop, for embedding tinydesk in another loop. It never sleeps; the caller decides how long to wait between passes (the ESP-IDF ports call `hal->sleep_ms(hal->ctx, TD_LOOP_SLEEP_MS)` themselves so they can do other work between passes). Returns false once `td_quit()` has been called.

A pass does the following:

1. **Read input.** Calls `read_byte` until it returns -1 and feeds each byte to the parser. If the event queue gets within 4 entries of full while reading (a long paste of keys, for example), the queued events are dispatched immediately so none are lost. The first byte of a pass can trigger a resync (see [Reconnect detection](#reconnect-detection)).
2. **Parser timeouts.** Turns a lone ESC into the ESC key after `TD_ESC_TIMEOUT_MS`, drops stalled escape sequences after `TD_SEQ_TIMEOUT_MS`, and delivers a stalled bracketed paste after `TD_PASTE_TIMEOUT_MS`.
3. **Dispatch events.** `TD_EV_RESIZE` events are handled by the core (below) and are not passed on. Every other event goes to `td_wm_dispatch()` (see [Window manager](wm.md)). After a `TD_EV_PASTE` has been dispatched, its text is freed.
4. **Timers.** Runs every due timer (`td_timers_run()`), which includes the windows' `on_tick` callbacks.
5. **Clock.** Once a second (whenever `td_millis() / 1000` changes), the whole screen is marked for recomposition so the taskbar clock updates. Because the renderer only sends changed cells, this costs a compose per second but very few bytes.
6. **Size poll / link retry.** While the link is up, the terminal size is queried every `TD_SIZE_POLL_MS` (serial terminals do not report resizes on their own). While the link is down, a resync is scheduled every `TD_LINK_RETRY_MS` instead.
7. **Render.** If a resync is pending, the setup sequence and a size query are sent and the whole screen is redrawn. Otherwise, if the link is up and the window manager reports a change (`td_wm_needs_redraw()`), the screen is composed into the back buffer and the difference to the front buffer is sent.
8. **Statistics.** Updates `bytes_sent`, `bytes_per_sec` and `loop_ms`.

### td_quit

```c
void td_quit(void);
```

Makes the current and all later `td_step()` calls return false, so `td_run()` returns after the current pass. The start menu's Exit entry calls it. Calling `td_init()` again clears the request.

### td_shutdown

```c
void td_shutdown(void);
```

Restores the terminal: disables mouse reporting and bracketed paste, resets colours, clears the screen, re-enables auto-wrap, shows the cursor and leaves the alternate screen. The bytes are flushed immediately. It does nothing before `td_init()`. It does not close windows or free anything; the HAL is still referenced, so keep it valid until this call returns.

### td_full_redraw

```c
void td_full_redraw(void);
```

Schedules a resync for the next `td_step()`: the terminal setup sequence and a size query are sent again and every cell is redrawn. Use it when the terminal may have lost its state, for example after switching the link to a different client (the ESP-IDF port calls it when a Telnet session takes over or releases the desktop), or after changing ASCII mode with `td_set_ascii_mode()` (see [Screen](screen.md)). Ctrl+L on the desktop also calls it.

### td_millis / td_uptime_ms

```c
uint32_t td_millis(void);
uint32_t td_uptime_ms(void);
```

`td_millis()` returns `hal->millis(ctx)`, or 0 before `td_init()`. Use it as the `now_ms` argument of the timer and parser functions. `td_uptime_ms()` returns the milliseconds elapsed since `td_init()`. Both wrap after about 49 days; compare times with unsigned subtraction (`now - then >= interval`).

## Terminal size handling

The size in use is always clamped to `TD_MIN_COLS`..`TD_MAX_COLS` by `TD_MIN_ROWS`..`TD_MAX_ROWS`. It is learned by moving the cursor to row 999, column 999 and asking for the cursor position (`ESC 7 ESC [ 999 ; 999 H ESC [ 6 n ESC 8`); the terminal clamps the move to its last cell and replies `ESC [ rows ; cols R`, which the input parser turns into `TD_EV_RESIZE`.

When a size report arrives:

- If it differs from the last reported size (`term_cols` x `term_rows`), a resync is scheduled. This also happens when the clamped size stays the same (the window grew beyond the maximum, or shrank back to it), because a terminal that changes size has usually cleared or shifted its content.
- If the clamped size differs from the size in use, both screen buffers are re-initialised, the window manager is told (`td_wm_set_screen_size()`), and a resync is scheduled.

Size queries are sent at start-up, with every resync, and every `TD_SIZE_POLL_MS` while the link is up. Setting `TD_SIZE_POLL_MS` to 0 disables the periodic query; resizes are then only noticed on a resync.

Gotcha: a program that sends its own `ESC [ 6 n` to the *host* terminal would have the reply taken as a resize. Cursor position reports with a row of 1 are not treated as resizes (they are indistinguishable from Shift+F3, `ESC [ 1 ; 2 R`).

## Link supervision

tinydesk is designed for links where the far end may not be there (a USB-serial port with no terminal open, a dropped Telnet session). The renderer detects this from the HAL `write` callback:

- **Dropped frame.** When `write` returns `<= 0`, the rest of the frame is discarded instead of stalling the UI. The core then counts a dropped frame, sets `link_up` to false and invalidates the front buffer so the next successful frame resends everything.
- **While the link is down**, no normal frames are rendered and the size is not polled. Every `TD_LINK_RETRY_MS` a resync (setup sequence, size query, full redraw) is attempted. The first frame that is accepted completely sets `link_up` back to true.

### Reconnect detection

The first input byte of a pass schedules a resync when either:

- input has been received before and the link has been silent for more than `TD_RECONNECT_SILENCE_MS`, or
- `link_up` is false (frames are being dropped).

Both usually mean that a terminal has just been opened on the other end and shows nothing yet; the resync sends it the setup sequence and the whole screen.

## Statistics

```c
typedef struct {
    int cols, rows;
    int term_cols, term_rows;
    uint32_t frames;
    uint32_t frame_ms;
    uint32_t loop_ms;
    uint32_t bytes_sent;
    uint32_t bytes_per_sec;
    uint32_t dropped_frames;
    bool link_up;
} td_stats_t;

const td_stats_t *td_stats(void);
```

`td_stats()` returns a pointer to the core's live statistics (never NULL). The structure is updated in place by `td_step()`; do not modify it. The System Monitor app displays it.

| Field | Meaning |
|---|---|
| `cols`, `rows` | Screen size in use (after clamping to the limits). |
| `term_cols`, `term_rows` | Size the terminal last reported; may exceed `TD_MAX_COLS` x `TD_MAX_ROWS`. 0 until the first report. |
| `frames` | Frames rendered, including dropped ones. |
| `frame_ms` | Duration of the last compose + render. |
| `loop_ms` | Duration of the last `td_step()` pass (excluding the sleep in `td_run()`). |
| `bytes_sent` | Total bytes the HAL accepted. Wraps at 2^32. |
| `bytes_per_sec` | Output rate, recomputed about once a second. |
| `dropped_frames` | Frames the link did not accept completely. |
| `link_up` | False while writes are being dropped. |

## Host clipboard (OSC 52)

```c
void td_host_clipboard_set(const char *text, int len);
```

Puts `len` bytes of `text` on the clipboard of the PC running the terminal, using `ESC ] 52 ; c ; <base64> BEL`. Only terminals that support OSC 52 act on it (for example Windows Terminal, xterm, WezTerm, kitty); others such as PuTTY ignore it. The Editor app calls it when copying.

| Parameter | Meaning |
|---|---|
| `text` | Bytes to copy (UTF-8 expected; it need not be NUL-terminated). |
| `len` | Number of bytes. |

Notes:

- Nothing is sent if `text` is NULL, `len <= 0`, `len > TD_OSC52_MAX`, `TD_OSC52_MAX` is 0, or before `td_init()`. Text longer than the limit is **not** truncated; it is not sent at all.
- The sequence is written and flushed immediately, outside the normal frame. If the link is currently dropping writes, the sequence is silently lost.
- There is no way to read the host clipboard back; pasting from the PC arrives as `TD_EV_PASTE` (see [Input](input.md)).

## Version

```c
#define TD_VERSION "0.2.15"   /* the current version, see the changelog */
#define TD_REPO_URL "github.com/schikani/tinydesk"
```

`TD_VERSION` is the core version string. The ESP-IDF projects set their own firmware version (`PROJECT_VER`, overridable with the `TD_VERSION` environment variable at build time); that does not change this macro. `TD_REPO_URL` is shown by the About app and is currently a placeholder.

## System information

`td.c` also implements `td_set_sysinfo()` and `td_sysinfo()`, declared in `td_sysinfo.h`. See [System info](sysinfo.md).

## Compile-time configuration

Every static pool in the core is sized in `td_config.h`. Each value except `TD_MIN_COLS` and `TD_MIN_ROWS` is wrapped in `#ifndef`, so it can be overridden from the build system (for example `-DTD_MAX_COLS=100`). Override a value consistently for every translation unit that includes the tinydesk headers, because several of them size public structures (`td_buffer_t`, `td_renderer_t`, `td_vterm_t`).

The host build (top-level `CMakeLists.txt`, used for the Windows and POSIX ports) uses the defaults. The ESP-IDF component (`ports/esp32c6/components/tinydesk/CMakeLists.txt`) is shared by the ESP32-C6 and classic ESP32 projects and sets `PUBLIC` compile definitions, with different screen limits depending on `CONFIG_SPIRAM`:

- **Without PSRAM** (the ESP32-C6 port): the buffers live in internal RAM, which TinyDesk Shell, Wi-Fi and SSH also need, so the screen is limited to 80x25.
- **With PSRAM** (the classic ESP32 port on an ESP32-WROVER, `CONFIG_SPIRAM=y`; its tinydesk statics are placed in PSRAM by `ports/esp32/main/extram.lf`): large enough for a maximised PuTTY.

In the table, "ESP-IDF value" lists `no PSRAM / PSRAM` where they differ; "-" means the default is used.

### Screen and terminal size

| Macro | Default | ESP-IDF value | Meaning |
|---|---|---|---|
| `TD_MAX_COLS` | 132 | 80 / 256 | Largest number of columns the screen buffers hold. Each `td_buffer_t` costs `TD_MAX_COLS * TD_MAX_ROWS * 8` bytes and the core has two (80x25: 32 KB total; 132x50: about 103 KB; 256x96: about 384 KB). |
| `TD_MAX_ROWS` | 50 | 25 / 96 | Largest number of rows. |
| `TD_DEFAULT_COLS` | 80 | - | Columns used until the terminal answers the size query (and if it never does). |
| `TD_DEFAULT_ROWS` | 25 | - | Rows used until the terminal answers. |
| `TD_MIN_COLS` | 40 | - | Smallest desktop width; smaller reported sizes are raised to it. Not overridable. |
| `TD_MIN_ROWS` | 12 | - | Smallest desktop height. Not overridable. |

### Output and link timing

| Macro | Default | ESP-IDF value | Meaning |
|---|---|---|---|
| `TD_OUT_BUF_SIZE` | 4096 | 1024 | Renderer output buffer (bytes, inside `td_renderer_t`). Output is written to the HAL whenever it fills and at the end of each frame. |
| `TD_SIZE_QUERY_TIMEOUT_MS` | 300 | - | How long `td_init()` waits for the start-up size answer. |
| `TD_SIZE_POLL_MS` | 1000 | - | Interval of the periodic size query while the link is up. 0 disables it. |
| `TD_LINK_RETRY_MS` | 500 | - | After a dropped frame, how often a full resync is retried. |
| `TD_RECONNECT_SILENCE_MS` | 5000 | - | Input after this much silence is treated as a (re)connected terminal and triggers a resync. |
| `TD_LOOP_SLEEP_MS` | 5 | - | Sleep between passes in `td_run()` (the ESP-IDF UI task uses it too). |
| `TD_OSC52_MAX` | 8192 | - | Largest text `td_host_clipboard_set()` sends; longer text is not sent. 0 disables OSC 52. |

### Input

| Macro | Default | ESP-IDF value | Meaning |
|---|---|---|---|
| `TD_EVENT_QUEUE_SIZE` | 32 | - | Capacity of the event ring buffer. |
| `TD_ESC_TIMEOUT_MS` | 50 | - | A lone ESC becomes the ESC key after this many milliseconds. |
| `TD_SEQ_TIMEOUT_MS` | 500 | - | An unfinished escape sequence (CSI, SS3, legacy mouse) is discarded after this long. |
| `TD_PASTE_MAX` | 8192 | - | Most bytes one bracketed paste may bring; the rest is dropped and the event is flagged as cut. The text is held in a heap buffer only while it arrives and while the event is handled. |
| `TD_PASTE_TIMEOUT_MS` | 2000 | - | A paste that stalls this long (end marker lost) is delivered anyway. |
| `TD_DOUBLE_CLICK_MS` | 400 | - | Maximum time between two clicks of a double-click (list widgets, desktop icons, window title bars). |

### Window manager and widget pools

| Macro | Default | ESP-IDF value | Meaning |
|---|---|---|---|
| `TD_MAX_WINDOWS` | 12 | - | Windows open at once. See [Window manager](wm.md). |
| `TD_MAX_WIDGETS` | 64 | 40 / 64 | Widgets across all windows. See [Widgets](widgets.md). |
| `TD_MAX_TIMERS` | 16 | - | Timers, shared by `td_timer_start()` callers and windows with `on_tick`. See [Input](input.md#timers). |
| `TD_MAX_APPS` | 16 | - | Registered apps. See [Apps API](apps.md). |
| `TD_PATH_MAX` | 160 | 160 | Longest real path (file system root + the path the shell sees) the apps and `td_drag_item_t` handle. The PC build sets 512, because its root is `<working directory>/tinydesk_fs`. A path that does not fit is refused, never cut. |
| `TD_TITLE_MAX` | 32 | - | Window title buffer, bytes including the NUL. |
| `TD_TEXT_MAX` | 64 | 48 | Widget text buffer, bytes including the NUL (text boxes accept `TD_TEXT_MAX - 1` bytes). |

### Terminal emulator

| Macro | Default | ESP-IDF value | Meaning |
|---|---|---|---|
| `TD_VT_MAX_COLS` | `TD_MAX_COLS` | (follows `TD_MAX_COLS`) | Largest [Terminal emulator](vterm.md) width. |
| `TD_VT_MAX_ROWS` | `TD_MAX_ROWS` | (follows `TD_MAX_ROWS`) | Largest emulator height. The screen costs `TD_VT_MAX_COLS * TD_VT_MAX_ROWS * 4` bytes. |
| `TD_VT_SCROLLBACK` | 200 | 12 / 200 | Scrollback lines; each costs `TD_VT_MAX_COLS * 4` bytes. 0 disables scrollback. |

### Other definitions set by the ESP-IDF component

These are not in `td_config.h` but are set on the same command line:

| Macro | Default | ESP-IDF value | Meaning |
|---|---|---|---|
| `TD_HAVE_TLS` | undefined | defined | Enables TLS in the protocol code. The host build defines it only when mbedTLS 3.x is found. See [TLS](tls.md). |
| `TD_LOG_LINES` | 64 | 32 | Lines kept by the Log Viewer app (`apps/logview.c`). |
| `TD_LOG_LINE_MAX` | 100 | 88 | Bytes per Log Viewer line. |
