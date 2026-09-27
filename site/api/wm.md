# Window manager

The window manager owns every window, their stacking order and focus, the desktop (background pattern and icons), the taskbar with its clock and tray, the start menu and popup menus, and file drag and drop. Every frame is composed from scratch: the desktop, then the visible windows from bottom to top, then the taskbar and any open menu; the renderer only sends the cells that changed (see [screen.md](screen.md)). Windows and their callbacks are plain C structures taken from static pools, so nothing here allocates memory.

Header: `include/tinydesk/td_wm.h` (included by `tinydesk/td.h`)
Sources: `src/wm.c`, `src/theme.c`

The app registry (`td_app_t`, `td_app_register()`, `td_app_launch()`) is declared in this header too; it is documented in [apps.md](apps.md#app-registry).

All functions on this page must be called from the UI task (the task that runs `td_run()` or `td_step()`, see [core.md](core.md)). None of them are thread-safe.

## Limits

| Macro | Default | Meaning |
|---|---|---|
| `TD_MAX_WINDOWS` | 12 | Open windows at once, dialogs included. `td_win_create()` returns `NULL` beyond it. |
| `TD_MAX_TIMERS` | 16 | Shared timer pool; each window with an `on_tick` uses one. |
| `TD_MAX_APPS` | 16 | Registered apps (start menu entries and desktop icons). |
| `TD_TITLE_MAX` | 32 | Bytes of a window title, including the NUL. Longer titles are cut. |
| `TD_DOUBLE_CLICK_MS` | 400 | Double-click window for title bars, desktop icons and lists. |

All of them live in `include/tinydesk/td_config.h` and can be overridden from the build system.

## Window flags

```c
#define TD_WIN_MOVABLE    0x0001u
#define TD_WIN_RESIZABLE  0x0002u
#define TD_WIN_CLOSABLE   0x0004u
#define TD_WIN_MODAL      0x0008u
#define TD_WIN_RAW_KEYS   0x0010u  /* all keys (Tab, Esc, ...) go to on_event */
#define TD_WIN_HIDDEN     0x0100u  /* minimised to the taskbar */
#define TD_WIN_MAXIMIZED  0x0200u
#define TD_WIN_FULLSCREEN 0x0400u  /* no frame, covers the taskbar */

#define TD_WIN_DEFAULT (TD_WIN_MOVABLE | TD_WIN_RESIZABLE | TD_WIN_CLOSABLE)
```

| Flag | Set by | Effect |
|---|---|---|
| `TD_WIN_MOVABLE` | you | The title bar can be dragged with the mouse (not while maximised). |
| `TD_WIN_RESIZABLE` | you | The bottom-right corner is a resize grip; the window can be maximised (title double-click, window menu) and put in full screen with F11 or the window menu. |
| `TD_WIN_CLOSABLE` | you | Shows `[x]` in the title bar and "Close" in the window menu. Ctrl+Q and Alt+F4 close any window, closable or not. |
| `TD_WIN_MODAL` | you | A dialog: it stays above ordinary windows, keeps the keyboard and mouse until closed, has no `[-]` button, cannot be minimised, closes on Esc and has no taskbar button. |
| `TD_WIN_RAW_KEYS` | you | Every key the window manager does not handle itself goes straight to `on_event`; widgets get no keys (see [Keyboard](#keyboard)). Used by the Terminal and the Editor. |
| `TD_WIN_HIDDEN` | window manager | The window is minimised. |
| `TD_WIN_MAXIMIZED` | window manager | The window covers the desktop area above the taskbar. |
| `TD_WIN_FULLSCREEN` | window manager | No frame; the client area is the whole screen. The taskbar is hidden while this window is on top. |

Set the first five in `td_window_desc_t.flags`. Read the last three from `td_window_t.flags`, but change them only through `td_win_minimize()`, `td_win_toggle_maximize()` and `td_win_set_fullscreen()`.

## Creating windows

### td_window_desc_t

```c
typedef struct {
    const char *title;
    td_rect_t rect;         /* outer frame; x or y < 0 centres the window */
    uint16_t flags;
    int min_w, min_h;       /* resize limits (0 = defaults) */

    void (*on_draw)(td_window_t *win, int client_w, int client_h);
    bool (*on_event)(td_window_t *win, const td_event_t *ev);
    void (*on_close)(td_window_t *win);
    bool (*on_close_request)(td_window_t *win);
    void (*on_tick)(td_window_t *win);
    uint32_t tick_ms;
    bool (*on_drag_start)(td_window_t *win, int x, int y, td_drag_item_t *item);
    bool (*on_drop)(td_window_t *win, int x, int y, const td_drag_item_t *item);
    const char *icon;
    void *user;
} td_window_desc_t;
```

Everything needed to open a window. The descriptor is only read during `td_win_create()`; it can live on the stack. Unused callbacks may be `NULL` (a designated initializer leaves them zero).

| Field | Meaning |
|---|---|
| `title` | Title bar and taskbar text. Copied (at most `TD_TITLE_MAX - 1` bytes). `NULL` is an empty title. |
| `rect` | Outer frame in screen cells, border included. The client area is 2 columns narrower and 2 rows lower. `x < 0` centres horizontally, `y < 0` centres vertically on the desktop (each axis on its own). `w <= 0` becomes 40, `h <= 0` becomes 12. The rectangle is then clamped to the screen. |
| `flags` | `TD_WIN_*` flags, see above. |
| `min_w`, `min_h` | Smallest outer size for resizing. 0 (or negative) means 16 x 4. |
| `on_draw` | Draws the client area, see [Callbacks](#callbacks). |
| `on_event` | Receives events no widget consumed. |
| `on_close` | Called just before the window is destroyed. |
| `on_close_request` | Asked before a user-initiated close; return `false` to keep the window. `NULL` always allows. |
| `on_tick` | Called every `tick_ms` milliseconds while the window is open. |
| `tick_ms` | Tick interval. The timer is only started when both `on_tick` and `tick_ms > 0` are set. |
| `on_drag_start` | Optional: start dragging a file or folder from the client area. |
| `on_drop` | Optional: receive a file or folder dropped on the client area. |
| `icon` | Two-cell glyph for the taskbar button (large taskbar only). `NULL` takes the icon of the app being launched, if the window is opened from `td_app_launch()`, the start menu or a desktop icon. The pointer is stored, not copied: use a string literal. |
| `user` | Your pointer, stored in `td_window_t.user`. |

### td_window_t

```c
struct td_window {
    bool used;
    uint8_t id;
    char title[TD_TITLE_MAX];
    td_rect_t rect;          /* outer frame in screen cells */
    td_rect_t restore_rect;  /* rect before maximise / fullscreen */
    uint16_t flags;
    int min_w, min_h;
    td_widget_t *widgets;    /* singly linked, in creation order */
    td_widget_t *focus;      /* focused widget or NULL */
    void (*on_draw)(td_window_t *win, int client_w, int client_h);
    bool (*on_event)(td_window_t *win, const td_event_t *ev);
    void (*on_close)(td_window_t *win);
    bool (*on_close_request)(td_window_t *win);
    void (*on_tick)(td_window_t *win);
    bool (*on_drag_start)(td_window_t *win, int x, int y, td_drag_item_t *item);
    bool (*on_drop)(td_window_t *win, int x, int y, const td_drag_item_t *item);
    int timer_id;
    const char *icon;        /* taskbar glyph or NULL */
    void *user;
};
```

A window slot in the static pool. Read the fields freely; change them through the functions below.

| Field | Meaning |
|---|---|
| `used` | True while the slot holds an open window. |
| `id` | Pool index (0 .. `TD_MAX_WINDOWS - 1`). |
| `title` | Current title. |
| `rect` | Outer frame in screen cells. |
| `restore_rect` | Frame to return to after maximise or full screen. |
| `flags` | `TD_WIN_*` flags, including the state flags. |
| `min_w`, `min_h` | Resolved minimum size. |
| `widgets` | First widget; the list is linked through `td_widget_t.next` in creation order (see [widgets.md](widgets.md)). |
| `focus` | Widget with the keyboard focus inside this window, or `NULL`. |
| `on_*` | The callbacks from the descriptor. |
| `timer_id` | Tick timer id, or -1 when the window has no tick (or the timer pool was full). |
| `icon` | Taskbar glyph or `NULL`. |
| `user` | Your pointer. |

Window slots are reused. A pointer to a closed window must not be used: `td_win_is_open()` only checks that the slot is in use, so after the slot has been given to a new window a stale pointer looks valid again. The usual pattern is a static pointer that `on_close` sets back to `NULL`.

### td_win_create

```c
td_window_t *td_win_create(const td_window_desc_t *desc);
```

Opens a window on top of the others and focuses it.

| | |
|---|---|
| `desc` | Window description; read during the call only. |
| Returns | The window, or `NULL` when all `TD_MAX_WINDOWS` slots are in use. |

- While a modal dialog is open, a new ordinary window is placed below the dialog, so the dialog keeps the focus.
- Opening a window closes any open popup or start menu.
- If `on_tick` is set but the timer pool (`TD_MAX_TIMERS`) is full, the window opens without a tick and `timer_id` is -1. Nothing reports this.
- The first focusable widget you add later gets the keyboard focus.

```c
td_window_desc_t d = {
    .title = "Status",
    .rect = td_rect(-1, -1, 40, 10),   /* centred */
    .flags = TD_WIN_DEFAULT,
    .on_draw = on_draw,
    .on_close = on_close,
};
td_window_t *win = td_win_create(&d);
if (!win) return;                      /* window pool full */
```

## Closing windows

### td_win_close

```c
void td_win_close(td_window_t *win);
```

Closes a window at once: calls `on_close`, stops the tick timer, frees the window's widgets and releases the slot. `on_close_request` is not asked. Calling it with `NULL` or a window that is not open does nothing. `on_close` runs only once even if it closes the window again. A widget callback may close its own window (the message box buttons do); do not touch the window or its widgets after that.

### td_win_request_close

```c
void td_win_request_close(td_window_t *win);
```

Closes the window as if the user had asked to: `on_close_request` is called first and may return `false` to keep the window open (for example to ask about unsaved changes). The window manager uses this for `[x]`, the window menu's "Close", Ctrl+Q / Alt+F4 and Esc on a dialog. Ignored for windows that are not open.

### td_wm_close_all

```c
void td_wm_close_all(void);
```

Closes every window, from the top, without asking (`on_close` runs, `on_close_request` does not), cancels any drag and closes the menu. Used when the desktop user changes (see `td_session_switch()` in [apps.md](apps.md#sessions)). `on_close` handlers must not open new windows while this runs.

## Focus, order and state

### td_win_focus

```c
void td_win_focus(td_window_t *win);
```

Raises the window to the top, un-minimises it and gives it the focus. Does nothing if the window is not open, or if a modal dialog is open and `win` is not that dialog.

### td_win_focused

```c
td_window_t *td_win_focused(void);
```

Returns the focused window, which is the top-most window that is not minimised, or `NULL` when every window is closed or minimised. An open modal dialog is always the focused window.

### td_win_set_title

```c
void td_win_set_title(td_window_t *win, const char *title);
```

Changes the title (copied, at most `TD_TITLE_MAX - 1` bytes; `NULL` means empty). Ignored for windows that are not open.

### td_win_move / td_win_resize

```c
void td_win_move(td_window_t *win, int x, int y);
void td_win_resize(td_window_t *win, int w, int h);
```

Move the outer frame's top-left corner, or change its outer size. The result is clamped: the width and height stay between the minimum size and the screen (the desktop height, above the taskbar), the window stays inside the screen horizontally and its title bar stays on the desktop. `td_win_resize()` keeps the current position, so the size is also limited by the space to the right and below. For a maximised or full-screen window the rectangle is reset to the maximised / full-screen area, so these calls have no visible effect.

### td_win_minimize

```c
void td_win_minimize(td_window_t *win);
```

Hides the window to the taskbar (sets `TD_WIN_HIDDEN`). Its button stays in the taskbar, dimmed; clicking it (or `td_win_focus()`) brings the window back. Modal dialogs cannot be minimised. A minimised window keeps its tick timer running.

### td_win_toggle_maximize

```c
void td_win_toggle_maximize(td_window_t *win);
```

Maximises the window to the desktop area above the taskbar, or restores the previous rectangle when it is maximised or in full screen. Only works for windows with `TD_WIN_RESIZABLE`.

### td_win_set_fullscreen

```c
void td_win_set_fullscreen(td_window_t *win, bool on);
```

Turns full screen on or off. In full screen the window has no frame, its client area is the whole screen, and the taskbar is hidden while it is the top window. Turning it off restores the rectangle from before maximise or full screen. The window is also focused. The function itself does not check `TD_WIN_RESIZABLE`; F11 and the window menu only offer it for resizable windows.

### td_win_client

```c
td_rect_t td_win_client(const td_window_t *win);
```

Returns the client area in absolute screen coordinates: the outer rectangle minus the one-cell frame, or the whole rectangle in full screen. `win` must be an open window.

### td_win_invalidate

```c
void td_win_invalidate(td_window_t *win);
```

Requests a redraw. The next frame recomposes the whole screen, so the argument is not used; it is the same as `td_wm_invalidate()`. Call it after changing state that `on_draw` shows. Widget setters already do this.

### td_win_is_open

```c
bool td_win_is_open(const td_window_t *win);
```

True when `win` points into the window pool and the slot is in use. `NULL` is allowed. See the note on reused slots under [td_window_t](#td_window_t).

## Callbacks

### on_draw

```c
void (*on_draw)(td_window_t *win, int client_w, int client_h);
```

Draws the client area on every frame that is composed (whenever anything on screen changed). The drawing origin and clip rectangle are already set to the client area, so (0, 0) is its top-left cell and nothing can be drawn outside it. The area has been filled with the theme's window colours (`win_fg` / `win_bg`) before the call. Widgets are drawn after `on_draw`, on top of it. Use the drawing functions from [screen.md](screen.md) (`td_text()`, `td_fill()`, `td_putc()`, ...). There is no resize callback: `client_w` and `client_h` are always the current size.

Keep it short and non-blocking: it runs inside the frame composition, on the UI task. Drawing static text here instead of creating label widgets saves widgets from the shared pool (see [widgets.md](widgets.md#the-widget-pool)).

### on_event

```c
bool (*on_event)(td_window_t *win, const td_event_t *ev);
```

Receives the events of this window that no widget consumed:

- key events (`TD_EV_KEY`) while the window has the focus; with `TD_WIN_RAW_KEYS`, every key the window manager does not handle itself;
- mouse events (`TD_EV_MOUSE`) over the client area, with coordinates relative to the client area; after a press in the client area, the drag motion and the release are delivered to the same window even outside it (coordinates may then be negative or past the edge). Wheel events go to the window under the pointer without focusing it;
- pasted text (`TD_EV_PASTE`) when no text box took it; read the text with `td_paste_text()` (see [input.md](input.md)).

Return `true` when the event was handled. For keys, returning `false` lets the window manager handle Tab (next widget) and Esc (closes a modal dialog). The return value is ignored for mouse and paste events. `TD_EV_RESIZE` and `TD_EV_TICK` events are not delivered to windows.

### on_close

```c
void (*on_close)(td_window_t *win);
```

Called just before the window is destroyed, whatever closed it (`[x]`, `td_win_close()`, `td_wm_close_all()`, a user switch). The window and its widgets are still valid during the call. Free the app's per-window memory and clear static pointers to the window and its widgets here.

### on_close_request

```c
bool (*on_close_request)(td_window_t *win);
```

Asked when the user closes the window (`[x]`, window menu "Close", Ctrl+Q, Alt+F4, Esc on a dialog) and by `td_win_request_close()`. Return `false` to keep the window open, for example to show a "Save changes?" message box and close later with `td_win_close()`. `NULL` always allows.

### on_tick

```c
void (*on_tick)(td_window_t *win);
uint32_t tick_ms;
```

Called every `tick_ms` milliseconds while the window is open, minimised or not. The timer is started in `td_win_create()` and stopped in `td_win_close()`. Ticks run from the main loop, so the real interval is at least one loop pass (`TD_LOOP_SLEEP_MS`, 5 ms by default); a timer that falls far behind skips the missed calls instead of catching up. A tick does not redraw by itself: call a widget setter or `td_win_invalidate()` when something changed.

## Popup menus

```c
typedef void (*td_menu_fn)(int item, void *user);

void td_menu_popup(int x, int y, const char *const *items, int count,
                   td_menu_fn fn, void *user);
void td_menu_close(void);
bool td_menu_is_open(void);
```

`td_menu_popup()` opens a context menu with its top-left corner near screen cell (x, y).

| Parameter | Meaning |
|---|---|
| `x`, `y` | Screen cell. The menu is moved so it stays on the screen and above the taskbar. |
| `items` | Item labels. They are copied (at most 27 bytes each), so the array may be temporary. An item `"-"` is a separator line and cannot be chosen. |
| `count` | Number of items; more than 20 are cut to 20. |
| `fn` | Called with the index of the chosen item. Not called when the menu is dismissed with Esc, F10 or a click elsewhere. |
| `user` | Passed to `fn`. |

Only one menu is open at a time: opening a popup replaces the start menu or another popup. The highlight follows the mouse and the Up / Down / Home / End keys; Enter or a left or right click chooses. The menu is closed before `fn` runs, so `fn` may open another menu or a dialog. While a menu is open it takes every key (except that F10 opens the start menu instead), and pasted text is dropped. A click outside closes the menu and then goes on to whatever is under it.

`td_menu_close()` closes the open menu without calling `fn`. `td_menu_is_open()` is true while any menu, including the start menu, is open.

```c
static void on_menu(int item, void *user)
{
    (void)user;
    if (item == 0) do_copy();
    else if (item == 2) do_delete();
}

static bool on_event(td_window_t *win, const td_event_t *ev)
{
    if (ev->type == TD_EV_MOUSE && ev->action == TD_MOUSE_PRESS && ev->button == TD_BUTTON_RIGHT) {
        static const char *const items[] = { "Copy", "-", "Delete" };
        td_rect_t c = td_win_client(win);            /* ev->x/y are client-relative */
        td_menu_popup(c.x + ev->x, c.y + ev->y, items, 3, on_menu, NULL);
        return true;
    }
    return false;
}
```

## Start menu

### td_wm_toggle_start_menu

```c
void td_wm_toggle_start_menu(void);
```

Opens the start menu at the bottom-left corner, or closes it when it is open. F10, a click on `[Start]`, and Enter or Esc while no window is focused call it. The menu lists, from the top:

1. every registered app in registration order (with its glyph for the medium and large start menu sizes),
2. a separator,
3. the entries added with `td_wm_add_start_item()`,
4. "Redraw screen" (calls `td_full_redraw()`),
5. "Exit" (calls `td_quit()`; on the ESP32 ports the board then restarts).

The menu holds at most 20 lines, so at most `17 - extra entries` apps are listed. Right-clicking the empty desktop opens the start menu at the mouse when no desktop provider handles the right-click.

### td_wm_add_start_item

```c
void td_wm_add_start_item(const char *label, void (*fn)(void));
```

Adds an entry to the start menu's lower section, above "Redraw screen". `fn` runs when it is chosen. At most 4 entries can be added; further calls, and calls with `NULL` arguments, are ignored. The `label` pointer is stored, not copied: pass a string that stays valid (a literal). There is no way to remove an entry. The session code adds "Switch user..." when the port supplies `authenticate` (see [sysinfo.md](sysinfo.md)).

## Taskbar

The taskbar is the bottom row (two rows for the large size). From the left: `[Start]`, one button per open window except dialogs (in pool order, so buttons do not move when the focus changes; buttons that do not fit are left out), and on the right the user name, the network indicator and the clock.

- Clicking a window button focuses that window, or minimises it when it is already focused. Right-clicking it opens the window menu (Maximize / Restore, Minimize, Full screen (F11), Close, as the window's flags allow). The same menu opens on a right-click on a title bar.
- The network indicator appears when the port supplies `td_sysinfo()->net` with a `status` callback. It shows "LAN", "Wi-Fi" with 1 to 3 signal bars (-60 dBm and above: 3, -72 dBm and above: 2), or "Offline". Clicking it runs `td_app_launch("Network")`. `status` is called on every frame, so it must be cheap (see [sysinfo.md](sysinfo.md#network)).
- The taskbar and the start menu stay usable while a modal dialog is open; windows opened from them are placed below the dialog.
- The taskbar is hidden while a full-screen window is on top.

### td_wm_set_user_label

```c
void td_wm_set_user_label(const char *label);
```

Sets the name shown in the taskbar tray, normally the logged-in user. Copied (at most 23 bytes). `NULL` or `""` hides it. It is not shown on the small taskbar.

### td_wm_desktop_rows

```c
int td_wm_desktop_rows(void);
```

Height of the usable desktop: screen rows minus the taskbar height (1, or 2 for the large taskbar). Maximised windows and menus use this height. The value does not change while a full-screen window hides the taskbar.

## Taskbar clock

```c
typedef struct {
    bool (*text)(char *buf, int cap);
    void (*click)(int button, int x, int y);
    bool (*parts)(char *time, int tcap, char *date, int dcap);
} td_clock_provider_t;
void td_wm_set_clock(const td_clock_provider_t *clock);
```

The window manager has no clock of its own; a clock provider fills in the text. `td_wm_set_clock()` stores the pointer (not a copy), so the provider must stay valid; `NULL` removes the clock. The built-in provider from `td_datetime_install_clock()` (see [apps.md](apps.md#date-and-time)) follows the current user's time zone and clock preferences.

| Member | Meaning |
|---|---|
| `text` | Fills `buf` (`cap` bytes, 32 in the current code) with the clock text, for example `"14:05 25-09-2026"`. Return `false`, or leave `buf` empty, to hide the clock. Required for the clock to appear at all. Called on every frame. |
| `click` | Optional. A left click on the clock calls it with `TD_BUTTON_LEFT`, a right click with `TD_BUTTON_RIGHT`, and the screen cell. With a click handler the clock also gets a hover highlight. |
| `parts` | Optional. Fills the time and the date apart (`tcap` is 16, `dcap` 24). The small taskbar then shows the time only, and the large taskbar shows the time over the date. Without `parts`, every size shows the `text` string on one row. |

## UI sizes

```c
typedef enum { TD_UI_SMALL, TD_UI_MEDIUM, TD_UI_LARGE } td_ui_size_t;
void td_wm_set_icon_size(td_ui_size_t size);
td_ui_size_t td_wm_icon_size(void);
void td_wm_set_start_menu_size(td_ui_size_t size);
td_ui_size_t td_wm_start_menu_size(void);
void td_wm_set_taskbar_size(td_ui_size_t size);
td_ui_size_t td_wm_taskbar_size(void);
const char *td_ui_size_name(td_ui_size_t size);   /* "Small", "Medium", "Large" */
```

Three independent size settings. All default to `TD_UI_MEDIUM`; values outside the enum are treated as `TD_UI_MEDIUM`. The Settings app stores them per user (see `td_settings_save()` in [apps.md](apps.md#settings)).

| Setting | Small | Medium | Large | Fallback |
|---|---|---|---|---|
| Desktop icons | One line per icon: glyph and name (21-column slots). | 4 x 3 box with the glyph, name on up to two lines (12 x 6 slots). | 8 x 5 double-framed box, one wider name line (16 x 7 slots). | When the icons do not all fit on the desktop at the chosen size, the next smaller size that fits is drawn. `td_wm_icon_size()` still returns the chosen size. |
| Start menu | Names only. | Glyph and name. | Glyph and name with a blank row per item. | When the large menu is taller than the desktop, it uses one row per item. |
| Taskbar | One row; the time only (with a `parts` clock); titles cut to 8 columns; no user name. | One row; the clock `text`; titles cut to 14 columns. | Two rows; glyph and title (18 columns); the time over the date; a line under each button (bright for the focused window, dim for others, none for minimised ones). | None. |

Changing the taskbar size changes the desktop height: open windows are clamped to it again and an open menu is closed. `td_ui_size_name()` returns `"Small"`, `"Medium"` or `"Large"` (anything unknown gives `"Medium"`).

## Themes

```c
typedef struct {
    const char *name;
    uint8_t desktop_fg, desktop_bg;
    uint8_t win_fg, win_bg;              /* window client area */
    uint8_t frame_fg, frame_active_fg;   /* borders */
    uint8_t title_fg, title_bg;          /* focused title bar */
    uint8_t title_inactive_fg, title_inactive_bg;
    uint8_t button_fg, button_bg;
    uint8_t focus_fg, focus_bg;          /* focused widget */
    uint8_t input_fg, input_bg;          /* text boxes, lists */
    uint8_t select_fg, select_bg;        /* selected list item */
    uint8_t shadow_fg, shadow_bg;
    uint8_t taskbar_fg, taskbar_bg;
    uint8_t taskbar_active_fg, taskbar_active_bg;
    uint8_t menu_fg, menu_bg, menu_select_fg, menu_select_bg;
    uint8_t accent;                      /* highlights, progress bars */
    uint8_t dim;                         /* disabled / secondary text */
    uint8_t icon_fg;                     /* desktop icons */
    uint8_t close_hover_fg, close_hover_bg; /* [x] under the mouse */
} td_theme_t;
```

Colours are xterm 256-colour palette indexes: 0 to 15 are the ANSI colours (0 black, 1 red, 2 green, 3 yellow, 4 blue, 5 magenta, 6 cyan, 7 light grey, 8 to 15 the bright versions).

| Field | Used for |
|---|---|
| `name` | Theme name shown in Settings. |
| `desktop_fg`, `desktop_bg` | Desktop background pattern (Dark: teal 24 on 234, so the pattern is clearly visible). `desktop_bg` is also the background of desktop icons. |
| `win_fg`, `win_bg` | Window client area, labels, checkboxes, frame background. |
| `frame_fg`, `frame_active_fg` | Border of unfocused / focused windows (single / double line). |
| `title_fg`, `title_bg` | Title bar of the focused window. |
| `title_inactive_fg`, `title_inactive_bg` | Title bar of other windows. |
| `button_fg`, `button_bg` | Buttons without focus. |
| `focus_fg`, `focus_bg` | Focused or hovered button, focused checkbox caption. |
| `input_fg`, `input_bg` | Text boxes and lists. |
| `select_fg`, `select_bg` | Selected list item (in a focused list), selected desktop icon label, the dragged item. |
| `shadow_fg`, `shadow_bg` | Drop shadows of windows and menus. |
| `taskbar_fg`, `taskbar_bg` | Taskbar. |
| `taskbar_active_fg`, `taskbar_active_bg` | Focused window's taskbar button, `[Start]` while the start menu is open. |
| `menu_fg`, `menu_bg`, `menu_select_fg`, `menu_select_bg` | Popup and start menus, and their highlighted item. |
| `accent` | Progress bars, the focused window's underline on the large taskbar. |
| `dim` | Secondary text, minimised windows' taskbar buttons, "Offline", the selected item of an unfocused list. |
| `icon_fg` | Desktop icons. |
| `close_hover_fg`, `close_hover_bg` | `[x]` under the mouse. |

### Theme functions

```c
const td_theme_t *td_theme(void);
int td_theme_count(void);
const td_theme_t *td_theme_get(int index);
void td_theme_set(int index);
int td_theme_index(void);
```

| Function | Description |
|---|---|
| `td_theme()` | The active theme. Never `NULL`. Read it in `on_draw` rather than caching it, so a theme change shows at once. |
| `td_theme_count()` | Number of built-in themes (2). |
| `td_theme_get(index)` | Built-in theme 0 (`TD_THEME_CLASSIC`) or 1 (`TD_THEME_DARK`); `NULL` for other indexes. `TD_THEME_DEFAULT` (Dark) is active until a user's settings choose another. |
| `td_theme_set(index)` | Activates a built-in theme and redraws. Invalid indexes are ignored. Themes are compiled in; there is no call to add one. |
| `td_theme_index()` | Index of the active theme. |

## Desktop

### Background pattern

```c
void td_desktop_set_pattern(uint32_t ch);
uint32_t td_desktop_pattern(void);
```

The character (Unicode code point) that fills the desktop, in `desktop_fg` on `desktop_bg`. The default is U+2591 (light shade). 0 is stored as a space. The Settings app offers U+2591, U+2592, U+2593, U+00B7 and a space. In ASCII mode, characters are replaced by their ASCII fallback when drawn (see [screen.md](screen.md)).

### Desktop icons

```c
void td_desktop_set_icons(bool on);
bool td_desktop_icons(void);
```

Shows or hides all desktop icons (default: shown). There is one icon per registered app, in registration order, followed by the desktop provider's items. Icons are laid out in columns from the top-left corner; windows cover them.

- A click selects an icon, a double-click opens it (the app's `launch`, or the provider's `open`).
- While no window is focused, the arrow keys move the selection and Enter opens the selected icon.
- A right-click on an app icon shows an "Open" menu. A right-click on a provider item or on the empty desktop goes to the provider's `context` callback; without one, a right-click on the empty desktop opens the start menu at the mouse.
- An icon's glyph is the app's `icon` (two cells); `NULL` shows the first letter of the name.

### Desktop provider

```c
typedef struct {
    int (*count)(void *user);
    const char *(*label)(int index, void *user);
    const char *(*icon)(int index, void *user);      /* two cells, or NULL */
    int (*icon_fg)(int index, void *user);           /* glyph colour, -1: the theme's */
    void (*open)(int index, void *user);             /* double-click / Enter */
    void (*context)(int index, int x, int y, void *user);
    bool (*drag)(int index, td_drag_item_t *item, void *user);
    void (*drop)(int index, const td_drag_item_t *item, void *user);
    void *user;
} td_desktop_provider_t;

void td_desktop_set_provider(const td_desktop_provider_t *provider);
```

Adds icons after the app icons, for example the files in the user's Desktop folder (the built-in `apps/desktop.c` is such a provider, see [apps.md](apps.md#files-and-desktop-folder)). Index arguments count from 0 within the provider's own items. `td_desktop_set_provider()` stores the pointer, so the structure must stay valid; `NULL` removes the provider. Only one provider is active.

| Member | Meaning |
|---|---|
| `count` | Number of items. Called on every frame and for every hit test: keep it cheap. `NULL` means no items. |
| `label` | Name shown under item `index`. `NULL` (the callback or its result) shows `"?"`. The string is read at once, not kept. |
| `icon` | Two-cell glyph for item `index`, or `NULL` for the first letter of the label. |
| `icon_fg` | Optional. Colour of item `index`'s glyph (a 256-colour palette index), or -1 for the theme's `icon_fg`. Not used while the icon is hovered or selected (the highlight colours win). The Desktop folder uses it for the green `#!` of `.tdsh` scripts. |
| `open` | Double-click or Enter on item `index`. |
| `context` | Right-click on item `index`, or on the empty desktop (`index` -1), at screen cell (x, y). Usually opens a `td_menu_popup()` there. |
| `drag` | A drag starts on item `index`: fill `*item` (it is zeroed first) and return `true`, or return `false` to refuse. `NULL` makes the items not draggable. |
| `drop` | An item was released over provider item `index`, or over the empty desktop or an app icon (`index` -1). |
| `user` | Passed to every callback. |

## Drag and drop

```c
typedef struct {
    char path[TD_PATH_MAX];   /* real path */
    char name[48];
    bool is_dir;
} td_drag_item_t;

bool td_drag_active(void);
```

Files and folders can be dragged between the desktop provider and windows that implement `on_drag_start` / `on_drop`. App icons cannot be dragged.

| Field | Meaning |
|---|---|
| `path` | Real path of the file or folder (including the filesystem root, for example `"/fs/root/Desktop/a.txt"`). |
| `name` | Name shown next to the pointer while dragging. |
| `is_dir` | True for a folder. |

How a drag works:

1. A left-button press on a draggable provider item, or in the client area of a window with `on_drag_start`, arms a drag. The press is still delivered to the window and its widgets as usual.
2. When the mouse has moved 2 cells or more (horizontal plus vertical distance) with the button held, the window manager asks `on_drag_start(win, x, y, item)` with the client coordinates of the original press, or the provider's `drag`. Return `true` after filling `*item` to start the drag; `false` lets the motion go on to the window as a normal mouse drag.
3. During the drag the item's name follows the pointer; the window gets no motion events.
4. On release, the item goes to whatever is under the pointer: a window's `on_drop(win, x, y, item)` if the pointer is over its client area (client coordinates; the return value is not used), otherwise the provider's `drop`. Releasing over the taskbar or a window frame drops nothing. The window where the drag started gets no release event.

`td_drag_active()` is true while an item is being dragged, for example to show a drop highlight in `on_draw`.

The window manager only moves the description around; moving or copying the file is up to the receiver (the built-in apps use `td_move_into()`, see [apps.md](apps.md#files-and-desktop-folder)).

## Keyboard

The window manager looks at every key first. In this order:

| Key | Action |
|---|---|
| F10 (no modifiers) | Opens or closes the start menu, always, even in `TD_WIN_RAW_KEYS` windows. |
| any key while a menu is open | Goes to the menu (Up, Down, Home, End, Enter, Esc, F10); nothing else sees it. |
| F6 (no modifiers), Alt+Tab | Cycles the windows: the top window goes to the bottom. Does nothing while a modal dialog is open. |
| Ctrl+L | Resends the terminal setup and redraws the whole screen (`td_full_redraw()`). In a `TD_WIN_RAW_KEYS` window the key is then also passed to `on_event` (the Terminal forwards it to the shell). |
| Ctrl+Q, Alt+F4 | `td_win_request_close()` on the focused window, in every window. Alt+F4 only arrives where the terminal passes it through. |
| no window focused | The arrow keys and Enter move between and open desktop icons; Enter (with no icon selected) or Esc opens the start menu. |
| F11 (no modifiers) | Toggles full screen for the focused window if it has `TD_WIN_RESIZABLE`. |
| any other key, `TD_WIN_RAW_KEYS` window | Goes to `on_event`. Widgets get no keys; Tab and Esc are not handled by the window manager. |
| any other key, normal window | Offered to the focused widget, then to `on_event`. If both decline: Tab moves the focus to the next widget, Shift+Tab to the previous one, and Esc on a `TD_WIN_MODAL` window calls `td_win_request_close()`. |

Keys always go to the focused window, which is the top-most visible one (an open modal dialog). Ctrl+letter arrives as the lower-case letter with `TD_MOD_CTRL` (see [input.md](input.md)).

## Paste

Text pasted into the terminal (bracketed paste) arrives as one `TD_EV_PASTE` event and is routed like this:

1. While a menu is open, or when no window is focused, the paste is dropped.
2. In a window without `TD_WIN_RAW_KEYS`, if the focused widget is a visible text box, `td_widgets_paste()` inserts the text (the first line, printable ASCII only, up to the box's length; see [widgets.md](widgets.md#td_widgets_paste)).
3. Otherwise the event goes to the focused window's `on_event`, which reads the text with `td_paste_text()`. The Editor inserts it and the Terminal types it.

## Mouse

In summary (details in the sections above): a press on a window raises and focuses it (wheel events do not). On the title bar: `[x]` requests a close, `[-]` minimises, a double-click toggles maximise, dragging moves the window. Dragging the bottom-right corner resizes. A right-click on the title bar opens the window menu. Presses in the client area go to the widgets and then to `on_event`, and the window keeps the mouse until the button is released. While a modal dialog is open, clicks on other windows and on the desktop are ignored.

## Queries

### td_wm_windows

```c
int td_wm_windows(td_window_t **out, int max);
```

Fills `out` with the open windows, leaving out dialogs (`TD_WIN_MODAL`) and including minimised ones, and returns how many were stored (at most `max`). The order is the window pool's slot order: that is creation order until a slot is reused. The Task Manager uses it for its window list.

```c
td_window_t *wins[TD_MAX_WINDOWS];
int n = td_wm_windows(wins, TD_MAX_WINDOWS);
for (int i = 0; i < n; i++) td_logf('I', "window: %s", wins[i]->title);
```

### td_wm_window_at

```c
td_window_t *td_wm_window_at(int x, int y);
```

The top-most window (dialogs included, minimised ones left out) whose outer rectangle contains screen cell (x, y), or `NULL` for the desktop.

### td_wm_mouse_pos

```c
bool td_wm_mouse_pos(int *x, int *y);
```

Last known mouse position in screen cells. Returns `false` (and leaves `*x`, `*y` alone) before the first mouse event. Use it for hover effects in `on_draw`; the frame is recomposed when the pointer moves onto a different element.

## Used by the core

These are called by the main loop in `src/td.c` (see [core.md](core.md)). Applications normally only need `td_wm_invalidate()`.

```c
void td_wm_init(int cols, int rows);
void td_wm_set_screen_size(int cols, int rows);
void td_wm_dispatch(const td_event_t *ev);
void td_wm_compose(td_buffer_t *back);
bool td_wm_needs_redraw(void);
void td_wm_invalidate(void);
```

| Function | Description |
|---|---|
| `td_wm_init()` | Closes every window, empties the widget pool and sets the screen size. Called by `td_init()`; windows created before `td_init()` are lost. |
| `td_wm_set_screen_size()` | The terminal size changed: clamps every window to the new size. |
| `td_wm_dispatch()` | Routes one key, mouse or paste event to the menu, taskbar, windows and widgets as described above. Other event types are ignored. |
| `td_wm_compose()` | Draws the desktop, windows, taskbar and menu into the back buffer and clears the redraw flag. |
| `td_wm_needs_redraw()` | True if something changed since the last compose. |
| `td_wm_invalidate()` | Marks the screen as needing a recompose. Safe to call often; it only sets a flag. |
