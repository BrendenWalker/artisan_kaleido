"""Unit tests for artisanlib.hybrid_controller module."""

import pytest

from artisanlib.hybrid_controller import (
    HybridController,
    HybridControllerConfig,
    RoastPhase,
    apply_slew,
    compute_ror_acceleration,
    detect_roast_phase,
)


@pytest.fixture
def config() -> HybridControllerConfig:
    return HybridControllerConfig()


@pytest.fixture
def controller(config: HybridControllerConfig) -> HybridController:
    hc = HybridController(config)
    hc.activate()
    return hc


class TestRoastPhaseDetection:
    def test_charge_before_events(self, config: HybridControllerConfig) -> None:
        timeindex = [-1, 0, 0, 0, 0, 0, 0, 0]
        assert detect_roast_phase(timeindex, 80.0, config) == RoastPhase.Charge

    def test_drying_after_dry_event(self, config: HybridControllerConfig) -> None:
        timeindex = [10, 100, 0, 0, 0, 0, 0, 0]
        assert detect_roast_phase(timeindex, 120.0, config) == RoastPhase.Drying

    def test_maillard_after_fcs(self, config: HybridControllerConfig) -> None:
        timeindex = [10, 100, 500, 0, 0, 0, 0, 0]
        assert detect_roast_phase(timeindex, 200.0, config) == RoastPhase.FirstCrack

    def test_development_after_fce(self, config: HybridControllerConfig) -> None:
        timeindex = [10, 100, 500, 600, 0, 0, 0, 0]
        assert detect_roast_phase(timeindex, 210.0, config) == RoastPhase.Development

    def test_bt_fallback_yellow(self, config: HybridControllerConfig) -> None:
        timeindex = [10, 0, 0, 0, 0, 0, 0, 0]
        assert detect_roast_phase(timeindex, 155.0, config) == RoastPhase.Yellow


class TestSlewLimiter:
    def test_no_change_within_rate(self) -> None:
        assert apply_slew(50.0, 52.0, 10.0, 1.0) == 52.0

    def test_limits_large_jump(self) -> None:
        result = apply_slew(50.0, 90.0, 5.0, 1.0)
        assert result == 55.0


class TestRorAcceleration:
    def test_positive_accel(self) -> None:
        assert compute_ror_acceleration([8.0, 10.0], 2.0) == pytest.approx(1.0)

    def test_insufficient_samples(self) -> None:
        assert compute_ror_acceleration([8.0], 2.0) == 0.0


class TestHybridController:
    def test_outputs_clamped(self, controller: HybridController) -> None:
        timeindex = [0, 0, 0, 0, 0, 0, 0, 0]
        for t in range(20):
            hp, fc = controller.update(150.0, 210.0, 5.0, 0.0, timeindex, 10.0, float(t))
            assert 0 <= hp <= 100
            assert 0 <= fc <= 100

    def test_reset_clears_state(self, controller: HybridController) -> None:
        timeindex = [0, 0, 0, 0, 0, 0, 0, 0]
        controller.update(150.0, 210.0, 5.0, 0.0, timeindex, 10.0, 1.0)
        controller.reset()
        assert not controller.active
        hp, fc = controller.update(150.0, 210.0, 5.0, 0.0, timeindex, 10.0, 2.0)
        assert hp == 0 and fc == 0

    def test_slew_prevents_instant_jump(self, config: HybridControllerConfig) -> None:
        config.heater_slew_pct_per_sec = 5.0
        hc = HybridController(config)
        hc.activate()
        timeindex = [0, 0, 0, 0, 0, 0, 0, 0]
        hp1, _ = hc.update(150.0, 210.0, 2.0, 0.0, timeindex, 20.0, 0.0)
        hp2, _ = hc.update(150.0, 210.0, 2.0, 0.0, timeindex, 20.0, 0.1)
        assert abs(hp2 - hp1) <= 1  # small dt, limited change

    def test_accel_trim_increases_fan(self, config: HybridControllerConfig) -> None:
        config.ror_accel_gain = 5.0
        config.ror_accel_threshold = 0.1
        hc = HybridController(config)
        hc.activate()
        timeindex = [0, 100, 500, 0, 0, 0, 0, 0]
        _, fc_low = hc.update(200.0, 240.0, 8.0, 0.0, timeindex, 10.0, 1.0)
        hc.reset()
        hc.activate()
        _, fc_high = hc.update(200.0, 240.0, 8.0, 3.0, timeindex, 10.0, 1.0)
        assert fc_high >= fc_low

    def test_schedule_lookup(self, controller: HybridController) -> None:
        offset, baseline = controller.get_schedule(RoastPhase.FirstCrack)
        assert offset == 35.0
        assert baseline == 70.0
