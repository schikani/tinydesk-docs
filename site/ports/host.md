# Desktop hosts (Windows, Linux)

The desktop build runs tinydesk in a console window for development and
testing, with TinyDesk Shell on its own thread and the Files app on a folder of the
host file system.

Source: `ports/windows/main.c`, `ports/posix/main.c`, `ports/common/`.

## Start-up

```c
const td_hal_t *td_host_hal_open(void);   /* raw mode; NULL if stdin/stdout is not a terminal */
void td_host_hal_close(void);             /* restore the terminal (safe to call twice) */
int td_host_main(const char *platform_name);
void td_host_setup(const td_hal_t *hal, const char *platform_name);
void td_host_use_net(const td_net_ops_t *net);
void td_host_use_users(bool (*exists)(const char *), bool (*auth)(const char *, const char *));
```

`td_host_main()` is the whole application: HAL, sysinfo (platform name,
settings file, file system rooted at `./tinydesk_fs`), the TinyDesk Shell Terminal,
all apps, then `td_run()`. `td_host_setup()` does everything except the
loop, for callers that drive `td_step()` themselves (the simulator).
`td_host_use_net()` and `td_host_use_users()` let the simulator plug in a
simulated network and test accounts; the normal desktop build has neither
(no Network app backend, and the desktop belongs to root).

## Helpers

```c
const td_fs_ops_t *td_fs_stdio(const char *root);   /* Files backend on the C library */
const td_term_backend_t *td_tdsh_host_backend(const char *fs_root, const char *hostname);
```

`td_tdsh_host_backend()` starts TinyDesk Shell on a thread the first time the
Terminal opens, with its files under `fs_root`. On Windows the unmodified
TinyDesk Shell core builds against a compatibility header that adds per-thread
`stdin`/`stdout` and `funopen()` to the C runtime.

## Differences from the boards

* No task list, PSRAM, OTA or network backend: the apps show "n/a" or
  hide those parts.
* TLS for MQTT is built when ESP-IDF's mbedTLS sources are found
  (`TD_MBEDTLS_DIR`, detected automatically); CA certificates come from the
  Windows ROOT store or the Linux system bundle.
* The screen limit is 132x50 (`td_config.h` defaults).

## Simulator

`tools/tdsim.c` runs the full host desktop against a simulated terminal and
prints text screenshots; see [Tools](../tools.md). It saves settings like the
desktop build does (`build/tinydesk_fs/root/.tinydesk_settings`).
