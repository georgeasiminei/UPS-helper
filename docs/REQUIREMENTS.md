# UPS control requirements

Updated: 2026-11-13. Owner: George. Status: **documented requirements;
implementation started as a local observe-only foundation; live deployment
and hardware acceptance tests remain future work**. See
[implementation and configuration](IMPLEMENTATION.md).

This file is the source of truth for the requested behavior. The
[control proposal](OUTAGE-CONTROL-PROPOSAL.md) supplies candidate thresholds and
implementation choices; the [Pi resilience proposal](RESILIENCE.md) covers
controller power, storage and recovery. Proposed numbers and mechanisms are
not accepted or validated merely because they appear in those documents.
The [original telemetry report](UPS-TELEMETRY-2026-11-07.md) and
[current two-UPS hardware report](HARDWARE-2026-11-13.md) record observations,
not configured policy.

## Scope and current authorization

- **SCOPE-01 — Local implementation; live actions disabled.** The original
  implementation task was restricted to local work without SSH. The owner
  separately authorized read-only Pi diagnostics on 2026-11-13; those checks
  do not authorize deployment or equipment-changing actions.
  Keep equipment-changing actions disabled: no CPU/GPU limits, Vast changes,
  server shutdown/wake, outlet changes or live power tests. Servers are live,
  rented on Vast.ai. The original monitor-in-standby description is historical:
  the latest UPS readings were 418 W on the 1550 and 46 W on the 1150. Which
  equipment is supplied by each UPS has not been verified; do not infer server
  placement or validated runtime from these readings.
- **SCOPE-02 — Explicit equipment mapping.** Maintain a configured inventory of
  managed hosts, the UPS protecting each host, dependencies, and wake targets.
  The Pi controller is not a server shutdown target. Machine identities,
  addresses, credentials and MAC addresses belong in private configuration,
  not these public requirements.
- **SCOPE-03 — Existing verification.** UPS USB communication and read-only
  telemetry collection have passed for both UPSes. The 1550 repeatedly loses
  its USB connection; successful point reads do not establish reliable
  monitoring. Persistent monitoring and outage control
  are not currently deployed. The local observe-only monitor and simulator do
  not provide physical outage protection or claim verified live control.

## Outage detection and sequence

- **OUTAGE-01 — One-minute grace.** During the first minute without usable
  mains, do not impose workload restrictions, change cloud maintenance or
  shut down servers unless battery energy is critically low. Observation and
  logging may continue.
- **OUTAGE-02 — Combined triggers.** Escalation must combine elapsed outage
  time, conservative estimated remaining runtime and battery charge. Exact
  thresholds are still to be selected and validated under representative load;
  the existing idle runtime estimate is insufficient.
- **OUTAGE-03 — Two reduction stages.** Following grace, first apply a **light**
  power reduction. If the outage persists or energy thresholds require it,
  escalate to a distinct **drastic** reduction. Use CPU PL1, CPU PL2 and GPU
  power limits where the actual host hardware supports them.
- **OUTAGE-04 — Maintenance then shutdown.** After the reduction stages,
  attempt to place affected machines in Vast maintenance for two hours. If
  maintenance cannot be confirmed, continue to graceful shutdown. Successful
  maintenance must not postpone shutdown past the local safety deadline.
- **OUTAGE-05 — Emergency precedence.** Critically low energy or an imminent
  UPS supply failure overrides grace, stage dwell times and cloud waits. The
  controller must be able to advance through or skip ordinary stages so that
  shutdown starts while sufficient energy remains. It must not spend the
  shutdown reserve proving that a power cap or API call succeeded.
- **OUTAGE-06 — Graceful host shutdown.** Use an orderly host shutdown sequence
  with enough measured reserve for workloads, OS services and storage. Treat
  unknown command outcomes separately from confirmed shutdown. Rental jobs
  cannot be assumed to support application-level checkpointing.

## Temporary CPU/GPU restrictions

- **POWER-01 — Different profiles.** Define normal, light and drastic profiles
  per host/device. Light reduction should minimize workload impact; drastic
  reduction should substantially reduce demand. The drastic profile must not
  raise any limit above the light profile; neither stage may increase a normal
  limit. Exact watts and any percentage targets remain proposed tuning values.
- **POWER-02 — Runtime changes only.** Both reduction stages are temporary.
  Preserve normal firmware and persistent startup restrictions. A server
  restart must discard the incident's overrides and return to its normal
  startup limits; verify this on each supported platform. If an outage is still
  active, any new limit decision must use fresh state and the existing outage
  deadline rather than replaying stale overrides or starting a new grace period.
