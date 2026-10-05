# Screen

The screen module is the drawing layer under the window manager. The desktop is composed into a grid of character cells (`td_buffer_t`) with clipped drawing primitives, and the diff renderer turns the difference between the new grid and the one the terminal already shows into as few ANSI escape bytes as possible. The module also holds the UTF-8 helpers used throughout TinyDesk and the ASCII-only fallback for terminals without box-drawing glyphs.

Header: `include/tinydesk/td_screen.h`
Source: `src/screen.c` (buffers, rectangles), `src/draw.c` (primitives, ASCII mode), `src/render.c` (renderer), `src/utf8.c` (UTF-8)

Applications normally only use the drawing primitives, from a window's `on_draw` callback, where the window manager has already set the target, origin and clip (see [Window manager](wm.md)). The buffers and the renderer are driven by the main loop (see [Core](core.md)). All functions must be called from the UI task; the drawing state (target, origin, clip, ASCII mode) is global.

## Colours and attributes

Colours are 8-bit indexes into the xterm 256-colour palette:

| Index | Colours |
|---|---|
| 0..7 | Black, red, green, yellow/brown, blue, magenta, cyan, light grey |
| 8..15 | Bright versions of 0..7 (8 is dark grey, 15 white) |
| 16..231 | 6x6x6 colour cube |
| 232..255 | Grey ramp |

The renderer sends indexes 0..15 with the short SGR forms (`30..37`/`40..47` and `90..97`/`100..107`) so every terminal understands them, and indexes 16..255 as `38;5;n` / `48;5;n`. Theme colours are defined by the window manager; see [Window manager](wm.md).

```c
#define TD_BOLD      0x01u
#define TD_UNDERLINE 0x02u
#define TD_REVERSE   0x04u
```

| Attribute | SGR sent | Meaning |
|---|---|---|
| `TD_BOLD` | 1 | Bold (many terminals show it as a brighter colour). |
| `TD_UNDERLINE` | 4 | Underline. |
| `TD_REVERSE` | 7 | Swap foreground and background. |

Attributes can be ORed together.

## Cells and buffers

```c
typedef struct {
    uint32_t ch;
    uint8_t fg, bg;
    uint8_t attr;
    uint8_t _pad;
} td_cell_t;

#define TD_CH_INVALID 0xFFFFFFFFu
```

| Field | Meaning |
|---|---|
| `ch` | Unicode code point shown in the cell. Control characters (< U+0020) and U+007F are rendered as a space. |
| `fg`, `bg` | Palette indexes. |
| `attr` | `TD_BOLD`, `TD_UNDERLINE`, `TD_REVERSE`. |
| `_pad` | Padding; the renderer compares whole cells with `memcmp`, so keep it 0. |

A cell is 8 bytes. Every code point occupies exactly one column: there is no support for double-width (East Asian, emoji) or combining characters, which would misalign the terminal's cursor. `TD_CH_INVALID` is a value no real cell holds; `td_buffer_invalidate()` uses it to force a full redraw.

```c
typedef struct {
    int cols, rows;
    td_cell_t cells[TD_MAX_COLS * TD_MAX_ROWS];
} td_buffer_t;
```

| Field | Meaning |
|---|---|
| `cols`, `rows` | Part of the storage in use. |
| `cells` | Row-major storage. Cell (x, y) is `cells[y * cols + x]`: the stride is the *used* width, not `TD_MAX_COLS`. |

A buffer is `TD_MAX_COLS * TD_MAX_ROWS * 8 + 8` bytes (about 52 KB with the host defaults), so give it static storage rather than putting it on a stack. The core owns the two screen buffers; you only need your own for tests or off-screen composition.

### td_buffer_init

```c
void td_buffer_init(td_buffer_t *buf, int cols, int rows);
```

Sets the used size, clamped to 1..`TD_MAX_COLS` by 1..`TD_MAX_ROWS`, and clears every used cell to a space in colour 7 on 0 with no attributes.

