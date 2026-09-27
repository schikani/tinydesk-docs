# Platform services (sysinfo)

`td_sysinfo_t` is how a port tells tinydesk about the platform and hands it optional services: memory and task figures, the system clock and time zone, a filesystem, network control, firmware updates, user accounts and settings storage. The apps only reach the platform through this structure, so they build unchanged on the ESP32 and on the desktop hosts. Every member may be left `NULL` (or 0); the apps then show "n/a", hide a control or show a message.

Header: `include/tinydesk/td_sysinfo.h` (included by `tinydesk/td.h`)
Sources: `src/td.c` (storage); implementations in `ports/esp32c6/main/main.c`, `net_esp.c`, `ota_esp.c` (also used by the classic ESP32 port in `ports/esp32`), `ports/common/host_main.c` and `ports/common/td_fs_stdio.c`

## Threading

The apps call every callback from the UI task, often from `on_draw` or `on_tick`, so every callback must return quickly. Anything slow (a Wi-Fi scan, a firmware download, an SNTP sync) must be started in the background and report through a status call; the ESP32 port runs such jobs in short-lived FreeRTOS tasks. Data shared between such a worker and the callbacks must be protected by the port (`net_esp.c` and `ota_esp.c` use a mutex).

## Installing

```c
void td_set_sysinfo(const td_sysinfo_t *info);
const td_sysinfo_t *td_sysinfo(void);
```

`td_set_sysinfo()` stores the pointer, not a copy: the structure (and the ops tables it points to) must stay valid for the life of the program, so make it `static`. `NULL` resets to an empty structure. Call it before `td_init()` and before registering the apps, since `td_apps_register_all()` already reads the filesystem and settings.

`td_sysinfo()` returns the installed structure, or an empty one (all members `NULL`) when none was installed. It never returns `NULL`, so `td_sysinfo()->fs` is always safe to read; the members themselves must be checked.

```c
static td_sysinfo_t s_info;           /* static: tinydesk keeps the pointer */

static uint32_t my_free_heap(void) { return board_free_ram(); }

void port_setup(const td_hal_t *hal)
{
    s_info.platform = "My board";
    s_info.chip = "XYZ-1, 1 core";
    s_info.free_heap = my_free_heap;
    s_info.fs = td_fs_stdio("/data");   /* see td_fs_stdio below */
    td_set_sysinfo(&s_info);
    td_init(hal);
    td_apps_register_all();
}
```

## td_sysinfo_t

```c
typedef struct {
    const char *platform;      /* "ESP32-C6", "Windows host", ... */
    const char *chip;          /* e.g. "ESP32-C6 rev 0.1, 1 core" */
    const char *sdk_version;   /* e.g. ESP-IDF version */

    uint32_t (*free_heap)(void);
    uint32_t (*min_free_heap)(void);
    uint32_t (*total_heap)(void);
    uint32_t (*psram_free)(void);
    uint32_t (*psram_total)(void);
    int (*task_count)(void);
    int (*cpu_mhz)(void);
    int (*tasks)(td_task_info_t *out, int max);

    bool (*time_now)(int64_t *utc);
    bool (*time_set)(int64_t utc);
    bool (*time_auto_get)(void);
    bool (*time_auto_set)(bool on);
    bool (*time_sync)(void);

    bool (*get_tz)(long *seconds);
    bool (*set_tz)(long seconds);

    const td_net_ops_t *net;
    const td_ota_ops_t *ota;   /* NULL: no updates on this platform */

    bool (*user_exists)(const char *user);
    bool (*authenticate)(const char *user, const char *password);

    bool (*settings_load)(void *data, int len);
    bool (*settings_save)(const void *data, int len);

    const td_fs_ops_t *fs;

    const char *extra;
} td_sysinfo_t;
```

### Who implements what

