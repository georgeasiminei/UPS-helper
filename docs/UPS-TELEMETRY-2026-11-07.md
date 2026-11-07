# UPS telemetry — 7 November 2026

Captured through SSH to the Raspberry Pi and USB to the Eaton UPS, using
NUT 2.8.1-5 / usbhid-ups 0.52 / MGE HID 1.46. Sample times were
**18:16:49, 18:16:51 and 18:16:54 Europe/Bucharest** (+02:00).

Status: observed snapshot, not an enabled control policy.

## Collection and limits

All **92 exposed NUT variables**, **33 writable-variable definitions** and
**23 advertised instant commands** were retrieved. The three client reads
returned identical values; NUT caches values and not every field is refreshed
on every poll. This is not a battery endurance or independent accuracy test.
Serial-number values are redacted. This is all data exposed by this installed
NUT driver, not a raw HID descriptor dump or complete UPS event history.

The normal system server and monitor were inactive, with `MODE=none`. The
session used private temporary configuration, an empty control-account file,
and a diagnostic server bound only to Pi loopback. Driver and server processes
were terminated, their temporary directory removed, and the diagnostic port
confirmed closed afterward. No persistent NUT configuration was installed.
No UPS setting writes, instant commands, battery tests, outlet changes or
mains interruptions were performed. No rented machine was contacted.

## Readings that matter for control

| Item | Observation | Limit or implication |
| --- | --- | --- |
| Status | `OL CHRG` | Mains online; charging flag reported |
| Battery | 100%, 26.8 V, nominal 24 V, charger `floating` | Reported state; capacity not tested |
| Runtime estimate | 6,600 s / 110 min | At reported 0 W / 0% load; unusable as a loaded-host guarantee |
| Input/output | 225.4 V, 50.0 Hz | Nominal 230 V / 50 Hz |
| UPS rating | 770 W / 1,150 VA | Combined connected equipment and transients must fit both ratings |
| Low-battery threshold | 15% | Controller must begin graceful shutdown earlier when reserve requires |
| Restart charge | 5% | UPS setting, not a suitable validated host-restart energy budget |
| Automatic UPS restart | `yes` | Does not establish that a gracefully halted server will boot |
| Switched groups | PowerShare 1 and 2, both on | Two groups; mapping to equipment unverified |
| Self-test result | `Done and passed` | Stored result with no verified date; no new test was run |
| Shutdown/start timer | Both `-1` | No countdown reported in this snapshot |
| Beeper | Disabled | Current setting recorded only |

`battery.capacity` is reported as 9.00; do not infer measured usable energy
from that configured/reported nominal value. There is no exposed temperature,
verified battery age, individual-cell health, or complete event history in this
snapshot. No alarm variable was exposed; that is not proof of complete hardware
health. Unusual values and sentinel-looking delays below are preserved verbatim.

## All exposed variables

```text
battery.capacity: 9.00
battery.charge: 100
battery.charge.low: 15
battery.charge.restart: 5
battery.charger.status: floating
battery.energysave: no
battery.energysave.delay: 300
battery.energysave.load: 5
battery.protection: yes
battery.runtime: 6600
battery.type: PbAc
battery.voltage: 26.8
battery.voltage.nominal: 24
device.mfr: EATON
device.model: 5P 1150
device.serial: [REDACTED]
device.type: ups
driver.debug: 0
driver.flag.allow_killpower: 0
driver.name: usbhid-ups
driver.parameter.pollfreq: 30
driver.parameter.pollinterval: 2
driver.parameter.port: auto
driver.parameter.productid: ffff
driver.parameter.synchronous: auto
driver.parameter.vendorid: 0463
driver.state: quiet
driver.version: 2.8.1
driver.version.data: MGE HID 1.46
driver.version.internal: 0.52
driver.version.usb: libusb-1.0.28 (API: 0x100010a)
input.current: 0.10
input.frequency: 50.0
input.frequency.extended: no
input.frequency.nominal: 50
input.sensitivity: normal
input.transfer.boost.low: 184
input.transfer.high: 294
input.transfer.low: 160
input.transfer.trim.high: 265
input.voltage: 225.4
input.voltage.extended: no
input.voltage.nominal: 230
outlet.1.autoswitch.charge.low: 0
outlet.1.delay.shutdown: 65535
outlet.1.delay.start: 3
outlet.1.desc: PowerShare Outlet 1
outlet.1.id: 1
outlet.1.status: on
outlet.1.switchable: yes
outlet.2.autoswitch.charge.low: 0
outlet.2.delay.shutdown: 65535
outlet.2.delay.start: 6
outlet.2.desc: PowerShare Outlet 2
outlet.2.id: 2
outlet.2.status: on
outlet.2.switchable: yes
outlet.desc: Main Outlet
outlet.id: 0
outlet.switchable: no
output.current: 0.00
output.frequency: 50.0
output.frequency.nominal: 50
output.powerfactor: 0.00
output.voltage: 225.4
output.voltage.nominal: 230
ups.beeper.status: disabled
ups.delay.shutdown: 20
ups.delay.start: 30
ups.efficiency: 0
ups.firmware: 02.14.0026
ups.load: 0
ups.load.high: 105
ups.mfr: EATON
ups.model: 5P 1150
ups.power: 0
ups.power.nominal: 1150
ups.productid: ffff
ups.realpower: 0
ups.realpower.nominal: 770
ups.serial: [REDACTED]
ups.shutdown: enabled
ups.start.auto: yes
ups.start.battery: yes
ups.start.reboot: yes
ups.status: OL CHRG
ups.test.interval: 2592000
ups.test.result: Done and passed
ups.timer.shutdown: -1
ups.timer.start: -1
ups.type: offline / line interactive
ups.vendorid: 0463
```