### td_buffer_invalidate

```c
void td_buffer_invalidate(td_buffer_t *buf);
```

Sets `ch = TD_CH_INVALID` in every used cell. Applied to the front buffer, it makes the next `td_render_diff()` resend every cell.

### td_buffer_cell

```c
td_cell_t *td_buffer_cell(td_buffer_t *buf, int x, int y);
```

Returns the cell at absolute (x, y), or NULL when the position is outside the used area. It ignores the drawing origin and clip.

## Rectangles

```c
typedef struct {
    int x, y, w, h;
} td_rect_t;

static inline td_rect_t td_rect(int x, int y, int w, int h);
td_rect_t td_rect_intersect(td_rect_t a, td_rect_t b);
bool td_rect_contains(td_rect_t r, int x, int y);
```

`td_rect()` builds a rectangle. `td_rect_intersect()` returns the overlap of `a` and `b`; when they do not overlap, `w` and/or `h` is 0 (the `x`, `y` of such a result are not meaningful). `td_rect_contains()` is true when `r.x <= x < r.x + r.w` and `r.y <= y < r.y + r.h`, so an empty rectangle contains nothing.

## Drawing state

The primitives draw into one global target buffer. Coordinates passed to them are relative to the *origin*; anything outside the *clip* rectangle (in absolute coordinates) is silently skipped. Inside a window's `on_draw`, the origin is the top-left cell of the client area and the clip is the client area, so a window cannot draw outside itself.

### td_draw_target / td_draw_get_target

```c
void td_draw_target(td_buffer_t *buf);
td_buffer_t *td_draw_get_target(void);
```

`td_draw_target()` selects the buffer to draw into and resets the origin to (0, 0) and the clip to the whole buffer. `buf` may be NULL, which makes every primitive a no-op. `td_draw_get_target()` returns the current target (NULL before the first `td_draw_target()`).

### td_draw_origin

```c
void td_draw_origin(int x, int y);
```

Sets the absolute position that primitive coordinate (0, 0) maps to. It does not change the clip.

### td_draw_clip / td_draw_get_clip

```c
void td_draw_clip(td_rect_t clip);
td_rect_t td_draw_get_clip(void);
```

`td_draw_clip()` sets the clip rectangle in **absolute** coordinates, intersected with the target buffer. It is ignored when there is no target. `td_draw_get_clip()` returns the current clip.

To draw into a sub-area temporarily, save and restore the clip yourself:

```c
td_rect_t saved = td_draw_get_clip();
td_draw_clip(td_rect_intersect(saved, td_rect(abs_x, abs_y, 10, 3)));
/* ... draw ... */
td_draw_clip(saved);
```

The clip is absolute but primitive coordinates are origin-relative; convert with the origin you set (inside a window, `td_win_client(win)` gives the client rectangle in absolute coordinates).

## Primitives

### td_putc

```c
void td_putc(int x, int y, uint32_t ch, uint8_t fg, uint8_t bg, uint8_t attr);
```

Writes one cell at origin-relative (x, y), replacing its character, colours and attributes. Nothing happens outside the clip or without a target. `ch` is stored as given; control characters are turned into spaces only when rendered.

### td_fill

```c
void td_fill(td_rect_t r, uint32_t ch, uint8_t fg, uint8_t bg);
```

Fills the origin-relative rectangle `r` with `ch` in the given colours. Attributes are set to 0. Use `' '` to clear an area.

### td_text / td_textn

```c
int td_text(int x, int y, const char *str, uint8_t fg, uint8_t bg, uint8_t attr);
int td_textn(int x, int y, const char *str, int max_cols,
             uint8_t fg, uint8_t bg, uint8_t attr);
```

Draws the NUL-terminated UTF-8 string `str` on row `y`, starting at column `x`, one code point per column. `td_textn()` stops after `max_cols` columns.

