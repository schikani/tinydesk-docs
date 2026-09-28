# Security

TinyDesk is meant for a bench or a trusted local network. This page lists
what protects what, and where the limits are.

## Physical access

* The board's own console (USB Serial/JTAG on the ESP32-C6, UART0 on the
  ESP32) opens the desktop as the **boot user without a password**, and
  `rootrecover` there sets a new root password. Whoever holds the board
  (or its cable) is root.
* Flash is **not encrypted** and **secure boot is off**: with esptool anyone
  can read NVS (password hashes, Wi-Fi passwords, the SSH host key, SMB
  credentials) and the file system, or write other firmware. ESP-IDF's flash
  encryption and secure boot can be enabled for a deployment, at the cost
  of easy reflashing; they are not configured here.

## Accounts

* The factory root password is **`TinyDesk`**, shared across boards. Use it
  locally with `passwd` to choose a unique password. Remote authentication
  through Telnet, SSH and FTP is blocked until the root password changes.
  Telnet starts disabled. See [First login](guide/first-login.md).
* Telnet shares the desktop shell and therefore accepts **root only**.
  Physical recovery is locked until reboot after remote takeover, including
  after disconnect. A recovery prompt holds a lease that refuses takeover.
  Separate SSH sessions cannot acquire that physical-console lease.
* Passwords are stored salted and hashed (SHA-256, 2048 rounds), up to 12
  accounts. There is no lock-out after failed logins.
* Non-root users are sandboxed to their home in the shell, the Files app,
  SFTP and FTP.

## Network services

| Service | Port | Default | Protection | Notes |
| --- | --- | --- | --- | --- |
| Telnet remote desktop | 23 | **off**, explicit Network opt-in | root only, after password setup | **plain text**: passwords and screens can be read on the network. Off in the Network app (saved) |
| SSH / SFTP | 22 | off (`ssh start`, Network app, or a `.tdshrc.tdsh` line) | password login, encrypted | per-device ECDSA P-256 host key (compare `ssh hostkey`); one client at a time |
| FTP | 21 | off (`ftp start`) | TinyDesk Shell login | **plain text** |
| Modbus TCP server | 502 | off (Modbus app, `modbus server start`) | **none** | anyone on the network can read and write its tables; Modbus TCP has no authentication |
| MQTT client | out | off | TLS 1.2 optional, CA and client certificates | `tls_insecure` turns certificate checks off; the password and key file paths live in `mqtt.conf` |
| Firmware update | out | on demand, root only | SHA-256 and image checks | **images are not signed**: see below |

Firmware updates check the image format, the chip and a SHA-256 of the
image, and a new image runs on trial with automatic rollback. That protects
against broken downloads, not against a crafted image: anyone who can make
root install a file, or who can change an `http://` download on the way,
can run their own firmware. Use `https://` URLs (checked against the
ESP-IDF certificate bundle) or copy the file over SFTP.

## The terminal

* Copying in the Editor also sends the text to the terminal with OSC 52,
  which some terminals put on the PC's clipboard.
* Pasted text from the PC is inserted as it is; pasting into the Terminal
  runs it as shell input, line by line.

## Recommendations

* Change the factory root password (`passwd`) at the first start and give
  people their own accounts; make a non-root user the boot user for shared
  desks.
* Prefer SSH to Telnet; switch Telnet off on networks you do not trust.
* Start the Modbus TCP server and FTP only while you need them.
* Use MQTT over TLS with the broker's CA certificate, not `tls_insecure`.
* Serve updates over HTTPS or install them from a file.
* Keep boards where only trusted people can plug into them.

## Reporting a problem

Report a security problem in TinyDesk or TinyDesk Shell itself (not a
configuration choice above) privately through GitHub: the repository's
**Security → Report a vulnerability** page. Other bugs go to the issue
tracker. Fixes are noted in the [changelog](changelog.md).
