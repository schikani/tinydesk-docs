# Input

The input module turns the raw bytes a terminal sends (keys, escape sequences, mouse reports, bracketed paste, cursor-position replies) into `td_event_t` events. It also contains the fixed-size event queue that carries them to the window manager, and the pool of millisecond timers that the main loop runs. Applications see the events in their windows' `on_event` callbacks (see [Window manager](wm.md)); the parser, queue and timers are driven by the main loop (see [Core](core.md)).

Header: `include/tinydesk/td_input.h` (events, event queue, parser and timers are all in this header; there is no separate `td_event.h` or `td_timer.h`)
Source: `src/input.c` (parser, paste, key names), `src/event.c` (queue), `src/timer.c` (timers)

Everything on this page must be called from the UI task. The queue, the timer pool and the delivered paste are global state without locks.

## Events

```c
typedef enum { TD_EV_KEY, TD_EV_MOUSE, TD_EV_RESIZE, TD_EV_TICK, TD_EV_PASTE } td_ev_type_t;

typedef struct {
    td_ev_type_t type;
    uint32_t key;
    uint8_t mods;
    int16_t x, y;
    uint8_t button;
    uint8_t action;
    uint32_t time_ms;
} td_event_t;
```

| Field | Meaning |
|---|---|
| `type` | Event type (below). |
| `key` | `TD_EV_KEY`: a Unicode code point or a `TD_KEY_*` code. 0 for other types. |
| `mods` | Modifier bits `TD_MOD_SHIFT`, `TD_MOD_ALT`, `TD_MOD_CTRL` (keys and mouse). |
| `x`, `y` | `TD_EV_MOUSE`: 0-based cell coordinates (absolute in the queue; the window manager makes them client-relative before calling `on_event`). `TD_EV_RESIZE`: `x` = columns, `y` = rows reported by the terminal. `TD_EV_PASTE`: `x` is 1 if the paste was cut short, else 0. |
| `button` | `TD_EV_MOUSE`: a `TD_BUTTON_*` value. |
| `action` | `TD_EV_MOUSE`: a `TD_MOUSE_*` value. |
| `time_ms` | The `now_ms` passed to the parser when the event was completed (normally `td_millis()`). Used for double-click detection. |