- **POWER-03 — Preserve the original baseline.** Save the pre-incident settings
  once. Escalating from light to drastic must not overwrite that baseline with
  the light values. After a Pi or policy-process restart, reconcile the active
  stage and actual host settings before applying or restoring anything.
- **POWER-04 — Recovery restoration.** After power recovery is accepted,
  remove the restrictions this incident imposed and restore the appropriate
  normal/pre-incident settings. Preserve later operator changes and pre-existing
  restrictions. Track partial CPU/GPU success and verify each changed value.

## Maintenance and connectivity

- **MAINT-01 — Initial duration.** Request two hours of Vast maintenance for
  affected machines. The maintenance duration is an announcement of expected
  unavailability, not permission to run on battery for two hours.
- **MAINT-02 — Double coverage.** If recovery has not completed, extend
  maintenance coverage to double its previous duration: **2 → 4 → 8 → 16 hours**
  and so on. Renew before confirmed coverage expires. The proposal interprets
  this as total coverage measured from the original maintenance start; exact
  provider extension semantics still need verification.
- **MAINT-03 — Clear on recovery.** Remove incident-owned maintenance after the
  affected machine has recovered and is ready. Preserve unrelated/operator
  maintenance. If Internet/API access is unavailable, retain the pending
  operation and reconcile/retry when access returns.
- **MAINT-04 — Internet-independent safety.** Public Internet may fail during
  an outage. Cloud calls must have bounded attempts and must never prevent
  local power reduction or graceful shutdown. UPS-backed switches do not prove
  LAN/SSH availability; define and validate a separate local-control-loss
  fallback before activation.
- **MAINT-05 — API limitations remain open.** Vast maintenance is a notice;
  it neither stops workloads nor blocks new rentals. Published extension and
  selective cancellation semantics must be resolved before claiming automatic
  renewal/cleanup works. An independent Internet-connected coordinator is a
  proposed way to maintain notices while the Pi/site is unreachable. With no
  working route to Vast, cloud maintenance changes cannot be completed.

## Server recovery and Wake-on-LAN

- **WAKE-01 — Required recovery mechanism.** Servers shut down gracefully do
  not restart by themselves. The Pi must wake the configured recovery targets
  using **Wake-on-LAN** after usable mains and adequate energy have returned.
  Automatic server recovery is required functionality, not an optional future
  enhancement. Actual activation still requires hardware/network validation.
- **WAKE-02 — Retry until confirmed awake.** For each target, keep attempting
  Wake-on-LAN until the Pi confirms that the expected server is awake. Sending
  a magic packet, completing a command, or observing a ping response alone is
  not sufficient confirmation. There must be no fixed retry-count cutoff that
  silently abandons a required host. Retries must be paced and failures visible.
- **WAKE-03 — Separate awake from ready.** Confirm identity and host reachability
  (for example, authenticated SSH to the expected host), then check normal
  CPU/GPU limits and host/workload readiness before declaring full recovery or
  clearing its maintenance. If awake but not ready, keep checking readiness;
  do not assume more wake packets repair a running host.
- **WAKE-04 — Recovery gates and ordering.** Begin or resume waking only while
  fresh power observations satisfy the chosen recovery thresholds. Stagger
  boots according to power headroom and dependencies. If power fails again or
  becomes unknown, pause new wake attempts and return to outage handling for
  hosts already awake. A renewed outage must not be hidden by an old wake task.
- **WAKE-05 — Survive interruptions.** Persist per-host desired recovery state,
  whether shutdown was requested/confirmed, and wake/readiness progress so a Pi
  reboot or complete battery exhaustion does not lose pending recovery work.
  On return, inspect actual host state before continuing; skip already-awake
  hosts and resume retries for outstanding targets. Preserve deliberate manual
  disable/off intent instead of waking every host indiscriminately.
- **WAKE-06 — Validate the actual power path.** Verify Wake-on-LAN from graceful
  halt, after the UPS output has been lost and restored, and after switch/LAN
  restoration. Define the private per-host wake MAC, interface/network path,
  expected identity, readiness checks and dependency order. Sending a broadcast
  over an unverified route is not a recovery guarantee.

## Pi lifecycle and long outages

- **PI-01 — Never intentionally shut down.** The outage automation must never
  shut down the Pi. Exclude it from managed-server shutdown and prevent NUT's
  default local shutdown behavior from halting it. The Pi continues monitoring
  and recovery work for as long as its power supply supports it.
