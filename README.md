# UPS helper

A Raspberry Pi monitors an Eaton UPS over USB. The intended future use is to
automate an orderly response to a power outage and restoration. **That
automation has not been configured or tested yet.**

## Setup and status

Recorded on 2026-11-07 in Europe/Bucharest:

- UPS: Eaton 5P1150IR, rack 1U, 1150 VA / 770 W, with new batteries.
- Host: Raspberry Pi Zero 2 W, connected to the UPS by USB.
- Pi power: a 10 Ah power bank, charged from the UPS. Whether it supplies
  uninterrupted power when its charging input changes has not been validated.
- OS: Debian 13 (trixie), aarch64, kernel `6.18.60+rpt-rpi-v8`.
- Installed: `nut-server` and `nut-client` 2.8.1-5, and `usbutils` 1:018-2.
  SSH is enabled.
- USB enumeration, NUT driver communication, and UPS variable reads have
  **passed verification** after correcting the Pi's port connections.
- Persistent NUT services are not configured: `MODE=none`; the system server
  and monitor remain inactive. Diagnostic processes used temporary files and
  a localhost-only server, then exited and removed their temporary state.

No mains disconnection, battery runtime test, forced shutdown, outlet change,
or shutdown command has been performed. Tests so far have been monitoring and
read-only.

## Wiring

The Pi Zero 2 W has two adjacent micro-USB ports with different roles:

1. Connect the Pi's power supply to **PWR IN**, the outer port.
2. Connect the UPS USB data cable to **USB**, the port closest to mini HDMI.
3. Connect the power bank's charging input to an appropriate UPS-backed outlet.

