# Observe-only implementation

This foundation reads UPS telemetry, evaluates a tentative outage policy, and records plans for inspection. It cannot shut down or start machines, change power limits, or otherwise provide physical protection. Policy defaults are provisional and need calibration and acceptance against the actual equipment and operating conditions.

The implementation contains no SSH, subprocess, wake-on-LAN UDP, or Vast API action adapter. The NUT client connects only to loopback and sends the read-only `LIST VAR` request. A planned action is logged with `executed: false`; it is not evidence that an effect occurred. Monitor mode does not probe hosts or supply maintenance confirmations, so missing facts do not become fabricated confirmations. Offline simulations can supply host and maintenance facts to exercise policy paths, but those supplied facts verify simulated behavior only, not hardware behavior.

## Local setup and commands

Python 3.9 or newer and PyYAML 6 are required at runtime; pytest 8 is the optional test dependency. From the repository root, create a local environment and install the project in editable mode:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e '.[test]'
.venv/bin/ups-helper --help
.venv/bin/ups-helper config-check --config config/observe.example.yaml
```

The command forms are:

```text
ups-helper config-check --config FILE
ups-helper simulate --config FILE --scenario FILE
ups-helper monitor --config FILE [--once] [--state PATH]
```

Use `ups-helper COMMAND --help` for argparse's full option help. Configuration validation requires explicit `version: 1` and `mode: observe`; live modes and unknown configuration fields are rejected.

To try the complete offline outage/recovery simulation without connecting to
NUT, run the included scenario:

```sh
.venv/bin/ups-helper simulate --config config/simulation.example.yaml --scenario examples/outage-and-recovery.json
```

Events have ordered Unix-second timestamps, string-valued NUT variables, and optional host facts (`awake`, `ready`, `shutdown_confirmed`, `boot_id`) and per-host boolean maintenance facts. Simulation prints JSON lines for plans followed by a summary; it uses neither NUT nor a checkpoint.

Each event is a complete observation: omitted energy/host/maintenance fields
are unknown, not automatically carried forward as current measurements. The
included example provides a synthetic runtime and explicit simulated host/cloud
confirmations; it does not describe the real servers or the monitor in standby.

The planner retains incident age, stage, affected hosts, desired coverage and
retry counts. In-process service timing uses a monotonic clock anchored at
startup. A restarted process always observes a new continuous stable-mains
period before proposing wake actions. Cross-boot wall-clock trust, complete
hardware freshness guarantees and host-side watchdog execution still need
validation before implementing live operation.

To observe a local NUT server once, optionally run:

```sh
mkdir -p .local
.venv/bin/ups-helper monitor --config config/observe.example.yaml --once --state .local/observe-state.json
```

An unavailable NUT server produces an unknown observation rather than stopping the long-running monitor; a successful command does not imply the UPS is healthy. The monitor takes an exclusive sidecar checkpoint lock for its run, validates existing state, and saves meaningful state changes before logging plans. A corrupt checkpoint or inaccessible lock/state path causes an error instead of silently discarding state. Status and plan records are JSON lines; raw NUT variables and device serials are not logged. `SIGINT` and `SIGTERM` stop the Python loop, not attached equipment.

## Configuration, state, and service

YAML is operator configuration: NUT connection settings, service timing and state location, policy thresholds, and host profiles. The examples in `config/` show the supported structure. JSON is used separately for persisted controller state, structured log records, and offline scenario input. Treat checkpoint files as runtime state, not configuration or proof of applied equipment actions.

Copy the observation example to a private `config/local.yaml` and edit that
file; `config/local*.yaml` is git-ignored. The deployed counterpart will be
`/etc/ups-helper/config.yaml`. Configuration is validated at startup; reload it
by restarting only the helper service after editing. There is no hot reload or
live/armed execution setting in this release. `hosts[].enabled` only includes
a host in planning. It does not enable network actions.

The included `deploy/ups-helper.service` describes a future local systemd deployment. It expects the virtual environment at `/opt/ups-helper/.venv`, configuration at `/etc/ups-helper/config.yaml`, and uses `DynamicUser` with `StateDirectory=ups-helper` for `/var/lib/ups-helper`. The unit restarts on failure, writes output to the journal, and does not require NUT to remain available. It enables filesystem protections including `ProtectSystem=strict`. A custom `service.state_path` or `--state` must be writable within the service sandbox, including its sidecar lock and temporary checkpoint files. Checkpoint persistence must be verified under the intended read-only OS and systemd configuration before relying on restart continuity.

No installation or service enabling on the Pi was performed as part of this work.

## Work before live operation

Live adapters and confirmation mechanisms remain to be designed, implemented, and tested, along with a watchdog, persistent NUT behavior and source freshness verification, loaded runtime and policy calibration, Vast integration extensions, and wake-on-LAN topology verification. End-to-end failure testing and explicit acceptance on the actual installation are still required. This observe-only release is a foundation for that work; it does not implement the complete protection requirements.

## Validation and CI

Run `.venv/bin/python -m pytest -q` for the local suite. The initial implementation
passed 135 tests on Python 3.9, including loopback fake-NUT integration tests;
the package wheel and the supplied offline scenario were also verified.
No hardware or server tests were run. `deploy/test-workflow.example.yaml` is an
inactive GitHub Actions template for Python 3.9 and 3.13. The current GitHub
connection lacks workflow-write permission, so CI is not installed and Linux /
Pi Python validation remains outstanding.