| Parameter | Meaning |
|---|---|
| `x`, `y` | Origin-relative start cell. |
| `str` | UTF-8 text. NULL draws nothing and returns 0. Malformed bytes are shown as U+FFFD. |
| `max_cols` | (`td_textn` only) Maximum columns to write; `<= 0` writes nothing. |
| `fg`, `bg`, `attr` | Colours and attributes for every cell written. |

Returns the number of columns the text occupies (up to `max_cols`), counting cells that were clipped away, so the return value can be used for layout. Control characters, including `\n` and `\t`, are drawn as a single space: the functions never wrap. There is no ellipsis or padding; clear the rest of a field with `td_fill()` if needed. For the display width of a string, use `td_utf8_len()`; for a column of a fixed width, `td_utf8_pad()`.

### td_box

```c
typedef enum {
    TD_BOX_SINGLE = 0,
    TD_BOX_DOUBLE,
    TD_BOX_ASCII,
} td_box_style_t;

void td_box(td_rect_t r, td_box_style_t style, uint8_t fg, uint8_t bg);
```

Draws a frame on the outermost cells of the origin-relative rectangle `r`; the interior is not touched. Nothing is drawn when `r.w < 2` or `r.h < 2`. Frame cells get attribute 0.

| Style | Corners | Horizontal | Vertical |
|---|---|---|---|
| `TD_BOX_SINGLE` | U+250C U+2510 U+2514 U+2518 (`┌ ┐ └ ┘`) | U+2500 `─` | U+2502 `│` |
| `TD_BOX_DOUBLE` | U+2554 U+2557 U+255A U+255D (`╔ ╗ ╚ ╝`) | U+2550 `═` | U+2551 `║` |
| `TD_BOX_ASCII` | `+` | `-` | `\|` |

`style` is not range-checked; pass only these three values.

### td_shadow

```c
void td_shadow(td_rect_t r);
```

Darkens the one-cell drop shadow of the origin-relative rectangle `r`: the column just right of it (rows `r.y + 1` to `r.y + r.h`) and the row just below it (columns `r.x + 1` to `r.x + r.w - 1`). The characters underneath are kept; their colours become 8 on 0 and attributes are cleared.

### td_draw_vscroll

```c
void td_draw_vscroll(int x, int y, int h, int pos, int total, int page,
                     uint8_t fg, uint8_t bg);
```

Draws a one-column vertical scrollbar at origin-relative (x, y), `h` cells tall: an up arrow (U+25B2) at the top, a down arrow (U+25BC) at the bottom and a light-shade track (U+2591) between. When `total > page`, a solid thumb (U+2588) sized `track * page / total` (at least 1 cell) is placed according to `pos`.

| Parameter | Meaning |
|---|---|
| `x`, `y`, `h` | Position and height. Nothing is drawn when `h < 3`. |
| `pos` | Index of the first visible line; clamped to `0..total - page`. |
| `total` | Number of lines in the content. |
| `page` | Number of lines visible. No thumb is drawn when `total <= page`. |
| `fg`, `bg` | Colours for the whole bar. |

The function only draws; mouse handling on the bar is up to the caller (the widgets use it for their scrollbars, see [Widgets](widgets.md)).

### Example

An `on_draw` callback for a window (see [Window manager](wm.md) for `td_window_desc_t`):

```c
#include "tinydesk/td.h"

static void my_draw(td_window_t *win, int w, int h)
{
    (void)win;
    td_fill(td_rect(0, 0, w, h), ' ', 0, 7);                 /* clear client area */
    td_box(td_rect(1, 1, w - 3, h - 2), TD_BOX_SINGLE, 8, 7);
    int n = td_text(3, 1, " Status ", 15, 4, TD_BOLD);       /* title in the frame */
    td_textn(3 + n + 1, 1, "all systems nominal", w - 3 - n - 6, 2, 7, 0);
    td_draw_vscroll(w - 1, 0, h, 10, 100, h, 0, 7);
}
```

