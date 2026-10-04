# Writing an app

This tutorial builds a small TinyDesk app step by step: a window with widgets, a timer tick, a start menu entry and a desktop icon. It starts from the two programs in `examples/` and ends with a complete stopwatch app that follows the RAM rules of the ESP32 port. Everything here runs on the host build too, which is the quickest way to try it.

Header: `tinydesk/td.h` (core, windows, widgets), plus `apps/td_apps.h` if you use the built-in app services
Examples: `examples/hello_window.c`, `examples/counter_app.c`, `apps/counter.c`

Reference pages: [core.md](../api/core.md) (main loop), [wm.md](../api/wm.md) (windows), [widgets.md](../api/widgets.md), [screen.md](../api/screen.md) (drawing), [apps.md](../api/apps.md) (registry and shared services), [sysinfo.md](../api/sysinfo.md) (platform services).

## 1. The smallest program

`examples/hello_window.c` opens one window with a label and a button that quits:

```c
#include "td_host_hal.h"
#include "tinydesk/td.h"

static void on_quit(td_widget_t *w, void *user)
{
    (void)w;
    (void)user;
    td_quit();
}

int main(void)
{
    const td_hal_t *hal = td_host_hal_open();
    if (!hal) return 1;
    td_init(hal);

    td_window_desc_t desc = {
        .title = "Hello",
        .rect = td_rect(-1, -1, 32, 7),     /* centred */
        .flags = TD_WIN_MOVABLE,
    };
    td_window_t *win = td_win_create(&desc);
    td_label(win, 2, 1, 0, "Hello from TinyDesk!");
    td_button(win, 10, 3, "Quit", on_quit, NULL);

    td_run();
    td_shutdown();
    td_host_hal_close();
    return 0;
}
```

What happens:

- `td_host_hal_open()` (from `ports/common/td_host_hal.h`) puts the console into raw mode and returns the host HAL. On the ESP32 the port supplies its own HAL (see [core.md](../api/core.md)).
- `td_init()` sets up the screen and the window manager. Create windows after it: `td_init()` resets the window and widget pools.
- `td_window_desc_t` describes the window. `td_rect(-1, -1, 32, 7)` is the outer frame, border included; a negative x or y centres the window. The client area is 30 x 5 cells.
- Widget positions are relative to the client area. `td_label(win, 2, 1, 0, ...)` has width 0, which means "to the right edge".
- `td_run()` runs the main loop until `td_quit()`. Everything (drawing, events, callbacks) happens inside it, on this one thread.

Build it with the host CMake project (`cmake -B build && cmake --build build`) and run `./build/hello_window` in a terminal such as Windows Terminal or xterm.

## 2. An app instead of a window

A TinyDesk app is a `launch` function in a `td_app_t`. Registering it puts it in the start menu (F10) and on the desktop as an icon. `examples/counter_app.c`:

```c
static td_widget_t *s_label;
static int s_count;

static void show(void) { td_widget_printf(s_label, "Count: %d", s_count); }

static void on_plus(td_widget_t *w, void *user) { (void)w; (void)user; s_count++; show(); }
static void on_reset(td_widget_t *w, void *user) { (void)w; (void)user; s_count = 0; show(); }

/* Called every 1000 ms while the window is open. */
static void on_tick(td_window_t *win) { (void)win; s_count++; show(); }

static void launch(void)
{
    td_window_desc_t desc = {
        .title = "Counter",
        .rect = td_rect(-1, -1, 28, 7),
        .flags = TD_WIN_MOVABLE | TD_WIN_CLOSABLE,
        .on_tick = on_tick,
        .tick_ms = 1000,
    };
    td_window_t *win = td_win_create(&desc);
    if (!win) return;
    s_label = td_label(win, 2, 1, 0, "");
    td_button(win, 2, 3, "+1", on_plus, NULL);
    td_button(win, 10, 3, "Reset", on_reset, NULL);
    show();
}

static const td_app_t counter_app = { "Counter", launch, "+1" };
```

and in `main()`, after `td_init()`:

