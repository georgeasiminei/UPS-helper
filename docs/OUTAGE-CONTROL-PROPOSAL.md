# UPS control proposal for Vast.ai hosts

Date: 2026-11-07. Status: **proposal only; no controller deployed**.
George owns the operating-policy decision, equipment mapping and acceptance.
Implementation and controlled hardware tests are future work. Current work
retrieved UPS/Pi diagnostics only; it did not contact rented hosts or change
their power limits, workloads, listings or maintenance windows.

The [requirements](REQUIREMENTS.md) are authoritative for user-requested
behavior. Light and drastic reduction, Pi-driven Wake-on-LAN with retries, and
an always-running Pi policy are requirements. Values and implementation
choices below remain provisional until validated.

Local implementation has started: see [implementation status](IMPLEMENTATION.md)
for the observe-only service, YAML settings, JSON checkpoints and offline
simulation. This foundation cannot execute SSH or operate equipment; the
remaining live integrations and acceptance work below are still outstanding.

## Evidence, goals and constraints

The [live telemetry snapshot](UPS-TELEMETRY-2026-11-07.md) contains 92 variables,
33 writable-variable definitions and 23 advertised commands. At 18:16 local
time, the UPS reported mains online, 100% charge and 110 minutes of estimated
runtime at 0 W reported load. The rented machines are not yet UPS-connected.
Loaded runtime, host shutdown times, maximum combined demand and hardware
power-limit support are unknown.

