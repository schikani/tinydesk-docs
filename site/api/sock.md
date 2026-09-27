# Sockets, clock and lock

`td_sock` is the platform layer under the protocol library ([MQTT](mqtt.md), [Modbus](modbus.md), [TLS](tls.md)). It gives non-blocking TCP sockets, a millisecond clock, a sleep, and one process-wide lock. A single implementation covers Winsock (Windows), POSIX (Linux) and lwIP (ESP-IDF). Every function returns at once, except `td_sock_resolve()` (DNS) and `td_proto_sleep_ms()`.

Header: `proto/td_sock.h`
Source: `proto/td_sock.c`

## Types

```c
typedef intptr_t td_sock_t;
#define TD_SOCK_INVALID ((td_sock_t)-1)

typedef struct {
    uint8_t data[28];   /* a struct sockaddr_in / sockaddr_in6 */
    int len;
} td_addr_t;
```

| Name | Meaning |
|---|---|
| `td_sock_t` | A socket handle: a `SOCKET` on Windows, a file descriptor elsewhere. |
| `TD_SOCK_INVALID` | "No socket". Returned on failure; safe to pass to `td_sock_close()`. |
| `td_addr_t.data` | The raw `sockaddr_in` or `sockaddr_in6`. |
| `td_addr_t.len` | Its length in bytes. |

A `td_addr_t` is a plain value: copy it freely. Keeping one lets a client reconnect without another DNS lookup (the MQTT and Modbus clients do this).

## Error messages

Functions that take `char *err, size_t cap` write a one-line message there on failure. The format depends on the platform:

| Platform | Format | Example |
|---|---|---|
| Windows | `what (error N)` with the WSA error code | `connect (error 10061)` |
| POSIX, ESP-IDF | `what: strerror(errno)` | `connect: Connection refused` |

`err` may be `NULL` (or `cap` 0) in every `td_sock` function; the message is then dropped.

## Addresses

### td_split_host_port

```c
bool td_split_host_port(const char *text, char *host, size_t host_cap, uint16_t *port, uint16_t default_port);
```

Splits `"host"`, `"host:port"` or `"[v6]:port"` into a host and a port. No DNS is done.

| Parameter | Meaning |
|---|---|
| `text` | Input text. |
| `host`, `host_cap` | Output buffer for the host part (without brackets). |
| `port` | Output: the port, or `default_port` when the text has none. |
| `default_port` | Used when no port is given. |

Returns `false` when the text is empty, the host is empty or does not fit in `host_cap`, a `[` has no `]`, or the port is not a number in 1..65535.

Gotchas:

- A text with more than one `:` and no brackets is taken as a bare IPv6 address with no port (`fe80::1` gives host `fe80::1`, port `default_port`).
- `[v6]` must be followed by nothing or by `:port`.

### td_sock_resolve

```c
bool td_sock_resolve(const char *host, uint16_t port, td_addr_t *out, char *err, size_t cap);
```

Resolves a host name or literal address with `getaddrinfo()` and stores the address and port in `out`. When both IPv4 and IPv6 addresses exist, the first IPv4 address is used (lwIP builds often have no IPv6 route).

Returns `false` with `cannot resolve <host>`, `unsupported address` or `network unavailable` in `err`.

This call **blocks** for the DNS lookup. Do not hold `td_proto_lock()` while calling it; the MQTT and Modbus clients resolve before they take the lock.

### td_addr_text

```c
void td_addr_text(const td_addr_t *addr, char *buf, size_t cap);
```

Writes `a.b.c.d:port` (IPv4) or `[v6]:port` (IPv6) into `buf`, or `?` for another family.

## Client sockets

### td_sock_connect_start

```c
td_sock_t td_sock_connect_start(const td_addr_t *addr, char *err, size_t cap);
```

Creates a TCP socket, makes it non-blocking, sets `TCP_NODELAY` and starts `connect()`. Returns the socket, or `TD_SOCK_INVALID` with a message in `err`. The connection is usually still in progress: poll it with `td_sock_connect_poll()`.

The caller owns the returned socket and must close it with `td_sock_close()`.

### td_sock_connect_poll

```c
int td_sock_connect_poll(td_sock_t s, char *err, size_t cap);
```

Checks a connection started with `td_sock_connect_start()` without waiting (`select()` with a zero timeout).

| Return | Meaning |
|---|---|
| `1` | Connected. |
| `0` | Still connecting: call again later. |
| `-1` | Failed; message in `err` (on Windows, `connection refused` or `connect failed`). |

There is no timeout inside: the caller decides how long to wait (MQTT waits 10 s, Modbus TCP 2 s). On a failure the socket is not closed; close it yourself.

### td_sock_send

```c
int td_sock_send(td_sock_t s, const void *buf, int len);
```

