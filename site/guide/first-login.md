# First login and users

## A freshly installed board

1. Open the board's serial port in a terminal
   ([settings](terminals.md#putty-settings)). Press a key if the screen stays
   empty.
2. The desktop opens as **root**, without a password: the board's own
   console is trusted, like a keyboard plugged into a PC.

The factory root password is **`TinyDesk`** (capital T and D). Change it
locally before enabling remote access. Telnet starts disabled; Telnet, SSH
and FTP refuse remote authentication until the root password changes.
Enable Telnet explicitly in Network only on a trusted network: it sends
passwords in plain text and accepts root only (see [Security](../security.md)):

```text
passwd                 # in the Terminal, as root: old password, then the new one twice
```

Existing user passwords are preserved on upgrade. A saved Telnet setting is
honored only when the root password has changed.

## Accounts

TinyDesk Shell keeps up to 12 accounts in NVS: `root` and the users root creates.
Passwords are stored salted and hashed (SHA-256, 2048 rounds). User names
are 1-31 characters: letters, digits, `_`, `-` and `.`.

| Command | Who | What it does |
| --- | --- | --- |
| `users` | anyone | list the accounts |
| `useradd <username>` | root | create a user (asks for the password twice), with the home `/home/<username>` |
| `userdel <username> [-f]` | root | delete a user and their home; without `-f` it asks for that user's password |
| `passwd` | anyone | change your own password (asks for the old one) |
| `login <username>` | anyone | continue the session as another user (asks for their password) |
| `logout` | anyone | end the session; the console asks who logs in next |
| `bootuser [username]` | show: anyone, set: root | the account the board's console starts as |
| `rootrecover` | the board's console only | set a new root password without the old one |

`rootrecover` is restricted to the physical console. After a Telnet takeover,
reboot locally before using it; remote input can remain queued after disconnect.
A Telnet takeover is refused while recovery is prompting for a password.
See [Security](../security.md).

## Which user the desktop belongs to

The desktop starts as the **boot user** (`bootuser`, root on a new board).
It changes when:

* root logs in over **Telnet**: the shared desktop belongs to root until
  that connection ends; other accounts use separate SSH shell sessions;
* you choose **Start → Switch user...** (name and password);
* you run `login <user>` or `logout` in the Terminal.

A change closes the previous user's windows (unsaved Editor changes are
lost) and clears the Terminal, so nothing of theirs stays on screen.

| | root | other users |
| --- | --- | --- |
| home | `/root` | `/home/<user>` |
| Files app, SFTP, FTP | the whole file system | only their home |
| Wi-Fi networks | adds shared ones, may remove all | adds their own, uses their own and shared ones |
| SSH / FTP servers, Telnet switch | yes | from the board's console |
| Log Viewer, `reboot`, `useradd`, system clock, firmware updates | yes | no |
| theme, sizes, time zone, desktop icons | their own | their own |

A user's `~/.tdshrc.tdsh` runs when the console starts as that user (for
example `wificonnect` to join Wi-Fi at boot). It is not run again on a
switch; see [Configuration files](../shell/config-files.md).

## Typical set-up

```text
useradd alice          # as root, in the Terminal
bootuser alice         # the console starts as alice from the next boot
echo wificonnect >> /home/alice/.tdshrc.tdsh
```
