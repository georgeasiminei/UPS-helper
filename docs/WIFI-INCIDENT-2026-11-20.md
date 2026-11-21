# Wi-Fi authentication failure — 2026-11-20

On 20 November at 13:12:11 EET, the Pi lost its Wi-Fi connection with
reason 6, then repeatedly associated but failed the authentication handshake
with reason 15. NetworkManager reported `supplicant-timeout` at 13:12:31,
then `no-secrets` at 13:13:47. No further activation attempts were recorded
until the owner manually reactivated the connection at 13:55 on 21 November.
The saved profile had autoconnect enabled, default retry settings and a
system-owned saved PSK. The `no-secrets` result does not establish that the
password was wrong or missing.

The same reason 6 / reason 15 pattern occurred on 15 November around
09:53–09:54 and recovered. The evidence establishes an authentication failure between the client and
access point, but not its trigger or why automatic recovery did not resume.
The Pi had been up for 11 days; the incident did not coincide with a restart.
No kernel errors were found in the incident window. `vcgencmd get_throttled`
reported `0x0`. The [Pi Zero lacks undervoltage detection](https://www.raspberrypi.com/documentation/computers/raspberry-pi.html),
so this does not establish stable power.

The owner disabled Wi-Fi power saving before reconnecting; the kernel reported
it disabled on 21 November at 13:53:44. The connection profile still used the
default power-save setting and no global override was present, so persistence across reconnect or reboot has not
been established. Power saving as the cause and this change as a fix remain
unverified. Investigate access-point logs for the same period, then validate
recovery after a controlled access-point interruption with local console
access. Keep the network equipment required for outage coordination powered.
The NUT server and monitor were inactive at inspection, so this connection alone
does not provide continuous outage monitoring or shutdown automation.

For a future failure, collect logs before restarting services or rebooting:

```sh
journalctl -b -u NetworkManager --no-pager
journalctl -b -u wpa_supplicant --no-pager
journalctl -b -k --no-pager
```

Use `journalctl --list-boots` and `-b -1` for the previous boot if its journal
is retained. Redact private network identifiers, addresses and credentials
before sharing. See the [IEEE reason-code definitions](https://android.googlesource.com/platform/external/wpa_supplicant_8/+/master/src/common/ieee802_11_defs.h)
and [NetworkManager profile settings](https://networkmanager.dev/docs/api/latest/nm-settings-nmcli.html)
for autoconnect and retry semantics.
