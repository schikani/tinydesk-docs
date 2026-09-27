# TLS client

`td_tls` runs a TLS 1.2 client session over a non-blocking [td_sock](sock.md) socket, using mbedTLS 3.x. The MQTT client uses it for `mqtts://` brokers. It verifies the server against a CA you pass in or against the system's trusted roots, and can present a client certificate.

Header: `proto/td_tls.h`
Source: `proto/td_tls.c`

## Availability

The real implementation is built when `TD_HAVE_TLS` is defined:

| Build | TLS |
|---|---|
| ESP-IDF (ESP32-C6, ESP32) | Always (the `mbedtls` component). |
| Windows, Linux hosts | When CMake finds an mbedTLS 3.x source tree: `TD_MBEDTLS_DIR`, or the mbedTLS inside `$IDF_PATH` or the usual ESP-IDF 5.3.1 install paths. CMake prints `tinydesk: MQTT over TLS with mbedTLS from ...` or `tinydesk: no mbedTLS found, MQTT over TLS disabled`. |

Without `TD_HAVE_TLS`, `td_tls_available()` returns `false`, `td_tls_start()` fails with `TLS is not available in this build`, and the other functions do nothing (`td_tls_handshake()`, `td_tls_send()` and `td_tls_recv()` return `-1`). `td_read_file()` is always available.

## Types

```c
typedef struct td_tls td_tls_t;

typedef struct {
    const char *ca;          size_t ca_len;     /* NULL: the system's roots */
    const char *cert;        size_t cert_len;   /* client certificate (optional) */
    const char *key;         size_t key_len;    /* its private key */
    const char *key_pass;                       /* for an encrypted key, or NULL */
    const char *server_name;                    /* SNI and name check */
    bool insecure;                              /* do not verify the server */
} td_tls_config_t;
```

| Field | Meaning |
|---|---|
| `ca`, `ca_len` | CA certificate(s), PEM or DER file contents. `NULL`: use the system's trusted roots (see below). Ignored when `insecure` is set. |
| `cert`, `cert_len` | Client certificate, PEM or DER. Optional, but only together with `key`. |
| `key`, `key_len` | The client certificate's private key, PEM or DER. |
| `key_pass` | Password of an encrypted key; `NULL` or `""` for none. |
| `server_name` | Host name sent as SNI and checked against the server certificate. `NULL` or `""`: no SNI and no name check. |
| `insecure` | `true`: do not verify the server certificate at all (`MBEDTLS_SSL_VERIFY_NONE`). |

`td_tls_t` is opaque. It holds the mbedTLS SSL context, configuration, certificates, key, entropy and DRBG state.

### PEM, DER and the terminating NUL

A buffer that contains `-----BEGIN` is parsed as PEM and **must have a NUL byte at `data[len]`** (mbedTLS parses PEM including its terminator, so `len + 1` bytes are read). Anything else is parsed as DER with exactly `len` bytes. Buffers from `td_read_file()` satisfy this. The PEM check uses `strstr()`, so even a DER buffer must be NUL-terminated somewhere.

## CA sources

| `ca` | `insecure` | The server is checked against |
|---|---|---|
| set | `false` | The certificates in `ca` only. |
| `NULL` | `false` | The system's trusted roots: on ESP-IDF the ESP-IDF certificate bundle (`esp_crt_bundle_attach()`); on Windows every certificate in the `ROOT` system store; on Linux the first of `/etc/ssl/certs/ca-certificates.crt`, `/etc/pki/tls/certs/ca-bundle.crt`, `/etc/ssl/cert.pem` that loads. |
| any | `true` | Nothing: the server is not verified. `td_tls_info()` adds ` (server not verified)`. |

If there are no system roots (for example a Linux system without any of those files), `td_tls_start()` fails with `no trusted CA certificates here: set cafile (or insecure on)`.

Certificate dates are checked, so the device's clock must be set. On the ESP32 this happens once the network is up and SNTP has run.

## Functions

### td_tls_available

```c
bool td_tls_available(void);
```

`true` when this build has TLS. Check it before offering TLS; `td_mqtt_connect()` does.

### td_tls_start

```c
td_tls_t *td_tls_start(td_sock_t sock, const td_tls_config_t *cfg, char *err, size_t cap);
```

Sets up a client session on a socket that is already connected (`td_sock_connect_poll()` returned 1). It seeds the DRBG, applies the configuration (TLS 1.2 at most), loads the CA or system roots, parses the client certificate and key, and sets SNI. No bytes are exchanged yet; call `td_tls_handshake()` next.

| Parameter | Meaning |
|---|---|
| `sock` | A connected, non-blocking socket. It stays owned by the caller. |
| `cfg` | Settings; see above. Must not be `NULL`. |
| `err`, `cap` | Receives a message on failure. Must be a valid buffer. |

Returns the session, or `NULL` with a message in `err`. On failure everything allocated is freed.

Ownership: mbedTLS parses the certificate and key buffers and copies the host name during this call, so `cfg` and the buffers it points to may be freed after `td_tls_start()` returns. (The MQTT client keeps the file contents anyway, to reconnect.)

Error messages (the part after the colon comes from `mbedtls_strerror()`):

| Message | Cause |
|---|---|
| `not enough memory for TLS` | The session struct could not be allocated. |
| `<step>: not enough memory for TLS (close apps or stop a server, then retry)` | mbedTLS ran out of heap during a step. |
| `random seed: ...`, `TLS setup: ...`, `TLS session: ...` | mbedTLS set-up errors. |
| `cafile: ...` | The CA buffer does not parse. |
| `no trusted CA certificates here: set cafile (or insecure on)` | No CA given and no system roots found. |
| `certfile and keyfile go together` | Only one of `cert`, `key` was given. |
| `certfile: ...` | The client certificate does not parse. |
| `keyfile: ...`, `keyfile (wrong password?): ...` | The key does not parse (with a password given: probably the wrong one). |
| `client certificate: ...` | The certificate and key were refused together. |