The initial setup had these two Pi connections swapped: power was in the
inner/data port and the UPS cable was in the outer/power port. After correcting
the connections and rebooting the Pi, the UPS appeared on USB. See the
[official Raspberry Pi Zero documentation](https://www.raspberrypi.com/documentation/computers/zero.html)
for the port layout. Keep network equipment needed for monitoring and future
shutdown coordination on UPS-backed power too.

## Install and connect

On a Debian-based Pi, install the tools and enable SSH if it is not already
available:

```sh
sudo apt update
sudo apt install nut-server nut-client usbutils openssh-server
sudo systemctl enable --now ssh
```

Connect from another machine, substituting the actual account and address:

```sh
ssh <user>@<pi-address>
```

The account used during setup was not initially a member of the `nut` group.
If NUT USB access is denied, an administrator can add the appropriate account:

```sh
sudo usermod -aG nut <user>
```

Start a new login session for group membership to take effect, and check with
`id`. Membership grants access to the UPS device, including the ability to
control it, and read access to NUT configuration available to that group.
Use it only for trusted accounts. After the reboot, `sudo -n` required a
password. The administrator ran the group command interactively; a new SSH
session confirmed membership and successful USB discovery without sudo.

## Verify USB

Check the physical connection and enumeration:

```sh
lsusb
lsusb -d 0463:ffff
```

The corrected setup reports `0463:ffff MGE UPS Systems UPS`. Kernel USB
information identifies the manufacturer as `EATON`, the product as `Eaton 5P`,
and the device as full-speed USB HID at 12 Mb/s. The USB host controller's
`busconnected` value changed from `0` to `1`. This confirmed that the existing
cable carries USB data. Subsequent NUT tests also confirmed UPS variable reads.

If the UPS does not appear:

- Recheck both Pi ports and reboot after correcting the wiring. Initially,
  `lsusb` showed only the root hub, while `dwc_otg` reported host mode `0x1`
  and `busconnected=0`.
- Check the cable and inspect recent USB messages with `dmesg` (administrator
  privileges may be needed).
- Check power with `vcgencmd get_throttled`, if available. The initial value
  was `0x0`, with no undervoltage events reported; after the fix no
  undervoltage was reported either.

## Verified NUT communication

The installed `usbhid-ups` driver selected subdriver `MGE HID 1.46` and exited
successfully after three update loops using its data-dump option. A separate
temporary `upsd` listening only on `127.0.0.1:13493` exposed the UPS as
`eaton5p`; `upsc` returned live status and telemetry. Three subsequent status
queries returned `OL CHRG` (mains online, charging flag reported).

The test used private temporary configuration and state directories, with no
monitor process or control accounts. It did not replace `/etc/nut` files.
Both diagnostic processes were stopped and temporary files were removed.
An initial server query briefly returned `WAIT` while the driver initialized;
readings were collected again after initialization completed.
The diagnostic server used `/lib/nut/upsd` directly: Debian's `/usr/sbin/upsd`
wrapper consults `/etc/nut/nut.conf` and exits while its mode is `none`, even
when an alternative configuration directory is supplied to the underlying
server. The final check waited for complete telemetry, then asserted that
three successive samples were online with valid battery charge readings.

Observed values during the communication tests:

| Variable | Value | Interpretation |
| --- | --- | --- |
| `ups.model` | `5P 1150` | Matches the stated UPS family and rating |
| `ups.firmware` | `02.14.0026` | Firmware reported by the UPS |
| `ups.status` | `OL CHRG` | Mains present; charging flag set |
| `battery.charge` | `100` | Reported charge, percent |
| `battery.charge.low` | `15` | Reported low-charge threshold, percent |
| `battery.charge.restart` | `5` | Reported restart charge threshold, percent |
| `battery.charger.status` | `floating` | Charger state reported by the UPS |
| `battery.voltage` | `26.8` | Battery voltage, V; nominal battery system is 24 V |
| `battery.runtime` | `6600` | Estimated seconds remaining, about 110 minutes |
| `input.voltage` | about `234` | Input voltage, V |
| `output.voltage` | about `234` | Output voltage, V |
| `ups.load` | `0` | UPS-reported load percentage |
| `ups.realpower` | `0` | UPS-reported real power, W |
| `ups.test.result` | `Done and passed` | Existing stored result; no test was started here |
| `outlet.1.switchable` | `yes` | PowerShare Outlet 1 is exposed as switchable |
| `outlet.2.switchable` | `yes` | PowerShare Outlet 2 is exposed as switchable |
| `ups.start.auto` | `yes` | Automatic start setting reported by the UPS |

Runtime is the UPS estimate at the reported load, not a measured battery
endurance result. A zero load reading does not establish that no equipment is
connected, and these tests do not validate the capacity of the new batteries.
The stored self-test result has no verified date in this record.

Read-only command discovery also advertised outlet-group on/off commands,
whole-UPS load and shutdown commands, beeper control, and battery tests.
Command availability was inspected only; actual switching, battery testing,
and graceful equipment shutdown remain untested. The two PowerShare groups
are candidates for later load shedding; they do not imply six independently
controlled sockets.

To repeat a driver-only data read with the installed NUT 2.8.1, while no
other driver owns this USB device:

```sh
(
    set -eu
    ups_test_dir=$(mktemp -d /tmp/ups-helper-test.XXXXXX)
    trap 'rm -rf -- "$ups_test_dir"' EXIT
    export NUT_STATEPATH="$ups_test_dir"
    export NUT_ALTPIDPATH="$ups_test_dir"
    timeout 45 /lib/nut/usbhid-ups -s eaton5p \
        -x port=auto -x vendorid=0463 -x productid=ffff -d 3
)
```

Raw scanner and driver output includes the UPS serial number. Redact it before
publishing logs. Serial numbers, credentials, and private network addresses
are omitted from this repository.

## NUT: persistent configuration next steps

The following is an **example**, not a deployed configuration. Confirm the
appropriate driver and settings against the installed NUT documentation and
hardware before making changes. For a locally attached USB UPS, an example
entry in `/etc/nut/ups.conf` is:

```ini
[eaton5p]
    driver = usbhid-ups
    port = auto
    vendorid = 0463
    productid = ffff
```

Configure NUT's operating mode, server and monitor deliberately for the desired
installation, including appropriate credentials and permissions. Do not commit
credentials or private network details to this public repository. Once the
driver and server are configured, verify the connection and read-only telemetry
with the configured UPS name, for example:

```sh
upsc eaton5p@localhost
```

The diagnostic localhost server has been stopped, so a connection refused error
from the default system server is still expected until persistent services are
configured. Successful diagnostic reads do not mean that monitoring starts at
boot or that equipment shutdown is implemented.

### Access and scanner troubleshooting

The detected device was `/dev/bus/usb/001/002`, owned by `root:nut` with mode
`0664`. USB device numbers can change after reconnecting or rebooting; inspect
the current device rather than assuming this path is permanent. An unprivileged
scanner initially reported access denied because the account was not in the
`nut` group. Check the current device permissions and login groups before
investigating the driver.

`nut-scanner` can also report missing optional SNMP, XML, Avahi or IPMI
libraries. Those warnings concern other discovery methods and do not explain a
USB access failure.

References: [NUT hardware compatibility list](https://networkupstools.org/stable-hcl.html),
[NUT overview](https://networkupstools.org/docs/user-manual.chunked/Overview.html),
[`nut-scanner` documentation](https://networkupstools.org/docs/man/nut-scanner.html),
and [`usbhid-ups` documentation](https://networkupstools.org/docs/man/usbhid-ups.html).

## Future outage policy

Telemetry works; the next step is to design and test the policy. It needs explicit
choices for outage delays, mains return, low-battery behavior, shutdown order,
and restoration, based on the devices connected and their dependencies. Verify
power-bank continuity and network availability as part of that work. No load
shedding, shutdown orchestration, or restoration automation is currently
claimed to be functional.

## Repository workflow

`development` is the default integration branch. Make changes on a feature
branch and merge them through a pull request into `development`. Create or
update `staging` from the merged `development` state when preparing the staging
branch.