The Eaton is rated **770 W and 1,150 VA total**, including all attached
equipment. Unrestricted load during the first minute, boot transients and
short CPU/GPU bursts must fit: software limiting after a minute cannot make an
undersized UPS safe. Eaton lists 11.5 minutes at half load for this model;
that is a manufacturer reference, not a measurement of this installation.
See [Eaton specifications](https://www.eaton.com/gr/en-gb/skuPage.5P1150IR.html).

| Priority | Required outcome | Current evidence |
| --- | --- | --- |
| Must preserve | Leave workloads alone during the first minute unless energy is critically low | User requirement; thresholds below proposed |
| Must preserve | Light reduction precedes a separate drastic stage during an ordinary outage | User requirement; per-host profiles unmeasured |
| Must preserve | Graceful shutdown completes before usable UPS energy runs out | Loaded runtime and shutdown time unmeasured |
| Must preserve | Cloud/API failure cannot block local protective actions | Design requirement; no implementation |
| Must preserve | Temporary overrides restore existing normal settings, including after host reboot | Existing host startup configuration uninspected |
| Must preserve | Pi or network failure has a defined recovery path | Pi handover resets previously observed |
| Must preserve | Pi never intentionally shuts down and resumes after reboot or physical battery exhaustion/power return | User requirement; complete power-return path unverified |
| Must preserve | Pi retries Wake-on-LAN until each configured recovery target is confirmed awake | User requirement; actual host/network support unverified |
| Must preserve | Announce two hours of Vast maintenance, expand coverage if recovery is delayed | Required behavior; API access and extension semantics unresolved |

## Recommended shape and alternatives

Use **NUT on the Pi, one small local policy service, and a small executor on
each managed host**. NUT owns USB telemetry; the policy service owns the outage
state and desired actions; the host executor owns actual CPU/GPU settings and
OS shutdown. SSH over the LAN can invoke the executor. A host-local watchdog
and cached shutdown deadline cover a lost Pi/SSH connection. Each executor must
be armed only for a host explicitly mapped to this UPS. Nothing should be armed
while hosts remain on ordinary mains power.

Keep any Vast API worker separate from the time-critical local action loop.
For maintenance changes after local Internet or Pi power is lost, use a small
independent Internet-connected coordinator with an incident lease. This can be
an optional later component; it is necessary if renewal must continue through
a long site outage. The coordinator may manage cloud notices, but cannot
override local electrical safety or infer successful recovery from silence.

| Option | Benefit | Cost / rejection reason |
| --- | --- | --- |
| Pi issues every SSH action without host support | Smallest initial deployment | Cannot shut down a host when the LAN or Pi fails; unsuitable as the sole protection |
| Pi policy plus host executor/watchdog | Local safety and explicit ownership, works without public Internet | Small host component, bounded leases, and conservative shutdown on lost control |
| Cloud-only policy | Independent maintenance renewal | Public Internet loss would disable electrical protection; rejected as safety authority |

NUT's `upsmon`/`upssched` can provide events, but time, battery, runtime and
per-host recovery need one explicit state machine. Coordinate NUT shutdown hooks
with it so the Pi is not inadvertently halted or the whole UPS switched off by
a second policy. The Pi must never be a managed-server shutdown target or run
a default local shutdown action as part of this outage policy. See [upsmon](https://networkupstools.org/docs/man/upsmon.html)
and [upssched](https://networkupstools.org/docs/man/upssched.html).

## Proposed initial thresholds

These values make the intended behavior reviewable. They are **not validated
operating settings** and must remain inactive until capacity and shutdown-time
checks pass.

Let `t` be elapsed time since confirmed loss of usable mains, `B` charge in
percent, and `R` a conservative remaining-runtime estimate. `OB` means on battery;
`OL` means mains online. Use status tokens, not input voltage alone.

Derive `R` from reported runtime after subtracting measurement age, detection
and actuation latency, and a measured allowance for optimistic estimates and
sudden load increases. Until a load-test envelope establishes that allowance,
`R` is a planning input, not a validated lower bound. Do not smooth away a low
reading or substitute the 110-minute idle estimate. A slow field refresh adds
to the uncertainty even if status polling is frequent.

Let `S` be the reserve needed to finish shutdown. Initially budget **8 minutes**
for planning. Replace it with at least `max(5 minutes, 2*Tstop + 1 minute)` after
measurement, where `Tstop` is the worst observed end-to-end shutdown duration
for the dependency sequence, including stopping workloads, local command
latency and storage flushes. Increase the margin if runtime estimates prove
optimistic. If loaded runtime cannot cover the grace period and this reserve,
the requirements need a larger UPS or lower normal load.

Evaluate emergency conditions first on every poll and during every action.
Within each row, any listed trigger is sufficient; escalation stays latched
until recovery. The first-minute exception is the emergency row only.

| Stage | Trigger while on battery | Proposed response |
| --- | --- | --- |
| Grace | `t < 60 s`, no emergency | Observe and log only; no host or cloud changes |
| Light reduction | `t >= 60 s`, no emergency | Apply the light CPU PL1/PL2 and per-GPU profile; verify results within a bounded 15 s stage budget |
| Drastic reduction | After attempting light reduction, and any of `t >= 120 s`, `R <= S + 3 min`, or `B <= 50%`; always after grace unless emergency | Apply the distinct drastic profile; verify within a bounded 15 s stage budget, shortened by the shutdown deadline |
| Announce outage | Immediately after attempting drastic reduction while still on battery | Request a two-hour Vast maintenance window; allow at most 15 s total API work, less if reserve requires |
| Graceful shutdown | Maintenance fails/is unreachable/unconfirmed within its budget, or `t >= 5 min` | Start OS shutdown independently of cloud success; complete within measured reserve |
| Emergency | `OB` plus UPS `LB`, or `R <= S`, or `B <= 20%`; an existing forced-shutdown state also requires immediate handling | Bypass grace and cloud waits; begin shutdown immediately; cap power only if it cannot delay shutdown |

For an outage continuing after successful maintenance scheduling, the default
above keeps hosts capped until five minutes elapsed or a safety threshold is
reached, whichever comes first. This is a proposal to balance short outages
against rented-workload interruption; it does not wait two hours to shut down.
The two-hour value describes expected unavailability announced to renters.
After the first minute, energy thresholds can cause light and drastic attempts
to follow immediately; no minimum dwell is required if reserve is tightening.
Emergency shutdown may skip either stage. Both stages use the same original
baseline, and reaching drastic must never reclassify the light profile as normal.

Caps and API calls must not block emergency evaluation. The 15-second stage
budgets are total bounded budgets across hosts/devices, with limited concurrent
work; one unresponsive target cannot hold up the others or a global deadline.
Budget detection, telemetry age, transport, lease expiration, any cap delay and
actual host shutdown against minimum usable loaded endurance, including the
case where the Pi fails immediately after mains loss. If that budget cannot
fit, reject activation rather than claiming the watchdog solves it.

If a cap stage fails, continue to the next stage or maintenance/shutdown with
the unreduced demand assumption. Never credit power savings until verified.
Reevaluate runtime after caps, but do not reverse an already-entered stage
because an estimate rises.
Missing or invalid charge/runtime cannot count as healthy energy. Do not wait
for the UPS's configured 15% low-battery signal; NUT warns that some devices
announce low battery late. See [NUT UPS configuration guidance](https://networkupstools.org/docs/man/ups.conf.html).

An overload or UPS fault needs a distinct immediate-risk path; do not apply the
ordinary grace period to a supply that cannot sustain its load. The actual fault
signals and available reaction time require hardware verification.

## CPU/GPU limits and restoration

Discover CPU model, writable RAPL constraints, GPU identities and supported
minimum/maximum limits in a later authorized host-inspection pass. No universal
watt limits can be selected from UPS telemetry alone. Configure a normal,
light and drastic profile for every supported device. Candidate tuning values:

| Profile | CPU PL1 / PL2 | GPU limit | Intent |
| --- | --- | --- | --- |
| Normal | Existing normal settings | Existing normal settings | Preserve existing operating policy |
| Light | Approximately 85–90% of the normal limits | Approximately 85–90% of the normal cap | Modest savings with limited workload impact |
| Drastic | Approximately 40–60% of normal PL1, with PL2 near the reduced PL1 | Lowest validated supported cap that produces substantial savings | Conserve energy aggressively before shutdown |

Every candidate must fit hardware-supported ranges and must never raise an
existing limit. Drastic must not exceed light for any controlled limit; record
unsupported settings explicitly rather than claiming a stage was applied.
These are candidate tests, not promised savings or safe performance levels for
the present renters. Exact watts remain open. Measure whole-system AC demand;
CPU/GPU limits do not cap RAM, disks, fans, PSU losses or network equipment.

Use supported runtime interfaces: Linux powercap/RAPL for compatible CPUs and
NVML or `nvidia-smi` for compatible NVIDIA GPUs. Discover constraint names and
units rather than assuming every CPU has identical constraint numbering. See
[Linux powercap](https://docs.kernel.org/power/powercap/powercap.html) and
[NVIDIA management interface](https://docs.nvidia.com/deploy/nvidia-smi/index.html).
NVIDIA classifies software power caps as GPU-initialization-lifetime state, so
GPU deinitialization can also remove them without a full host reboot. Detect
this through periodic read-back and reconcile fresh outage intent. See
[NVIDIA state lifetimes](https://docs.nvidia.com/deploy/driver-persistence/data-persistence.html).

For each host, record boot ID, hardware identity, pre-incident values, requested
values, current stage and read-back results. Capture the baseline before light
reduction and retain it through drastic reduction. Keep temporary override
state under `/run` on the host and reconcile it after a policy-process restart.
Keep only essential incident/recovery state and acknowledgements durably on
the Pi, using the storage/recovery conditions
in [the resilience proposal](RESILIENCE.md).

Do not alter firmware defaults or persist emergency values in startup scripts.
On host reboot discard the old override generation and let its normal startup
configuration establish normal limits. Verify this behavior on the actual
hardware, including services that normally enforce power settings. A controller
restart must not mistake an already-applied emergency value for the baseline.
A fresh decision after boot reconciles an ongoing confirmed outage without
resetting its grace timer; it is separate from replaying an old override. If
the Pi is unavailable, the conservative watchdog path applies. Verify CPU and
GPU reset behavior per platform instead of assuming all runtime interfaces
reset identically. Automatic reboot/power-on during an outage is not proposed.

When mains recovery is accepted, restore the saved pre-incident values only
where the current value still equals the automation's applied value. An operator
change takes precedence and should produce a reconciliation notice. Handle
partial multi-GPU and CPU writes individually; never reset every GPU blindly
to a manufacturer's default or remove an existing normal restriction.

## Vast maintenance and doubling the window

**Vast maintenance is a notification, not workload draining or rental blocking.**
Its [maintenance guide](https://docs.vast.ai/host/set-maintenance-window) says
running and stopped instance owners are notified, but instances keep running
and new rentals remain possible. The local shutdown deadline remains binding.
An OS shutdown can stop processes and flush host storage; it cannot guarantee
that a renter's training job has saved a resumable checkpoint.

Request a future start near the planned shutdown time and duration **2 hours**,
using the `power` category and an incident reason. If energy forces earlier
shutdown, use the earliest accepted future time and proceed locally without
waiting for the notice time. The API requires an ISO date-time `sdate`; the
CLI uses epoch seconds. Follow the selected interface, and use whole hours.
See [schedule API](https://docs.vast.ai/api-reference/machines/schedule-maint)
and [schedule CLI](https://docs.vast.ai/host/cli/schedule-maint).

The requested renewal policy should mean total coverage of **2 → 4 → 8 → 16
hours from the original maintenance start**, without creating overlapping
independent outage records. Check 15 minutes before each confirmed end time
and extend early enough to avoid a gap. Persist the intended end, observed
cloud end and ownership. Lack of a fresh recovery confirmation keeps the
incident open; alert if coverage cannot be confirmed.

**Extension is an unresolved integration requirement.** Published documentation
and the official client do not establish an in-place extension, overlap/replace
behavior, or safe duplicate scheduling. Do not implement repeated schedule calls
as if they were a verified extension. Establish supported behavior with Vast
or a safe test machine first. The independent coordinator can execute this
renewal policy only after those semantics are verified; without working
Internet anywhere, neither extension nor cancellation can reach Vast.

On recovery, cancel only controller-owned coverage after the machine is ready.
The documented [cancel API](https://docs.vast.ai/api-reference/machines/cancel-maint)
is machine-scoped and can remove scheduled windows. If unrelated windows exist,
do not call it blindly. Read/reconcile state first and leave an explicit pending
cleanup if selective cancellation cannot be guaranteed. Timed-out create/cancel
requests have uncertain outcomes; inspect current state before retrying so
retries do not send duplicate notices or remove somebody else's work.

If preventing new rentals is also desired, unlisting is a separate operation.
Vast says it stops new contracts without affecting existing ones in its
[hosting overview](https://docs.vast.ai/host/hosting-overview). Add it only as an
explicit extension of the agreed policy, coordinating ownership with any
existing price/listing automation. Restoration must preserve the previous
offers and later operator changes; do not assume a generic relist is equivalent.

## Network loss, stale telemetry and restarts

Poll status approximately every two seconds; full-variable refresh frequency
and per-field validity must be verified. Treat NUT stale-data responses,
driver disconnects and invalid values as unknown. A healthy TCP response alone
does not establish a fresh measurement. Track last successful UPS update and
last trustworthy runtime/charge separately from client read time.

Require valid, sufficiently recent status, runtime **and** charge to sustain
an on-battery safety lease; a missing field does not silently fall back to the
others. Validate range, units and age. If a driver provides no per-field update
timestamp, establish a conservative age bound from its verified polling and
stale-data behavior or declare the energy fields unknown. `driver.state=quiet`
and identical client reads are not source-update timestamps. The observed
30-second `pollfreq` must be included in the budget or deliberately reduced
and verified in a future configuration pass.

Proposed conservative fallback: after 30 seconds without trustworthy UPS data
or either required on-battery energy field, declare control degraded; after a
total 60 seconds without a valid safety
lease, each armed host caps demand and starts graceful shutdown. If power was
already known lost, obey the earlier cached shutdown deadline as well. These
deadlines must fit the measured energy budget. This trades availability for
protection: a prolonged Pi/LAN failure on otherwise healthy mains may shut down
hosts. That tradeoff needs explicit policy acceptance before arming.

The host lease can be renewed only when the Pi has fresh acceptable UPS data.
Carry the incident generation, host boot ID and remaining safe interval in
every control message. Anchor intervals to host-local monotonic receipt time,
subtracting a conservative transport allowance. Retain wall-clock timestamps
for reconciliation/audit, rather than trusting equal Pi/host clocks. At each
valid update set the shutdown deadline no later than the earlier of the
five-minute incident deadline and `now + max(0, R-S)`. A reboot loses monotonic
context and requires immediate reconciliation or the bounded fallback, with
no new grace period. A heartbeat reporting unknown UPS state must not silently
postpone a deadline. During healthy control, transient API loss alone is not an
electrical outage. It causes shutdown only if the on-battery policy has reached
its maintenance stage and cannot complete that stage within budget.

The Pi remains the policy owner while reachable. Watchdogs are bounded fallback
executors, not competing schedulers. Latch emergency decisions, make repeated
requests safe, reject obsolete generations, read back effects, and keep uncertain
outcomes separate from confirmed failures. No stale or missing telemetry alone
authorizes an outlet power cut. An unreachable host is not confirmed shut down;
continue other hosts and report the gap.

After Pi restart, obtain fresh UPS and host state and reconcile a valid incident
checkpoint. Preserve outage age and deadlines; do not restart a full grace
minute. Monotonic timers handle a running boot; cross-boot wall-clock deadlines
need a trustworthy clock. A Pi without valid history/time that boots on battery
must use the emergency/unknown-data fallback, not infer a fresh outage.
An existing forced-shutdown state also requires reconciliation rather than
assuming a brief `OL` report automatically cancels it.

Keep the Pi charger and LAN equipment powered through all host shutdowns. The
Pi's known power-bank handover reset and low input voltage remain deployment
blockers until corrected/accepted with recovery evidence. The full runtime of
the Pi bank and the network's separate UPS is unmeasured. A cloud worker cannot
repair a failed local control path.

The Pi's policy is to stay running throughout the outage, including after host
shutdown and UPS output loss. Its battery may last approximately 24 hours, but
that duration is unmeasured. If its battery physically runs out, the owner
reports that it starts again when power reaches it. Verify this full return
path and boot-enabled control; do not confuse battery exhaustion with a command
to halt the Pi. Reconnect and reconcile after either a brief handover restart
or a prolonged loss of Pi power, retaining per-host recovery intent.

## Recovery and required Wake-on-LAN

Require **two continuous minutes of fresh `OL`**, no on-battery/fault status,
and a validated energy reserve for a repeat outage before lifting caps on
hosts that stayed running. Initial conservative candidate: at least 50% charge
and enough energy at restored load to survive the grace minute plus shutdown
reserve. An idle runtime estimate while the hosts are off is insufficient proof.
Return to outage handling immediately if mains fails during recovery.

The servers do not automatically restart after graceful shutdown. The Pi must
use **Wake-on-LAN**, retrying until each configured recovery target is confirmed
awake. This is required behavior that remains unimplemented and untested.
The UPS's `ups.start.auto=yes` must not be treated as server restart handling.

For hosts already halted, propose **five minutes stable mains and at least
80% charge**, plus measured energy for staggered boot and an immediate repeat
outage, before waking them. These recovery gates remain candidate values. The
Pi can boot before the UPS or network has recovered; retry dependencies and
hold pending wakes until fresh power evidence passes the gates.

For each managed host, keep explicit desired recovery state and the expected
wake MAC, network path, host identity, normal profile and readiness checks in
private configuration. Persist shutdown intent and whether the host is a
recovery target before issuing shutdown. Preserve deliberate manual off/disable
intent; do not wake every discovered device. On every Pi boot, reconcile this
intent with current host state before resuming outstanding work.

Proposed per-host wake loop:

1. Recheck recovery gates and dependency/boot power headroom. Stagger hosts so
   normal startup limits and boot transients fit the UPS.
2. Probe the expected host. If not confirmed awake, send a Wake-on-LAN packet
   through its configured interface/network path and wait for a bounded period.
3. Check identity-aware reachability, for example authenticated SSH with the
   expected host key and host identity. A sent packet, successful sender exit
   status, ping, or open port alone is not confirmation that the intended server
   is awake.
4. Retry that target until confirmed awake. Candidate pacing: every 30 seconds
   for five minutes, then every minute up to 30 minutes, then every five minutes.
   There is **no automatic attempt-count cutoff**; report prolonged failure
   without abandoning the target. Use bounded probes and independent per-host
   progress so one server cannot starve other recovery work.
5. Once awake, stop wake packets for that host and check normal CPU/GPU settings,
   host services and workload readiness. A booted but unhealthy server remains
   pending readiness; more magic packets are not a readiness repair. Clear its
   owned maintenance only after readiness is confirmed.

Pause new wake attempts immediately on renewed mains loss, unsafe energy or
unknown power. Return awake hosts to outage handling and keep pending targets
for the next qualified recovery. If the Pi restarts or exhausts its battery
mid-loop, resume from durable intent after fresh-state reconciliation; do not
reset the outage grace timer. If a host later becomes unconfirmed while desired
on, re-enter reconciliation and the gated retry loop. Intentional operator
disable/off must suppress automatic waking.

Validate host firmware/NIC wake settings, the graceful-halt path, the actual
post-UPS-exhaustion power-return path and the Pi-to-host LAN route. A prior
successful packet-send command does not establish any of these. Startup must
restore normal host restrictions; old light/drastic overrides must not be
persisted as the next boot's normal settings.

After readiness checks, remove owned maintenance and any owned listing changes.
If the Internet is still down, retain and retry the cloud cleanup independently;
do not falsely report it complete or delete unrelated windows. Once shutdown
has committed, finish it and use the recovery path instead of attempting to
reverse a partly stopped OS. Do not cut UPS output or cycle outlet groups as
part of the initial policy: mapping, shutdown acknowledgement and restart
behavior need separate validation.

## Verification, ownership and next slices

No live-host experiment is justified by this proposal. Start with a recorder
and simulation that produce intended actions without executing them, then use
an isolated machine and scheduled host maintenance for physical tests.

| Check / missing evidence | Acceptance evidence | Owner / follow-up |
| --- | --- | --- |
| UPS-to-host mapping and capacity | Both W/VA ratings and transients fit at unrestricted worst load | George; hardware/load inventory |
| Shutdown budget and battery estimate | Measured workload stop, OS halt, and usable runtime at representative/worst load | George with implementation owner; controlled tests |
| Grace and emergency precedence | 59 s outage does nothing; 61 s caps; critically low energy bypasses grace | Backend implementation owner; deterministic simulation |
| Distinct reduction profiles | Ordinary outage applies light then drastic; original baseline retained; drastic limits never exceed light | Host/backend owners; simulation then isolated host |
| Cloud failure and timeouts | API unavailable/429/ambiguous response never consumes shutdown reserve | Integration owner; mocked API tests |
| Maintenance create/extend/cancel | Confirmed 2→4→8 coverage, safe retries, and unrelated windows retained | Vast integration owner; provider clarification/safe machine |
| Runtime-only overrides | Per-device read-back; exact restoration; host reboot removes emergency overrides; existing host startup policy preserved | Host integration owner; isolated host |
| LAN/USB/Pi failure | Armed watchdog meets cached deadline; no fresh grace on reboot; no unintended outlet cut | Backend/host owners; fault simulation then controlled tests |
| Pi power/storage | Stable input voltage, unattended recovery and durable minimal state as required | George; existing resilience plan and backup |
| Mains flapping and low recharge | No repeated lift/reapply loops; restart energy budget proven | Implementation owner; simulation and controlled test |
| Required Wake-on-LAN recovery | Repeated failed packets/probes do not exhaust attempts; expected host identity confirms awake, then readiness | George and host integration owner; isolated host/network |
| Pi restart/battery exhaustion during waking | No intentional Pi shutdown; automatic return and pending per-host recovery resume after power returns | George and implementation owner; controlled tests |
| Power fails during staggered waking | New wakes pause; awake hosts return to outage protection; outstanding targets retained | Host/backend owners; simulation then controlled test |

Recommended order: approve/tune policy and equipment mapping; implement a
read-only recorder and simulation; resolve Vast semantics; deploy local
executors, watchdogs and the required Pi Wake-on-LAN loop on isolated hosts;
validate both outage stages and recovery on representative load; then arm only
the verified UPS-connected machines. Coordinator placement and separate
unlisting remain design choices; required maintenance renewal still needs its
provider semantics verified.

The recommendation favors a small local service over multiple local services
or a cloud dependency for electrical safety. The proposed costs are a host
component and conservative shutdown during prolonged control loss; the
availability tradeoff still needs explicit acceptance. Loaded runtime too
short for the grace/reserve, unsupported host controls, or an
unreliable Pi power path would require revisiting the hardware/design before
activation.
