# MQTT client

`td_mqtt` is a small MQTT 3.1.1 client over TCP or [TLS](tls.md), with QoS 0 and 1. There is one connection per device, shared by the MQTT app and the [`mqtt` shell command](../shell/commands.md#mqtt): a broker connected from the shell shows up in the app, and the other way round. Nothing blocks except `td_mqtt_connect()`; the connection is driven by `td_mqtt_poll()`.

Header: `proto/td_mqtt.h`
Sources: `proto/td_mqtt.c` (client), `proto/td_mqtt_conf.c` (config file, broker URLs, template)

## Polling model

The desktop starts a 20 ms repeating timer on the UI task (`td_proto_service_start()` in `apps/apps.c`) that calls `td_mqtt_poll()` and `td_mb_poll()`. There is no extra task. Shell commands that wait (`mqtt connect`, `mqtt listen`) also call `td_mqtt_poll()` themselves from the shell task; the [protocol lock](sock.md#the-protocol-lock) keeps the two apart.

`td_mqtt_poll()` returns at once when no connection exists, so the timer costs nothing while MQTT is unused.

A port without the desktop's apps must call `td_mqtt_poll()` often (every 10 to 50 ms) itself.

## Limits

```c
#define TD_MQTT_DEFAULT_PORT 1883
#define TD_MQTT_TLS_PORT 8883
#define TD_MQTT_PATH_MAX 160      /* certificate file paths (real paths) */
#define TD_MQTT_CERT_MAX 16384    /* largest certificate / key file read */
#define TD_MQTT_TOPIC_MAX 64      /* longer topics are refused (sub/pub) */
#define TD_MQTT_PAYLOAD_KEEP 120  /* bytes of each message kept in the log */
#define TD_MQTT_LOG 20            /* messages kept */
#define TD_MQTT_SUBS 8            /* subscriptions */
```

Other limits inside `td_mqtt.c`:

| Limit | Value | Effect |
|---|---|---|
| Receive buffer | 1024 bytes | An incoming packet larger than this is skipped: not logged and, for QoS 1, not acknowledged. |
| Transmit buffer | 1024 bytes | A publish that does not fit with what is still queued fails with `-2`. |
| Connect timeout | 10 s | For each of TCP connect, TLS handshake and CONNACK. |
| Retry delay | 5 s | Between reconnect attempts (`auto_reconnect`). |
| Topics | 1..63 bytes | Longer or empty topics are refused. |
| Memory | about 7 KB | Allocated by `td_mqtt_connect()`, freed by `td_mqtt_disconnect()`. A TLS session adds its own (see [TLS memory notes](tls.md#memory-notes)). |

## Configuration

```c
typedef struct {
    char host[64];
    uint16_t port;            /* 0: 1883, or 8883 with TLS */
    char client_id[32];       /* "" = tinydesk-<random> */
    char user[32];            /* "" = no login */
    char pass[64];
    uint16_t keepalive;       /* seconds; 0 = 60 */
    bool auto_reconnect;      /* retry every 5 s after a drop */
    bool persistent;          /* clean_session off: the broker keeps our session */

    bool tls;
    bool insecure;            /* do not verify the server certificate */
    char ca_file[TD_MQTT_PATH_MAX];
    char cert_file[TD_MQTT_PATH_MAX];
    char key_file[TD_MQTT_PATH_MAX];
    char key_pass[64];

    char will_topic[TD_MQTT_TOPIC_MAX];
    char will_payload[128];
    uint8_t will_qos;
    bool will_retain;

    int nsubs;
    char sub_topic[TD_MQTT_SUBS][TD_MQTT_TOPIC_MAX];
    uint8_t sub_qos[TD_MQTT_SUBS];
} td_mqtt_config_t;
```

| Field | Meaning |
|---|---|
| `host` | Broker host name or address. Required. |
| `port` | Broker port; 0 picks 1883, or 8883 when `tls` is set. |
| `client_id` | Client identifier; `""` makes `tinydesk-xxxxxxxx` (hex, from the clock and a heap address). |
| `user`, `pass` | Login. The password is only sent when `user` is set too. |
| `keepalive` | Keep-alive in seconds; 0 means 60. |
| `auto_reconnect` | After a drop, try again every 5 s. |
| `persistent` | `true` clears the clean-session flag, so the broker keeps the session. |
| `tls` | Use TLS (`mqtts`). |
| `insecure` | Do not verify the server certificate. |
| `ca_file` | CA certificate file (real path); `""` uses the system's trusted roots. |
| `cert_file`, `key_file` | Client certificate and key (real paths); both or neither. |
| `key_pass` | Password of an encrypted key. |
| `will_topic`, `will_payload` | Last will; sent by the broker if the device disappears. `""` topic: no will. |
| `will_qos` | 0 or 1 (larger values are sent as 1). |
| `will_retain` | Retain flag of the will. |
| `nsubs`, `sub_topic`, `sub_qos` | Subscriptions made on connect (up to 8). QoS above 1 becomes 1. |

The struct is about 1.7 KB; allocate it on the heap on the ESP32 rather than on a task stack. It holds passwords: clear it with `memset()` when done.

### td_mqtt_parse_broker

```c
bool td_mqtt_parse_broker(const char *text, td_mqtt_config_t *cfg);
```

Parses a broker text into `cfg->host`, `cfg->port` and `cfg->tls`. Other fields are left alone.

| Text | `tls` | `port` |
|---|---|---|
| `host`, `host:port`, `[v6]:port` | unchanged | the port, or 0 |
| `mqtt://host[:port]`, `tcp://host[:port]` | `false` | the port, or 0 |
| `mqtts://host[:port]`, `ssl://host[:port]`, `tls://host[:port]` | `true` | the port, or 0 |

Anything after a `/` following the host is ignored (`mqtt://host/`). Other schemes (`ws://` and so on) return `false`, as does a host that does not fit or a bad port.

### td_mqtt_load_config

```c
typedef bool (*td_mqtt_resolve_fn)(const char *path, char *real, size_t cap, void *ctx);

bool td_mqtt_load_config(const char *path, td_mqtt_resolve_fn resolve, void *ctx, td_mqtt_config_t *cfg,
                         char *err, size_t cap);
```

Reads a config file (format: [config files](../shell/config-files.md#mqttconf)) into `cfg`. `cfg` is cleared first, then `host` is set to `localhost`, then each line is applied in order.

| Parameter | Meaning |
|---|---|
| `path` | The file as the user wrote it, for example `~/mqtt.conf`. |
| `resolve` | Maps a user path (`~/certs/ca.crt`, `/root/x`, `certs/ca.crt`) to a real path, or returns `false` if the user may not use it. Called for `path` itself and for each `cafile`, `certfile`, `keyfile`. |
| `ctx` | Passed to `resolve` (the shell passes its session). |
| `cfg` | Output. |
| `err`, `cap` | Receives the error. |

Returns `false` with a message in `err`:

| Message | Cause |
|---|---|
| `<path>: not allowed here` | `resolve` refused the file. |
| `cannot open ...`, `... is too big (over 8192 bytes)` | From `td_read_file()`; config files are limited to 8 KB. |
| `line N (key): <reason>` | The first bad line, for example `line 4 (port): port must be 1..65535`. |
| `certfile and keyfile go together` | Only one of them is set. |

A relative certificate path inside the file is taken from the file's own folder before `resolve` is called. The file buffer is wiped before it is freed, and `cfg->pass` is cleared on failure.

The shell resolves paths with `tdsh_path_to_real()`, which applies the user's sandbox: non-root users can only name files in their own home.

### td_mqtt_config_template

```c
extern const char td_mqtt_config_template[];
```

The commented example file that `mqtt config init` and the MQTT app's **Config...** button write. Its full text is in [config files](../shell/config-files.md#the-template).

## States and status

```c
typedef enum {
    TD_MQTT_OFF,              /* not connected (see td_mqtt_status for why) */
    TD_MQTT_CONNECTING,       /* TCP connect */
    TD_MQTT_TLS_HANDSHAKE,
    TD_MQTT_WAIT_CONNACK,
    TD_MQTT_CONNECTED,
    TD_MQTT_RETRY,            /* waiting to reconnect */
} td_mqtt_state_t;
```

| State | Meaning | Next |
|---|---|---|
| `TD_MQTT_OFF` | Not connected. The status text says why (the last error), or `Not connected` when no client exists. | `td_mqtt_connect()` |
| `TD_MQTT_CONNECTING` | TCP connect in progress (10 s timeout). | `TLS_HANDSHAKE` with TLS, else `WAIT_CONNACK` |
| `TD_MQTT_TLS_HANDSHAKE` | TLS handshake in progress (10 s timeout). | `WAIT_CONNACK` |
| `TD_MQTT_WAIT_CONNACK` | CONNECT sent, waiting for the broker's answer (10 s timeout). | `CONNECTED`, or `OFF` if refused |
| `TD_MQTT_CONNECTED` | Logged in. Pings are sent after 3/4 of the keep-alive without traffic. | `RETRY` or `OFF` on a drop |
| `TD_MQTT_RETRY` | Dropped with `auto_reconnect` on; a new TCP connect starts after 5 s. | `CONNECTING` |

A failure goes to `RETRY` when `auto_reconnect` is set and to `OFF` otherwise. Some failures turn `auto_reconnect` off because retrying will not help: a CONNACK refusal (bad password, client id rejected, ...), a TLS set-up error (bad certificate or key file), and a rejected server certificate.

```c
typedef struct {
    td_mqtt_state_t state;
    char text[80];            /* "Connected to 1.2.3.4:1883", or the last error */
    char broker[72];          /* host:port given */
    uint32_t rx, tx;          /* messages received / published */
    uint32_t connected_ms;    /* since when (td_proto_millis) */
    int subs;
    bool tls;
    char security[72];        /* "TLSv1.2 TLS-ECDHE-..." once connected */
} td_mqtt_status_t;
```

| Field | Meaning |
|---|---|
| `state` | Current state. |
| `text` | `Connecting to <broker>...`, `TLS handshake with <broker>...`, `Connected to <broker>` (plus ` (TLS)`), or the last error, for example `Refused: bad user name or password` or `No answer from the broker (timeout); retrying in 5 s`. |
| `broker` | `host:port` as given (the name, not the resolved address). |
| `rx`, `tx` | Messages received and published since `td_mqtt_connect()`. |
| `connected_ms` | `td_proto_millis()` when the last CONNACK arrived. |
| `subs` | Number of remembered subscriptions. |
| `tls` | TLS is configured. |
| `security` | `td_tls_info()` text after the handshake, else `""`. |

CONNACK refusals are reported as `Refused: unsupported protocol version`, `Refused: client id rejected`, `Refused: server unavailable`, `Refused: bad user name or password`, `Refused: not authorised`, or `Refused by the broker`.

## Connection functions

### td_mqtt_connect

```c
bool td_mqtt_connect(const td_mqtt_config_t *cfg, char *err, size_t cap);
```

Starts a connection. In order, it:

1. checks that a host is given (`No broker given`) and that TLS is available when asked for (`TLS (mqtts) is not available in this build`);
2. reads `ca_file`, `cert_file` and `key_file` (up to 16 KB each) outside the lock, and checks that certificate and key come together;
3. resolves the host (may **block** for DNS);
4. under the lock, allocates the client or closes the running connection, copies `cfg`, adds `cfg`'s subscriptions to the remembered ones, fills in defaults, and starts the TCP connect.

Returns `true` once the connect has started; the result arrives later through `td_mqtt_status()`. Returns `false` with a message in `err` on the errors above, on a file error from `td_read_file()`, on a DNS error (`cannot resolve <host>`), or with `Not enough memory`.

Ownership: `cfg` is copied; the caller may clear and free it at once. The certificate files are read once and kept in memory for reconnects.

Gotchas:

- Call it from a task that may block (the shell does). From the UI task, DNS and file reads stall the desktop.
- When a client already exists, its subscriptions are kept and the new config's subscriptions are added to them; the message log, sequence numbers and counters are reset. Use `td_mqtt_disconnect()` first for a clean start.

### td_mqtt_disconnect

```c
void td_mqtt_disconnect(void);
```

Sends DISCONNECT if connected, closes the socket and TLS session, wipes and frees everything (credentials, key material, subscriptions, the log). After this `td_mqtt_status()` reports `Not connected`. Safe to call when nothing is connected.

A drop without `auto_reconnect` only moves to `TD_MQTT_OFF`; the client stays allocated (with its subscriptions and log) until `td_mqtt_disconnect()` or the next `td_mqtt_connect()`.

### td_mqtt_status

```c
void td_mqtt_status(td_mqtt_status_t *out);
```

Copies the current status. Cheap; call it as often as you redraw.

### td_mqtt_poll

```c
void td_mqtt_poll(void);
```

Drives the connection: connect and handshake steps, timeouts, keep-alive pings, sending queued bytes, and reading and handling up to 8 reads of incoming data. It takes the lock and returns quickly. See [polling model](#polling-model).

## Subscriptions

```c
int td_mqtt_subscribe(const char *topic, int qos);
int td_mqtt_unsubscribe(const char *topic);
bool td_mqtt_subscription(int i, char *topic, size_t cap, int *qos);
```

Subscriptions are remembered in a table of 8 and sent again after every reconnect.

`td_mqtt_subscribe()` adds `topic` (a filter; `+` and `#` allowed) or updates the QoS of an existing entry. QoS is clamped to 0..1. If connected, SUBSCRIBE is sent at once; otherwise it is sent after the next CONNACK.

| Return | Meaning |
|---|---|
| `0` | Remembered (and sent if connected). |
| `-1` | Topic empty or 64 bytes or longer, or no client exists (never connected, or after `td_mqtt_disconnect()`). |
| `-2` | The table is full (8 subscriptions). |

`td_mqtt_unsubscribe()` removes a topic (exact text match) and sends UNSUBSCRIBE if connected. Returns `0`, or `-1` when not subscribed or no client exists.

`td_mqtt_subscription()` copies entry `i` (0 to `subs - 1`) and its QoS (`qos` may be `NULL`). Returns `false` past the end.

If the broker refuses a subscription (SUBACK code 0x80), the status text becomes `The broker refused a subscription`; the entry stays in the table.

## Publishing

```c
int td_mqtt_publish(const char *topic, const void *payload, int len, int qos, bool retain);
```

Queues a PUBLISH and tries to send it. The topic must not contain `+` or `#`. QoS is clamped to 0..1. The message is added to the log as outgoing.

| Return | Meaning |
|---|---|
| `0` | Queued. |
| `-1` | Not connected, bad topic, `len < 0`, or the connection dropped while sending. |
| `-2` | Does not fit in the 1 KB transmit buffer with what is still queued. |

QoS 1 note: a packet identifier is sent and the broker's PUBACK is accepted, but the client does not track it and does not resend. Delivery is as reliable as the TCP connection.

`payload` is copied; it need not stay valid.

## Receiving and the message log

Incoming PUBLISH packets are stored in a ring of `TD_MQTT_LOG` (20) entries together with your own publishes. QoS 1 messages are acknowledged with PUBACK. QoS 2 messages (not requested by this client, but possible) are answered with PUBREC and PUBCOMP.

```c
typedef struct {
    uint32_t seq;             /* 1, 2, 3... per connection */
    uint32_t ms;              /* td_proto_millis() when it arrived / was sent */
    int64_t utc;              /* wall clock then (seconds since 1970), 0 if unset */
    bool outgoing;            /* our own publish */
    uint8_t qos;
    bool retain;
    uint16_t len;             /* full payload length */
    char topic[TD_MQTT_TOPIC_MAX];
    char payload[TD_MQTT_PAYLOAD_KEEP + 1];   /* NUL-terminated, cut */
} td_mqtt_msg_t;
```

| Field | Meaning |
|---|---|
| `seq` | Sequence number, from 1, reset by `td_mqtt_connect()`. |
| `ms` | Arrival or send time (`td_proto_millis()`). |
| `utc` | Wall-clock time then, or 0 when the clock was not set (before late 2023). |
| `outgoing` | `true` for your own publish. |
| `qos`, `retain` | From the packet. |
| `len` | Full payload length (capped at 65535). |
| `topic` | Topic, cut to 63 bytes. |
| `payload` | First 120 bytes of the payload, NUL-terminated. Binary payloads are copied as they are; a NUL inside ends the string early. |

```c
uint32_t td_mqtt_last_seq(void);
bool td_mqtt_message(uint32_t seq, td_mqtt_msg_t *out);
```

`td_mqtt_last_seq()` returns the newest sequence number (0: none). `td_mqtt_message()` copies message `seq` if it is still in the ring (one of the last 20), else returns `false`.

To follow new messages, remember the last number you showed. If `td_mqtt_last_seq()` becomes smaller than it, the client reconnected with `td_mqtt_connect()` and numbering restarted: start again from 0. Messages that fall out of the ring before you read them are lost.

## Test helpers

```c
int td_mqtt_encode_length(uint32_t len, uint8_t out[4]);
int td_mqtt_decode_length(const uint8_t *p, int avail, uint32_t *len);
bool td_mqtt_topic_matches(const char *filter, const char *topic);
```

Exposed for `tests/`. `td_mqtt_encode_length()` writes the MQTT variable-length encoding and returns its size (1 to 4). `td_mqtt_decode_length()` returns the bytes used, 0 if more are needed, or -1 if invalid. `td_mqtt_topic_matches()` applies `+` and `#`, including `a/#` matching `a` and the rule that wildcards at the start do not match `$` topics.

## Thread safety

Every function takes `td_proto_lock()` itself and may be called from any task: the UI task (the MQTT app and the poll timer) or the shell task. Do not call them while holding `td_proto_lock()`. `td_mqtt_parse_broker()`, `td_mqtt_load_config()` and the test helpers use no shared state and take no lock.

## Example

Connect from a shell-side task, subscribe and publish:

```c
td_mqtt_config_t *cfg = calloc(1, sizeof(*cfg));
char err[160];
td_mqtt_parse_broker("mqtts://test.mosquitto.org:8886", cfg);
cfg->auto_reconnect = true;
snprintf(cfg->will_topic, sizeof(cfg->will_topic), "devices/kitchen/status");
snprintf(cfg->will_payload, sizeof(cfg->will_payload), "offline");
cfg->will_retain = true;
bool ok = td_mqtt_connect(cfg, err, sizeof(err));   /* may block for DNS */
memset(cfg, 0, sizeof(*cfg));
free(cfg);
if (!ok) return;

td_mqtt_subscribe("devices/+/status", 1);           /* sent after CONNACK */

td_mqtt_status_t st;
do {                                               /* the UI timer polls too */
    td_mqtt_poll();
    td_mqtt_status(&st);
    td_proto_sleep_ms(20);
} while (st.state != TD_MQTT_CONNECTED && st.state != TD_MQTT_OFF);

if (st.state == TD_MQTT_CONNECTED)
    td_mqtt_publish("devices/kitchen/status", "online", 6, 1, true);
```

Show new messages in a window's timer:

```c
static uint32_t s_seen;

static void on_tick(void *user)
{
    uint32_t last = td_mqtt_last_seq();
    if (last < s_seen) s_seen = 0;                 /* reconnected */
    td_mqtt_msg_t m;
    while (s_seen < last)
        if (td_mqtt_message(++s_seen, &m) && !m.outgoing)
            add_line(m.topic, m.payload);
}
```
