# Restart and filesystem resilience proposal

Recorded on 2026-11-07. Status: recommendation, not deployed. George is the
decision and operational owner; implementation and acceptance testing remain
future work. The intended device is a small, dedicated UPS controller.

## Evidence and priorities

The owner reproduced a Pi restart when removing the power bank's charging
input with at least three CPU cores loaded (`stress -c 3`). No restart has
been observed on input connection in the tests performed. This asymmetry is
observed behavior, not a guarantee for every load, bank state, or temperature.
Typical reported consumption is below 1 W. The goal is at least 24 hours of
operation from the 10 Ah bank, including recovery after a restart.

A read-only SSH inspection found:

| Item | Current observation |
| --- | --- |
| Root filesystem | SD-card ext4, mounted read/write |
| Boot filesystem | SD-card FAT, mounted read/write |
| RAM reported to Linux | About 415 MiB |
| `/tmp` | tmpfs |
| Swap | `/dev/zram0`, about 415 MiB; no disk swap listed |
| System journal configuration | `Storage=volatile` |
| Setup tooling | `raspi-config` available; systemd 257 |

Protecting bootability and preventing unintended equipment power actions take
priority over retaining every telemetry sample. The 24-hour runtime goal needs
measurement. No Pi settings were changed during this inspection.

## Recommended storage layout and tradeoffs