| Type | Produced by | Delivered to windows |
|---|---|---|
| `TD_EV_KEY` | Printable characters, control characters, key escape sequences. | Yes: focused window (widgets first unless `TD_WIN_RAW_KEYS`). |
| `TD_EV_MOUSE` | SGR (`ESC [ < b ; x ; y M/m`) and legacy X10 (`ESC [ M b x y`) mouse reports. | Yes, routed by position. |
| `TD_EV_RESIZE` | A cursor-position report `ESC [ rows ; cols R` with rows > 1 (the answer to the core's size query). | No: the main loop consumes it and resizes the desktop. |
| `TD_EV_TICK` | Nothing in the current code. It is declared but never generated, and `td_wm_dispatch()` ignores it; use `on_tick` or a timer instead. | No. |
| `TD_EV_PASTE` | A complete bracketed paste. Read the text with `td_paste_text()`. | Yes: the focused window. If its focused widget is a text box (and the window lacks `TD_WIN_RAW_KEYS`), the first line is inserted there; otherwise `on_event` gets it. |

### Modifiers

```c
#define TD_MOD_SHIFT 0x01u
#define TD_MOD_ALT   0x02u
#define TD_MOD_CTRL  0x04u
```

Ctrl+letter arrives as the **lower-case** letter with `TD_MOD_CTRL` (Ctrl+S is `key == 's'`, `mods == TD_MOD_CTRL`). Test modifiers with `==` when you want exactly that combination, or with `&` when extra modifiers are acceptable.

### Key codes

```c
enum {
    TD_KEY_BASE = 0x110000,
    TD_KEY_ENTER,
    TD_KEY_TAB,
    TD_KEY_BACKSPACE,
    TD_KEY_ESC,
    TD_KEY_UP,
    TD_KEY_DOWN,
    TD_KEY_RIGHT,
    TD_KEY_LEFT,
    TD_KEY_HOME,
    TD_KEY_END,
    TD_KEY_INSERT,
    TD_KEY_DELETE,
    TD_KEY_PGUP,
    TD_KEY_PGDN,
    TD_KEY_F1, TD_KEY_F2, TD_KEY_F3, TD_KEY_F4, TD_KEY_F5, TD_KEY_F6,
    TD_KEY_F7, TD_KEY_F8, TD_KEY_F9, TD_KEY_F10, TD_KEY_F11, TD_KEY_F12,
};
```

Special keys are numbered above the Unicode range (U+10FFFF), so `key < TD_KEY_BASE` means "a character" and `key > TD_KEY_BASE` means "a special key". `TD_KEY_BASE` itself is never produced.

### How bytes map to keys

| Input | Event |
|---|---|
| `CR` (0x0D) or `LF` (0x0A) | `TD_KEY_ENTER` |
| `HT` (0x09) | `TD_KEY_TAB` |
| `DEL` (0x7F) or `BS` (0x08) | `TD_KEY_BACKSPACE` |
| `NUL` (0x00) | `' '` + `TD_MOD_CTRL` (Ctrl+Space) |
| 0x01..0x1A (other than the above) | `'a'`..`'z'` + `TD_MOD_CTRL` |
| 0x1C..0x1F | `'\\'`, `']'`, `'^'`, `'_'` + `TD_MOD_CTRL` |
| Printable ASCII and UTF-8 | The code point, no modifiers. Malformed UTF-8 gives U+FFFD. |
| `ESC` alone, then nothing for `TD_ESC_TIMEOUT_MS` | `TD_KEY_ESC` |
| `ESC ESC` | `TD_KEY_ESC` for the first; the second starts a new sequence. |
| `ESC` + byte (not `[` or `O`) | That byte's key with `TD_MOD_ALT` added (Alt+x, Alt+Enter, Alt+Backspace, Ctrl+Alt+letter). |
| `ESC [ A/B/C/D`, `ESC O A/B/C/D` | Up, Down, Right, Left |
| `ESC [ H/F`, `ESC O H/F` | Home, End |
| `ESC O P/Q/R/S`, `ESC [ P/Q/R/S` | F1..F4 |
| `ESC [ 1 ; m X` (X one of the letters above) | That key with modifiers from `m` (xterm style: `m - 1` = Shift 1, Alt 2, Ctrl 4), for example `ESC [ 1 ; 5 A` = Ctrl+Up. |
| `ESC [ n ~` and `ESC [ n ; m ~` | 1/7 Home, 2 Insert, 3 Delete, 4/8 End, 5 PgUp, 6 PgDn, 11..15 F1..F5, 17..21 F6..F10, 23/24 F11/F12; `m` as above. |
| `ESC [ Z` | `TD_KEY_TAB` + `TD_MOD_SHIFT` (Shift+Tab) |
| `ESC [ 200 ~` ... `ESC [ 201 ~` | One `TD_EV_PASTE` (see [Bracketed paste](#bracketed-paste)). |

Gotchas:

- Ctrl+H, Ctrl+I, Ctrl+J and Ctrl+M are indistinguishable from Backspace, Tab and Enter, and Ctrl+[ is ESC.
- Alt only reaches single-byte characters. For `ESC` followed by a multi-byte UTF-8 character, the character arrives without `TD_MOD_ALT`. Alt+[ and Alt+O start escape sequences instead of producing keys: they are dropped, and after Alt+O the next byte is taken as the SS3 final byte (it yields an arrow, Home/End or F1..F4 key if it is one of `A B C D H F P Q R S`, and is lost otherwise).
- SS3 sequences (`ESC O x`) carry no modifiers.
- A lone ESC is only reported after `TD_ESC_TIMEOUT_MS`, and only if `td_input_poll_timeouts()` runs; the main loop calls it every pass.
- Private CSI sequences (first parameter byte outside `0`..`;`, such as `ESC [ ? ...` or `ESC [ > ...`), unknown final bytes and sequences longer than 32 bytes are discarded. Control bytes inside a CSI sequence are ignored; an ESC inside one abandons it and starts a new sequence. A sequence that stalls for `TD_SEQ_TIMEOUT_MS` is dropped.
- A cursor-position report whose row is 1 is read as F3 with modifiers (it has the same form as Shift+F3, `ESC [ 1 ; 2 R`).

### Mouse

```c
#define TD_MOUSE_PRESS   0
#define TD_MOUSE_RELEASE 1
#define TD_MOUSE_DRAG    2
#define TD_MOUSE_MOVE    3

#define TD_BUTTON_LEFT       0
#define TD_BUTTON_MIDDLE     1
#define TD_BUTTON_RIGHT      2
#define TD_BUTTON_NONE       3
#define TD_BUTTON_WHEEL_UP   4
#define TD_BUTTON_WHEEL_DOWN 5
```

| Report | `button` | `action` |
|---|---|---|
| Button pressed | `TD_BUTTON_LEFT`/`MIDDLE`/`RIGHT` | `TD_MOUSE_PRESS` |
| Button released (SGR) | The released button | `TD_MOUSE_RELEASE` |
| Button released (X10, which does not say which button) | `TD_BUTTON_NONE` | `TD_MOUSE_RELEASE` |
| Motion with a button held | That button | `TD_MOUSE_DRAG` |
| Motion with no button held | `TD_BUTTON_NONE` | `TD_MOUSE_MOVE` |
| Wheel up / down | `TD_BUTTON_WHEEL_UP` / `TD_BUTTON_WHEEL_DOWN` | `TD_MOUSE_PRESS` (wheel releases are dropped) |

Coordinates are converted from the terminal's 1-based cells to 0-based. Shift, Alt (Meta) and Ctrl held during the report set the corresponding `mods` bits. The core enables SGR reporting (`?1006`), so coordinates are not limited; the legacy X10 encoding is still decoded but cannot report positions beyond column/row 223.

Consecutive motion events (`TD_MOUSE_DRAG` / `TD_MOUSE_MOVE`) for the same button are merged in the queue (see [td_event_push](#td_event_push)), so a handler sees the latest position, not every intermediate one.

### td_key_name

```c
const char *td_key_name(const td_event_t *ev, char *buf, int cap);
```

Writes a short readable name of the key in `ev` into `buf` and returns `buf`. The format is `[Ctrl+][Alt+][Shift+]<key>`, where `<key>` is one of `Enter`, `Tab`, `Backspace`, `Esc`, `Up`, `Down`, `Right`, `Left`, `Home`, `End`, `Insert`, `Delete`, `PgUp`, `PgDn`, `F1`..`F12`, `Space`, or the character itself as UTF-8.

| Parameter | Meaning |
|---|---|
| `ev` | Event to describe; only `key` and `mods` are used. |
| `buf` | Output buffer; always NUL-terminated (via `snprintf`). |
| `cap` | Size of `buf` in bytes; must be at least 1. 32 is enough for every name. |

Notes: letters keep the case they arrived in, so Ctrl+A is named `Ctrl+a`. For an event with `key == 0` (mouse, paste) the key part is empty. Intended for demos and diagnostics.

## Bracketed paste

The core enables bracketed paste (`ESC [ ? 2004 h`), so a terminal that supports it wraps pasted text in `ESC [ 200 ~` ... `ESC [ 201 ~`. Everything between the markers, including escape sequences and control characters, is collected as text and delivered as one `TD_EV_PASTE` event, instead of as thousands of key events. The text is kept in a heap buffer (grown with `realloc`, starting at 256 bytes) only while it arrives and while the event is handled.

- At most `TD_PASTE_MAX` bytes are kept; the rest is dropped and the event's `x` is set to 1. `x` is also 1 if the buffer could not be grown.
- If the end marker never arrives, the paste is delivered anyway once no byte has arrived for `TD_PASTE_TIMEOUT_MS`.
- An empty paste produces no event.
- Terminals without bracketed paste deliver pasted text as ordinary key events.

### td_paste_text

```c
const char *td_paste_text(int *len);
```

Returns the text of the `TD_EV_PASTE` being handled and stores its length in bytes in `*len` (`len` may be NULL). Returns NULL (and `*len = 0`) when no paste is pending. The text is NUL-terminated, may contain any bytes including NUL, and keeps line breaks as the terminal sent them (usually CR, which is what a shell expects for Enter; convert to LF yourself when inserting into a document).

Lifetime: the pointer is valid only while the `TD_EV_PASTE` event is being handled. The main loop frees the text right after dispatching the event; do not keep the pointer, copy the text if you need it later.

Gotcha: the parser keeps only the most recent paste. If a second paste completes before the first event is dispatched, the first event sees the second text and the second event then sees none. In practice pastes are separated by far more than one main-loop pass.

```c
#include <string.h>
#include "tinydesk/td.h"

static char s_line[TD_TEXT_MAX];

static bool my_event(td_window_t *win, const td_event_t *ev)
{
    if (ev->type == TD_EV_PASTE) {
        int n = 0;
        const char *text = td_paste_text(&n);
        if (!text) return true;
        if (n > (int)sizeof(s_line) - 1) n = (int)sizeof(s_line) - 1;
        memcpy(s_line, text, (size_t)n);           /* copy: text is freed after this event */
        s_line[n] = '\0';
        td_win_invalidate(win);
        return true;
    }
    if (ev->type == TD_EV_KEY && ev->key == 's' && ev->mods == TD_MOD_CTRL) {
        /* Ctrl+S */
        return true;
    }
    if (ev->type == TD_EV_MOUSE && ev->action == TD_MOUSE_PRESS &&
        ev->button == TD_BUTTON_LEFT) {
        /* ev->x, ev->y are relative to the client area here */
        return true;
    }
    return false;
}
```

## Event queue

A ring buffer of `TD_EVENT_QUEUE_SIZE` events. The parser pushes into it; the main loop pops and dispatches. Applications can push synthetic events (for example a key) that the next `td_step()` will dispatch like real input.

### td_event_push

```c
bool td_event_push(const td_event_t *ev);
```

Appends a copy of `*ev`. If `ev` is a motion event (`TD_EV_MOUSE` with `TD_MOUSE_DRAG` or `TD_MOUSE_MOVE`) and the newest queued event is a motion event with the same `button`, that queued event is overwritten instead, so a slow link never builds up a motion backlog. Returns false, dropping the event, if the queue is full.

The parser ignores a full queue, so events can be lost if nobody pops them. The main loop avoids this by dispatching early when the queue is within 4 entries of full while reading input.

### td_event_pop

```c
bool td_event_pop(td_event_t *ev);
```

Removes the oldest event and copies it to `*ev`. Returns false when the queue is empty (`*ev` is not written).

### td_event_count / td_event_clear

```c
int td_event_count(void);
void td_event_clear(void);
```

`td_event_count()` returns the number of queued events. `td_event_clear()` drops them all; `td_init()` calls it.

## Parser

The core owns one parser instance and feeds it every byte the HAL returns. The functions are public so that other byte sources can be parsed the same way and for tests (`tests/test_input.c`).

```c
typedef struct {
    uint8_t state;
    uint8_t seq[32];
    uint8_t seq_len;
    bool seq_overflow;
    uint8_t x10_left;
    uint32_t seq_start;
    td_utf8_decoder_t utf8;
    uint32_t last_byte_ms;
    char *paste;
    int paste_len, paste_cap;
    uint8_t paste_match;
    bool paste_cut;
    char *pasted;
    int pasted_len;
} td_input_t;
```

Treat the fields as private. `paste` is the paste being received and `pasted` the last one delivered; both are heap buffers owned by the parser.

### td_input_init

```c
void td_input_init(td_input_t *p);
```

Resets the parser to its initial state and frees any paste buffers it holds. Because it frees `p->paste` and `p->pasted`, the structure must be zeroed before the first call (static storage, or `td_input_t p = {0};`); calling it on uninitialised stack memory frees garbage pointers.

### td_input_feed

```c
void td_input_feed(td_input_t *p, uint8_t byte, uint32_t now_ms);
```

Feeds one received byte. Completed events are pushed to the event queue with `time_ms = now_ms`. Sequences may be split across any number of calls. `now_ms` should be `td_millis()`; it is also used for the ESC, sequence and paste timeouts.

### td_input_poll_timeouts

```c
void td_input_poll_timeouts(td_input_t *p, uint32_t now_ms);
```

Call regularly (the main loop calls it every pass). It:

- turns a lone ESC older than `TD_ESC_TIMEOUT_MS` into `TD_KEY_ESC`;
- discards a CSI, SS3 or X10 mouse sequence older than `TD_SEQ_TIMEOUT_MS`;
- delivers a bracketed paste when no byte has arrived for `TD_PASTE_TIMEOUT_MS`.

### td_input_paste_done

```c
void td_input_paste_done(td_input_t *p);
```

Frees the delivered paste text, after which `td_paste_text()` returns NULL. The main loop calls it after dispatching each `TD_EV_PASTE`; applications should not call it for the core's parser.

## Timers

A pool of `TD_MAX_TIMERS` millisecond timers, run by the main loop after event dispatch on every pass. The same pool serves windows' `on_tick` callbacks (one timer per window with `on_tick` and `tick_ms > 0`, see [Window manager](wm.md)), so count those against the limit too.

```c
typedef void (*td_timer_fn)(void *user);
```

### td_timer_start

```c
int td_timer_start(uint32_t interval_ms, bool repeat, td_timer_fn fn,
                   void *user, uint32_t now_ms);
```

| Parameter | Meaning |
|---|---|
| `interval_ms` | Delay before the first call, and the period of a repeating timer. 0 is treated as 1. |
| `repeat` | true: call every `interval_ms` until stopped. false: call once. |
| `fn` | Callback; must not be NULL. |
| `user` | Passed to `fn`. |
| `now_ms` | The current time, normally `td_millis()`. The first call is due at `now_ms + interval_ms`. |

Returns the timer id (>= 0), or -1 if the pool is full or `fn` is NULL.

Behaviour:

- Timers run from `td_step()`, so their resolution is one main-loop pass (`TD_LOOP_SLEEP_MS` plus the time the pass takes). They never run early.
- A repeating timer is rescheduled at `due + interval_ms`, keeping a steady rate. If the loop fell behind by more than one period, it is rescheduled at `now + interval_ms` instead of firing several times to catch up.
- Due times are compared with a signed 32-bit difference, so timers keep working when `td_millis()` wraps.
- A callback may start or stop timers, including its own.

### td_timer_stop

```c
void td_timer_stop(int id);
```

Stops the timer. Ids outside the pool (including -1) and timers that are not running are ignored.

Gotcha: ids are slot indexes and are reused. A one-shot timer's slot is freed just before its callback runs, so after it fires the id may already belong to a different timer; stopping the old id would stop that one. Reset your stored id (to -1) in the one-shot callback, and after `td_timer_stop()`.

### td_timers_run

```c
void td_timers_run(uint32_t now_ms);
```

Calls every timer that is due at `now_ms`. The main loop calls it each pass; applications do not need to.

### td_timers_reset

```c
void td_timers_reset(void);
```

Stops all timers. `td_init()` calls it, so timers must be started after `td_init()`.

### Example

```c
#include "tinydesk/td.h"

static int s_blink = -1;
static bool s_on;

static void blink(void *user)
{
    td_window_t *win = user;
    s_on = !s_on;
    if (td_win_is_open(win)) td_win_invalidate(win);
}

static void start_blinking(td_window_t *win)
{
    if (s_blink < 0) s_blink = td_timer_start(500, true, blink, win, td_millis());
}

static void stop_blinking(void)
{
    td_timer_stop(s_blink);
    s_blink = -1;
}
```

For work tied to one window, the window's `on_tick` / `tick_ms` is simpler: the window manager stops that timer when the window closes.
