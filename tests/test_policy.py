import pytest

from ups_helper.config import Config, HostConfig
from ups_helper.model import HostFacts, State, Telemetry
from ups_helper.policy import Engine


NAME = "server-a"
AWAKE = {NAME: HostFacts(awake=True, ready=True, boot_id="boot-a")}
ASLEEP = {NAME: HostFacts(awake=False, shutdown_confirmed=True)}
CONFIRMED = {NAME: True}


def sample(at, status="OB", charge="100", runtime="3600", age=0):
    values = {"ups.status": status}
    if charge is not None:
        values["battery.charge"] = charge
    if runtime is not None:
        values["battery.runtime"] = runtime
    return Telemetry.from_variables(values, at, age)


def engine(extra_hosts=()):
    return Engine(Config(hosts=(HostConfig(NAME, enabled=True),) + extra_hosts))


def prime(e):
    e.step(sample(1000, "OL"), AWAKE)
    return e.step(sample(1001), AWAKE)


def kinds(actions):
    return [a.kind for a in actions]


def shutdown_and_recover(e):
    prime(e)
    e.step(sample(1121), AWAKE, CONFIRMED)
    assert "shutdown" in kinds(e.step(sample(1301), AWAKE, CONFIRMED))
    e.step(sample(1302, "OL"), ASLEEP, CONFIRMED)
    return e.step(sample(1602, "OL"), ASLEEP, CONFIRMED)


def test_normal_outage_grace_two_stages_then_deadline():
    e = engine()
    assert prime(e) == []
    assert e.step(sample(1060), AWAKE) == []
    assert kinds(e.step(sample(1061), AWAKE)) == ["power_light"]
    assert kinds(e.step(sample(1121), AWAKE, CONFIRMED)) == ["power_drastic", "maintenance_request"]
    assert e.step(sample(1299), AWAKE, CONFIRMED) == []
    assert kinds(e.step(sample(1301), AWAKE, CONFIRMED)) == ["shutdown"]


@pytest.mark.parametrize("values", [
    {"charge": "20"}, {"runtime": "500"}, {"status": "OB LB"},
    {"status": "FSD"}, {"status": "OB OVER"}, {"charge": "10", "runtime": None},
])
def test_emergency_bypasses_grace_and_cloud(values):
    e = engine()
    prime(e)
    planned = kinds(e.step(sample(1002, **values), AWAKE))
    assert "shutdown" in planned
    assert not set(planned).intersection({"power_light", "power_drastic", "maintenance_request"})


def test_conservative_runtime_subtracts_age_and_error():
    e = engine()
    prime(e)
    assert "shutdown" in kinds(e.step(sample(1002, runtime="560", age=30), AWAKE))


def test_boot_on_battery_does_not_create_grace_even_with_old_online_checkpoint():
    e = Engine(Config(hosts=(HostConfig(NAME, enabled=True),)), State(seen_online=True))
    assert kinds(e.step(sample(1000))) == ["shutdown"]


@pytest.mark.parametrize("missing", ["charge", "runtime"])
def test_missing_energy_does_not_postpone_shutdown_indefinitely(missing):
    e = engine()
    prime(e)
    e.step(sample(1002, **{missing: None}), AWAKE)
    assert "shutdown" not in kinds(e.step(sample(1061, **{missing: None}), AWAKE))
    assert "shutdown" in kinds(e.step(sample(1062, **{missing: None}), AWAKE))


def test_maintenance_timeout_is_not_success_and_forces_planned_shutdown():
    e = engine()
    prime(e)
    e.step(sample(1121), AWAKE)
    assert "shutdown" not in kinds(e.step(sample(1135), AWAKE))
    assert kinds(e.step(sample(1136), AWAKE)) == ["shutdown"]


def test_declined_maintenance_does_not_wait_for_budget():
    e = engine()
    prime(e)
    assert "shutdown" in kinds(e.step(sample(1121), AWAKE, {NAME: False}))


def test_escalation_latches_when_runtime_estimate_improves():
    e = engine()
    prime(e)
    e.step(sample(1061, charge="45"), AWAKE, CONFIRMED)
    assert e.state.stage == 2
    assert e.step(sample(1062), AWAKE, CONFIRMED) == []
    assert e.state.stage == 2


def test_wake_is_retried_until_awake_then_readiness_is_separate():
    e = engine()
    assert kinds(shutdown_and_recover(e)) == ["wake"]
    assert e.step(sample(1620, "OL"), ASLEEP, CONFIRMED) == []
    assert kinds(e.step(sample(1632, "OL"), ASLEEP, CONFIRMED)) == ["wake"]
    waking = {NAME: HostFacts(awake=True, ready=False, boot_id="boot-b")}
    assert kinds(e.step(sample(1633, "OL"), waking, CONFIRMED)) == ["check_readiness"]
    assert e.step(sample(1663, "OL"), waking, CONFIRMED) == []
    ready = {NAME: HostFacts(awake=True, ready=True, boot_id="boot-b")}
    assert kinds(e.step(sample(1664, "OL"), ready, CONFIRMED)) == ["maintenance_cancel"]
    assert e.state.outage_since is not None  # Not a confirmed cloud cancellation.
    e.step(sample(1665, "OL"), ready, {NAME: False})
    assert e.state.outage_since is None


