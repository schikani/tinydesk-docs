# Terminal emulator

`td_vterm` is a small VT100/ANSI terminal emulator that keeps a grid of character cells for the output of a program (a shell, a serial device) and draws it inside a window through the normal [Screen](screen.md) primitives. The Terminal app (`apps/terminal.c`) uses it to show TinyDesk Shell. It is deliberately a subset of VT100/xterm: enough for line editors and simple full-screen programs such as TinyDesk Shell's nano, with no double-width characters, no character sets and no real alternate screen.

Header: `include/tinydesk/td_vterm.h` (not included by `td.h`; include it explicitly)
Source: `src/vterm.c`

All functions work on the `td_vterm_t` you pass and have no global state, but `td_vterm_draw()` uses the global drawing target, so call everything from the UI task. Program output produced on another task must be handed to the UI task first (the Terminal app reads its backend from a timer).

## Types

### td_vcell_t

```c
typedef struct {
    uint16_t ch;
    uint8_t fg, bg;
} td_vcell_t;
```

| Field | Meaning |
|---|---|
| `ch` | Character, limited to the Basic Multilingual Plane. Code points above U+FFFF are stored as `?`. |
| `fg`, `bg` | 256-colour palette indexes, with bold and reverse already applied (see [SGR](#sgr-select-graphic-rendition)). |

A cell is 4 bytes. There is no attribute byte, so underline is tracked but never displayed.

### td_vterm_reply_fn

```c
typedef void (*td_vterm_reply_fn)(void *user, const char *data, int len);
```

Called with bytes the emulator must send back to the program: answers to device-status, cursor-position and device-attribute queries. `data` is not NUL-terminated and only valid during the call. Write it to the program's input.

### td_vterm_t

```c
typedef struct {
    int cols, rows;
    td_vcell_t cells[TD_VT_MAX_ROWS * TD_VT_MAX_COLS];
    td_vcell_t sb[TD_VT_SCROLLBACK * TD_VT_MAX_COLS];
    int sb_head;
    int sb_count;
    int cx, cy;
    int saved_cx, saved_cy;
    uint8_t fg, bg;
    uint8_t attr;
    uint8_t saved_fg, saved_bg, saved_attr;
    uint8_t def_fg, def_bg;
    int top, bottom;
    bool wrap_pending;
    bool autowrap;
    bool cursor_visible;
    bool newline_mode;

    uint8_t state;
    char params[40];
    int plen;
    bool priv;
    td_utf8_decoder_t utf8;

    td_vterm_reply_fn reply;
    void *reply_user;
    bool dirty;
} td_vterm_t;
```

| Field | Meaning |
|---|---|
| `cols`, `rows` | Size in use (1..`TD_VT_MAX_COLS` by 1..`TD_VT_MAX_ROWS`). |
| `cells` | Screen, row-major with a stride of `TD_VT_MAX_COLS` (cell (x, y) is `cells[y * TD_VT_MAX_COLS + x]`). |
| `sb` | Scrollback ring of `TD_VT_SCROLLBACK` lines, each `TD_VT_MAX_COLS` cells. |
| `sb_head` | Next scrollback line to overwrite. |
| `sb_count` | Lines currently held (up to `TD_VT_SCROLLBACK`). |
| `cx`, `cy` | Cursor, 0-based. |
| `saved_cx`, `saved_cy`, `saved_fg`, `saved_bg`, `saved_attr` | State saved by `ESC 7` (position, colours, attributes); `CSI s` saves only the position. |
| `fg`, `bg` | Current colours, before bold/reverse are applied. |
| `attr` | Current `TD_BOLD` / `TD_UNDERLINE` / `TD_REVERSE`. |
| `def_fg`, `def_bg` | Default colours, 7 on 0 after init. SGR 0/39/49 return to them. |
| `top`, `bottom` | Scroll region, inclusive rows. |
| `wrap_pending` | The last column was written; the next printable character wraps first. |
| `autowrap` | DECAWM (`CSI ? 7 h/l`); on after init. |
| `cursor_visible` | DECTCEM (`CSI ? 25 h/l`); on after init. |
| `newline_mode` | When true, LF (and VT, FF) also returns the cursor to column 0. On after init; no escape sequence changes it, but you may set the field after `td_vterm_init()`. |
| `state`, `params`, `plen`, `priv`, `utf8` | Parser state; private. |
| `reply`, `reply_user` | Reply callback and its argument (may be NULL: queries are then ignored). |
| `dirty` | Set whenever content may have changed (`td_vterm_init()`, `td_vterm_resize()`, any `td_vterm_write()` with `len > 0`). The emulator never clears it; clear it yourself after scheduling a redraw. |

Read the fields freely; change only `reply`, `reply_user`, `dirty`, `def_fg`/`def_bg` and `newline_mode` directly.

Memory: a `td_vterm_t` is about `TD_VT_MAX_COLS * (TD_VT_MAX_ROWS + TD_VT_SCROLLBACK) * 4` bytes, about 129 KB with the host defaults (132x50, 200 lines), about 12 KB on the ESP32-C6 (80x25, 12 lines) and about 296 KB on the classic ESP32 with PSRAM (256x96, 200 lines). Always give it static storage. See [Core](core.md#terminal-emulator) for the limits.

## Functions

### td_vterm_init

```c
void td_vterm_init(td_vterm_t *vt, int cols, int rows);
```

Resets `vt` to a blank screen of `cols` x `rows` (each clamped to 1..the maximum), with the cursor at (0, 0), default colours, the full-screen scroll region, auto-wrap and cursor on, and an empty scrollback.

`reply` and `reply_user` are preserved across the reset (everything else is zeroed), so you can set them before or after the call. Because they are read before the reset, `vt` must not contain garbage: use static (zero-initialised) storage, or set `reply`/`reply_user` first. Calling it again later clears the screen and scrollback but keeps the callback (the Terminal app does this when a new session starts).

### td_vterm_resize

```c
void td_vterm_resize(td_vterm_t *vt, int cols, int rows);
```

Changes the size (clamped like `td_vterm_init()`); does nothing if the size is unchanged. Content stays anchored at the top-left: shrinking cuts off the right columns and bottom rows, growing exposes blank cells. If the cursor row would fall off the bottom, the screen is first scrolled up just enough to keep it visible, and the lines that leave the top go to the scrollback. The scroll region is reset to the full screen, the cursor is clamped into the new size, and `dirty` is set.

The emulator does not tell the program about the new size; do that through your backend (the Terminal app passes the size to its shell backend).

### td_vterm_write

```c
void td_vterm_write(td_vterm_t *vt, const uint8_t *data, int len);
```

Feeds `len` bytes of program output. Escape sequences and UTF-8 characters may be split across calls. Replies to queries are sent through `reply` from inside this call. Sets `dirty` if `len > 0`.

### td_vterm_scrollback_lines

```c
int td_vterm_scrollback_lines(const td_vterm_t *vt);
```

Returns the number of lines in the scrollback (`sb_count`), the largest useful `scroll_back` value for `td_vterm_draw()`.

### td_vterm_draw

```c
void td_vterm_draw(const td_vterm_t *vt, int x, int y, int scroll_back, bool show_cursor);
```

Draws `vt->cols` x `vt->rows` cells at origin-relative (x, y) with `td_putc()`, so the current drawing origin and clip apply (inside `on_draw`, (0, 0) is the client area's top-left).

| Parameter | Meaning |
|---|---|
| `x`, `y` | Top-left cell, relative to the drawing origin. |
| `scroll_back` | 0 shows the live screen. `n > 0` shifts the view up by `n` lines into the scrollback (clamped to `sb_count`); the bottom `n` rows of the live screen are then not shown. |
| `show_cursor` | Draw the cursor as a reverse-video cell. It is only drawn when `vt->cursor_visible` is also set and `scroll_back` is 0. |

Cells are drawn with attribute 0 except the cursor. The function does not clear `dirty`.

## Supported control characters and sequences

Anything not listed here is parsed and ignored.

### C0 control characters

| Byte | Action |
|---|---|
| `CR` (0x0D) | Cursor to column 0. |
| `LF` (0x0A), `VT` (0x0B), `FF` (0x0C) | Line feed; also column 0 when `newline_mode` is set (the default). At the bottom of the scroll region the region scrolls up. Below the region, the cursor moves down until the last row and then stays. |
| `BS` (0x08) | Cursor one column left (stops at 0). |
| `HT` (0x09) | Next multiple-of-8 column, at most the last column. Tab stops cannot be set. |
| `BEL` (0x07), other C0, `DEL` (0x7F) | Ignored. |

Control characters are also executed when they appear in the middle of a CSI sequence.

### Escape sequences

| Sequence | Name | Action |
|---|---|---|
| `ESC 7` | DECSC | Save cursor position, colours and attributes. |
| `ESC 8` | DECRC | Restore them. |
| `ESC D` | IND | Line feed (without carriage return). |
| `ESC E` | NEL | Carriage return + line feed. |
| `ESC M` | RI | Reverse index: at the top of the scroll region, scroll the region down; otherwise move up one row. |
| `ESC c` | RIS | Reset state (colours, modes, cursor, scroll region) and clear the screen. The size is kept; scrollback lines already stored remain. |
| `ESC (` `ESC )` `ESC *` `ESC +` `ESC #` + one byte | Character-set designation, DEC line attributes | Consumed and ignored. |
| `ESC ]` ... `BEL` or `ESC \` | OSC (window title etc.) | Consumed and ignored. |
| `ESC [` ... | CSI | See below. |

Any other `ESC x` is ignored.

### CSI sequences

Parameters are decimal, separated by `;` or `:`, at most 16 are used and each is capped at 9999. Missing parameters are 0; for movement and count sequences 0 or missing means 1. `?` is recognised only as the first parameter byte (private mode). The parameter text is limited to 40 bytes; the excess is dropped. Unless noted, the sequences also cancel a pending wrap. Cursor movement is clamped to the screen and is not limited by the scroll region.

| Sequence | Name | Action |
|---|---|---|
| `CSI n A` | CUU | Cursor up n. |
| `CSI n B`, `CSI n e` | CUD, VPR | Cursor down n. |
| `CSI n C`, `CSI n a` | CUF, HPR | Cursor right n. |
| `CSI n D` | CUB | Cursor left n. |
| `CSI n E` | CNL | Down n, column 0. |
| `CSI n F` | CPL | Up n, column 0. |
| `CSI n G`, ``CSI n ` `` | CHA, HPA | Column n (1-based). |
| `CSI n d` | VPA | Row n (1-based). |
| `CSI r ; c H`, `CSI r ; c f` | CUP, HVP | Row r, column c (1-based; missing = 1). |
| `CSI n J` | ED | 0: cursor to end of screen. 1: start of screen to cursor. 2: whole screen. 3: whole screen and the scrollback. |
| `CSI n K` | EL | 0: cursor to end of line. 1: start of line to cursor. 2: whole line. |
| `CSI n L` | IL | Insert n blank lines at the cursor row (only inside the scroll region). |
| `CSI n M` | DL | Delete n lines at the cursor row (only inside the scroll region); deleted lines do not go to the scrollback. |
| `CSI n P` | DCH | Delete n characters, shifting the rest of the line left. |
| `CSI n @` | ICH | Insert n blank characters, shifting the rest right. |
| `CSI n X` | ECH | Erase n characters from the cursor. |
| `CSI n S` | SU | Scroll the region up n lines. |
| `CSI n T` | SD | Scroll the region down n lines. |
| `CSI t ; b r` | DECSTBM | Scroll region rows t..b (1-based; missing = whole screen). Ignored unless `t < b` and `b` is on screen. Homes the cursor to (0, 0). |
| `CSI s` | SCOSC | Save the cursor position (position only). |
| `CSI u` | SCORC | Restore the saved position. |
| `CSI ... m` | SGR | Colours and attributes; does not cancel a pending wrap. See below. |
| `CSI ? 7 h` / `l` | DECAWM | Auto-wrap on / off. |
| `CSI ? 25 h` / `l` | DECTCEM | Show / hide the cursor. |
| `CSI ? 47 h/l`, `? 1047 h/l`, `? 1049 h/l` | Alternate screen | Approximated: the screen is cleared on both enter and leave (the cursor is homed on enter). The previous content is **not** saved or restored. |
| `CSI 5 n` | DSR | Replies `ESC [ 0 n` (terminal OK). Does not cancel a pending wrap. |
| `CSI 6 n` | CPR | Replies `ESC [ row ; col R` with the 1-based cursor position. Does not cancel a pending wrap. |
| `CSI c`, `CSI 0 c` | DA | Replies `ESC [ ? 1 ; 2 c` (VT100 with advanced video). Also answers `CSI > c`, because `>` is not treated as a private marker. Does not cancel a pending wrap. |

Non-private `CSI h` / `CSI l` (ANSI modes such as insert mode or LNM) are ignored, as are all other private modes.

Erased and inserted cells take the current background colour (with reverse video, the current foreground), in the default foreground colour.

Lines that scroll off the top go to the scrollback only when the scroll region is the whole screen. Content scrolled out of a partial region (as a full-screen editor does) is discarded.

### SGR (select graphic rendition)

| Parameter | Action |
|---|---|
| none, `0` | Reset: default colours, no attributes. |
| `1` / `22` | Bold on / off. |
| `4` / `24` | Underline on / off (tracked but not displayed). |
| `7` / `27` | Reverse on / off. |
| `30`..`37` | Foreground colour 0..7. |
| `90`..`97` | Foreground colour 8..15. |
| `39` | Default foreground. |
| `40`..`47` | Background colour 0..7. |
| `100`..`107` | Background colour 8..15. |
| `49` | Default background. |
| `38;5;n` / `48;5;n` | 256-colour foreground / background (n clamped to 0..255). |
| `38;2;r;g;b` / `48;2;r;g;b` | True colour, approximated with the nearest entry of the xterm 6x6x6 colour cube (indexes 16..231). |

Colon separators (`38:5:n`) are accepted too. A malformed `38`/`48` stops processing of the rest of that SGR sequence. Other parameters (dim, italic, blink, hidden, strike-through) are ignored.

Bold and reverse are folded into the cell colours when a character is written: bold turns foreground colours 0..7 into their bright versions 8..15, and reverse swaps foreground and background.

### Characters

Printable bytes are decoded as UTF-8 (malformed input becomes U+FFFD). Every character takes one column, so double-width and combining characters are not rendered correctly. Characters above U+FFFF are shown as `?`.

## Example

A window that shows a terminal and answers queries through a program backend. `prog_write()` stands for whatever sends bytes to the program (a pipe, a socket, a UART):

```c
#include "tinydesk/td.h"
#include "tinydesk/td_vterm.h"

void prog_write(const char *data, int len);   /* your backend */

static td_vterm_t s_vt;                       /* static: it is large */

static void vt_reply(void *user, const char *data, int len)
{
    (void)user;
    prog_write(data, len);
}

static void term_draw(td_window_t *win, int w, int h)
{
    td_vterm_resize(&s_vt, w, h);             /* follow the window size */
    td_vterm_draw(&s_vt, 0, 0, 0, win == td_win_focused());
}

/* Call from the UI task (a timer or on_tick) with output read from the program. */
static void term_output(td_window_t *win, const uint8_t *buf, int n)
{
    td_vterm_write(&s_vt, buf, n);
    if (s_vt.dirty) {
        s_vt.dirty = false;
        td_win_invalidate(win);
    }
}

static void term_setup(void)
{
    s_vt.reply = vt_reply;
    td_vterm_init(&s_vt, 80, 24);             /* keeps the reply callback */
}
```

Keys typed into the window have to be translated back into the bytes a VT100 sends (arrows as `ESC [ A`, and so on); the emulator does not do that. `apps/terminal.c` contains a complete translation and shows scrollback with Shift+PgUp / Shift+PgDn and the mouse wheel. See [Apps API](apps.md) for the Terminal app's backend interface.