- **PI-02 — Separate battery supply.** The Pi is powered through its own battery,
  charged from the UPS. It may have approximately 24 hours of endurance; this
  is an estimate/goal, not an established guarantee. UPS exhaustion or missing
  USB telemetry does not itself mean the Pi has lost power.
- **PI-03 — Restart on disconnect is possible.** The owner considers a restart
  on source disconnection unlikely in ordinary operation, but it can happen;
  the earlier high-load handover restart remains a recorded observation.
  Controller, USB and networking recovery must be automatic, with no fresh
  outage grace period or loss of pending server recovery.
- **PI-04 — Physical battery exhaustion.** During a sufficiently long outage
  (possibly 24+ hours), the Pi may lose power when its own battery is exhausted.
  This physical loss is distinct from an intentional OS shutdown. The owner
  reports that the Pi starts again when power reaches it; verify the complete
  UPS → battery → Pi power-return path without manual intervention.
- **PI-05 — Resume after any boot.** Start monitoring and control automatically.
  Reconnect with paced retries to UPS, LAN and hosts; reconcile durable state
  and trustworthy time; resume required Wake-on-LAN after recovery gates pass.
  A stopped/empty UPS or missing network must not cause the Pi to halt itself.
- **PI-06 — Bounded resources and durable essentials.** Support long dependency
  outages within the Pi Zero 2 W's memory/storage limits. Bound logs and retry
  work. Preserve only essential incident/recovery progress durably, accounting
  for any chosen read-only filesystem design and unexpected power loss.

## Acceptance scenarios

These are required checks for a future implementation, not tests executed by
this documentation change.

| Scenario | Required result / requirement coverage |
| --- | --- |
| Short outage with adequate energy | No host/cloud action before the first minute; OUTAGE-01 |
| Persistent outage | Light → drastic → maintenance → graceful shutdown, unless emergency advances the sequence; OUTAGE-02–06 |
| Critically low energy during grace or an action | Shutdown reserve takes precedence; OUTAGE-05 |
| Light → drastic → recovery | Original normal limits restored, no light-baseline substitution; POWER-01–04 |
| Host reboot after either cap stage | Incident overrides gone, normal startup restrictions intact; POWER-02 |
| Internet/API unavailable or ambiguous | Local safety continues; cloud result recorded/reconciled; MAINT-01–05 |
| Outage exceeds maintenance coverage | Confirmed 2 → 4 → 8 coverage, or visible pending renewal when unreachable; MAINT-02, MAINT-05 |
| One server ignores several magic packets | Other hosts progress; retries continue until that server is confirmed awake; WAKE-01–03 |
| Server awake but not ready | Stop treating it as asleep; retain pending readiness/maintenance cleanup; WAKE-03 |
| Power fails during a wake sequence | Pause new wakes, protect awake hosts, resume only after fresh recovery gates; WAKE-04 |
| Pi resets while reducing power, shutting down, or waking | Services resume and reconcile each host without losing intent or resetting grace; POWER-03, WAKE-05, PI-03, PI-05 |
| UPS exhausted while Pi battery remains | Pi stays active, retries dependencies, issues no self-shutdown; PI-01–02 |
| Pi battery depleted, then power restored | Pi boots automatically, reconnects, and resumes pending recovery; WAKE-05, PI-04–05 |
| Automatic host/NUT shutdown path | Managed servers halt; Pi remains running; PI-01 |
| Missing/corrupt checkpoint or untrusted time | Explicit recovery/unknown state; no invented host identity, grace reset, or blind outlet cut; PI-05–06 |

## Decisions and measurements still open

The user has specified the behavior above; implementation parameters still need
evidence. See the proposal for candidate values, keeping these distinctions:

- Light/drastic watt limits and escalation thresholds need CPU/GPU capability,
  unrestricted peak load, loaded battery runtime and shutdown-duration data.
- Recovery stability/recharge thresholds, wake pacing, readiness checks and boot
  concurrency are proposed settings, not confirmed hardware behavior.
- Prolonged local control loss needs a selected fallback. The current proposal
  favors conservative host shutdown, accepting possible shutdown on healthy
  mains if the Pi/LAN fails; that availability tradeoff is not yet accepted.
- Maintenance renewal/cancellation semantics, coordinator placement and whether
  separate unlisting is desired remain open. Do not equate maintenance with
  rental blocking.
- Pi battery endurance, automatic return after complete depletion, storage
  resilience and post-outage Wake-on-LAN must be tested in the real topology.
