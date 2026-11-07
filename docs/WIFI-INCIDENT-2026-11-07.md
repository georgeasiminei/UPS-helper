# Wi-Fi profile loss investigation — 2026-11-07

## Symptom and recovery

After several owner-performed cold restarts, Wi-Fi stopped reconnecting. The
local console showed `wlan0` disconnected, Wi-Fi enabled and unblocked,
NetworkManager active, and only the loopback connection profile loaded.
Reloading profiles and rebooting did not restore the missing Wi-Fi connection.

The owner restored access using the following pattern, entering the password
only at the local prompt:

```sh
sudo nmcli connection reload
sudo nmcli --ask device wifi connect "<SSID>" ifname wlan0
```

Subsequent SSH inspection confirmed a connected interface and a new persistent
Wi-Fi keyfile in `/etc/NetworkManager/system-connections/`, owned by `root:root`
with mode `0600`, with autoconnect enabled. Persistence through a subsequent
controlled reboot has not been verified as part of this investigation.

## Evidence collected over SSH

The inspection was read-only; no network configuration was changed, no
filesystem repair was run, and no restart was initiated by the agent.

| Check | Observation |
| --- | --- |
| Persistent Netplan files | Two `/etc/netplan/90-NM-*.yaml` files, both zero bytes, mode `0600`, owned by root |
| Empty-file modification times | Four seconds apart, before the current boot |
| NetworkManager boot log | No Wi-Fi activation until the owner's new `connection-add-activate` operation |
| Cloud-init log | Repeatedly reports `No network config applied. Neither a new instance nor datasource network update allowed` |
| Root filesystem | ext4, still mounted read/write |
| ext4 error counters | `errors_count=0`, first and last error times both zero |
| Current kernel log | No matching SD I/O, filesystem corruption, or ext4 recovery errors found |
| Boot FAT check | Completed without reported errors |
| Package verification | `dpkg -V network-manager cloud-init netplan.io` reported no mismatches |
| Failed systemd units | None at inspection |
| Previous boot journals | Unavailable: only the current boot appears in the volatile journal |

Relevant installed versions:

- NetworkManager: `1.52.1-1+rpt4`
- Netplan: `1.1.2-7+rpt1`
- cloud-init: `25.2-1~bpo13+1+rpt20`

## Interpretation and limits

The immediate failure was the absence of a usable, loaded Wi-Fi profile.
Empty Netplan files contain no connection definition. This is consistent with
profile persistence failing and the failure becoming visible on reboot, but
the original profile contents and the operation that emptied or created those
files were not captured. File metadata alone does not prove their prior
contents, which process wrote them, or that a cold reset caused the loss.

Cloud-init's recorded decision explains why another boot did not automatically
reapply its initial network configuration. Creating a new Wi-Fi profile restored
the working connection.

There is a closely matching [upstream Raspberry Pi Trixie report, issue #99](https://github.com/raspberrypi/trixie-feedback/issues/99):
Pi Zero 2 W, the same NetworkManager package version, Imager/cloud-init setup,
and two empty `90-NM` files created four seconds apart. That reporter also had
a clean offline filesystem check. As reviewed on 2026-11-07, the discussion
does not establish the original trigger, a confirmed fix, or a guaranteed
mitigation. The similarity strengthens a profile-persistence hypothesis; it
does not establish that this Pi experienced the same underlying cause.

The available evidence does **not** demonstrate widespread filesystem damage
or SD hardware failure. It also does not establish that all stored files are
intact. Ext4 journaling protects structural consistency, while interrupted
file writes can still lose contents. Package verification covered the three
named packages, not every installed file or private configuration. See
[Linux ext4 journaling](https://www.kernel.org/doc/html/latest/filesystems/ext4/journal.html).

## Follow-up

1. Obtain a backup on stable power before more interruption testing.
2. Confirm the new profile reconnects after a controlled reboot on stable power.
3. If a structural check is wanted, check an unmounted root partition or a
   captured image offline. A live check of the mounted writable root cannot
   provide a valid full filesystem assessment; a clean structural check would
   still not prove that every file's original contents survived. See
   [e2fsck documentation](https://man7.org/linux/man-pages/man8/e2fsck.8.html).
4. Implement and validate the read-only storage and recovery proposal before
   treating repeated abrupt resets as an accepted operating mode.

Private SSIDs, addresses, UUIDs, credentials and raw configuration contents are
omitted from this public record. NetworkManager keyfiles and cloud-init network
configuration can contain Wi-Fi passwords and must remain private.