### td_tls_handshake

```c
int td_tls_handshake(td_tls_t *t, char *err, size_t cap);
```

Advances the handshake without blocking. Call it from your poll function until it returns something other than 0, and apply your own timeout (the MQTT client gives up after 10 s with `TLS handshake timed out`).

| Return | Meaning |
|---|---|
| `1` | Handshake done; use `td_tls_send()` / `td_tls_recv()`. |
| `0` | Waiting for the network: call again. |
| `-1` | Failed; message in `err`. Free the session. |

Error messages:

| Message | Cause |
|---|---|
| `server certificate rejected:<reasons>` | Verification failed. The reasons come from `mbedtls_x509_crt_verify_info()`, joined with `;` (there is no space after the colon). ` (is the clock set?)` is added when the certificate is expired or not yet valid. |
| `server certificate not trusted: set cafile to the broker's CA (or tls_insecure on)` | The ESP-IDF bundle check fails this way for an unknown CA. |
| `the broker refused the TLS connection (does it need certfile/keyfile?)` | The server sent a fatal alert and no client certificate was configured. |
| `TLS handshake: ...` | Any other mbedTLS error. |

The wording names the MQTT config keys (`cafile`, `tls_insecure`, `certfile`, `keyfile`) because MQTT is the only user today.

### td_tls_send, td_tls_recv

```c
int td_tls_send(td_tls_t *t, const void *buf, int len);
int td_tls_recv(td_tls_t *t, void *buf, int cap);
```

Same contract as `td_sock_send()` / `td_sock_recv()`: the number of bytes, `0` if the call would block (or, for `recv`, when mbedTLS only processed a session ticket), `-1` on error or when the peer closed the session.

`td_tls_send()` may return 0 until mbedTLS has sent a whole record. Call it again with the same data, as with a plain socket.

### td_tls_info

```c
void td_tls_info(td_tls_t *t, char *buf, size_t cap);
```

Writes the protocol version and cipher suite, for example `TLSv1.2 TLS-ECDHE-RSA-WITH-AES-128-GCM-SHA256`, plus ` (server not verified)` in insecure mode. Call it after the handshake. The MQTT status shows this as `Security:`.

### td_tls_free

```c
void td_tls_free(td_tls_t *t);
```

Sends a close-notify alert (best effort on a non-blocking socket), frees the session and all certificate, key and random state. `NULL` is ignored. Call it **before** `td_sock_close()` on the socket it uses; the socket itself is not closed.

### td_read_file

```c
char *td_read_file(const char *path, size_t max, size_t *len, char *err, size_t cap);
```

Reads a whole file into a new NUL-terminated buffer that the caller frees with `free()`. `*len` receives the size without the NUL. Only as much memory as the file needs is allocated.

| Error | Cause |
|---|---|
| `cannot open <path>` | `fopen()` failed. |
| `cannot read <path>` | The size could not be determined. |
| `<path> is too big (over <max> bytes)` | Larger than `max`. |
| `not enough memory for <path> (<n> bytes)` | `malloc()` failed. |

`path` is a real path (for example `/fs/root/certs/ca.crt` on the ESP32), not a shell path with `~`. `err` must be a valid buffer. Clear buffers that hold private keys before freeing them.

## Thread safety

A `td_tls_t` is not locked internally. Use one session from one place at a time. The MQTT client only touches its session inside `td_proto_lock()` (see [sockets and lock](sock.md#the-protocol-lock)). Sessions do not share state, so separate sessions may run in different tasks.

`td_tls_start()` does CPU-heavy work (key parsing), and `td_tls_handshake()` does the public-key operations: on the ESP32 a handshake step can take a noticeable time, during which the calling task (usually the UI task, from the 20 ms poll timer) does not run.

## Memory notes

- Only TLS 1.2 is offered (`mbedtls_ssl_conf_max_tls_version(..., TLS1_2)`). The ESP-IDF build has no TLS 1.3, and the host mbedTLS 3.6.0 TLS 1.3 client had problems with insecure mode and some servers.
- On hosts built with PSA crypto, `td_tls_start()` calls `psa_crypto_init()`. On the ESP32 it does not, which saves about 1.8 KB of static RAM that the SSH server needs at start-up.
- Both ESP32 ports set `CONFIG_MBEDTLS_DYNAMIC_BUFFER=y`: record buffers are sized per message instead of a fixed 16 KB + 4 KB per session. The README measures about 17 KB for an MQTT TLS session with a client certificate on the ESP32.
- The SSH server needs a lot of free internal RAM when it starts (96 KiB on the C6). Start SSH before connecting over TLS.
- Allocation failures inside mbedTLS are reported as `not enough memory for TLS (close apps or stop a server, then retry)`.

## Example

```c
size_t ca_len;
char err[160];
char *ca = td_read_file("/fs/root/certs/ca.crt", 16384, &ca_len, err, sizeof(err));
if (!ca) return;

td_tls_config_t cfg = {
    .ca = ca, .ca_len = ca_len,
    .server_name = "broker.example.com",
};
td_tls_t *tls = td_tls_start(sock, &cfg, err, sizeof(err));   /* sock is connected */
free(ca);                                                     /* already parsed */
if (!tls) return;

/* in the poll function: */
int r = td_tls_handshake(tls, err, sizeof(err));
if (r > 0) {
    char info[72];
    td_tls_info(tls, info, sizeof(info));
    td_tls_send(tls, "ping", 4);
} else if (r < 0) {
    td_tls_free(tls);
    td_sock_close(sock);
}
```