```c
td_app_register(&counter_app);   /* appears in the start menu (F10) */
```

Points to note:

- `td_win_create()` returns `NULL` when the window pool (`TD_MAX_WINDOWS`, 12) is full. Always check it.
- `on_tick` with `tick_ms` gives the window a repeating timer that starts and stops with the window. See [on_tick](../api/wm.md#on_tick).
- `td_widget_printf()` only changes (and redraws) the label when the text differs, so it is cheap to call on every tick.
- The `td_app_t` is stored by pointer, so it is `static const`. Its third field is the icon: two display cells, shown on the desktop icon, in the start menu and on the large taskbar.
- This version has a flaw: launching it twice opens two windows sharing one `s_label`. The built-in `apps/counter.c` fixes that by remembering its window, which the next step does too.

## 3. One window per app

Keep a pointer to the open window, focus it instead of opening a second one, and clear the pointer in `on_close`:

```c
static td_window_t *s_win;

static void on_close(td_window_t *win)
{
    (void)win;
    s_win = NULL;
}

static void launch(void)
{
    if (td_win_is_open(s_win)) {
        td_win_focus(s_win);
        return;
    }
    td_window_desc_t d = { /* ... */ .on_close = on_close };
    s_win = td_win_create(&d);
    if (!s_win) return;
    /* ... widgets ... */
}
```

Clearing the pointer matters: window slots are reused, and a stale pointer to a slot that now holds another window would pass `td_win_is_open()`.

## RAM rules on the ESP32

The ESP32-C6 has no PSRAM. Its internal RAM is shared with Wi-Fi, TinyDesk Shell and the SSH server, so the C6 build shrinks tinydesk's pools (`ports/esp_idf/components/tinydesk/CMakeLists.txt`): 96 widgets for all windows together (`TD_MAX_WIDGETS`, about 144 bytes each), 48-byte widget texts (`TD_TEXT_MAX`), an 80 x 25 screen. The built-in apps follow these rules, and yours should too:

1. **Allocate state while the window is open.** Put everything the window needs in one structure, `malloc` it in `launch` and `free` it in `on_close`. A closed app should cost only a few static pointers. Files, the Editor, MQTT and the Task Manager all do this.
2. **Keep the widget count small.** Widgets come from one pool shared by every open window. Draw text that never changes (captions, column headings, hints) in `on_draw` with `td_text()` instead of creating label widgets, and use widgets only for what the user interacts with or what changes. A message box also takes widgets from the pool (one per line and button).
3. **Handle `NULL`.** When the pool is full, widget constructors return `NULL`. All setters accept `NULL`, so the window still works, just with parts missing; do not dereference widget pointers yourself without a check.
4. **Keep stack use low in callbacks.** Callbacks run on the UI task (5 KB stack on the C6). Put large buffers in the allocated state, not in local arrays.
5. **Never block.** `on_draw`, `on_tick` and widget callbacks run on the UI loop. Slow work belongs in another task or in a non-blocking API polled from `on_tick` (as the Network, MQTT and Software Update apps do).
6. **Use a sensible tick.** A tick timer uses one of 16 shared timers (`TD_MAX_TIMERS`). Tick only as fast as the display needs to change; 100 to 1000 ms is typical.

## 4. The complete example: a stopwatch

The stopwatch shows the elapsed time with tenths, has Start/Stop and Reset buttons, and demonstrates everything above: state allocated while open and passed through `user`, static text drawn in `on_draw`, three widgets, a 100 ms tick, and registration with a desktop icon.

```c
/*
 * stopwatch.c - a TinyDesk app: state allocated while the window is open,
 * static text drawn in on_draw, three widgets and a 100 ms tick.
 */
#include <stdlib.h>

#include "td_host_hal.h"
#include "tinydesk/td.h"

/* Everything the window needs; allocated in launch(), freed in on_close(). */
typedef struct {
    bool running;
    uint32_t started_ms;      /* td_millis() when started */
    uint32_t elapsed_ms;      /* time counted before the last start */
    td_widget_t *time;        /* the only dynamic text */
} stopwatch_t;

static td_window_t *s_win;    /* the open window, or NULL */

static uint32_t elapsed(const stopwatch_t *sw)
{
    return sw->elapsed_ms + (sw->running ? td_millis() - sw->started_ms : 0);
}

static void show(stopwatch_t *sw)
{
    uint32_t t = elapsed(sw) / 100;   /* tenths of a second */
    td_widget_printf(sw->time, "%02u:%02u.%u", (unsigned)(t / 600), (unsigned)(t / 10 % 60),
                     (unsigned)(t % 10));
}

static void on_start(td_widget_t *w, void *user)
{
    stopwatch_t *sw = user;
    if (sw->running) {
        sw->elapsed_ms = elapsed(sw);
        sw->running = false;
    } else {
        sw->started_ms = td_millis();
        sw->running = true;
    }
    td_widget_set_text(w, sw->running ? "Stop" : "Start");
    show(sw);
}

static void on_reset(td_widget_t *w, void *user)
{
    (void)w;
    stopwatch_t *sw = user;
    sw->elapsed_ms = 0;
    sw->started_ms = td_millis();
    show(sw);
}

/* Static text: drawn every frame instead of spending label widgets. */
static void on_draw(td_window_t *win, int w, int h)
{
    (void)win;
    (void)w;
    const td_theme_t *t = td_theme();
    td_text(2, 1, "Elapsed:", t->win_fg, t->win_bg, 0);
    td_text(2, h - 1, "Space or Enter presses a button", t->dim, t->win_bg, 0);
}

/* Every 100 ms while the window is open. td_widget_printf() only redraws
 * when the text changed, so a stopped watch costs nothing. */
static void on_tick(td_window_t *win)
{
    show(win->user);
}

static void on_close(td_window_t *win)
{
    free(win->user);
    s_win = NULL;
}

static void launch(void)
{
    if (td_win_is_open(s_win)) {
        td_win_focus(s_win);
        return;
    }
    stopwatch_t *sw = calloc(1, sizeof(*sw));
    if (!sw) {
        td_msgbox("Stopwatch", "Not enough memory.", "OK", NULL, NULL);
        return;
    }
    td_window_desc_t d = {
        .title = "Stopwatch",
        .rect = td_rect(-1, -1, 38, 8),
        .flags = TD_WIN_MOVABLE | TD_WIN_CLOSABLE,
        .on_draw = on_draw,
        .on_close = on_close,
        .on_tick = on_tick,
        .tick_ms = 100,
        .user = sw,
    };
    s_win = td_win_create(&d);
    if (!s_win) {
        free(sw);                     /* on_close is not called for a window never opened */
        return;
    }
    sw->time = td_label(s_win, 11, 1, 0, "");
    td_button(s_win, 2, 3, "Start", on_start, sw);
    td_button(s_win, 12, 3, "Reset", on_reset, sw);
    show(sw);
}

static const td_app_t s_app = { "Stopwatch", launch, "SW" };

void stopwatch_register(void) { td_app_register(&s_app); }

int main(void)
{
    const td_hal_t *hal = td_host_hal_open();
    if (!hal) return 1;
    td_init(hal);
    stopwatch_register();   /* start menu entry and desktop icon */
    launch();
    td_run();               /* start menu > Exit to quit */
    td_shutdown();
    td_host_hal_close();
    return 0;
}
```

How the pieces fit:

- **State.** `launch` allocates a `stopwatch_t` and passes it as the window's `user` and as the buttons' `user`. `on_tick` gets it back from `win->user`. `on_close` frees it, whatever closed the window (`[x]`, Ctrl+Q, a user switch). If `td_win_create()` fails, `on_close` never runs, so `launch` frees the state itself.
- **Widgets.** Only three: the time label (it changes), and the two buttons. "Elapsed:" and the hint are drawn by `on_draw`, which runs on every frame with the origin at the client area's top-left corner. `h - 1` is the last client row. The hint uses the theme's `dim` colour, read from `td_theme()` each frame so a theme change applies at once.
- **Button captions.** `td_widget_set_text()` on a button recomputes its width ("[ Stop ]" is one cell narrower than "[ Start ]"); the Reset button is placed far enough right for the wider caption.
- **Timing.** The tick only refreshes the display; the time itself comes from `td_millis()`, so a late tick does not make the stopwatch slow.
- **Keyboard.** Tab moves between the buttons, Space or Enter presses the focused one, Ctrl+Q or `[x]` closes the window. These come from the window manager and the widgets; the app has no `on_event`.
- **Icon.** `"SW"` is the two-cell glyph on the desktop icon and in the start menu. Windows opened from the start menu or the desktop icon also get it on the large taskbar. The window opened directly from `main()` does not, because it was not launched through the registry; set `td_window_desc_t.icon` to give a window its own glyph in every case.

To build it as a standalone host program, save it as `examples/stopwatch.c` and add `stopwatch` to the `foreach(ex hello_window counter_app)` list in the top-level `CMakeLists.txt`; the examples link `tinydesk_core` and `tinydesk_hal`.

## 5. Adding the app to the full desktop

In the full desktop (host `tinydesk` executable, ESP32 firmware) the port owns `main()`. Drop the `main()` function and the `td_host_hal.h` include from the app, then:

1. Add the source file to the build: to the `tinydesk_apps` library in the top-level `CMakeLists.txt` for the host, and to the `SRCS` list in `ports/esp_idf/components/tinydesk/CMakeLists.txt` for the ESP32 ports (all three use this component).
2. Declare `void stopwatch_register(void);` in a header of your own.
3. Call it after `td_apps_register_all()`: in `td_host_setup()` in `ports/common/host_main.c` for the hosts, and in `ui_task()` in `ports/esp_idf/app/main.c` for the ESP32 ports. Apps appear in the start menu and on the desktop in registration order.

`td_apps_register_all()` registers 13 apps; `TD_MAX_APPS` is 16, so three more fit without raising it (`td_app_register()` returns -1 when the table is full). The start menu shows at most 17 apps minus its extra entries (such as "Switch user...").

Inside the full desktop an app can also use the shared services from [apps.md](../api/apps.md): `td_logf()` to write to the Log Viewer, `td_clipboard_set()` / `td_clipboard_get()`, `td_editor_open()` and `td_files_open()`, the current user's folders (`td_home_dir()`, `td_desktop_dir()`), and the platform services in `td_sysinfo()` ([sysinfo.md](../api/sysinfo.md)), whose members must always be checked for `NULL`.

## 6. Going further

- **Asking before closing.** Set `on_close_request` and return `false` to keep the window, for example to show a `td_msgbox()` about unsaved changes and call `td_win_close()` from its callback. See [wm.md](../api/wm.md#on_close_request) and the message box example in [widgets.md](../api/widgets.md#td_msgbox).
- **Your own input handling.** `on_event` receives keys, mouse events (client coordinates) and pasted text that no widget consumed. Add `TD_WIN_RAW_KEYS` to get every key, including Tab and Esc, as the Terminal and Editor do. See [Keyboard](../api/wm.md#keyboard).
- **Lists.** A `td_list()` stores no items; its `get_item` callback returns the text of each visible row, which keeps large lists cheap. Pair it with a `td_scrollbar()`. See [td_list](../api/widgets.md#td_list).
- **Context menus.** `td_menu_popup()` opens a right-click menu with up to 20 items. See [Popup menus](../api/wm.md#popup-menus).
- **Drag and drop.** `on_drag_start` and `on_drop` let windows exchange files with the desktop and with Files. See [Drag and drop](../api/wm.md#drag-and-drop).
- **Resizable windows.** With `TD_WIN_RESIZABLE`, place widgets with negative positions and sizes (for example `td_rect(0, 1, -1, -1)` for a list and `td_scrollbar(win, -1, 1, -1, list)` beside it) so they follow the window. `on_draw` always receives the current client size. See [Positions and sizes](../api/widgets.md#positions-and-sizes).
