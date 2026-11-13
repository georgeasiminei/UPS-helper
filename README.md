# UPS helper

A Raspberry Pi Zero 2 W can read two Eaton UPSes through a USB hub. Its intended
future use is to automate an orderly response to a power outage and restoration. **That
automation has not been configured or tested yet.**

An **observe-only service and offline simulator are implemented locally**.
They evaluate the policy and record proposed actions; this release cannot
execute SSH, change power limits, call Vast, shut down servers or send wake
packets. Nothing has been installed or enabled on the Pi by this implementation.

- [Implementation and usage](docs/IMPLEMENTATION.md): Python service, systemd
  unit, local setup, simulation and current limitations.
- [YAML configuration example](config/observe.example.yaml): UPS connection,
  policy timings/thresholds and host inventory. JSON is used for checkpoints,
  logs and simulation inputs.

Quick offline check after the local setup described above:

```sh
.venv/bin/ups-helper config-check --config config/observe.example.yaml
.venv/bin/ups-helper simulate --config config/simulation.example.yaml --scenario examples/outage-and-recovery.json
```

The [requirements](docs/REQUIREMENTS.md) record the requested outage and recovery
behavior: one-minute grace, light then drastic CPU/GPU power reduction, Vast
maintenance and graceful server shutdown, followed by Pi-driven Wake-on-LAN
retries until each recovery target is confirmed awake. The Pi must never be
intentionally shut down by this policy; it must resume control after a possible
power-transition restart or battery exhaustion and subsequent power return.

## Setup and status

Updated on 2026-11-13 in Europe/Bucharest:

Latest inspection: [two-UPS hardware inventory and diagnostics at 08:12](docs/HARDWARE-2026-11-13.md).
The earlier [complete 1150 telemetry capture](docs/UPS-TELEMETRY-2026-11-07.md)
contains 92 variables, writable-variable definitions and command discovery. See the
[Vast.ai outage-control proposal](docs/OUTAGE-CONTROL-PROPOSAL.md) for suggested
grace, two-stage reduction, maintenance, shutdown and Wake-on-LAN recovery rules.
These rules have not been deployed; rented machines were not contacted.

- UPSes: Eaton 5P1550IR, rack 1U, **1550 VA / 1100 W**, and Eaton 5P1150IR,
  rack 1U, **1150 VA / 770 W**. New batteries were previously reported for the 1150.
- Latest reported loads: **418 W / 48%** on the 1550 and **46 W / 7%** on the
  1150. Both reported `OL CHRG` and 100% charge. These are instantaneous UPS
  readings, not a verified inventory of connected equipment or runtime tests.
- Host: Raspberry Pi Zero 2 W, connected to both UPSes through a Realtek
  `0bda:5411` USB hub. Observed paths: `1-1.1` for the 1550, `1-1.2` for the 1150.
  Each UPS has a distinct serial for persistent driver selection; USB device
  numbers change on reconnection.
- Previously documented Pi power: a Duracell PB3 power bank (owner-described
  10 Ah; label: 36.5 Wh,
  5 V / 2.4 A maximum input and output) charged from the UPS, with a capacitor
  hold-up circuit between the bank and Pi. Owner testing shows source switching
  usually succeeds, but removing the bank's charging input under heavy CPU
  load causes a reboot. The owner reproduced this with `stress -c 3` (three
  of four cores loaded); no reboot has been observed on input connection.
- OS recorded on 2026-11-07: Debian 13 (trixie), aarch64, kernel `6.18.60+rpt-rpi-v8`.
- Packages recorded then: `nut-server` and `nut-client` 2.8.1-5, and `usbutils` 1:018-2.
  SSH is enabled.
- Read-only NUT driver probes **returned telemetry from both UPSes** on
  2026-11-13. The 1550's USB connection is unstable: 624 disconnects in the
  checked 12-hour window, with a median interval of 65.28 seconds. The 1150
  remained connected during that window. See the latest diagnostic report.
- Persistent NUT services are not configured: `MODE=none`; the system server
  and monitor remain inactive. Earlier diagnostics used a temporary localhost
  server; the latest probes used the driver directly. All diagnostic processes
  exited and removed their temporary state. No continuous power-event history
  was available to explain the owner's approximately hourly click and beep.
- A later Wi-Fi failure after cold restarts was recovered by recreating the
  connection. Read the [Wi-Fi profile loss investigation](docs/WIFI-INCIDENT-2026-11-07.md)
  for the two empty Netplan files, filesystem checks, upstream report and
  remaining uncertainty about the cause.

The SSH diagnostic sessions did not disconnect UPS mains, run a battery runtime
test, change outlets, or send shutdown commands. Those sessions used monitoring
and read-only tests. The owner's separate power-bank tests are recorded below.