def test_retries_have_no_attempt_count_cutoff():
    e = engine()
    shutdown_and_recover(e)
    for at in range(1902, 100000, 300):
        actions = e.step(sample(at, "OL"), ASLEEP, CONFIRMED)
        assert "wake" in kinds(actions)
    assert e.state.wake_attempts[NAME] > 300
    assert len(e.state.emitted) < 12  # History bounded by action types/hosts.


def test_restarted_pi_requalifies_mains_before_resuming_wakes():
    e = engine()
    shutdown_and_recover(e)
    resumed = Engine(e.config, State.from_dict(e.state.to_dict()))
    assert "wake" not in kinds(resumed.step(sample(5000, "OL"), ASLEEP, CONFIRMED))
    assert "wake" in kinds(resumed.step(sample(5300, "OL"), ASLEEP, CONFIRMED))
    assert resumed.state.wake_attempts[NAME] == 2


def test_renewed_outage_interrupts_wakes_and_reprotects_awakened_host():
    e = engine()
    shutdown_and_recover(e)
    e.step(sample(1603, "OL"), {NAME: HostFacts(awake=True, boot_id="boot-b")}, CONFIRMED)
    assert kinds(e.step(sample(1604), {NAME: HostFacts(awake=True, boot_id="boot-b")}, CONFIRMED)) == ["shutdown"]
    assert "wake" not in kinds(e.step(sample(1904), ASLEEP, CONFIRMED))


def test_host_reboot_reconciles_power_stage_without_resetting_outage_age():
    e = engine()
    prime(e)
    e.step(sample(1121), AWAKE, CONFIRMED)
    old_since = e.state.outage_since
    actions = e.step(sample(1122), {NAME: HostFacts(awake=True, boot_id="boot-b")}, CONFIRMED)
    assert kinds(actions) == ["power_light", "power_drastic"]
    assert e.state.outage_since == old_since


def test_deliberately_off_host_is_neither_woken_nor_blocks_completion():
    other = HostConfig("manual-off", enabled=True)
    e = engine((other,))
    e.step(sample(998, "OL"), {"manual-off": HostFacts(awake=True)})
    e.step(sample(999, "OL"), {"manual-off": HostFacts(awake=False)})
    actions = shutdown_and_recover(e)
    assert all(a.target != "manual-off" for a in actions)
    assert "manual-off" not in e.state.affected
    e.step(sample(1603, "OL"), AWAKE, {NAME: False})
    assert e.state.outage_since is None


def test_low_recharge_or_stale_data_does_not_wake():
    e = engine()
    shutdown_and_recover(e)
    count = e.state.wake_attempts[NAME]
    assert "wake" not in kinds(e.step(sample(2000, "OL", charge="79"), ASLEEP, CONFIRMED))
    assert "wake" not in kinds(e.step(sample(2001, "OL", age=31), ASLEEP, CONFIRMED))
    assert e.state.wake_attempts[NAME] == count


def test_only_light_recovery_needs_no_fabricated_cloud_cancellation():
    e = engine()
    prime(e)
    e.step(sample(1061), AWAKE)
    e.step(sample(1062, "OL"), AWAKE)
    assert kinds(e.step(sample(1182, "OL"), AWAKE)) == ["restore_power"]
    assert e.state.outage_since is None


def test_maintenance_doubling_is_desired_coverage_not_confirmed_api_effect():
    e = engine()
    prime(e)
    e.step(sample(1121), AWAKE, CONFIRMED)
    e.step(sample(1301), AWAKE, CONFIRMED)
    actions = e.step(sample(7421), ASLEEP, CONFIRMED)
    extension = next(a for a in actions if a.kind == "maintenance_extend")
    assert extension.details == {"hours": 4, "provider_semantics_verified": False}


@pytest.mark.parametrize("key,value", [
    ("last_at", "1000"), ("last_at", float("nan")),
    ("awake_before", [{}]), ("wake_last_at", {NAME: "1000"}),
    ("host_awake", {NAME: 1}), ("stage", True),
])
def test_invalid_state_is_rejected_as_validation_error(key, value):
    state = State().to_dict()
    state[key] = value
    with pytest.raises(ValueError):
        State.from_dict(state)


@pytest.mark.parametrize("value", ["nan", "inf", "-1", "101", "unknown"])
def test_invalid_charge_is_unknown(value):
    assert sample(1, charge=value).charge is None


def test_conflicting_online_and_battery_flags_are_unknown():
    reading = sample(1, "OL OB")
    assert not reading.online and not reading.on_battery


def test_controller_can_never_be_managed_shutdown_target():
    with pytest.raises(ValueError):
        Engine(Config(hosts=(HostConfig("ups-controller", enabled=True),)))


def test_preincident_shutdown_fact_does_not_authorize_waking_manually_off_host():
    e = engine()
    e.step(sample(1000, "OL"), ASLEEP)
    e.step(sample(1001), ASLEEP)
    e.step(sample(1301), ASLEEP)
    e.step(sample(1302, "OL"), ASLEEP)
    assert "wake" not in kinds(e.step(sample(1602, "OL"), ASLEEP))
    assert not e.state.recovery_targets


def test_unknown_timer_before_incident_does_not_shorten_known_incident_budget():
    e = engine()
    e.step(sample(1000, "OL"), AWAKE)
    e.step(sample(1001, ""), AWAKE)
    e.step(sample(1100, ""), AWAKE)
    e.step(sample(1101, runtime=None), AWAKE)
    assert "shutdown" not in kinds(e.step(sample(1102, runtime=None), AWAKE))
    assert "shutdown" in kinds(e.step(sample(1161, runtime=None), AWAKE))
