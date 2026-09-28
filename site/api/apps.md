# Apps

TinyDesk ships a set of optional apps (Terminal, Files, Editor, Network, MQTT, Modbus, System Monitor, and more) and the services they share: the app registry, the desktop user session, the text clipboard, per-user settings, the taskbar clock, the Desktop folder and the log buffer. A port links the app sources it wants and registers them after `td_init()`, usually all at once with `td_apps_register_all()`.

Header: `apps/td_apps.h` (the app registry itself is in `include/tinydesk/td_wm.h`)
Sources: `apps/*.c`; registry in `src/wm.c`

Add `apps/` to the include path and `#include "td_apps.h"`; it includes `tinydesk/td.h`. Everything on this page runs on the UI task and must be called from it, except `td_log_append()` / `td_logf()` once a lock is installed.

Most apps get platform services (filesystem, network, firmware update, clock, users) through `td_sysinfo()`; a missing service shows "n/a" or a message instead of failing. See [sysinfo.md](sysinfo.md).

## App registry

Declared in `include/tinydesk/td_wm.h`.

### td_app_t

```c
typedef struct {
    const char *name;        /* shown in the start menu and under the icon */
    void (*launch)(void);    /* open (or focus) the app's window */
    const char *icon;        /* two-cell desktop icon glyph, e.g. ">_" (NULL:
                              * first letter of the name) */
} td_app_t;
```

| Field | Meaning |
|---|---|
| `name` | Start menu entry, desktop icon label and the key for `td_app_launch()`. |
| `launch` | Opens the app's window, or focuses it if it is already open. Called from the start menu, a desktop icon double-click or `td_app_launch()`. |
| `icon` | Two display cells: two ASCII characters, or one wide or two narrow Unicode characters in UTF-8 (`">_"`, `"i "`, `"\xE2\x86\x91 "`). Shown on the desktop icon, in the medium and large start menu, and on the large taskbar for windows opened while `launch` runs. `NULL` uses the first letter of the name. |

### td_app_register

```c
int td_app_register(const td_app_t *app);
```

Adds an app to the start menu and the desktop. The descriptor is stored by pointer and must stay valid for the life of the program (make it `static const`). Apps appear in registration order. Returns 0, or -1 when `app` is `NULL` or `TD_MAX_APPS` (16) apps are registered. Names are not checked for duplicates. There is no unregister call.