## ASCII mode

```c
void td_set_ascii_mode(bool on);
bool td_get_ascii_mode(void);
uint32_t td_ascii_fallback(uint32_t ch);
```

In ASCII mode the renderer replaces every non-ASCII character with `td_ascii_fallback(ch)` as it sends it. The buffers keep the real code points, so the setting can be toggled at any time; call `td_full_redraw()` (see [Core](core.md)) afterwards so cells already on the terminal are resent. The Settings app exposes it for terminals or fonts without box-drawing glyphs.

`td_ascii_fallback()` returns `ch` unchanged when it is below 128, otherwise:

| Code points | Replacement |
|---|---|
| U+2500 `─`, U+2550 `═` | `-` |
| U+2502 `│`, U+2551 `║` | `\|` |
| Corners U+250C, U+2510, U+2514, U+2518, U+2554, U+2557, U+255A, U+255D; tees and cross U+251C, U+2524, U+252C, U+2534, U+253C | `+` |
| U+2591 `░` | `.` |
| U+2592 `▒` | `:` |
| U+2593 `▓`, U+2588 `█`, U+25A0 `■`, U+2580 `▀`, U+2584 `▄`, U+258C `▌`, U+2590 `▐` | `#` |
| U+00B7 `·`, U+2022 `•` | `.` |
| U+25B2 `▲`, U+2191 `↑` | `^` |
| U+25BC `▼`, U+2193 `↓` | `v` |
| U+25BA `►`, U+2192 `→` | `>` |
| U+25C4 `◄`, U+2190 `←` | `<` |
| U+00D7 `×` | `x` |
| U+2261 `≡` | `=` |
| U+263C `☼` | `*` |
| anything else | `?` |

Gotcha: "anything else" includes accented and other non-ASCII letters, so in ASCII mode text such as `é` is shown as `?`.

## UTF-8

### td_utf8_encode

```c
int td_utf8_encode(uint32_t cp, uint8_t out[4]);
```

Encodes `cp` into `out` and returns the byte count (1..4). Surrogates (U+D800..U+DFFF) and values above U+10FFFF are encoded as U+FFFD (3 bytes). `out` is not NUL-terminated.

### td_utf8_next

```c
uint32_t td_utf8_next(const char **s);
```

Decodes one code point from `*s` and advances `*s` past it. Returns 0 at the terminating NUL (without advancing). Malformed input (invalid lead byte, missing continuation byte, overlong form, surrogate, value above U+10FFFF) yields U+FFFD and advances by one byte only. `*s` must not be NULL.

```c
const char *p = "caf\xC3\xA9";
uint32_t cp;
while ((cp = td_utf8_next(&p)) != 0) {
    /* 'c', 'a', 'f', 0xE9 */
}
```

### td_utf8_len

```c
int td_utf8_len(const char *s);
```

Returns the number of code points in the NUL-terminated string `s` (each malformed byte counts as one). Because every code point is one column, this is also the width `td_text()` gives the string.

### td_utf8_pad

```c
int td_utf8_pad(char *out, size_t cap, const char *s, int cols);
```

Makes a column of exactly `cols` cells for a list or a table: copies `s` (NULL counts as "") into `out`, at most `cols` code points and never part of one, then pads with spaces to `cols` code points. Returns the bytes written, without the NUL.

- Code points are counted as the screen draws them (`td_utf8_next()`): a malformed byte is one cell, and is copied as it is, so the copy draws the same cells. Strings that are not UTF-8 at all, such as Wi-Fi network names (arbitrary bytes), line up too.
- Use it instead of `printf`'s `%-32s` or `%.32s`, which count bytes: every extra byte of a multibyte character makes such a column one cell short, and `%.Ns` can cut a character in half.
- When `out` fills up it stops early, at a character boundary, and still NUL-terminates; with `cap == 0` nothing is written. Room for `cols` cells needs `cols` + the string's length in bytes + 1.
- Double-width characters (CJK, emoji) count as one cell, as everywhere in TinyDesk (see *Cells and buffers* above); a terminal that draws them two columns wide shifts the rest of that row.