| Member | ESP32-C6 / ESP32 (`ports/esp32c6/main/main.c`) | Windows / Linux / macOS host (`ports/common/host_main.c`) |
|---|---|---|
| `platform` | board name (`board_platform()`) | `"Windows host"`, `"Linux host"`, `"macOS host"` |
| `chip` | model, revision and cores from `esp_chip_info()` | `"host CPU"` |
| `sdk_version` | `"ESP-IDF v5.3.1"` style, from `esp_get_idf_version()` | `"n/a"` |
| `free_heap`, `min_free_heap`, `total_heap` | internal 8-bit RAM (`heap_caps_*`) | not set |
| `psram_free`, `psram_total` | `MALLOC_CAP_SPIRAM` (0 on the C6, which has none) | not set |
| `task_count` | `uxTaskGetNumberOfTasks()` | not set |
| `cpu_mhz` | `CONFIG_ESP_DEFAULT_CPU_FREQ_MHZ` | not set |
| `tasks` | `uxTaskGetSystemState()`, only when FreeRTOS trace facility and run-time stats are enabled | not set |
| `time_now` | `time()`, false before it is set | `time()` |
| `time_set` | `settimeofday()` | not set |
| `time_auto_get`, `time_auto_set`, `time_sync` | TinyDesk Shell's SNTP settings; sync in a short-lived task | not set |
| `get_tz`, `set_tz` | `~/.tdsh_tz` (TinyDesk Shell's `tz` file) | `~/.tdsh_tz`, else the PC's offset |
| `net` | `net_esp_ops()` (`net_esp.c`) | only through `td_host_use_net()` (the `tools/tdsim.c` simulator uses a fake one) |
| `ota` | `ota_esp_ops()` (`ota_esp.c`) | not set |
| `user_exists`, `authenticate` | TinyDesk Shell's user database | only through `td_host_use_users()` (tdsim test accounts) |
| `settings_load`, `settings_save` | NVS namespace `"tinydesk"`, key `"settings"` | file `tinydesk_settings.bin` in the working directory |
| `fs` | `td_fs_stdio("/fs")`, TinyDesk Shell's LittleFS mount point | `td_fs_stdio("<cwd>/tinydesk_fs")` |
| `extra` | `"Shell:     TinyDesk Shell <version>"` | the same with `TD_WITH_TDSH` |

### Identification

| Member | Meaning |
|---|---|
| `platform` | Platform name shown by About. |
| `chip` | Chip description shown by About. |
| `sdk_version` | SDK version shown by About. |
| `extra` | Optional extra line for About, for example the embedded shell version. |

The strings are read when About draws; they must stay valid.

### Memory and CPU

| Member | Used by | Meaning |
|---|---|---|
| `free_heap` | About, System Monitor, Task Manager | Free heap in bytes. |
| `min_free_heap` | System Monitor | Lowest free heap since boot. |
| `total_heap` | System Monitor, Task Manager | Heap size. The memory bars need both `free_heap` and a non-zero `total_heap`. |
| `psram_free`, `psram_total` | About, System Monitor, Task Manager | External RAM (PSRAM) on the heap. Leave `psram_total` `NULL` or return 0 when there is none. When `psram_total()` returns non-zero, `psram_free` must be set too: the apps call it without checking. |
| `task_count` | System Monitor | Number of tasks or threads. |
| `cpu_mhz` | System Monitor, Task Manager | CPU clock. |
| `tasks` | Task Manager | Fill up to `max` entries of `out` and return how many. See below. |

With external RAM (`psram_total` non-zero), the three heap figures must cover internal RAM only. It is the scarce part (task stacks, DMA buffers, the SSH server's start check), and the apps show internal RAM and PSRAM separately.

### td_task_info_t

```c
typedef struct {
    char name[16];
    char state;                /* 'R' running, 'r' ready, 'B' blocked, 'S' suspended, 'D' deleted */
    uint8_t priority;
    int8_t core;               /* pinned to this core, -1 any */
    uint32_t stack_free;       /* bytes of stack never used so far */
    int16_t cpu_tenths;        /* share of all cores since the previous call, in 0.1 %; -1 unknown */
} td_task_info_t;
```

| Field | Meaning |
|---|---|
| `name` | Task name, NUL-terminated (15 characters at most). |
| `state` | `'R'` running, `'r'` ready, `'B'` blocked, `'S'` suspended, `'D'` deleted. |
| `priority` | Current priority. |
| `core` | Core the task is pinned to, or -1 for any. |
| `stack_free` | Bytes of stack never used so far (the high-water mark). |
| `cpu_tenths` | Share of all cores used since the previous `tasks()` call, in tenths of a percent (0 to 1000), or -1 when unknown. The first call has no previous sample and returns -1. |

The Task Manager calls `tasks()` about once a second with `max` = 40. It computes the total CPU load as 100 % minus the share of tasks whose name starts with `"IDLE"`, so name the idle tasks that way. The ESP32 implementation allocates its previous sample on the first call, so the cost is only paid while the Task Manager is open.

### Clock and time zone

| Member | Used by | Meaning |
|---|---|---|
| `time_now` | taskbar clock, Date & time | Store the current time in seconds since 1970-01-01 UTC and return `true`; return `false` while the clock is not set (the taskbar then shows `"--:-- no clock"`). Called on every frame: keep it cheap. The ESP32 port treats times before 1700000000 (November 2023) as not set. |
| `time_set` | Date & time | Set the system clock. Optional; without it the window says the time comes from the host. The window only lets root call it, and only while automatic time is off. |
| `time_auto_get` | Date & time | Whether the clock is set automatically from the network. Its presence also decides whether the window shows the "Set time automatically" checkbox and "Sync now" button. |
| `time_auto_set` | Date & time | Turn automatic time on or off; kept across reboots. Root only in the window. |
| `time_sync` | Date & time, clock menu | Start a network time sync now and return at once: `true` if it was started, `false` if it cannot run (no network, already running). |
| `get_tz` | clock, `td_time_of_day()`, Date & time | Store the current desktop user's offset from UTC in seconds (east positive) and return `true`. Called on every frame through the clock: cache the value (both ports re-read their file at most every few seconds, and at once when `td_session_user()` changes). Without it, UTC is shown. |
| `set_tz` | Date & time zone picker | Store a new offset for the current desktop user. Any user may change their own time zone. |

The time zone is per user (`td_session_user()` and `td_session_home()` from [apps.md](apps.md#sessions) tell whose); the clock itself and automatic time are device-wide.

### User accounts

| Member | Meaning |
|---|---|
| `user_exists` | True if a user with that name exists. Asked by Start > Switch user... before the password prompt. |
| `authenticate` | True if the password is right for that user. When set, the session code adds "Switch user..." to the start menu at start-up. |

Without them the desktop always belongs to root (unless the terminal backend reports another shell user).

### Settings storage

| Member | Meaning |
|---|---|
| `settings_load` | Fill `len` bytes of `data` from storage and return `true`, or return `false` if nothing (or a blob of another size) is stored. `td_settings_apply_saved()` calls it with `len` = 8 to read the device defaults for users who have no `~/.tinydesk_settings` file yet. |
| `settings_save` | Store `len` bytes of `data`. The current apps never call it: per-user settings are written as files through `fs` (see `td_settings_save()` in [apps.md](apps.md#settings)). |

### Filesystem, network, updates

`fs`, `net` and `ota` point to the ops tables described below. Each may be `NULL`: Files and the Editor then show "No filesystem on this platform.", the Network app and the taskbar network indicator are absent or show "n/a", and Software Update says "Firmware updates are not available on this platform."

## Filesystem

```c
typedef struct {
    const char *root;   /* starting directory, e.g. "/fs" */

    int (*list)(const char *dir,
                void (*fn)(const char *name, bool is_dir, uint32_t size, void *user),
                void *user);
    int (*read)(const char *path, char *buf, int cap);
    int (*remove)(const char *path);
    int (*mkdir)(const char *path);
    int (*write)(const char *path, const char *data, int len);
    int (*rename)(const char *from, const char *to);
    int (*exists)(const char *path);
} td_fs_ops_t;
```

Minimal file access for Files, the Editor, the Desktop folder, per-user settings and the MQTT app's saved configuration. Paths are real paths: `root` followed by the path the shell sees (`"/fs" + "/root/Desktop/a.txt"`). Paths passed in are at most about 160 bytes.

| Member | Required | What it must do |
|---|---|---|
| `root` | yes | Top of the tree the apps may use, without a trailing `/`. Users' homes are `root + "/root"` and `root + "/home/<user>"`. |
| `list` | yes | Call `fn(name, is_dir, size, user)` once per entry of `dir`, not for `"."` or `".."`. Return the number of entries, or -1 when the folder cannot be read. `name` only needs to be valid during the call. |
| `read` | yes | Read up to `cap` bytes from the start of the file into `buf` (no NUL is added) and return the byte count, or -1 on error. The Editor asks for one byte more than it can hold to detect files that are too large. |
| `write` | yes | Create or replace the file with exactly `len` bytes (`len` may be 0). Return 0 on success. |
| `mkdir` | yes | Create one folder (the parent exists or the call fails). Return 0 on success. It is called on existing folders too; failing then is fine. |
| `remove` | yes | Delete a file, or a folder with everything in it. Return 0 on success. |
| `rename` | yes | Rename or move a file or folder. Return 0 on success. Should fail rather than overwrite an existing target. |
| `exists` | no | Return 1 if the path exists, else 0. Used to refuse names that are taken; without it, `rename` and `write` decide. |

The apps check `fs` and a few members (Files checks `list`, the Editor `read` and `write`), but Files and the Desktop menus then call `write`, `mkdir`, `remove` and `rename` without checking, so implement all members except `exists`. All calls are made on the UI task and should finish in milliseconds; a flash filesystem is fine.

### td_fs_stdio

Every port uses the same implementation on top of the C library and `<dirent.h>` (on the ESP32 the ESP-IDF VFS maps these calls to LittleFS).

```c
const td_fs_ops_t *td_fs_stdio(const char *root);
```

Declared in `ports/common/td_fs_stdio.h`. Returns a static table (one per program; a second call replaces the root). `root` is copied into a 128-byte buffer, so longer paths are cut. Behaviour: `remove` deletes folders recursively up to 8 levels deep; `rename` refuses to overwrite an existing target; `write` writes the whole file in one `fopen("wb")`; `mkdir` uses mode 0755 (`_mkdir` on Windows); entries whose `stat()` fails are listed as files of size 0.

## Network

```c
typedef struct {
    bool wifi_up;              /* associated and has an IP address */
    char ssid[33];
    int rssi;                  /* dBm */
    char wifi_ip[16];
    bool eth_present;          /* Ethernet hardware enabled */
    bool eth_up;
    char eth_ip[16];
    bool busy;                 /* a scan / connect / disconnect is running */
    char message[64];          /* outcome of the last operation */
} td_net_status_t;

enum { TD_SERVER_SSH = 0, TD_SERVER_FTP = 1 };

typedef struct {
    char ssid[33];
    int rssi;
    bool secure;               /* needs a password */
    bool saved;                /* credentials are stored */
} td_wifi_ap_t;
```

`td_net_status_t` fields:

| Field | Meaning |
|---|---|
| `wifi_up` | Associated with an access point and has an IP address. |
| `ssid` | Network name while connected. |
| `rssi` | Signal strength in dBm. The taskbar shows 3 bars from -60 dBm, 2 from -72 dBm, else 1. |
| `wifi_ip` | Wi-Fi address as dotted text. |
| `eth_present` | Ethernet hardware is enabled. |
| `eth_up` | Ethernet link is up with an address. |
| `eth_ip` | Ethernet address as dotted text. |
| `busy` | A scan, connect or disconnect is running. |
| `message` | Outcome of the last operation, shown by the Network app (for example "Connected to home"). |

`td_wifi_ap_t` fields: `ssid` (network name), `rssi` (dBm), `secure` (needs a password), `saved` (credentials are stored, so connecting needs no password).

### td_net_ops_t

```c
typedef struct {
    void (*status)(td_net_status_t *out);
    bool (*scan)(void);
    int (*scan_results)(td_wifi_ap_t *out, int max);
    bool (*connect)(const char *ssid, const char *password);
    bool (*disconnect)(void);
    bool (*forget)(const char *ssid);

    bool (*server_status)(int which, int *port, int *clients);
    bool (*server_set)(int which, bool on);

    bool (*telnet_enabled)(void);
    void (*telnet_enable)(bool on);
    const char *(*telnet_peer)(void);
} td_net_ops_t;
```

Network control for the Network app and the taskbar indicator. Every call returns at once; slow work runs in the background and its outcome shows up in `status()`.

| Member | Required | What it must do |
|---|---|---|
| `status` | yes | Fill `*out` (it is zeroed by the taskbar, but fill every field). Called on every frame by the taskbar and every second by the Network app: cache the figures (the ESP32 port refreshes them once a second). |
| `scan` | no | Start a Wi-Fi scan in the background. Return `true` if it started. |
| `scan_results` | no | Copy up to `max` results of the last scan (the Network app passes 24) and return how many, or -1 while the scan is still running. |
| `connect` | no | Start connecting to `ssid`. `password` `NULL` means use the saved credentials; otherwise the network and password are saved. Return `true` if the attempt started. Wi-Fi passwords come from `td_passwordbox()`, so at most `TD_TEXT_MAX - 1` characters (47 on the ESP32 builds). |
| `disconnect` | no | Start disconnecting. |
| `forget` | no | Delete a saved network. Return `false`, with an explanation in `status().message`, when the current user may not (on the ESP32 port saved networks belong to the user who added them and root's are shared). |
| `server_status` | no | For `which` = `TD_SERVER_SSH` or `TD_SERVER_FTP`: return `true` while that server runs and store its port and client count (either pointer may be `NULL`). |
| `server_set` | no | Start or stop a server. Return `true` if the request was taken; report the result in `status().message`. The ESP32 port does this on the calling (UI) task, because the SSH server checks for 96 KiB of free internal RAM when it starts. Both `server_status` and `server_set` are needed for the Network app's server buttons. |
| `telnet_enabled` | no | Whether remote desktop over Telnet is on. |
| `telnet_enable` | no | Turn remote desktop over Telnet on or off. |
| `telnet_peer` | no | Address of the connected Telnet client, or `NULL`. |

Implementation: `ports/esp32c6/main/net_esp.c` (`net_esp_ops()`), on top of TinyDesk Shell's Wi-Fi and Ethernet modules (so the Network app and TinyDesk Shell share saved networks) and `telnet.c`. Scans and connects run in a worker task with a 6 KiB stack; one job at a time. The host build has no network backend unless one is installed with `td_host_use_net()` (declared in `ports/common/td_host_hal.h`).

## Software update

```c
enum { TD_OTA_IDLE, TD_OTA_CHECKING, TD_OTA_INSTALLING, TD_OTA_DONE, TD_OTA_FAILED };

typedef struct {
    char version[32];          /* running firmware, e.g. "0.2.0" */
    char built[32];            /* "Sep 24 2026 10:12:03" */
    char sdk[32];              /* "v5.3.1" */
    char running[17];          /* slot names, e.g. "ota_0" */
    char next[17];             /* where an update goes */
    bool on_trial;             /* new version not confirmed yet: a crash rolls back */
    bool can_roll_back;        /* the other slot holds a working version */
    char other_version[32];    /* its version */
} td_ota_info_t;

typedef struct {
    int state;                 /* TD_OTA_* */
    int percent;               /* -1 while the size is unknown */
    uint32_t done, total;      /* bytes */
    uint32_t bytes_per_s;
    char new_version[32];      /* of the image being checked / installed */
    char new_built[32];
    char message[96];
} td_ota_status_t;

typedef struct {
    void (*info)(td_ota_info_t *out);
    bool (*start)(const char *source, bool check_only);
    void (*status)(td_ota_status_t *out);
    void (*cancel)(void);
    void (*restart)(void);
    bool (*roll_back)(void);   /* boot the other slot's version */
} td_ota_ops_t;
```

States:

| Value | Meaning |
|---|---|
| `TD_OTA_IDLE` | Nothing running. |
| `TD_OTA_CHECKING` | Reading and checking an image without installing it. |
| `TD_OTA_INSTALLING` | Writing an image to the other slot. |
| `TD_OTA_DONE` | Finished; after an install, a restart runs the new version. |
| `TD_OTA_FAILED` | Failed or cancelled; `message` says why. |

`td_ota_info_t` describes the installed firmware: `version`, `built` (build date and time), `sdk`, the `running` and `next` slot names, `on_trial` (the running version is new and not confirmed yet, so a crash rolls back), `can_roll_back` and the other slot's `other_version`.

`td_ota_status_t` is the progress of the current job: `state`, `percent` (-1 while the size is unknown), `done` and `total` bytes, `bytes_per_s`, the image's `new_version` and `new_built`, and a `message` for the user.

| Member | What it must do |
|---|---|
| `info` | Fill `*out` (zero what is unknown). |
| `start` | Start checking (`check_only`) or installing from `source`, an `http://` or `https://` URL or a real file path, in the background. Return `false` if a job is already running or `source` is empty. |
| `status` | Copy the current progress. Polled every 250 ms by the Software Update window. |
| `cancel` | Ask the running job to stop; the installed version stays. |
| `restart` | Restart the device (to run the new version). |
| `roll_back` | Boot the other slot's version. Return `false` if that is not possible; on success it normally does not return. |

When `ota` is set, all six members must be set; the app calls them without checking. The app only lets root start, cancel or roll back; everyone can look.

Implementation: `ports/esp32c6/main/ota_esp.c` (`ota_esp_ops()`), shared with the `ota` shell command. An update is written to the slot that is not running, checked (image format, chip, SHA-256) and made the boot slot. HTTPS is checked against the ESP-IDF certificate bundle. The new version runs on trial after the restart until `ota_esp_boot_ok()` confirms it (30 s after start-up, or on a requested restart); a crash before that makes the bootloader go back. The hosts have no `ota`.