`td_apps_register_all()` registers 13 apps, leaving 3 slots with the default `TD_MAX_APPS`. The start menu lists at most 17 apps minus the entries added with `td_wm_add_start_item()` (see [wm.md](wm.md#start-menu)).

### td_app_count / td_app_get

```c
int td_app_count(void);
const td_app_t *td_app_get(int index);
```

The number of registered apps, and app `index` (0-based, registration order), or `NULL` when out of range.

### td_app_launch

```c
bool td_app_launch(const char *name);
```

Runs the `launch` function of the app whose name equals `name` exactly (case-sensitive). Windows created during the call get the app's icon on the taskbar. Returns `false` if no app has that name. The taskbar network indicator uses `td_app_launch("Network")` and the desktop menus use `"Terminal"` and `"Settings"`, so keep those names if you replace the apps.

```c
static void launch(void);
static const td_app_t s_app = { "Weather", launch, "~ " };

void weather_register(void) { td_app_register(&s_app); }
```

## Built-in apps

| App | Glyph | Source | What it does |
|---|---|---|---|
| Terminal | `>_` | `apps/terminal.c` | Runs the port's text program (normally TinyDesk Shell) through a `td_term_backend_t` with a VT100 emulator ([vterm.md](vterm.md)); scrollback with Shift+PgUp/PgDn and the wheel. The program keeps running while the window is closed. |
| Files | `[]` | `apps/files.c` | Browses the port's filesystem: open files in the Editor, create files and folders, rename, delete, drag and drop. Non-root users stay inside their home. |
| Editor | `¶_` | `apps/editor.c` | Text editor for one file at a time (`TD_EDITOR_MAX`, 16384 bytes, allocated while open; bigger files open read-only), with selection, undo/redo, the clipboard and Ctrl+S save. |
| Network | `((` | `apps/network.c` | Wi-Fi and Ethernet status, Wi-Fi scan / connect / forget, the Telnet remote-desktop switch and the SSH/SFTP and FTP servers, through `td_sysinfo()->net`. |
| MQTT | `MQ` | `apps/mqtt.c` | Connects to a broker, subscribes, publishes and lists messages; shares the connection with the `mqtt` shell command ([mqtt.md](mqtt.md)). |
| Modbus | `MB` | `apps/modbus.c` | Reads and writes coils and registers over Modbus TCP or RTU, optionally repeated, and switches the Modbus TCP server ([modbus.md](modbus.md)). |
| System Monitor | `▄█` | `apps/sysmon.c` | Live heap and PSRAM bars, task count, CPU clock, uptime and tinydesk's own frame and link statistics. |
| Task Manager | `▐▌` | `apps/taskmgr.c` | Lists the open windows (switch to one, end it) and, where the port can list them, the system tasks with state, priority, core, CPU share and free stack. |
| Log Viewer | `≡≡` | `apps/logview.c` | Shows the log ring buffer filled by `td_log_append()` with level colours. |
| Settings | `☼ ` | `apps/settings.c` | Theme, ASCII / UTF-8 mode, desktop pattern and icons, icon / start menu / taskbar sizes; saved per user. |
| Software Update | `↑ ` | `apps/update.c` | Shows the installed firmware and installs a new one from a URL or a file, with progress and roll-back, through `td_sysinfo()->ota`. Only root may install. |
| Counter | `+1` | `apps/counter.c` | The minimal example app: a label, two buttons, a checkbox and a one-second tick. |
| About | `i ` | `apps/about.c` | Name, version, platform, chip, SDK version, free heap and uptime. |
| Date & time | (none) | `apps/datetime.c` | Not a registered app: opened by clicking the taskbar clock or with `td_datetime_open()`. Big clock, time zone picker, automatic time, manual setting (root only), 12/24-hour and date format. |

### td_apps_register_all

```c
void td_apps_register_all(void);
```

Registers every built-in app, in the order of the table above (Terminal first, About last), then installs the taskbar clock (`td_datetime_install_clock()`), starts the MQTT / Modbus service timer (`td_proto_service_start()`) and starts the desktop session (`td_session_init()`, which also applies the user's saved settings and shows their Desktop folder). Call it once, after `td_init()` and `td_set_sysinfo()`.

### Individual register functions

```c
void td_about_register(void);
void td_sysmon_register(void);
void td_taskmgr_register(void);
void td_logview_register(void);
void td_settings_register(void);
void td_files_register(void);
void td_counter_register(void);
void td_terminal_register(void);
void td_editor_register(void);
void td_network_register(void);
void td_update_register(void);
void td_mqtt_register(void);
void td_modbus_register(void);
```

Each registers one app with `td_app_register()`. Use them instead of `td_apps_register_all()` to pick a subset or change the order. If you do, also call `td_datetime_install_clock()`, `td_session_init()` and (for MQTT or Modbus) `td_proto_service_start()` yourself. Calling a register function twice registers the app twice. The header comment of `td_update_register()` says "Open the Software Update window", but it only registers the app like the others.

## Files and Desktop folder

The Desktop folder is `~/Desktop` of the current desktop user. Its files and folders are shown as desktop icons after the app icons, through a desktop provider (see [wm.md](wm.md#desktop-provider)) implemented in `apps/desktop.c`. Double-click opens a folder in Files and a file in the Editor; right-click offers Open / Rename / Delete, and on the empty desktop New file, New folder, Terminal, Open Desktop folder, Refresh and Settings. Files and folders can be dragged onto folders, into Files, into the Editor (opens the file) and into the Terminal (types the path). Up to 24 entries are shown; names starting with `.` are hidden.

All paths on this page are real paths, which include the filesystem root from `td_sysinfo()->fs->root` (for example `/fs` on the ESP32). The shell sees the same files without that prefix.

### td_editor_open

```c
void td_editor_open(const char *path);
```

Opens the text file at the real path `path` in the Editor, or an empty unnamed file for `NULL`. If the Editor is already open with that file it is focused; if it holds another file with unsaved changes, the Editor is focused with a "Save or close this file first" note and nothing else happens; otherwise the open file is closed. Shows a message box when there is no filesystem, not enough memory for the `TD_EDITOR_MAX` buffer, or the file cannot be read. Files larger than `TD_EDITOR_MAX` open read-only. CR characters are dropped when loading.

### td_files_open

```c
void td_files_open(const char *dir);
```

Opens (or focuses) the Files app in folder `dir`. A `dir` outside the user's allowed area (`td_session_jail()`), or `NULL`, keeps the last folder, or starts at the home folder. The entry table (64 entries) is allocated while the window is open.

### td_files_changed

```c
void td_files_changed(void);
```

Tells an open Files window to re-read its folder, after you changed something on disk. Does nothing when Files is closed.

### td_files_reset

```c
void td_files_reset(void);
```

Forgets the last Files folder and closes the Files window. Called when the user changes.

### td_home_dir / td_desktop_dir

```c
const char *td_home_dir(void);
const char *td_desktop_dir(void);
```

The current user's home folder (the same as `td_session_home()`) and Desktop folder as real paths, for example `"/fs/home/bob"` and `"/fs/home/bob/Desktop"` on the ESP32. `td_desktop_dir()` is `""` until `td_desktop_folder_init()` has run with a usable filesystem. The strings belong to the library and change on a user switch.

### td_desktop_folder_init

```c
void td_desktop_folder_init(void);
```

Creates the current user's Desktop folder if it does not exist (with the parents it needs and a `Welcome.txt`), installs the desktop provider and reads the folder. Starts a 3-second timer (on the first call) that re-reads the folder, so files created from the shell appear on their own. Called by the session code at start-up and after every user switch. Does nothing without a filesystem that has `list` and `mkdir`.

### td_desktop_refresh

```c
void td_desktop_refresh(void);
```

Re-reads the Desktop folder now and redraws if anything changed. Call it after creating, renaming or deleting something on the Desktop.

### td_move_into

```c
const char *td_move_into(const char *path, const char *dir);
```

Moves the file or folder at real path `path` into the folder `dir` (real path), keeping its name, with `td_sysinfo()->fs->rename`. Returns `NULL` on success or when it is already in that folder. Otherwise returns a message to show, for example in a `td_msgbox()`: "Moving is not supported here.", "A folder cannot be moved into itself.", "The path is too long.", "Something with that name is already there." or "Move failed.". The strings are constants. Refreshes the Desktop on success; call `td_files_changed()` yourself if Files may show either folder.

### td_shell_path

```c
const char *td_shell_path(const char *path);
```

The path as the shell sees it: the filesystem root removed, so `"/fs/root/Desktop/a.txt"` becomes `"/root/Desktop/a.txt"` and `"/fs"` becomes `"/"`. A path outside the root is returned unchanged. The result points into `path` (or is the literal `"/"`); it is valid as long as `path` is.

### td_valid_name

```c
bool td_valid_name(const char *name);
```

True for a usable file or folder name: not `NULL`, not empty, not `"."` or `".."`, and without `/` or `\`. It does not check the length.

## Log

A ring buffer of log lines shown by the Log Viewer. Ports feed it from their logging system; the ESP32 port hooks `esp_log_set_vprintf()`, so every ESP-IDF log line lands here.

| Macro | Default | ESP32 builds | Meaning |
|---|---|---|---|
| `TD_LOG_LINES` | 64 | 32 | Lines kept; older ones are overwritten. |
| `TD_LOG_LINE_MAX` | 100 | 88 | Bytes per line including the NUL; longer lines are cut. |

### td_log_append

```c
void td_log_append(char level, const char *text);
```

Appends text. `level` is `'E'`, `'W'`, `'I'`, `'D'` or `'V'`, or 0 to take it from an ESP-IDF style prefix (`"W (1234) tag: ..."`), defaulting to `'I'`. The text may contain several lines or end in the middle of one; a line is finished at each `'\n'`, and the level of a line is the one given when its first character arrived. CR characters and ANSI colour sequences (ESC up to `m`) are dropped and tabs become spaces. Safe to call from any task once a lock is installed with `td_log_set_lock()`; without a lock, call it from the UI task only.

### td_logf

```c
void td_logf(char level, const char *fmt, ...);
```

`printf`-style wrapper: formats into a buffer of `TD_LOG_LINE_MAX + 2` bytes (longer output is cut), adds a `'\n'` if missing and calls `td_log_append()`.

```c
td_logf('W', "sensor %d did not answer", id);
```

### td_log_set_lock

```c
void td_log_set_lock(void (*lock)(void *ctx), void (*unlock)(void *ctx), void *ctx);
```

Installs functions that serialise access to the log buffer when several tasks write to it. They are called around every append and around every read by the Log Viewer, so they must be short and must not call `td_log_append()`. The ESP32 port uses a FreeRTOS critical section (`taskENTER_CRITICAL` / `taskEXIT_CRITICAL`). Pass `NULL` functions to remove the lock.

## Settings

Each user's settings are stored in `~/.tinydesk_settings` (through `td_sysinfo()->fs`): theme, ASCII mode, desktop pattern, icons shown, clock format, date format, clock shown, and the icon, start menu and taskbar sizes. The file format is private to `apps/settings.c`. A user without that file gets the device defaults: the first 8 bytes of the blob loaded with `td_sysinfo()->settings_load` (theme, ASCII mode, pattern, icons; written by older versions), or the built-in defaults (Dark theme, light-shade pattern, icons shown).

### td_settings_apply_saved

```c
void td_settings_apply_saved(void);
```

Loads the current user's settings as described above and applies them: `td_theme_set()`, ASCII mode (with a full redraw if it changed), `td_desktop_set_pattern()`, `td_desktop_set_icons()`, the clock preferences and the three UI sizes. Called by `td_session_init()` and `td_session_switch()`.

### td_settings_save

```c
bool td_settings_save(void);
```

Saves the current state (active theme, ASCII mode, pattern, icons, `td_clock_prefs()`, UI sizes) to the current user's `~/.tinydesk_settings`. Returns `false` when there is no filesystem with `write`, no home folder, or writing failed. The Settings app and the Date & time window call it after every change. It does not call `td_sysinfo()->settings_save`.

```c
td_theme_set(1);                       /* Dark */
td_wm_set_taskbar_size(TD_UI_LARGE);
if (!td_settings_save()) td_logf('W', "settings not saved");
```

### Clock preferences

```c
enum { TD_DATE_DMY = 0, TD_DATE_YMD = 1, TD_DATE_MDY = 2, TD_DATE_FORMATS = 3 };
typedef struct {
    uint8_t clock_12h;      /* 0: 24-hour */
    uint8_t date_format;    /* TD_DATE_* */
    uint8_t hide_clock;     /* 1: no date and time in the taskbar */
} td_clock_prefs_t;
td_clock_prefs_t *td_clock_prefs(void);
```

| Field | Meaning |
|---|---|
| `clock_12h` | 0: 24-hour (`14:05`), 1: 12-hour (`2:05 PM`). |
| `date_format` | `TD_DATE_DMY` (`25-09-2026`), `TD_DATE_YMD` (`2026-09-25`) or `TD_DATE_MDY` (`09/25/2026`). `TD_DATE_FORMATS` is the count. |
| `hide_clock` | 1 hides the date and time in the taskbar. |

`td_clock_prefs()` returns a pointer to the current user's preferences (a single static structure, never `NULL`). Changes show on the next frame (call `td_wm_invalidate()`); call `td_settings_save()` to keep them. They are replaced by `td_settings_apply_saved()` on a user switch.

## Clipboard

A text clipboard shared by the apps (the Editor's copy, cut and paste). It is emptied when the desktop user changes. It is separate from the PC's clipboard: the Editor also sends copies to the PC with `td_host_clipboard_set()` (OSC 52, see [core.md](core.md)), and text pasted in the terminal arrives as a `TD_EV_PASTE` event instead (see [wm.md](wm.md#paste)).

```c
bool td_clipboard_set(const char *text, int len);
const char *td_clipboard_get(int *len);   /* NULL when empty */
void td_clipboard_clear(void);
```

| Function | Description |
|---|---|
| `td_clipboard_set()` | Replaces the clipboard with a heap copy of `len` bytes of `text` (a NUL is added; the text may contain NUL bytes). Returns `false` if the copy could not be allocated; the old contents are then kept. `len` must be 0 or more. |
| `td_clipboard_get()` | Returns the clipboard text (NUL-terminated) and stores its length in `*len` (`len` may be `NULL`), or returns `NULL` with `*len = 0` when empty. The pointer is valid until the next `td_clipboard_set()` or `td_clipboard_clear()`. |
| `td_clipboard_clear()` | Frees the clipboard. |

## Date and time

```c
void td_datetime_open(void);
void td_datetime_install_clock(void);
void td_time_of_day(int64_t utc, char *buf, int cap);
```

| Function | Description |
|---|---|
| `td_datetime_open()` | Opens (or focuses) the Date & time window. Also opened by a left click on the taskbar clock. |
| `td_datetime_install_clock()` | Installs the built-in taskbar clock provider with `td_wm_set_clock()`. Its text follows `td_clock_prefs()` and the user's time zone (`td_sysinfo()->get_tz`), shows `"--:-- no clock"` while `time_now` fails and nothing when `hide_clock` is set. A right click opens a menu: Adjust date and time, Change time zone..., Sync time now, Settings. Called by `td_apps_register_all()`. |
| `td_time_of_day()` | Writes the time of day of the UTC moment `utc` (seconds since 1970) in the current user's time zone and clock format, with seconds (`"14:05:09"` or `"2:05:09 PM"`), into `buf` (`cap` bytes). Writes `""` when `utc <= 0` (clock not set). |

The time zone is per user (read with `get_tz`); the system clock and automatic network time are device-wide, so the Date & time window lets only root change them. See [sysinfo.md](sysinfo.md#clock-and-time-zone).

## Sessions

The desktop belongs to one user at a time, mirroring TinyDesk Shell: root sees the whole filesystem and has its home in `<root>/root`; any other user has `<root>/home/<user>` and cannot leave it. The Desktop folder, the Files app, the settings and the Terminal's shell all follow the current user. User accounts come from the port (`user_exists` and `authenticate` in [sysinfo.md](sysinfo.md#user-accounts)); without them the desktop is root's.

The user changes when someone logs in through Start > Switch user... (added when the port has `authenticate`), when a Telnet client logs in (on the ESP32 ports, `ports/esp32c6/main/hal_mux.c` calls `td_session_switch()`), and when `login` / `logout` in the Terminal change the shell's user (checked once a second through the backend's `user` callback).

### td_session_init

```c
void td_session_init(void);
```

Starts the session for the shell's current user (from the terminal backend's `user`), or root. Computes the home and jail paths, resets Files, applies the user's saved settings, sets up the Desktop folder and the taskbar user label. The first call also starts the one-second timer that follows the shell's user and adds "Switch user..." to the start menu when `td_sysinfo()->authenticate` is set. Called by `td_apps_register_all()` and again by `td_terminal_set_backend()`.

### td_session_switch

```c
void td_session_switch(const char *user, bool switch_shell);
```

Switches the desktop to `user`. Closes the menu and every window without asking (`td_wm_close_all()`), clears the Terminal screen and history, recomputes the paths, resets Files, applies the new user's settings, clears the clipboard, sets up their Desktop folder and the taskbar label, and logs the change. With `switch_shell` and a backend `set_user` callback, the shell is asked to continue as that user; otherwise the shell is sent Ctrl+L to redraw its prompt. The user must exist; authentication is the caller's job. `NULL` or `""` is ignored, and so is the current user unless `switch_shell` is set.

Message boxes that are open get their callback with -1 when the windows close.

### Session queries

```c
const char *td_session_user(void);
bool td_session_is_root(void);
const char *td_session_home(void);   /* real path, e.g. "/fs/home/bob" */
const char *td_session_jail(void);   /* the Files app cannot go above this */
```

| Function | Description |
|---|---|
| `td_session_user()` | Current user name (`"root"` at start). |
| `td_session_is_root()` | True when the user is `root`. |
| `td_session_home()` | Home folder, real path: `<root>/root` for root, `<root>/home/<user>` otherwise. Empty before `td_session_init()`. |
| `td_session_jail()` | The folder Files cannot leave: the filesystem root for root, the home folder otherwise. |

The strings are static buffers that change on a user switch; copy them if you keep them.

### td_session_real_path

```c
bool td_session_real_path(const char *path, char *real, size_t cap);
```

Turns a path the desktop user typed into a real path in `real` (`cap` bytes). `"~/x"` is relative to the user's home, `"/home/bob/x"` is taken as a shell path, anything else is relative to the home. Returns `false` when there is no filesystem, `path` is empty or contains `".."`, a non-root user's path leaves their home, or the result does not fit. The Software Update app uses it for firmware files.

```c
char real[160];
if (td_session_real_path("~/fw/tinydesk.bin", real, sizeof(real)))
    td_logf('I', "firmware at %s", real);   /* "/fs/root/fw/tinydesk.bin" for root */
```

## Terminal backend

```c
typedef struct {
    const char *name;                                   /* shown in the title */
    int (*start)(void *ctx, int cols, int rows);
    int (*read)(void *ctx, uint8_t *buf, int cap);
    int (*write)(void *ctx, const uint8_t *buf, int len);
    void (*resize)(void *ctx, int cols, int rows);
    const char *(*user)(void *ctx);
    void (*set_user)(void *ctx, const char *user);
    void *ctx;
} td_term_backend_t;
```

The program the Terminal app talks to, for example an embedded shell running in its own task. All callbacks are called from the UI loop and must not block.

| Member | Required | Meaning |
|---|---|---|
| `name` | yes | Shown in the window title, `"Terminal - <name>"`. |
| `start` | no | Start the program with a `cols` x `rows` screen if it is not running yet. Return 0 on success; any other value makes the Terminal try again the next time its window opens. Called by `td_terminal_set_backend()` and when the window opens. |
| `read` | yes | Copy up to `cap` bytes of program output into `buf` and return how many (0 or less when there is none). Called every 15 ms while the window is open and every 100 ms while it is closed, up to 16 times 512 bytes per call, so a chatty program never blocks on a full pipe. |
| `write` | yes | Keyboard input for the program (VT100 / xterm byte sequences, pasted text, dropped file paths, replies to terminal queries). Return the bytes accepted; the Terminal does not retry the rest. |
| `resize` | no | The text area changed size (called from drawing, while the window is open). |
| `user` | no | Multi-user shells: the user the program runs as. The session follows it once a second. |
| `set_user` | no | Ask the program to continue as another existing user (after `td_session_switch(user, true)`). |
| `ctx` | | Passed to every callback. |

The ports supply this: `tdsh_bridge_esp_backend()` on the ESP32 (`ports/esp32c6/main/tdsh_bridge_esp.c`) and `td_tdsh_host_backend()` on the hosts (`ports/common/tdsh_bridge_host.c`).

### td_terminal_set_backend

```c
void td_terminal_set_backend(const td_term_backend_t *backend);
```

Installs the backend and starts the program right away (so a shell's start-up script runs at boot, not when the window first opens); output is collected in the background until the window is shown. Then calls `td_session_init()`, since the desktop belongs to the shell's user. The structure is stored by pointer and must stay valid. Call after `td_init()` and before `td_run()`. `NULL` removes the backend; the Terminal window then shows a hint instead of a shell.

### td_terminal_backend

```c
const td_term_backend_t *td_terminal_backend(void);
```

The installed backend, or `NULL`.

### td_terminal_reset

```c
void td_terminal_reset(void);
```

Drains pending output and clears the Terminal screen and its scrollback, keeping the size. Used on a user switch so nothing of the previous user stays visible. Does nothing before the Terminal's emulator exists.

### td_terminal_run

```c
bool td_terminal_run(const char *command);
```

Opens the Terminal window (or brings it to the front) and types `command` followed by Enter, as if the user had typed it. Ctrl+U is sent first, so a line the user had half-typed at the prompt is discarded rather than joined to the command. The text goes to whatever runs in the Terminal: if a program is still busy, it reads it. Returns `false`, after showing a message box, when the build has no shell backend.

### Shell scripts

```c
#define TD_SCRIPT_EXT ".tdsh"
bool td_is_script(const char *name);
bool td_script_run(const char *path);
uint8_t td_script_colour(uint8_t bg);
```

| Function | Meaning |
|---|---|
| `td_is_script` | True if the file name ends in `.tdsh` (and is not just the extension). |
| `td_script_run` | Runs the script at `path` (a real path, as the Files app and the Desktop use) in the Terminal: `td_terminal_run("tdsh run \"<shell path>\"")`, with the path converted by `td_shell_path()`. Refuses, with a message, a path containing `"` or one too long for the command line. |
| `td_script_colour` | The colour for script names and icons on background `bg` (a palette index): bright green (10) on dark backgrounds, dark green (28) on light ones. |

The Desktop folder and the Files app use them for the **Run** entry at the top of a script's right-click menu and for the `#!` icon; see [Using the desktop](../guide/using.md#shell-scripts-tdsh).

## MQTT and Modbus service

```c
void td_proto_service_start(void);
```

Starts a 20 ms repeating timer on the UI loop that calls `td_mqtt_poll()` and `td_mb_poll()`, which drive the MQTT and Modbus connections (see [mqtt.md](mqtt.md) and [modbus.md](modbus.md)). No extra task is created. Only the first call has an effect. Called by `td_apps_register_all()`; call it yourself if you register the MQTT or Modbus app individually or use those clients from your own code.
