# Modbus client and server

`td_modbus` is a Modbus client (master) over TCP or RTU, and a Modbus TCP server (slave) with its own data tables. Like [MQTT](mqtt.md), it is non-blocking, driven by `td_mb_poll()`, and shared by the Modbus app and the [`modbus` shell command](../shell/commands.md#modbus). The client runs one request at a time. Memory is allocated when the client or server is first used.

Header: `proto/td_modbus.h`
Source: `proto/td_modbus.c`

## Polling model

The desktop's 20 ms timer on the UI task calls `td_mb_poll()` (`apps/apps.c`), which drives both the client and the server. `td_mb_transact()` also calls `td_mb_poll()` from the calling task while it waits. All state is protected by `td_proto_lock()` (see [sockets and lock](sock.md#the-protocol-lock)). `td_mb_poll()` returns at once while neither the client nor the server exists.

## Function codes and tables

| Code | Request | Table |
|---|---|---|
| 01 | Read coils | coils |
| 02 | Read discrete inputs | discrete inputs |
| 03 | Read holding registers | holding registers |
| 04 | Read input registers | input registers |
| 05 | Write single coil | coils |
| 06 | Write single register | holding registers |
| 15 | Write multiple coils | coils |
| 16 | Write multiple registers | holding registers |

Other function codes are refused by `td_mb_build_pdu()` and answered with exception 1 (illegal function) by the server.

```c
typedef enum {
    TD_MB_COILS = 1,              /* 0x, read/write bits */
    TD_MB_DISCRETE = 2,           /* 1x, read-only bits */
    TD_MB_HOLDING = 3,            /* 4x, read/write registers */
    TD_MB_INPUT = 4,              /* 3x, read-only registers */
} td_mb_table_t;
```

Each table is named by its read function code, so `(uint8_t)table` is the function code of a read.

| Value | Names accepted by `td_mb_parse_table()` | `td_mb_table_name()` |
|---|---|---|
| `TD_MB_COILS` | `co`, `coil`, `coils`, `0x` | `coils` |
| `TD_MB_DISCRETE` | `di`, `discrete`, `inputs`, `1x` | `discrete inputs` |
| `TD_MB_HOLDING` | `hr`, `holding`, `4x` | `holding registers` |
| `TD_MB_INPUT` | `ir`, `input`, `3x` | `input registers` |

Names are case-sensitive.

```c
bool td_mb_parse_table(const char *name, td_mb_table_t *out);
const char *td_mb_table_name(td_mb_table_t t);
const char *td_mb_exception_text(int code);
```

`td_mb_exception_text()` returns the text for a Modbus exception code:

| Code | Text |
|---|---|
| 1 | `illegal function` |
| 2 | `illegal data address` |
| 3 | `illegal data value` |
| 4 | `server device failure` |
| 5 | `acknowledge (busy, try later)` |
| 6 | `server device busy` |
| 10 | `gateway path unavailable` |
| 11 | `gateway target did not respond` |
| other | `exception` |

## Limits

```c
#define TD_MB_TCP_PORT 502
#define TD_MB_MAX_READ 125        /* registers per read (bits: 2000) */
#define TD_MB_MAX_WRITE 64        /* values per write request */
#define TD_MB_TABLE_SIZE 128      /* server: entries per table */
```

| Limit | Value |
|---|---|
| Registers per read (FC 03, 04) | 1..125 |
| Bits per read (FC 01, 02) | 1..2000 in the request, but only the first 125 are returned in `td_mb_result_t` |
| Values per write (FC 15, 16) | 1..64 |
| TCP timeout (connect and answer) | 2000 ms from submit |
| RTU timeout | 1000 ms from submit |
| Idle close | A TCP link or open serial line is closed after 15 s without requests |
| Frame size | 260 bytes |
| Server clients | 3 at once; a fourth connection is closed at once |
| Server tables | 128 entries each |

## Targets

`td_mb_request_t.target` selects the transport:

| Target | Meaning |
|---|---|
| `host` | Modbus TCP to `host`, port 502. |
| `host:port`, `[v6]:port` | Modbus TCP to that port. |
| `rtu` | RTU on line 1, 9600 baud, 8N1. |
| `rtuN` | RTU on line N (one digit, 1..9), 9600 baud, 8N1. |
| `rtu[N]:baud` | That baud rate (1200..1000000), 8N1. |
| `rtu[N]:baud:8N1`, `:8E1`, `:8O1` | Frame format: 8 data bits, no/even/odd parity, 1 stop bit. |

Examples: `192.168.1.50`, `plc.local:1502`, `rtu`, `rtu2:19200`, `rtu1:9600:8E1`.

Gotchas:

- The frame format can only follow a baud rate (`rtu:8E1` is not accepted).
- Stop bits are always 1.
- A text that starts with `rtu` but does not match the syntax (for example `rtu10` or `rtufoo`) is treated as a TCP host name.
- Errors: `Bad baud rate in :<text>`, `Frame format must be 8N1, 8E1 or 8O1`, `Modbus RTU is not available on this device` (no serial lines set), `There is no RTU line N here (rtu1..rtuM)`, `Target must be host[:port] or rtu[:baud]`.

## Serial lines (RTU)

```c
typedef struct {
    int ports;                    /* how many lines (rtu1, rtu2, ...) */
    const char *(*name)(int port);   /* e.g. "RS485-1 (UART1: TX16 RX17 DE18)" */
    bool (*open)(int port, uint32_t baud, char parity, int stop_bits, char *err, size_t cap);
    int (*write)(const uint8_t *buf, int len);    /* bytes written, -1 error */
    int (*read)(uint8_t *buf, int cap);           /* non-blocking */
    void (*close)(void);
} td_mb_serial_t;

void td_mb_set_serial(const td_mb_serial_t *serial);
const td_mb_serial_t *td_mb_serial(void);
```

A port provides its serial lines through this table. Lines are numbered from 1, and only one is open at a time.

| Member | Contract |
|---|---|
| `ports` | Number of lines. |
| `name(port)` | A label for line `port`, shown in the `modbus` usage text. |
| `open(port, baud, parity, stop_bits, err, cap)` | Open line `port` with `parity` `'N'`, `'E'` or `'O'` and `stop_bits` (td_modbus passes 1). Return `false` with a message in `err` on failure. |
| `write(buf, len)` | Write bytes; return the number written (fewer is fine, the rest is sent on the next poll) or -1. |
| `read(buf, cap)` | Non-blocking read; return the bytes read, 0 if none, or -1. |
| `close()` | Close the open line. |

`td_mb_set_serial()` stores the pointer; the table must stay valid (make it `static const`). Call it once at start-up, before any request; it is not locked. `NULL` means no RTU. `td_mb_serial()` returns the table set, or `NULL`.

The callbacks run with `td_proto_lock()` held, on whichever task called `td_mb_submit()` or `td_mb_poll()`. They must not block and must not call `td_mb_*` functions.

Before each RTU request, stale bytes are drained with `read()`. The line is reopened when the line, baud rate or parity changes, and closed after 15 s idle or when a TCP request is made.

### The boards' lines

| Port | `td_mb_serial()` | Lines |
|---|---|---|
| ESP32-C6, ESP32 (`ports/esp32c6/main/rs485.c`) | the configured lines, or `NULL` | From the [board configuration](../guide/board-config.md): line N exists when `rs485.N.uart`, `.tx`, `.rx` and `.de` are all set. Named from them, e.g. `RS485-1 (UART1: TX16 RX17 DE18)`. |
| Windows, Linux | not set | none |

On the ESP ports, each line runs its UART in RS-485 half-duplex mode (the UART drives DE through its RTS pin). A UART driver is installed only while its line is open; a closed line holds DE low so it never drives its bus. Because the driver is released after 15 s idle, `hwtest rs485` can use the pins again. If `hwtest` holds the UART, `open` fails with `...: <esp error> (in use by hwtest?)`.

## Client

### td_mb_request_t

```c
typedef struct {
    char target[64];              /* "host[:port]" or "rtu[N][:baud[:8N1|8E1|8O1]]" */
    uint8_t unit;                 /* slave / unit id (0..247; TCP often 1 or 255) */
    uint8_t fc;                   /* function code */
    uint16_t addr;                /* 0-based */
    uint16_t count;               /* reads; writes use nvalues */
    uint16_t nvalues;
    uint16_t values[TD_MB_MAX_WRITE];
} td_mb_request_t;
```

| Field | Meaning |
|---|---|
| `target` | See [targets](#targets). |
| `unit` | Unit (slave) id. For RTU, the answer must come from the same id. |
| `fc` | Function code 1, 2, 3, 4, 5, 6, 15 or 16. |
| `addr` | First address, 0-based (register 40001 is holding address 0). |
| `count` | Number of values to read (FC 1 to 4). |
| `nvalues`, `values` | Values to write. FC 5 and 6 need exactly 1; FC 15 and 16 take 1..64. For coils, any non-zero value is ON. |

### td_mb_result_t

```c
typedef struct {
    int status;                   /* 0 ok, >0 Modbus exception, <0 error */
    char text[72];                /* human-readable outcome */
    uint8_t fc;
    uint16_t addr;
    uint16_t count;               /* values read */
    uint16_t values[TD_MB_MAX_READ];   /* registers, or bits as 0/1 when count <= 125 */
    uint32_t ms;                  /* round trip */
} td_mb_result_t;
```

| `status` | `text` examples | Meaning |
|---|---|---|
| `0` | `Read 3 holding registers`, `Read 8 coils`, `Wrote 2 values` | Success. |
| `> 0` | `Exception 2: illegal data address` | The device answered with this exception code. |
| `-1` | `Connection lost`, `Connection closed by the device`, `Serial write failed`, `Serial read failed`, a connect error | I/O failure. |
| `-2` | `No connection (timeout)`, `No answer (timeout)` | Timeout. |
| `-3` | `Unexpected answer (function N)`, `Malformed answer`, `CRC error in the answer`, `Answer from another unit`, `Bad frame from the device` | The answer was not valid. |

`count` and `values` are filled only for successful reads; bit reads give one 0/1 value per bit. `ms` is the time from submit to the answer. The struct is about 330 bytes.

### td_mb_submit

```c
int td_mb_submit(const td_mb_request_t *req, char *err, size_t cap);
```

Validates and queues a request, and starts sending it. Returns a ticket (> 0), or 0 with a message in `err`:

| Message | Cause |
|---|---|
| `Bad request (check function, count and values)` | Unknown function code, count or number of values out of range. |
| Target errors | See [targets](#targets). |
| `cannot resolve <host>` | DNS failure. |
| `Busy with another request` | The client is already running a request (from the app or the shell). |
| `Not enough memory` | The client could not be allocated. |
| `Cannot open the serial port`, or the port's message | `open` failed. |
| A connect error | `td_sock_connect_start()` failed. |

For TCP, the connection is kept open while the same `target` text is used, so a series of requests to one device needs no new connect or DNS lookup. A different target closes the old link. DNS is resolved without the lock but **may block**, so avoid calling this with a new host name from the UI task.

`req` is copied.

### td_mb_result, td_mb_busy

```c
bool td_mb_result(int ticket, td_mb_result_t *out);
bool td_mb_busy(void);
```

`td_mb_result()` returns `true` and copies the result once request `ticket` has finished. It returns `false` while the request runs, and also forever if a newer request has replaced it (the client keeps only the last one), so apply your own timeout.

`td_mb_busy()` is `true` while a request is in progress.

### td_mb_transact

```c
bool td_mb_transact(const td_mb_request_t *req, td_mb_result_t *out, char *err, size_t cap);
```

Submits and waits, for callers on their own task (the shell). While the client is busy it retries every 20 ms, up to 100 times. Then it waits up to 5 s for the result, calling `td_mb_poll()` every 5 ms.

Returns `true` with the result in `out` (check `out->status`: a timeout or exception is still `true`). Returns `false` with a `td_mb_submit()` message in `err`, or with `The request was replaced by another one` when another caller's request took its place.

It sleeps with `td_proto_sleep_ms()`: never call it on the UI task.

## Server

The server answers Modbus TCP requests from its own four tables of 128 entries (FC 1 to 6, 15, 16). It answers every unit id. Tables start at zero and keep their values until the server is stopped.

```c
bool td_mb_server_start(uint16_t port, char *err, size_t cap);
void td_mb_server_stop(void);
bool td_mb_server_status(uint16_t *port, int *clients, uint32_t *requests);
int td_mb_server_get(td_mb_table_t t, uint16_t addr, uint16_t count, uint16_t *out);
int td_mb_server_set(td_mb_table_t t, uint16_t addr, uint16_t count, const uint16_t *in);
```

| Function | Behaviour |
|---|---|
| `td_mb_server_start` | Listens on `port` (0 means 502). Already running on that port: returns `true` and does nothing. Running on another port: moves the listener, keeping tables and connected clients. Returns `false` with `bind: ...`, `listen: ...` or `Not enough memory`. |
| `td_mb_server_stop` | Closes the listener and all clients and frees the tables. |
| `td_mb_server_status` | `true` while running. Any output pointer may be `NULL`. `requests` counts answered requests since start. |
| `td_mb_server_get` | Copies up to `count` entries from `addr` (bits as 0/1). Returns the number copied: fewer at the end of the table, 0 if the server is not running. |
| `td_mb_server_set` | Writes entries (bits: non-zero is 1). Also writes the read-only tables (discrete inputs, input registers), which is how the device publishes data. Returns the number written. |

Remote clients get exception 2 (illegal data address) when a request goes past entry 127, and exception 3 (illegal data value) for a bad quantity or byte count. A frame with a protocol id other than 0 or a bad length makes the server drop that client.

## Test helpers

```c
uint16_t td_mb_crc16(const uint8_t *p, int len);

typedef struct {
    uint8_t coils[TD_MB_TABLE_SIZE / 8];
    uint8_t discrete[TD_MB_TABLE_SIZE / 8];
    uint16_t holding[TD_MB_TABLE_SIZE];
    uint16_t input[TD_MB_TABLE_SIZE];
} td_mb_tables_t;

int td_mb_serve_pdu(td_mb_tables_t *t, const uint8_t *req, int len, uint8_t *resp);
int td_mb_build_pdu(const td_mb_request_t *req, uint8_t *pdu);
void td_mb_decode_pdu(const td_mb_request_t *req, const uint8_t *pdu, int len, td_mb_result_t *res);
```

Pure functions without shared state, used by `tests/test_proto.c` and internally. `td_mb_crc16()` is the Modbus RTU CRC (sent low byte first). `td_mb_serve_pdu()` answers one request PDU (function code first) from `t` and returns the response length. `td_mb_build_pdu()` returns the request PDU length or -1 for an invalid request. `td_mb_decode_pdu()` fills `status`, `text`, `count` and `values` of `res`.

## Thread safety

All functions except the test helpers and `td_mb_set_serial()` take `td_proto_lock()` and may be called from the UI task or the shell task. Do not call them with the lock held or from a serial callback. The client is shared: a request from the app and one from the shell cannot run at the same time; the second gets `Busy with another request` (the shell's `td_mb_transact()` retries for about 2 s).

## Examples

A blocking read from a shell-side task:

```c
td_mb_request_t r = { .unit = 1, .fc = 3, .addr = 0, .count = 4 };
snprintf(r.target, sizeof(r.target), "192.168.1.50");
td_mb_result_t res;
char err[80];
if (!td_mb_transact(&r, &res, err, sizeof(err))) printf("modbus: %s\n", err);
else if (res.status) printf("%s\n", res.text);
else for (int i = 0; i < res.count; i++) printf("%u: %u\n", r.addr + i, res.values[i]);
```

Non-blocking from the UI task (the app pattern):

```c
static int s_ticket;
static uint32_t s_sent;

void read_now(void)
{
    td_mb_request_t r = { .unit = 17, .fc = TD_MB_INPUT, .addr = 10, .count = 2 };
    snprintf(r.target, sizeof(r.target), "rtu1:19200:8E1");
    char err[80];
    s_ticket = td_mb_submit(&r, err, sizeof(err));
    s_sent = td_proto_millis();
}

void on_tick(void *user)   /* a td_timer; td_mb_poll() runs from the desktop's timer */
{
    td_mb_result_t res;
    if (!s_ticket) return;
    if (td_mb_result(s_ticket, &res)) { show(&res); s_ticket = 0; }
    else if (td_proto_millis() - s_sent > 5000) s_ticket = 0;      /* replaced */
}
```

Serve values to a SCADA system:

```c
char err[80];
if (td_mb_server_start(502, err, sizeof(err))) {
    uint16_t v[2] = { 215, 1 };               /* temperature x10, running */
    td_mb_server_set(TD_MB_INPUT, 0, 2, v);
}
```