## Wiring

The Pi Zero 2 W has two adjacent micro-USB ports with different roles:

1. Connect the Pi's power supply to **PWR IN**, the outer port.
2. Connect the USB hub to **USB**, the port closest to mini HDMI, and connect
   one data cable from each UPS to the hub.
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
- Diode: **15SQ045**, a Schottky rectifier designation commonly rated 15 A /
  45 V. The manufacturer and exact circuit topology have not been provided.
  Forward voltage depends on current and temperature; it is not a zero-drop
  ideal diode. See a [manufacturer 15SQ045 datasheet](https://diotec.com/files/diotec/files/pdf/datasheets/15sq045.pdf).
- The owner recalls measuring at most about **150 mV across the diode while
  the assembled circuit powered the Pi**, before insulating it 1-2 years ago.
  This was an operating-circuit measurement; the load used and present drop
  under four-core stress have not been established.
- A high-value resistor to discharge the capacitors over time; its value has
  not been provided.
- The circuit sits between the power bank's output and the Pi's power input.
- The supplied label photo identifies a **Duracell PB3**, **36.5 Wh**, with
  **5 V / 2.4 A maximum** input and output. These are steady-state ratings,
  not evidence of uninterrupted charge-input handover.
- Switching the bank's source produces a brief dip. The circuit usually bridges
  it without a Pi restart. The owner has never observed a restart on connecting
  the charging input during the tests performed.
- Removing the bank's charging input causes a restart when at least three of
  the four CPU cores are fully loaded, reproduced with **`stress -c 3`**.
  The earlier maximum-load measurement was about **3 W**; usual reported Pi
  consumption is **less than 1 W**.
- At least **24 hours** of operation on the bank, including recovery after a
  restart, is a desired outcome; a full runtime test has not established it.
- The controller must never intentionally shut down. The owner reports that
  after a sufficiently long outage exhausts the Pi's battery, it starts again
  when power reaches it. This full depletion/return path remains to be verified;
  monitoring and pending server-wake retries must resume automatically.
- Subsequent multimeter readings at the **circuit output / Pi input** were
  **4.7 V at idle** and varying between **4.4 and 4.5 V with all four cores
  stressed**. These are owner-reported readings, not oscilloscope captures.
  The circuit input cannot currently be probed because it is covered with
  liquid electrical insulation. These readings were taken **on battery, with
  the power bank's charging input disconnected**.

An [official Duracell PB3 manual](https://www.duracell.co.uk/upload/2018/03/ce610_n_dur_pb_manual_10050mah_eng.pdf)
also lists 36.5 Wh, but refers to a different item code from the photographed
unit. No uninterrupted charging-input handover guarantee was found in the
manual's extracted text. Simultaneous charging and output observed by the owner
does not itself establish seamless switching.

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

The subsequently measured 4.7 V idle and 4.4-4.5 V loaded readings do not match
that illustrative starting voltage. Correct the sustained supply-voltage drop
before sizing hold-up capacitors: the Pi is intended for a nominal 5 V supply.
More passive capacitance cannot raise a continuously low supply to 5 V, and an
extra series inductor adds resistance. The varying multimeter display does not
establish the frequency or shape of any electrical oscillation. See
[Raspberry Pi supply guidance](https://www.raspberrypi.com/documentation/computers/getting-started.html#power-supply).

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
capacitor voltage ratings/ESR, resistor value, diode manufacturer, and the
voltage-versus-time waveform at the Pi power input during the failing transition
at 3 W. The owner does not have an oscilloscope, so the transient remains
unmeasured. No circuit change or additional power interruption test was performed
in response to this report.

Pi-input multimeter readings are now available, but the insulated circuit input
prevents directly measuring the bank-to-Pi voltage loss. Diode drop, wiring and
connector resistance, solder joints, and power-bank regulation are possible
contributors; none has been isolated as the cause. An ordinary multimeter,
including many MIN/MAX modes, can miss a millisecond dip; the readings cannot
establish the handover dip's duration or minimum voltage.

A proposed comparison avoids opening the insulated circuit: cleanly shut down
the Pi, then power its PWR IN port directly from the same bank with a short,
known-good USB power cable. Compare idle and steady full-load voltage at the
same Pi-input measurement point in battery-only mode to match the original
readings. Do not switch its input during this comparison. A materially higher voltage
would implicate the bypassed inline path; similarly low voltage would keep the
bank/source and direct cable in scope. This comparison has not been performed.

If the diode is in series with the Pi supply or capacitor charging path, its
drop can reduce the starting voltage and invalidate the illustrative 5.00 V
starting assumption above. For example only, a 5.00 V source minus a measured
0.25 V drop leaves 4.75 V before discharge; this is not a claim about the actual
drop or Pi reset threshold. Confirm topology and normal voltages before sizing
more capacitance. A properly specified MOSFET ideal-diode solution could reduce
this loss while retaining reverse-current blocking, but its transient behavior
and capacitor inrush still need design. See [TI's ideal-diode discussion](https://www.ti.com/lit/an/slvae57b/slvae57b.pdf).

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

The current setup reports two `0463:ffff MGE UPS Systems UPS` devices behind
the hub. On the original single-UPS setup, kernel USB
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

The following capture describes the original single-UPS verification on
2026-11-07. For both UPSes and the current USB stability issue, see the
[2026-11-13 hardware report](docs/HARDWARE-2026-11-13.md).

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
other driver owns this USB device, select the intended UPS by its unique
serial from private inventory. Do not rely on discovery order or changing
USB device numbers:

```sh
(
    set -eu
    ups_serial='REPLACE_WITH_DEVICE_SERIAL'
    ups_test_dir=$(mktemp -d /tmp/ups-helper-test.XXXXXX)
    trap 'rm -rf -- "$ups_test_dir"' EXIT
    export NUT_STATEPATH="$ups_test_dir"
    export NUT_ALTPIDPATH="$ups_test_dir"
    timeout 45 /lib/nut/usbhid-ups -s eaton5p \
        -x port=auto -x vendorid=0463 -x productid=ffff \
        -x "serial=$ups_serial" -d 3
)
```

Raw scanner and driver output includes the UPS serial number. Redact it before
publishing logs. Serial numbers, credentials, and private network addresses
are omitted from this repository.

## NUT: persistent configuration next steps

The following is an **example**, not a deployed configuration. Confirm the
appropriate driver and settings against the installed NUT documentation and
hardware before making changes. For the two locally attached UPSes, example
entries in `/etc/nut/ups.conf` are below. Replace both serial placeholders
with their distinct values in private configuration:

```ini
[eaton1550]
    driver = usbhid-ups
    port = auto
    vendorid = 0463
    productid = ffff
    serial = REPLACE_WITH_1550_SERIAL

[eaton1150]
    driver = usbhid-ups
    port = auto
    vendorid = 0463
    productid = ffff
    serial = REPLACE_WITH_1150_SERIAL
```

Configure NUT's operating mode, server and monitor deliberately for the desired
installation, including appropriate credentials and permissions. Do not commit
credentials or private network details to this public repository. Once the
driver and server are configured, verify the connection and read-only telemetry
with the configured UPS name, for example:

```sh
upsc eaton1550@localhost
upsc eaton1150@localhost
```

The diagnostic localhost server has been stopped, so a connection refused error
from the default system server is still expected until persistent services are
configured. Successful diagnostic reads do not mean that monitoring starts at
boot or that equipment shutdown is implemented.

Fix and verify the 1550's USB stability before relying on its telemetry for
outage handling. The observe-only helper currently selects one UPS per
configuration; these two NUT entries alone do not implement coordinated
two-UPS policy. Map each managed host to its actual UPS and preserve the
requirement that the Pi must never intentionally shut itself down.
Set the private helper configuration's `nut.ups` to the intended NUT name;
the shipped `eaton5p` example name comes from the earlier single-UPS probe.

### Access and scanner troubleshooting

The originally detected device was `/dev/bus/usb/001/002`, owned by `root:nut` with mode
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

The [requirements](docs/REQUIREMENTS.md) are the source of truth for the requested
behavior; numerical thresholds and implementation choices in the
[control proposal](docs/OUTAGE-CONTROL-PROPOSAL.md) remain provisional.

See the [restart and filesystem resilience proposal](docs/RESILIENCE.md) for
the recommended storage layout, recovery behavior, runtime assumptions, and
acceptance tests. The current Pi configuration has only been inspected; these
changes have not been deployed.

The owner is willing to accept a Pi restart at each power-bank source change.
Removing the entire inline hold-up assembly and powering the Pi directly from
the bank is therefore a candidate simplification, subject to verifying steady
voltage and autonomous recovery. See the proposal's hardware options and
acceptance conditions. Removing only the blocking diode is a different change
and may allow stored energy to discharge upstream. No circuit has been removed
or modified by the agent.

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
- Never intentionally halt the Pi as part of server shutdown. It continues on
  its own battery, with automatic recovery if it restarts or eventually loses
  power and boots again when power returns.
- On qualified mains recovery, use the Pi to wake gracefully halted servers
  through Wake-on-LAN. Retry each pending target until identity-aware checks
  confirm it is awake, then verify readiness before clearing owned maintenance.
  Preserve pending wake work across Pi restarts and prolonged power loss.
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