```c
char ssid[80];
td_utf8_pad(ssid, sizeof(ssid), ap->ssid, 32);   /* the Network window's SSID column */
snprintf(item, sizeof(item), "%s %s", ssid, bars);
```

### td_utf8_copy, td_utf8_skip

```c
int td_utf8_copy(char *out, size_t cap, const char *s, int cols);
const char *td_utf8_skip(const char *s, int cols);
```

`td_utf8_copy()` is `td_utf8_pad()` without the padding: it copies at most `cols` code points of `s` (NULL counts as ""), never part of one, and stops early when `out` is full. Use it instead of `%.Ns` and of `snprintf(out, cap, "%s", s)` when the text may be cut, so a character is never cut in half; pass `INT_MAX` for `cols` to cut only to fit the buffer. It always NUL-terminates when `cap` > 0 and returns the bytes written. Window titles, `td_widget_set_text()`, desktop icon labels and the Delete and Save questions use it.

`td_utf8_skip()` returns the part of `s` after its first `cols` code points (the end of the string if it is shorter), counted as `td_utf8_next()` does: for example the second line of a label.

### Streaming decoder

```c
typedef struct {
    uint32_t cp;
    uint8_t need;
    uint8_t len;
} td_utf8_decoder_t;

int td_utf8_feed(td_utf8_decoder_t *d, uint8_t byte, uint32_t out[2]);
```

| Field | Meaning |
|---|---|
| `cp` | Code point being assembled. |
| `need` | Continuation bytes still expected (0 = between characters). |
| `len` | Continuation bytes of the current sequence. |

Treat the fields as private and zero-initialise the decoder before first use (`td_utf8_decoder_t d = {0};`). `td_utf8_feed()` takes one byte and returns how many code points it completed (0, 1 or 2), stored in `out[0]` and `out[1]`:

- An ASCII byte or the last byte of a valid sequence completes one code point.
- An invalid lead byte, or a stray continuation byte, produces U+FFFD.
- A sequence that decodes to an overlong form, a surrogate or a value above U+10FFFF produces U+FFFD.
- A sequence cut short by a non-continuation byte produces U+FFFD followed by the result of starting afresh with that byte (so 2 when the new byte is ASCII).

The input parser (see [Input](input.md)) and the [Terminal emulator](vterm.md) use this decoder.

## Renderer

The renderer keeps an output buffer and what it knows about the terminal's cursor and colour state, so it can skip redundant cursor moves and SGR sequences. The core owns the one renderer used for the desktop; applications do not normally call these functions. They are public for ports, tests (`tests/test_render.c`) and tools such as `tools/vtshot.c`.

```c
typedef struct {
    const td_hal_t *hal;
    int cur_x, cur_y;
    int cur_fg, cur_bg, cur_attr;
    uint8_t out[TD_OUT_BUF_SIZE];
    int out_len;
    bool write_failed;
    uint32_t bytes_sent;
} td_renderer_t;
```

| Field | Meaning |
|---|---|
| `hal` | HAL used for writing. |
| `cur_x`, `cur_y` | Terminal cursor position as far as the renderer knows (0-based); -1 = unknown. |
| `cur_fg`, `cur_bg`, `cur_attr` | Terminal colour and attribute state; -1 = unknown. |
| `out`, `out_len` | Output buffer and number of bytes queued. |
| `write_failed` | Set when a write in this frame came up short. While set, `td_render_flush()` discards queued output instead of writing it. `td_render_diff()` clears it at the start; clear it yourself before sending anything else. |
| `bytes_sent` | Running total of bytes the HAL accepted. |

