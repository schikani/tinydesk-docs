# Widgets

Widgets are the controls inside a window's client area: labels, buttons, checkboxes, text boxes, lists, progress bars and scrollbars, plus ready-made modal dialogs (message box, input box, password box). Every widget comes from one static pool shared by all windows, is linked into its window in creation order, and is freed with the window. Widgets draw themselves after the window's `on_draw` and get mouse and key events before `on_event` (see [wm.md](wm.md#callbacks)).

Header: `include/tinydesk/td_widgets.h` (included by `tinydesk/td.h`)
Source: `src/widgets.c`

All functions must be called from the UI task. None are thread-safe.

## The widget pool

| Macro | Default | ESP32-C6 build | Classic ESP32 build (PSRAM) | Meaning |
|---|---|---|---|---|
| `TD_MAX_WIDGETS` | 128 | 96 | 128 | Widgets in all open windows together (the last 4 only for a message box). |
| `TD_TEXT_MAX` | 64 | 48 | 48 | Bytes of a widget's text, including the NUL. |

When the pool is full a widget function returns NULL (every widget function
accepts NULL and does nothing), and the window is marked `incomplete`, as is
a window whose `on_tick` timer could not start (`TD_MAX_TIMERS`). The last 4
widgets and the last window slot are kept for message boxes (`TD_WIN_MODAL`).
A window opened by an app's `launch` that ends up incomplete, or an app
whose window got no slot, is closed again right after `launch` returns, with the message *Too many windows are open. Close
one, then try again.*, so no window opens with missing buttons or lists. An
app that reads widget fields itself (`w->count`, `w->scroll`) must check the
pointer first.

The ESP values are set in `ports/esp_idf/components/tinydesk/CMakeLists.txt`; the defaults are in `include/tinydesk/td_config.h`.

- When the pool is full, every creation function returns `NULL`. Nothing else reports it.
- Creating a widget on a window that is not open also returns `NULL`.
- All setters and getters accept `NULL` and then do nothing (getters return `false` or -1), so a failed creation does not crash later calls. `td_widget_rect()` is the exception: it needs a valid widget.
- The dialogs below create widgets too: a message box uses one label per text line plus one button per button, an input box uses four.
- Widgets cannot be deleted one by one; they are freed when their window closes. To show and hide parts of a window, create the widgets once and use `td_widget_set_visible()`.

On the ESP32-C6, 40 widgets are shared by every open window. Draw static text in `on_draw` with `td_text()` instead of creating label widgets, and keep widgets for things the user interacts with or that change (see [the tutorial](../guide/writing-an-app.md#ram-rules-on-the-esp32)).

## Positions and sizes

Widget positions are relative to the window's client area, in cells. They are resolved every time the widget is drawn or hit-tested, so widgets placed relative to the right or bottom edge follow window resizes.

| Value | Meaning |
|---|---|
| `x >= 0`, `y >= 0` | Column / row from the left / top edge. |
| `x < 0`, `y < 0` | Measured from the right / bottom edge: `x = -1` is the last column, `y = -1` the last row. |
| `width > 0`, `height > 0` | Size in cells. |
| `width <= 0`, `height <= 0` | Extends to that many cells before the right / bottom edge: 0 reaches the edge, -2 stops two cells before it. Sizes that come out negative are treated as 0. |

```c
/* A list filling the window except the last column (scrollbar) and the
 * last row (buttons), with a scrollbar and a button row at the bottom. */
td_widget_t *list = td_list(win, td_rect(0, 0, -1, -1), get_item, on_open, NULL);
td_scrollbar(win, -1, 0, -1, list);
td_button(win, 0, -1, "Open", on_open, NULL);
```

Buttons and checkboxes have a fixed width computed from their caption, so a negative `x` must leave room for it (`td_button(win, -10, -1, "Close", ...)` puts a 9-cell button one column from the right edge).

## Types

```c
typedef enum {
    TD_WT_LABEL,
    TD_WT_BUTTON,
    TD_WT_CHECKBOX,
    TD_WT_TEXTBOX,
    TD_WT_LIST,
    TD_WT_PROGRESS,
    TD_WT_SCROLLBAR,
} td_widget_type_t;

typedef enum { TD_ALIGN_LEFT, TD_ALIGN_CENTER, TD_ALIGN_RIGHT } td_align_t;

/* Colour value meaning "use the theme". */
#define TD_COLOR_DEFAULT (-1)

typedef void (*td_widget_fn)(td_widget_t *w, void *user);

typedef const char *(*td_list_item_fn)(td_widget_t *w, int index, int *fg, void *user);
```

| Type | Focusable | Created by |
|---|---|---|
| `TD_WT_LABEL` | no | `td_label()` |
| `TD_WT_BUTTON` | yes | `td_button()` |
| `TD_WT_CHECKBOX` | yes | `td_checkbox()` |
| `TD_WT_TEXTBOX` | yes | `td_textbox()` |
| `TD_WT_LIST` | yes | `td_list()` |
| `TD_WT_PROGRESS` | no | `td_progress()` |
| `TD_WT_SCROLLBAR` | no (but clickable) | `td_scrollbar()` |

`td_widget_fn` is the activation callback of buttons, checkboxes, text boxes and lists; it receives the widget and the `user` pointer given at creation. `td_list_item_fn` supplies list item text, see [td_list](#td_list).

## td_widget_t

```c
struct td_widget {
    bool used;
    uint8_t type;
    uint8_t align;
    bool focusable;
    bool visible;
    bool pressed;            /* button held down with the mouse */
    bool secret;             /* textbox: show '*' instead of the text */
    td_rect_t rect;          /* relative to the client area (see above) */
    td_window_t *win;
    td_widget_t *next;
    char text[TD_TEXT_MAX];  /* label / caption / textbox contents */
    int value;               /* checked, percent, selected item, cursor */
    int scroll;              /* first visible item / column */
    int count;               /* list item count */
    int maxlen;              /* textbox maximum length in bytes */
    int fg, bg;              /* TD_COLOR_DEFAULT or a palette index */
    td_widget_fn on_activate;
    td_list_item_fn get_item;
    td_widget_t *target;     /* scrollbar: the list it controls */
    uint32_t last_click_ms;  /* list double-click detection */
    void *user;
};
```

Read the fields freely; change them through the functions.

| Field | Meaning |
|---|---|
| `used` | Slot in use. |
| `type` | A `td_widget_type_t`. |
| `align` | A `td_align_t` (labels). |
| `focusable` | Can take the keyboard focus. |
| `visible` | Drawn and receives events. |
| `pressed` | A button is held down with the mouse. |
| `secret` | Text box shows `*` for each character (set by `td_passwordbox()`). |
| `rect` | Position and size as given, before resolving negative values (use `td_widget_rect()` for the result). |
| `win` | Owning window. |
| `next` | Next widget of the same window. |
| `text` | Label text, caption, or text box contents. |
| `value` | Checkbox: 1 checked, 0 not. Progress: percent. List: selected index. Text box: cursor position (byte offset). Message box buttons: the button index. |
| `scroll` | List: first visible item. Text box: first visible byte. |
| `count` | List: number of items. |
| `maxlen` | Text box: maximum length in bytes. |
| `fg`, `bg` | Custom colours, or `TD_COLOR_DEFAULT`. |
| `on_activate` | Activation callback. |
| `get_item` | List item callback. |
| `target` | Scrollbar: the list it controls. |
| `last_click_ms` | List: time of the last click, for double-clicks. |
| `user` | Pointer passed to the callbacks. |

## Creating widgets

### td_label

```c
td_widget_t *td_label(td_window_t *win, int x, int y, int width, const char *text);
```

Static or dynamic text, one row high. `width <= 0` means "to the right edge" (minus that many cells). The text is copied and cut to `TD_TEXT_MAX - 1` bytes; it is also cut at the widget's width when drawn. The label fills its whole width with its background, so it erases what `on_draw` drew below it. Labels ignore the mouse. Returns the widget or `NULL`.

### td_button

```c
td_widget_t *td_button(td_window_t *win, int x, int y, const char *caption,
                       td_widget_fn fn, void *user);
```

A push button drawn as `[ caption ]`, caption width plus 4 cells wide. `fn(w, user)` runs on a click (press and release over the button), or on Enter or Space while it has the focus. The button uses the focus colours while it has the focus or the mouse is over it. `fn` may be `NULL`. Changing the caption with `td_widget_set_text()` recomputes the width.

### td_checkbox

```c
td_widget_t *td_checkbox(td_window_t *win, int x, int y, const char *caption,
                         bool checked, td_widget_fn fn, void *user);
```

A `[x] caption` toggle, starting as `checked`. A click, Enter or Space toggles it, then `fn(w, user)` runs (after every change made by the user; not after `td_checkbox_set()`). Read the state with `td_checkbox_get()`. Two checkboxes can act as radio buttons by clearing the other one in `fn`, as the Date & time window does.

```c
bool td_checkbox_get(const td_widget_t *w);
void td_checkbox_set(td_widget_t *w, bool checked);
```

`td_checkbox_get()` returns the state (`false` for `NULL`). `td_checkbox_set()` changes it without calling `fn`.

### td_textbox

```c
td_widget_t *td_textbox(td_window_t *win, int x, int y, int width, int maxlen,
                        td_widget_fn fn, void *user);
```

A single-line text entry, starting empty. `maxlen` is the most bytes the user can type; it is clamped to 1 .. `TD_TEXT_MAX - 1`. `fn(w, user)` runs when Enter is pressed. The text is in `w->text`.

Keys: printable ASCII characters (0x20 to 0x7E) are inserted at the cursor; Backspace, Delete, Left, Right, Home and End edit and move. Keys with Ctrl or Alt are not used (they go on to `on_event`). A click places the cursor. The box scrolls horizontally to keep the cursor visible.

- Only ASCII can be typed. `td_widget_set_text()` accepts any text, but the cursor works in bytes, so keep text box contents ASCII.
- `td_widget_set_text()` on a text box moves the cursor to the end and is limited by `TD_TEXT_MAX`, not by `maxlen`.
- For longer text, give the box a buffer of the app's own: `td_textbox_set_buffer(w, buf, cap)` (it must live as long as the window; its contents become the text and `maxlen` becomes `cap - 1`). Read a widget's text with `td_widget_text(w)`, which works either way (`w->text` is empty for such a box). Software Update's URL field uses a 200-byte buffer.
- Text boxes in a `TD_WIN_RAW_KEYS` window get no keys.

### td_widgets_paste

```c
bool td_widgets_paste(td_window_t *win);
```

Inserts the text of the `TD_EV_PASTE` event being handled into the window's focused text box. Only the first line is used (up to the first CR or LF), tabs become spaces, other control characters and non-ASCII bytes are skipped, and insertion stops at the box's `maxlen`. Returns `false`, without doing anything, when the focused widget is not a visible text box (or `win` is `NULL`); returns `true` otherwise, even if nothing fitted. The window manager calls it for every paste into a window without `TD_WIN_RAW_KEYS` (see [wm.md](wm.md#paste)); call it yourself only if you handle `TD_EV_PASTE` in a raw-keys window.

### td_list

```c
td_widget_t *td_list(td_window_t *win, td_rect_t rect, td_list_item_fn get_item,
                     td_widget_fn fn, void *user);
```

A scrollable list. The list stores no items: `get_item` supplies the text of each visible row while it is drawn, and `td_list_set_count()` sets the number of items (0 at first).

| Parameter | Meaning |
|---|---|
| `rect` | Position and size, with the rules from [Positions and sizes](#positions-and-sizes). |
| `get_item` | `const char *get_item(td_widget_t *w, int index, int *fg, void *user)`: return the text of item `index`. `*fg` starts as `TD_COLOR_DEFAULT`; set it to a palette index to colour this item. The returned string is drawn at once and not kept, so a static buffer that is overwritten on the next call is fine. Returning `NULL` draws an empty row. |
| `fn` | Runs on Enter (when the list has items) or a double-click on an item. Read the item with `td_list_selected()`. |
| `user` | Passed to both callbacks. |

Keys: Up, Down, PgUp, PgDn, Home, End move the selection. A click selects; a second click on the selected item within `TD_DOUBLE_CLICK_MS` activates it. The mouse wheel scrolls three rows without changing the selection. The selected item is highlighted with `select_fg` / `select_bg` while the list has the focus, and with the theme's `dim` background otherwise.

```c
void td_list_set_count(td_widget_t *w, int count);
int td_list_selected(const td_widget_t *w);
void td_list_select(td_widget_t *w, int index);
```

| Function | Description |
|---|---|
| `td_list_set_count()` | Sets the item count (negative is 0). The selection is moved to the last item if it was past the end; the scroll offset is clamped. Call it whenever the underlying data changes. |
| `td_list_selected()` | Selected index, or -1 when the list is empty (or `NULL`). |
| `td_list_select()` | Selects `index`, clamped to the items, and scrolls it into view. Does nothing on an empty list. Does not call `fn`. |

```c
static const char *const s_names[] = { "red", "green", "blue" };

static const char *get_item(td_widget_t *w, int index, int *fg, void *user)
{
    (void)w; (void)user;
    if (index == 0) *fg = 9;          /* bright red */
    return s_names[index];
}

static void on_pick(td_widget_t *w, void *user)
{
    (void)user;
    td_logf('I', "picked %s", s_names[td_list_selected(w)]);
}

/* in launch(): */
td_widget_t *list = td_list(win, td_rect(1, 1, -1, -2), get_item, on_pick, NULL);
td_list_set_count(list, 3);
td_widget_focus(list);
```

### td_progress

```c
td_widget_t *td_progress(td_window_t *win, int x, int y, int width);
```

A horizontal bar, one row high, showing 0 to 100 percent with full and light-shade blocks in the theme's `accent` colour. Not focusable; ignores the mouse.

```c
void td_progress_set(td_widget_t *w, int percent);
```

Sets the value, clamped to 0 .. 100. Only redraws when the value changes.

### td_scrollbar

```c
td_widget_t *td_scrollbar(td_window_t *win, int x, int y, int height, td_widget_t *target);
```

A vertical scrollbar, one column wide, that shows and controls the scroll position of the list `target`. A click on the top or bottom row scrolls one item, a click or drag on the track jumps there, and the wheel scrolls three items. It follows the list automatically; there is nothing to update. `height <= 0` extends towards the bottom edge like any other size.

## Common functions

```c
void td_widget_set_text(td_widget_t *w, const char *text);
void td_widget_printf(td_widget_t *w, const char *fmt, ...);
void td_widget_set_align(td_widget_t *w, td_align_t align);
void td_widget_set_color(td_widget_t *w, int fg, int bg);
void td_widget_set_visible(td_widget_t *w, bool visible);
void td_widget_focus(td_widget_t *w);
td_rect_t td_widget_rect(const td_widget_t *w);
```

| Function | Description |
|---|---|
| `td_widget_set_text()` | Copies `text` (`NULL` is empty) into the widget, cut to `TD_TEXT_MAX - 1` bytes. For a button the width follows the new caption; for a text box the cursor moves to the end. Always redraws. |
| `td_widget_printf()` | Formats into a `TD_TEXT_MAX` buffer and sets the text only if it differs from the current text, so calling it on every tick costs no redraw when nothing changed. |
| `td_widget_set_align()` | Left, centre or right alignment of a label's text within its width. Does not request a redraw by itself; set it before the text, or call `td_win_invalidate()`. |
| `td_widget_set_color()` | Custom foreground and background: a palette index (0 to 255) or `TD_COLOR_DEFAULT` for the theme colour. Buttons still use the focus colours while focused or hovered. For a list, `fg` / `bg` colour the whole list; per-item colours come from `get_item`. |
| `td_widget_set_visible()` | Shows or hides a widget. A hidden widget is not drawn and gets no events; if it had the focus, the focus moves to the next focusable widget. |
| `td_widget_focus()` | Gives the keyboard focus to `w` within its window. Ignored for widgets that are not focusable or not visible. It does not raise the window. |
| `td_widget_rect()` | The widget's rectangle in absolute screen coordinates, with negative positions and sizes resolved. `w` must be a valid widget whose window is open. |

Colour values are theme-independent palette indexes; to follow the theme, pass a field of `td_theme()`, for example `td_widget_set_color(w, td_theme()->dim, TD_COLOR_DEFAULT)`. Such a colour is not updated when the theme changes later.

## Focus

- The first focusable widget created in a window gets the focus.
- Tab moves to the next focusable, visible widget in creation order and Shift+Tab to the previous one, wrapping around (not in `TD_WIN_RAW_KEYS` windows).
- A click on a focusable widget focuses it.
- `win->focus` is the focused widget of each window; the widget only draws as focused while its window is the focused window.

## Dialogs

The dialogs are modal windows (`TD_WIN_MOVABLE | TD_WIN_CLOSABLE | TD_WIN_MODAL`), centred on the screen. They return at once; the answer arrives in a callback after the dialog has been closed, so the callback may open another dialog. While a dialog is open, other windows and the desktop ignore the mouse and keyboard (the taskbar and start menu still work).

### td_msgbox

```c
td_window_t *td_msgbox(const char *title, const char *text, const char *buttons,
                       void (*fn)(int button, void *user), void *user);
```

Shows a message with one or more buttons.

| Parameter | Meaning |
|---|---|
| `title` | Title bar text. |
| `text` | Message. `'\n'` separates lines; at most 8 lines are shown, each cut to `TD_TEXT_MAX - 1` bytes, centred. |
| `buttons` | `'|'` separated captions, for example `"OK"` or `"Save|Discard|Cancel"`. At most 4. `NULL` or `""` means `"OK"`. |
| `fn` | `fn(button, user)` with the index of the chosen button (0 is the first), or -1 when the dialog is closed any other way: Esc, `[x]`, Ctrl+Q, or being closed by `td_win_close()` / `td_wm_close_all()` (for example on a user switch). May be `NULL`. |
| `user` | Passed to `fn`. |
| Returns | The dialog window, or `NULL` when 4 message boxes are already open or the window pool is full. |

The width fits the title, the longest line and the buttons, clamped to the screen. The strings are copied; they need not stay valid.

```c
static void on_answer(int button, void *user)
{
    td_window_t *editor = user;
    if (button == 0) save_file();
    if (button == 0 || button == 1) td_win_close(editor);   /* 2 or -1: keep editing */
}

static bool on_close_request(td_window_t *win)
{
    if (!s_modified) return true;
    td_msgbox("Editor", "Save changes?", "Save|Discard|Cancel", on_answer, win);
    return false;
}
```

### td_inputbox

```c
td_window_t *td_inputbox(const char *title, const char *prompt, const char *initial,
                         void (*fn)(const char *text, void *user), void *user);
```

A one-line text prompt with OK and Cancel. `initial` (may be `NULL`) is the starting text, with the cursor at its end. `fn(text, user)` runs when OK is clicked or Enter is pressed, not on Cancel, Esc or `[x]`. The `text` pointer is a copy on the stack, valid only during the call; copy it if you need it later. Up to `TD_TEXT_MAX - 1` characters can be typed (47 on the ESP32 builds). Returns the dialog, or `NULL` when two input boxes are already open or the window pool is full.

```c
static void on_name(const char *text, void *user)
{
    (void)user;
    if (!td_valid_name(text)) {
        td_msgbox("Rename", "That is not a valid name.", "OK", NULL, NULL);
        return;
    }
    do_rename(text);
}

td_inputbox("Rename", "New name:", current_name, on_name, NULL);
```

### td_passwordbox

```c
td_window_t *td_passwordbox(const char *title, const char *prompt,
                            void (*fn)(const char *text, void *user), void *user);
```

The same as `td_inputbox()` with an empty start and the typed text shown as `*`. It shares the pool of two input boxes. The password stays in the text box memory (the widget pool) after the dialog closes, until the widget slot is reused.

## Used by the window manager

These are called by `src/wm.c`; apps do not need them.

```c
void td_widgets_draw(td_window_t *win);
bool td_widgets_event(td_window_t *win, const td_event_t *ev);
void td_widgets_free(td_window_t *win);
void td_widgets_focus_next(td_window_t *win, int dir);
void td_widgets_reset(void);
```

| Function | Description |
|---|---|
| `td_widgets_draw()` | Draws the visible widgets of `win`, in creation order, with origin and clip set to the client area. |
| `td_widgets_event()` | Offers a key (to the focused widget) or a mouse event (client coordinates, to the widget under the pointer or to a button or scrollbar held with the mouse). Returns `true` if a widget consumed it. |
| `td_widgets_free()` | Returns every widget of `win` to the pool. Called by `td_win_close()`. |
| `td_widgets_focus_next()` | Moves the focus to the next (`dir > 0`) or previous focusable, visible widget. |
| `td_widgets_reset()` | Empties the whole pool. Called by `td_wm_init()`. |