Sends up to `len` bytes. Returns the number of bytes sent (possibly fewer than `len`), `0` if the socket would block, or `-1` on error. Keep the unsent rest and try again on the next poll. On POSIX `MSG_NOSIGNAL` is used, so a closed peer does not raise `SIGPIPE`.

### td_sock_recv

```c
int td_sock_recv(td_sock_t s, void *buf, int cap);
```

Receives up to `cap` bytes. Returns the number of bytes read, `0` when nothing is waiting, or `-1` when the peer closed the connection or an error occurred.

Unlike plain `recv()`, `0` means "nothing yet", not "closed".

### td_sock_close

```c
void td_sock_close(td_sock_t s);
```

Closes the socket. `TD_SOCK_INVALID` is ignored. When a [TLS session](tls.md) runs over the socket, free the session first with `td_tls_free()`.

## Server sockets

### td_sock_listen

```c
td_sock_t td_sock_listen(uint16_t port, char *err, size_t cap);
```

Opens a non-blocking IPv4 listening socket on all interfaces (`INADDR_ANY`) with `SO_REUSEADDR` and a backlog of 2. Returns `TD_SOCK_INVALID` with `bind: ...` or `listen: ...` in `err` on failure (for example when the port is in use). IPv6 is not listened on.

### td_sock_accept

```c
td_sock_t td_sock_accept(td_sock_t listener, char *peer, size_t peer_cap);
```

Accepts one waiting connection and makes it non-blocking. Returns `TD_SOCK_INVALID` when no connection is waiting. When `peer` is not `NULL`, the client's address is written there as by `td_addr_text()`. Call it from your poll function; it never waits.

## Clock and sleep

```c
uint32_t td_proto_millis(void);
void td_proto_sleep_ms(uint32_t ms);
```

`td_proto_millis()` returns a monotonic millisecond count:

| Platform | Source |
|---|---|
| ESP-IDF | `esp_timer_get_time() / 1000` (time since boot) |
| Windows | `GetTickCount64()` |
| POSIX | `clock_gettime(CLOCK_MONOTONIC)` |

The value is 32 bits wide and wraps after about 49.7 days. Compare times by unsigned subtraction (`td_proto_millis() - start >= timeout`), as the library does, never with `<` on absolute values.

`td_proto_sleep_ms()` blocks the calling task or thread. On ESP-IDF it is `vTaskDelay()`, and a request for 0 ms sleeps one tick. Use it only in code that runs on its own task (shell commands); never on the UI task.

## The protocol lock

```c
void td_proto_lock(void);
void td_proto_unlock(void);
```

One process-wide lock for all protocol state. The MQTT and Modbus state is used from two places:

- the UI task, where the desktop's 20 ms timer calls `td_mqtt_poll()` and `td_mb_poll()` (see `apps/apps.c`) and the MQTT and Modbus apps call the APIs;
- the TinyDesk Shell task (and SSH or Telnet sessions), where the `mqtt` and `modbus` [shell commands](../shell/commands.md) run.

Every public `td_mqtt_*` and `td_mb_*` function takes this lock itself. You only need it for your own state that is shared the same way.

| Platform | Implementation |
|---|---|
| ESP-IDF | A FreeRTOS mutex, created on first use. |
| Windows | A `CRITICAL_SECTION`, initialised once. |
| POSIX | A `pthread_mutex_t`. |

Gotchas:

- The lock is **not recursive**. Do not call any `td_mqtt_*` or `td_mb_*` function while you hold it, and do not call them from a `td_mb_serial_t` callback (those run with the lock held). On ESP-IDF a second take from the same task deadlocks.
- Do not block while holding it (no DNS, no file reads, no sleeps): the UI task waits for it every 20 ms.

## Example

A non-blocking connect driven from a poll function:

```c
static td_addr_t s_addr;
static td_sock_t s_sock = TD_SOCK_INVALID;
static uint32_t s_started;

bool start(const char *text, char *err, size_t cap)
{
    char host[64];
    uint16_t port;
    if (!td_split_host_port(text, host, sizeof(host), &port, 502)) {
        snprintf(err, cap, "bad address");
        return false;
    }
    if (!td_sock_resolve(host, port, &s_addr, err, cap)) return false;   /* may block */
    s_sock = td_sock_connect_start(&s_addr, err, cap);
    s_started = td_proto_millis();
    return s_sock != TD_SOCK_INVALID;
}

void poll(void)   /* e.g. from a 20 ms td_timer */
{
    char err[64];
    int r = td_sock_connect_poll(s_sock, err, sizeof(err));
    if (r == 0 && td_proto_millis() - s_started < 2000) return;   /* still connecting */
    if (r <= 0) {
        td_sock_close(s_sock);
        s_sock = TD_SOCK_INVALID;
        return;
    }
    td_sock_send(s_sock, "hello", 5);
}
```