## Writable-variable definitions — discovery only

This is the unmodified listing from `upsrw` without a setting operation.
Descriptions and units are supplied by the installed NUT variable database.
No value in this section was changed.

```text
[battery.charge.low]
Remaining battery level when UPS switches to LB (percent)
Type: STRING
Maximum length: 5
Value: 15

[battery.charge.restart]
Minimum battery level for restart after power off (percent)
Type: STRING
Maximum length: 3
Value: 5

[battery.energysave]
Switch off when running on battery and no/low load
Type: STRING
Maximum length: 5
Value: no

[battery.energysave.delay]
Delay before switch off UPS if on battery and load level low (min)
Type: STRING
Maximum length: 5
Value: 300

[battery.energysave.load]
Switch off UPS if on battery and load level lower (percent)
Type: STRING
Maximum length: 5
Value: 5

[battery.protection]
Prevent deep discharge of battery
Type: STRING
Maximum length: 5
Value: yes

[driver.debug]
Current debug verbosity level of the driver program
Type: NUMBER
Value: 0

[driver.flag.allow_killpower]
Safety flip-switch to allow the driver daemon to send UPS shutdown command (accessible via driver.killpower)
Type: NUMBER
Value: 0

[input.frequency.extended]
Extended input frequency range
Type: STRING
Maximum length: 5
Value: no

[input.sensitivity]
Input power sensitivity
Type: STRING
Maximum length: 10
Value: normal

[input.transfer.boost.low]
Low voltage boosting transfer point (V)
Type: STRING
Maximum length: 5
Value: 184

[input.transfer.high]
High voltage transfer point (V)
Type: STRING
Maximum length: 5
Value: 294

[input.transfer.low]
Low voltage transfer point (V)
Type: STRING
Maximum length: 5
Value: 160

[input.transfer.trim.high]
High voltage trimming transfer point (V)
Type: STRING
Maximum length: 5
Value: 265

[input.voltage.extended]
Extended input voltage range
Type: STRING
Maximum length: 5
Value: no

[outlet.1.autoswitch.charge.low]
Remaining battery level to power off this outlet (percent)
Type: STRING
Maximum length: 3
Value: 0

[outlet.1.delay.shutdown]
Interval to wait before shutting down this outlet (seconds)
Type: STRING
Maximum length: 5
Value: 65535

[outlet.1.delay.start]
Interval to wait before restarting this outlet (seconds)
Type: STRING
Maximum length: 5
Value: 3

[outlet.1.desc]
Outlet description
Type: STRING
Maximum length: 20
Value: PowerShare Outlet 1

[outlet.2.autoswitch.charge.low]
Remaining battery level to power off this outlet (percent)
Type: STRING
Maximum length: 3
Value: 0

[outlet.2.delay.shutdown]
Interval to wait before shutting down this outlet (seconds)
Type: STRING
Maximum length: 5
Value: 65535

[outlet.2.delay.start]
Interval to wait before restarting this outlet (seconds)
Type: STRING
Maximum length: 5
Value: 6

[outlet.2.desc]
Outlet description
Type: STRING
Maximum length: 20
Value: PowerShare Outlet 2

[outlet.desc]
Outlet description
Type: STRING
Maximum length: 20
Value: Main Outlet

[output.voltage.nominal]
Nominal output voltage (V)
Type: ENUM STRING
Maximum length: 3
Option: "200"
Option: "208"
Option: "220"
Option: "230" SELECTED
Option: "240"

[ups.delay.shutdown]
Interval to wait after shutdown with delay command (seconds)
Type: STRING
Maximum length: 10
Value: 20

[ups.delay.start]
Interval to wait before (re)starting the load (seconds)
Type: STRING
Maximum length: 10
Value: 30

[ups.load.high]
Load when UPS switches to overload condition (percent)
Type: STRING
Maximum length: 5
Value: 105

[ups.shutdown]
Description unavailable
Type: ENUM STRING
Maximum length: 10
Option: "disabled"
Option: "enabled" SELECTED

[ups.start.auto]
UPS starts when mains is (re)applied
Type: STRING
Maximum length: 5
Value: yes

[ups.start.battery]
Allow to start UPS from battery
Type: STRING
Maximum length: 5
Value: yes

[ups.start.reboot]
UPS reboots when power returns during shutdown delay
Type: STRING
Maximum length: 5
Value: yes

[ups.test.interval]
Interval between self tests (seconds)
Type: STRING
Maximum length: 8
Value: 2592000
```

