# UPS helper

A Raspberry Pi monitors an Eaton UPS over USB. The intended future use is to
automate an orderly response to a power outage and restoration. **That
automation has not been configured or tested yet.**

## Setup and status

Recorded on 2026-11-07 in Europe/Bucharest:

- UPS: Eaton 5P1150IR, rack 1U, 1150 VA / 770 W, with new batteries.
- Host: Raspberry Pi Zero 2 W, connected to the UPS by USB.
- Pi power: a 10 Ah power bank charged from the UPS, with a capacitor hold-up
  circuit between the bank and Pi. Owner testing shows that source switching
  usually succeeds, but removing the bank's charging input under heavy CPU
  load causes a reboot. The owner reproduced this with `stress -c 3` (three
  of four cores loaded); no reboot has been observed on input connection.
- OS: Debian 13 (trixie), aarch64, kernel `6.18.60+rpt-rpi-v8`.
- Installed: `nut-server` and `nut-client` 2.8.1-5, and `usbutils` 1:018-2.
  SSH is enabled.
- USB enumeration, NUT driver communication, and UPS variable reads have
  **passed verification** after correcting the Pi's port connections.
- Persistent NUT services are not configured: `MODE=none`; the system server
  and monitor remain inactive. Diagnostic processes used temporary files and
  a localhost-only server, then exited and removed their temporary state.

The SSH diagnostic sessions did not disconnect UPS mains, run a battery runtime
test, change outlets, or send shutdown commands. Those sessions used monitoring
and read-only tests. The owner's separate power-bank tests are recorded below.

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

## Power-bank hold-up circuit and known reboot condition

The owner reports the following circuit and test results, added on 2026-11-07:

- Three 4.7 mF capacitors in parallel: nominal total **14.1 mF / 14,100 uF**.
- A diode described as a special diode; its type, part number, and circuit
  topology have not been provided.
- A high-value resistor to discharge the capacitors over time; its value has
  not been provided.
- The circuit sits between the power bank's output and the Pi's power input.
- Switching the bank's source produces a brief dip. The circuit usually bridges
  it without a Pi restart. The owner has never observed a restart on connecting
  the charging input during the tests performed.
- Removing the bank's charging input causes a restart when at least three of
  the four CPU cores are fully loaded, reproduced with **`stress -c 3`**.
  The earlier maximum-load measurement was about **3 W**; usual reported Pi
  consumption is **less than 1 W**.
- At least **24 hours** of operation on the bank, including recovery after a
  restart, is a desired outcome; a full runtime test has not established it.

Consequently, loss of UPS output at battery exhaustion, or a commanded outlet
shutdown that removes power from the bank's charger, may reboot the controller.
This is an inference from the owner's charging-input removal test; the full
UPS-exhaustion sequence has not been tested. The 10 Ah bank capacity does not
establish continuity during its internal source transition.

For scale, an ideal capacitor supplying a constant-power load gives
`t = C * (V_initial^2 - V_final^2) / (2 * P)`. With 14.1 mF, a hypothetical
5.00 V to 4.75 V discharge at 3 W gives only about **5.7 ms**. These voltages
are an illustrative window, not measured circuit voltages or an asserted Pi
reset threshold. Actual hold-up depends on starting voltage, the Pi's usable
voltage range, capacitor tolerances and ESR, diode/cable losses, and the load.
See [TI's capacitor hold-up discussion](https://www.ti.com/lit/pdf/ssztbp1).

For that same illustrative 5.00 V to 4.75 V window:

| Total nominal capacitance | Ideal hold-up at 1 W | Ideal hold-up at 3 W |
| --- | --- | --- |
| 14.1 mF (current bank) | 17.2 ms | 5.7 ms |
| 28.2 mF | 34.4 ms | 11.5 ms |
| 47 mF | 57.3 ms | 19.1 ms |
| 100 mF | 121.9 ms | 40.6 ms |

More capacitance can bridge a longer interruption, but these are ideal
calculations, not validated component selections. First measure the duration,
minimum voltage, and shape of the failing dip at the Pi input. A gradual droop
suggests insufficient stored energy; a large immediate step also calls for
checking capacitor ESR, diode drop, wiring resistance, and upstream isolation.
Stored energy should support the Pi rather than drain back into the bank.

Increasing capacitance increases charging inrush and recharge demand, which
can pull down the supply or trigger current limiting. The circuit may need a
controlled charging path sized with the power bank and diode; the existing
high-value discharge resistor does not by itself limit capacitor charging.
See [TI on capacitor inrush](https://www.ti.com/document-viewer/lit/html/SSZTBX2/GUID-2AF5E1CE-C09D-447F-ACB7-ED209C847E47).

A small series inductor is not recommended as an unmeasured addition for this
source handover. It can filter fast noise, but it does not establish enough
hold-up energy for the interruption. Its resistance adds voltage drop, its
current rating and saturation matter, and an LC network can ring unless
properly designed and damped. See [Analog Devices on LC filter resonance](https://www.analog.com/en/resources/analog-dialogue/articles/speed-up-the-design-of-emi-filters-for-switch-mode-power-supplies.html).

To diagnose or change the circuit, the missing evidence is the schematic,
component details, and the voltage-versus-time waveform at the Pi power input
during the failing transition at 3 W. No circuit change or additional power
interruption test was performed in response to this report.

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
- The diagnostic `vcgencmd get_throttled` value was `0x0`, but this does not
  establish a stable power rail. Raspberry Pi documents that the Zero range
  lacks the low-voltage detection circuitry found on other models; the value
  cannot rule out a supply dip on this Pi. Use measurement at the Pi input to
  characterize the reported transition. See
  [Raspberry Pi power supply warnings](https://www.raspberrypi.com/documentation/computers/raspberry-pi.html#power-supply-warnings).

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

See the [restart and filesystem resilience proposal](docs/RESILIENCE.md) for
the recommended storage layout, recovery behavior, runtime assumptions, and
acceptance tests. The current Pi configuration has only been inspected; these
changes have not been deployed.

Telemetry works; the next step is to design and test the policy. It needs explicit
choices for outage delays, mains return, low-battery behavior, shutdown order,
and restoration, based on the devices connected and their dependencies. The
known controller reboot condition adds these requirements:

- Start orderly equipment shutdown with enough UPS runtime remaining to finish
  before output disappears. Thresholds need measured shutdown times and a
  margin; the idle runtime estimate is insufficient to choose them.
- Keep the Pi's power-bank charger and required network equipment powered
  through equipment shutdown. Cutting the charger outlet early can provoke
  the same source transition before orchestration is complete.
- Start monitoring and the controller automatically after a Pi reboot, and
  reconnect to the UPS with retries. A reboot can occur mid-outage.
- When policy requires history across reboot, persist essential progress in a
  writable location outside the RAM overlay before actions that might interrupt
  the controller. Reconcile saved progress with fresh UPS telemetry and equipment
  state after boot; repeating an action must be safe. Stale progress or missing
  telemetry alone must not trigger an outlet shutdown.
- Complete any required controller-issued final UPS command while the Pi is
  still running. Recovery cannot substitute for a command that was never sent.
- Test controller reboot during orchestration, charger-input loss and return
  at maximum Pi load, and network loss/restoration before relying on the policy.

These are design requirements, not implemented behavior. No load shedding,
shutdown orchestration, reboot recovery, or restoration automation is currently
claimed to be functional.

## Repository workflow

`development` is the default integration branch. Make changes on a feature
branch and merge them through a pull request into `development`. Create or
update `staging` from the merged `development` state when preparing the staging
branch.