### td_render_init / td_render_reset_state

```c
void td_render_init(td_renderer_t *r, const td_hal_t *hal);
void td_render_reset_state(td_renderer_t *r);
```

`td_render_init()` zeroes `r`, stores `hal` and marks the terminal state unknown. `td_render_reset_state()` only forgets the cursor and colour state (sets them to -1), so the next output repositions the cursor and resends the colours; use it when the terminal may have been reset or reconnected.

### td_render_raw

```c
void td_render_raw(td_renderer_t *r, const char *s);
```

Appends the NUL-terminated string `s` (typically an escape sequence) to the output buffer, flushing whenever the buffer fills. It does not update the renderer's cursor or colour state; if the sequence moves the cursor or changes colours, call `td_render_reset_state()` afterwards.

### td_render_flush

```c
bool td_render_flush(td_renderer_t *r);
```

Writes everything queued to the HAL, calling `write` again for the remainder after a partial write. If `write` returns `<= 0`, `write_failed` is set and the rest is discarded (the link is assumed not to be draining; stalling the UI would be worse). The buffer is empty afterwards in either case. Returns `!write_failed`.

### td_render_diff

```c
bool td_render_diff(td_renderer_t *r, td_buffer_t *front, const td_buffer_t *back);
```

Sends every cell of `back` that differs from `front` and copies it into `front`, then flushes.

| Parameter | Meaning |
|---|---|
| `front` | What the terminal is believed to show. Updated in place. If its size differs from `back`, it takes `back`'s size and is invalidated (everything is resent). |
| `back` | The new frame. |

Returns false if bytes were dropped. The cells of `front` may then claim content the terminal never received, so the caller must invalidate `front` and redraw later (the main loop does this, see [Core](core.md#link-supervision)).

Output details:

- The cursor is moved with `ESC [ row ; col H` only when it is not already at the cell (consecutive changed cells on a row need no move).
- An SGR sequence is sent only for what changed. Attributes can only be cleared by a reset, so any attribute change sends `ESC [ 0 ; ... m` with all attributes and both colours.
- After writing the last column the cursor position is treated as unknown (auto-wrap is off and terminals differ in where they leave the cursor).
- Characters are sent as UTF-8, through `td_ascii_fallback()` in ASCII mode. Control characters and U+007F are sent as spaces.

### Terminal setup and teardown

```c
void td_render_setup_terminal(td_renderer_t *r);
void td_render_restore_terminal(td_renderer_t *r);
void td_render_query_size(td_renderer_t *r);
```

`td_render_setup_terminal()` queues (without flushing) the following, then marks the cursor at (0, 0) and the colours unknown:

| Sequence | Purpose |
|---|---|
| `CAN` (0x18) | Abort any half-sent escape sequence left over from before. |
| `ESC [ ? 1049 h` | Alternate screen. |
| `ESC [ ? 25 l` | Hide the cursor. |
| `ESC [ ? 7 l` | Auto-wrap off. |
| `ESC [ ? 1000 h`, `? 1002 h`, `? 1003 h`, `? 1006 h` | Mouse reporting: clicks, drags, all motion (for hover highlights), SGR coordinates. |
| `ESC [ ? 2004 h` | Bracketed paste. |
| `ESC [ 0 m ESC [ 2 J ESC [ H` | Reset colours, clear the screen, home the cursor. |

`td_render_restore_terminal()` undoes it: mouse modes and bracketed paste off, colours reset, screen cleared, auto-wrap on, cursor shown, alternate screen left. It flushes immediately and forgets the terminal state.

`td_render_query_size()` queues `ESC 7 ESC [ 999 ; 999 H ESC [ 6 n ESC 8` (save cursor, move far past the corner, which the terminal clamps, request the cursor position, restore). It does not flush. The reply `ESC [ rows ; cols R` arrives as a `TD_EV_RESIZE` event (see [Input](input.md)).