Use a read-only OS with a RAM-backed overlay, and write-protect the boot
partition after installing and validating the services and configuration.
Raspberry Pi OS provides both settings through `raspi-config`. This directs
ordinary OS changes into disposable RAM; changes there disappear on reboot.
Updates and configuration changes need a planned maintenance procedure that
makes them persistent before returning to read-only operation. See
[Raspberry Pi overlay configuration](https://www.raspberrypi.com/documentation/computers/configuration.html#enable-or-disable-overlay-file-system).

Keep runtime sockets, locks and temporary files in RAM. Retain volatile logging
and zram; avoid introducing SD-backed swap. Bound log, overlay and temporary
data growth because RAM is limited. The largest default tmpfs sizes are limits,
not preallocated memory. If retaining logs across a reboot is necessary, send
them to another host while connectivity is available; loss of that host must
not prevent local control. See [journald storage settings](https://www.freedesktop.org/software/systemd/man/257/journald.conf.html).

Keep only essential recovery checkpoints in a small, separately mounted,
writable location outside the RAM overlay, if cross-reboot history is needed.
This could be a dedicated ext4 data partition; it remains exposed to interrupted
writes and shares the same physical SD card. Provisioning it requires a backup
and an explicit layout plan. Do not enable an overlay while assuming a normal
file under the overlaid root will retain checkpoints across reboot.

For a small checkpoint file, write a temporary file in the same directory,
flush it with `fsync`, atomically replace the previous file, then `fsync` the
directory, checking all errors. Record only meaningful state transitions;
continuous sensor polling does not need durable writes. Validate the saved
schema and content at startup; missing or invalid state enters recovery mode.
These operations rely on storage honoring flushes and do not guarantee survival
of arbitrary hardware faults. See [Linux fsync documentation](https://man7.org/linux/man-pages/man2/fsync.2.html).

Alternatives considered:

| Option | Benefit | Cost or limitation |
| --- | --- | --- |
| Keep the whole SD card writable | Simple updates and persistent logs | More routine writes exposed to the known reset condition |
| Entirely read-only, reconstruct everything | Fewest persistent writes; simplest storage | Prior outage timing and ambiguous action history may be unavailable |
| Read-only OS plus minimal durable checkpoints | Protects OS from routine writes while retaining essential history | Separate writable storage and careful recovery logic required |

The third option is the recommendation when policy requires retained timing or
action history. Prefer the second if all necessary state can safely be rebuilt.
Keep a tested restore image. Ext4 journaling helps structural consistency but
does not guarantee the content of a file interrupted during a write, and a
read-only design cannot promise an SD card will never fail. See
[Linux ext4 journaling](https://www.kernel.org/doc/html/latest/filesystems/ext4/journal.html).

## Controller authority and recovery

Use one local controller as the owner of shutdown sequencing. NUT supplies live
UPS observations; each managed device supplies its actual operating state.
Saved progress is supporting evidence, not authority to cut power blindly.
Coordinate any NUT `upsmon` shutdown behavior with this controller so the two
do not independently issue conflicting final power commands.

On every boot or controller restart:

1. Connect to NUT with timeouts and paced retries. Missing, stale or incomplete
   data means **unknown**, not mains online or proof of battery exhaustion.
2. Read current UPS and equipment state, then reconcile any valid checkpoint.
   An exhausted UPS may be unpowered and unavailable over USB; keep retrying
   without rebooting the Pi or declaring mains restored.
3. Resume only actions safe to repeat. Record action intent before an external
   command, verify effects where possible, and record the observed result.
   A reset between sending and acknowledging a command leaves its outcome
   uncertain. Reconcile it instead of automatically replaying a power cut.
   A saved intent can mean the command was never sent or that it already took
   effect. When device feedback cannot resolve this, mark it unresolved;
   suppressing replay can leave work undone, while replay can duplicate it.
   Safe fallback and rearming conditions must be selected for each device.
4. Retain outage deadlines when valid. Monotonic timers do not span reboots;
   wall-clock deadlines require trustworthy time. If the Pi boots on battery
   with no valid history or clock, do not restart a full grace period silently.
   Apply an explicit fallback using fresh battery/runtime/low-battery evidence.
   When that evidence is unavailable too, retain an unknown state and retry;
   the proposed default is no newly inferred outlet power cut. This avoids an
   unverified destructive action but can leave equipment exposed to eventual
   battery exhaustion. George must choose the final missing-data policy.

There is no general exactly-once guarantee for an external power command across
an arbitrary reset without device-side support. A lost acknowledgement must
not be interpreted as proof that the command failed.

Run NUT and the controller as boot-enabled systemd services. Use supervised
restart with a delay, and ensure start-rate limits do not permanently defeat
recovery during a long USB/network outage; expected dependency loss should be
handled inside the running service. A watchdog can later address hangs if
supported and tested; it cannot bridge an electrical power dip. See
[systemd service restart behavior](https://www.freedesktop.org/software/systemd/man/257/systemd.service.html).

Keep workloads small, bound concurrent device operations, and consider a CPU
quota for the controller. A quota is averaged CPU time for that service, not an
instantaneous whole-Pi power limit. Other services, kernel activity and boot
remain outside it. The stress result justifies avoiding heavy work but does
not prove a software limit eliminates resets. See
[systemd CPU resource control](https://www.freedesktop.org/software/systemd/man/257/systemd.resource-control.html).

## Runtime and verification

If the bank's 10 Ah label refers to a nominal 3.7 V cell voltage, its nominal
energy is about 37 Wh, not 50 Wh at the 5 V output. At a total 1 W load the
ideal calculation is 37 hours before conversion losses and bank overhead.
Thus 24 hours is plausible, not established: actual usable capacity, efficiency,
bank cutoff behavior, peripherals, and the complete load profile determine it.

Before claiming acceptance, George and the implementation owner should verify:

| Scenario | Required evidence |
| --- | --- |
| Abrupt reset after read-only setup | OS boots with persistent configuration intact; temporary overlay writes disappear |
| Reset during an equipment action | Controller reconciles uncertainty; no unintended repeat power cut |
| Boot already on battery | Fresh UPS state obtained; no accidental new full grace period |
| USB/network absent for an extended period | Paced retry and bounded memory/logging; recovery when connectivity returns |
| Invalid or missing checkpoint | Recovery mode rather than blind use of saved commands |
| Checkpoint store missing, unmountable, full, or failing `fsync` | Error surfaced; no false claim of durable progress or unsafe action replay |
| Charging input removed at maximum tested load | Reset, if it occurs, leads back to working monitoring without manual repair |
| 24 hours on the bank with representative work and a restart | Monitoring remains available when dependencies are powered; elapsed time and remaining energy recorded |
| Maintenance and image restoration | Configuration changes persist deliberately, read-only protection returns, backup restores |

Prepare a known-good backup before further interruption tests. First validate
service restart and recovery on stable power, then enable and check read-only
operation; perform controlled power-interruption and endurance testing last.
If the policy cannot resolve ambiguous actions safely, revisit the policy or
device integration before adding automation. No acceptance tests in this table
have been executed as part of this proposal.