## Advertised commands — discovery only

This is the listing from `upscmd -l`. Availability does not establish that a
command has been tested or that every advertised operation works on this unit.
None was invoked.

```text
Instant commands supported on UPS [eaton5p]:

beeper.disable - Disable the UPS beeper
beeper.enable - Enable the UPS beeper
beeper.mute - Temporarily mute the UPS beeper
beeper.off - Obsolete (use beeper.disable or beeper.mute)
beeper.on - Obsolete (use beeper.enable)
driver.killpower - Tell the driver daemon to initiate UPS shutdown; should be unlocked with driver.flag.allow_killpower option or variable setting
driver.reload - Reload running driver configuration from the file system (only works for changes in some options)
driver.reload-or-error - Reload running driver configuration from the file system (only works for changes in some options); return an error if something changed and could not be applied live (so the caller can restart it with new options)
driver.reload-or-exit - Reload running driver configuration from the file system (only works for changes in some options); exit the running driver if something changed and could not be applied live (so service management framework can restart it with new options)
load.off - Turn off the load immediately
load.off.delay - Turn off the load with a delay (seconds)
load.on - Turn on the load immediately
load.on.delay - Turn on the load with a delay (seconds)
outlet.1.load.off - Turn off the load on outlet 1 immediately
outlet.1.load.on - Turn on the load on outlet 1 immediately
outlet.2.load.off - Turn off the load on outlet 2 immediately
outlet.2.load.on - Turn on the load on outlet 2 immediately
shutdown.return - Turn off the load and return when power is back
shutdown.stayoff - Turn off the load and remain off
shutdown.stop - Stop a shutdown in progress
test.battery.start.deep - Start a deep battery test
test.battery.start.quick - Start a quick battery test
test.battery.stop - Stop the battery test
```

## Pi observations

- Debian GNU/Linux 13 (trixie), aarch64, kernel `6.18.60+rpt-rpi-v8`.
- About 415 MiB RAM; 266 MiB available and 148 MiB used at capture, as reported
  by `free -m`; approximately 414 MiB swap, unused in this sample.
- Root ext4 and boot FAT filesystems mounted read/write.
- NUT packages `nut-client` and `nut-server` 2.8.1-5.
- USB ID `0463:ffff`; host services `nut-server` and `nut-monitor` inactive.
- Pi had been running for approximately 1 hour 16 minutes.

The previously reported power-bank handover reboot and low Pi-input voltage
remain unresolved; this session did not retest the power path. See
[resilience proposal](RESILIENCE.md).

## References

[NUT variable listing and setting semantics](https://networkupstools.org/docs/man/upsrw.html),
[NUT command listing semantics](https://networkupstools.org/docs/man/upscmd.html),
[Eaton 5P1150IR specifications](https://www.eaton.com/gr/en-gb/skuPage.5P1150IR.html).
