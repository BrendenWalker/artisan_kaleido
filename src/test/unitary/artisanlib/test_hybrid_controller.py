"""Unit tests for artisanlib.hybrid_controller module."""

from __future__ import annotations

import ast
import math
import pathlib

import pytest

from artisanlib.hybrid_controller import (
    DEFAULT_BASELINE_FAN,
    DEFAULT_BASELINE_HEATER,
    DEFAULT_CONTROL_BACKEND,
    DEFAULT_ET_BT_OFFSETS,
    DEFAULT_ROR_SHAPE,
    EnergyBiasEstimator,
    EnergyController,
    HybridController,
    HybridControllerConfig,
    RoastPhase,
    RoastPlanner,
    ThermalStateEstimator,
    apply_slew,
    compute_ror_acceleration,
    create_controller_backend,
    detect_roast_phase,
    interpolate_ror_target,
    normalize_control_backend,
    predict_ror,
)

ROASTS_DIR = pathlib.Path(__file__).resolve().parents[4] / 'docs' / 'roasts'


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

    def test_first_crack_early_after_fcs(self, config: HybridControllerConfig) -> None:
        timeindex = [10, 100, 500, 0, 0, 0, 0, 0]
        assert detect_roast_phase(timeindex, 185.0, config) == RoastPhase.FirstCrack

    def test_auto_development_after_fcs_without_fce(self, config: HybridControllerConfig) -> None:
        """Without FCe, BT past Development schedule start still enters Development."""
        timeindex = [10, 100, 500, 0, 0, 0, 0, 0]
        assert detect_roast_phase(timeindex, 200.0, config) == RoastPhase.Development

    def test_development_after_fce(self, config: HybridControllerConfig) -> None:
        timeindex = [10, 100, 500, 600, 0, 0, 0, 0]
        assert detect_roast_phase(timeindex, 210.0, config) == RoastPhase.Development

    def test_bt_fallback_yellow(self, config: HybridControllerConfig) -> None:
        timeindex = [10, 0, 0, 0, 0, 0, 0, 0]
        assert detect_roast_phase(timeindex, 155.0, config) == RoastPhase.Yellow


class TestRorShape:
    def test_ror_declines_across_drying(self, config: HybridControllerConfig) -> None:
        early = interpolate_ror_target(100.0, RoastPhase.Drying, config)
        late = interpolate_ror_target(150.0, RoastPhase.Drying, config)
        assert early > late
        assert early == pytest.approx(22.0)
        assert late == pytest.approx(15.5)

    def test_ror_maillard_to_development(self, config: HybridControllerConfig) -> None:
        maillard_start = interpolate_ror_target(170.0, RoastPhase.Maillard, config)
        fc_start = interpolate_ror_target(180.0, RoastPhase.FirstCrack, config)
        fc_end = interpolate_ror_target(195.0, RoastPhase.FirstCrack, config)
        dev_end = interpolate_ror_target(210.0, RoastPhase.Development, config)
        assert maillard_start == pytest.approx(14.0)
        assert fc_start == pytest.approx(10.0)
        assert fc_end == pytest.approx(7.0)
        assert dev_end == pytest.approx(3.5)
        assert maillard_start > fc_end > dev_end

    def test_planner_matches_interpolate(self, config: HybridControllerConfig) -> None:
        planner = RoastPlanner(config)
        assert planner.target_ror(120.0, RoastPhase.Drying) == interpolate_ror_target(
            120.0, RoastPhase.Drying, config)

    def test_log_refined_schedule_defaults(self) -> None:
        assert DEFAULT_BASELINE_HEATER[RoastPhase.Drying] == 90.0
        assert DEFAULT_BASELINE_HEATER[RoastPhase.FirstCrack] == 40.0
        assert DEFAULT_BASELINE_HEATER[RoastPhase.Development] == 25.0
        assert DEFAULT_BASELINE_FAN[RoastPhase.Maillard] == 40.0
        assert DEFAULT_BASELINE_FAN[RoastPhase.FirstCrack] == 60.0
        assert DEFAULT_BASELINE_FAN[RoastPhase.Development] == 70.0
        assert DEFAULT_ET_BT_OFFSETS[RoastPhase.Development] == 10.0
        assert DEFAULT_ROR_SHAPE[RoastPhase.Maillard] == (14.0, 10.0)
        assert DEFAULT_ROR_SHAPE[RoastPhase.FirstCrack] == (10.0, 7.0)
        assert DEFAULT_ROR_SHAPE[RoastPhase.Development] == (7.0, 3.5)


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

    def test_predict_ror(self) -> None:
        assert predict_ror(10.0, 0.2, 25.0) == pytest.approx(15.0)


class TestEnergyBias:
    def test_heater_raises_bias(self, config: HybridControllerConfig) -> None:
        est = EnergyBiasEstimator(config)
        for _ in range(20):
            est.update(90.0, 20.0, 1.0)
        assert est.bias > 0.0

    def test_air_lowers_bias(self, config: HybridControllerConfig) -> None:
        est = EnergyBiasEstimator(config)
        for _ in range(20):
            est.update(90.0, 20.0, 1.0)
        high = est.bias
        for _ in range(40):
            est.update(20.0, 90.0, 1.0)
        assert est.bias < high


class TestThermalTwin:
    def test_states_bounded(self, config: HybridControllerConfig) -> None:
        twin = ThermalStateEstimator(config)
        for _ in range(60):
            s = twin.update(160.0, 230.0, 16.0, 8.0, 95.0, 30.0, RoastPhase.Drying, 1.0, 18.0)
        assert -1.0 <= s.e_air <= 1.5
        assert 0.0 <= s.e_drum <= 1.5
        assert -0.5 <= s.e_beans <= 1.5
        assert 0.0 <= s.moisture <= 1.5

    def test_hp_raises_drum_then_beans(self, config: HybridControllerConfig) -> None:
        twin = ThermalStateEstimator(config)
        # Low power settle
        for _ in range(20):
            twin.update(150.0, 200.0, 12.0, 4.0, 40.0, 30.0, RoastPhase.Yellow, 1.0, 14.0)
        drum0 = twin.state.e_drum
        beans0 = twin.state.e_beans
        for _ in range(40):
            twin.update(155.0, 220.0, 13.0, 6.0, 95.0, 30.0, RoastPhase.Yellow, 1.0, 14.0)
        assert twin.state.e_drum > drum0
        assert twin.state.e_beans > beans0

    def test_moisture_decays_in_drying(self, config: HybridControllerConfig) -> None:
        twin = ThermalStateEstimator(config)
        m0 = twin.state.moisture
        # Match target so stall-rebound does not fight drying decay
        for _ in range(80):
            twin.update(120.0, 210.0, 18.0, 5.0, 90.0, 30.0, RoastPhase.Drying, 1.0, 18.0)
        assert twin.state.moisture < m0

    def test_heater_delay_matches_log_refined(self, config: HybridControllerConfig) -> None:
        assert config.machine.heater_response_delay_s == pytest.approx(25.0)


class TestHybridController:
    def test_outputs_clamped(self, controller: HybridController) -> None:
        timeindex = [0, 0, 0, 0, 0, 0, 0, 0]
        for t in range(20):
            hp, fc = controller.update(150.0, 210.0, 5.0, 0.0, timeindex, float(t), et_ror=2.0)
            assert 0 <= hp <= 100
            assert 0 <= fc <= 100

    def test_reset_clears_state(self, controller: HybridController) -> None:
        timeindex = [0, 0, 0, 0, 0, 0, 0, 0]
        controller.update(150.0, 210.0, 5.0, 0.0, timeindex, 1.0)
        controller.reset()
        assert not controller.active
        hp, fc = controller.update(150.0, 210.0, 5.0, 0.0, timeindex, 2.0)
        assert hp == 0 and fc == 0

    def test_hp_near_baseline_with_bounded_trim(self, config: HybridControllerConfig) -> None:
        config.heater_slew_pct_per_sec = 100.0
        config.heater_trim_limit = 20.0
        hc = HybridController(config)
        hc.activate()
        timeindex = [0, 0, 0, 0, 0, 0, 0, 0]
        for t in range(30):
            hp, _ = hc.update(120.0, 180.0, 16.0, 0.0, timeindex, float(t))
        assert 70 <= hp <= 100

    def test_slew_prevents_instant_jump(self, config: HybridControllerConfig) -> None:
        config.heater_slew_pct_per_sec = 5.0
        hc = HybridController(config)
        hc.activate()
        timeindex = [0, 0, 0, 0, 0, 0, 0, 0]
        hp1, _ = hc.update(150.0, 210.0, 2.0, 0.0, timeindex, 0.0)
        hp2, _ = hc.update(150.0, 210.0, 2.0, 0.0, timeindex, 0.1)
        assert abs(hp2 - hp1) <= 1

    def test_accel_trim_increases_fan(self, config: HybridControllerConfig) -> None:
        config.ror_accel_gain = 5.0
        config.ror_accel_threshold = 0.1
        config.fan_slew_pct_per_sec = 100.0
        hc = HybridController(config)
        hc.activate()
        # Early FirstCrack BT (before auto-Development at 190)
        timeindex = [0, 100, 500, 0, 0, 0, 0, 0]
        _, fc_low = hc.update(185.0, 220.0, 8.0, 0.0, timeindex, 1.0)
        hc.reset()
        hc.activate()
        _, fc_high = hc.update(185.0, 220.0, 8.0, 3.0, timeindex, 1.0)
        assert fc_high >= fc_low

    def test_crash_increases_fan_when_ror_undershoots(self, config: HybridControllerConfig) -> None:
        config.fan_slew_pct_per_sec = 100.0
        config.crash_ror_margin = 1.5
        config.crash_fc_gain = 4.0
        config.soft_brake_fc_gain = 0.0  # isolate crash path from soft-brake
        hc = HybridController(config)
        hc.activate()
        timeindex = [0, 100, 500, 0, 0, 0, 0, 0]
        # Target near ~9 at BT 185 in FirstCrack; 9.0 on target, 4.0 crashes
        _, fc_ok = hc.update(185.0, 220.0, 9.0, 0.0, timeindex, 1.0)
        hc.reset()
        hc.activate()
        _, fc_crash = hc.update(185.0, 220.0, 4.0, 0.0, timeindex, 1.0)
        assert fc_crash > fc_ok

    def test_schedule_lookup(self, controller: HybridController) -> None:
        offset, fc, hp = controller.get_schedule(RoastPhase.FirstCrack)
        assert offset == 30.0
        assert fc == 60.0
        assert hp == 40.0

    def test_soft_brake_increases_fan_when_ror_overshoots(self, config: HybridControllerConfig) -> None:
        config.fan_slew_pct_per_sec = 100.0
        config.heater_slew_pct_per_sec = 100.0
        config.soft_brake_ror_margin = 0.5
        config.soft_brake_fc_gain = 6.0
        config.soft_brake_hp_gain = 2.5
        ec = EnergyController(config)
        # On target → mild fan
        _, fc_ok = ec.update(192.0, 220.0, 7.0, 7.0, -0.2, RoastPhase.Development, 1.0)
        ec.reset()
        # Well above target → soft-brake air up / HP down
        hp_hi, fc_hi = ec.update(192.0, 220.0, 12.0, 7.0, 0.0, RoastPhase.Development, 1.0)
        assert fc_hi > fc_ok
        assert hp_hi < 40

    def test_drop_cuts_heater_immediately(self, config: HybridControllerConfig) -> None:
        """After DROP, HP must snap to 0 even with a slow heater slew."""
        config.heater_slew_pct_per_sec = 100.0
        config.fan_slew_pct_per_sec = 100.0
        hc = HybridController(config)
        hc.activate()
        # Build some heater command during development
        timeindex = [0, 100, 500, 600, 0, 0, 0, 0]
        hp_pre = 0
        for t in range(5):
            hp_pre, _ = hc.update(200.0, 220.0, 6.0, 0.0, timeindex, float(t + 1))
        assert hp_pre > 0
        # Slow slew would leave residual HP without the Cooling snap
        config.heater_slew_pct_per_sec = 1.0
        timeindex_drop = [0, 100, 500, 600, 0, 0, 800, 0]
        hp_drop, fc_drop = hc.update(200.0, 220.0, 0.0, 0.0, timeindex_drop, 10.0)
        assert hp_drop == 0
        assert fc_drop > 0

    def test_no_background_ror_argument(self, controller: HybridController) -> None:
        timeindex = [0, 0, 0, 0, 0, 0, 0, 0]
        hp, fc = controller.update(150.0, 200.0, 12.0, 0.0, timeindex, 1.0)
        assert isinstance(hp, int) and isinstance(fc, int)

    def test_energy_controller_exposes_bias(self, config: HybridControllerConfig) -> None:
        ec = EnergyController(config)
        for _ in range(15):
            ec.update(200.0, 235.0, 8.0, 9.0, 0.0, RoastPhase.FirstCrack, 1.0, et_ror=2.0)
        assert isinstance(ec.energy_bias, float)
        assert isinstance(ec.thermal_state.e_drum, float)

    def test_layered_facade_has_planner_and_energy(self, controller: HybridController) -> None:
        assert isinstance(controller.planner, RoastPlanner)
        assert isinstance(controller.energy, EnergyController)


class TestControllerBackend:
    def test_default_backend_is_energy(self) -> None:
        ctrl = create_controller_backend()
        assert ctrl.backend_name == DEFAULT_CONTROL_BACKEND
        assert normalize_control_backend(None) == 'energy'
        assert normalize_control_backend('ENERGY') == 'energy'

    def test_mpc_request_returns_mpc_backend(self) -> None:
        from artisanlib.mpc_controller import MPCBackend
        ctrl = create_controller_backend('mpc')
        assert isinstance(ctrl, MPCBackend)
        assert ctrl.backend_name == 'mpc'

    def test_unknown_backend_falls_back_to_energy(self) -> None:
        assert normalize_control_backend('not-a-backend') == 'energy'
        ctrl = create_controller_backend('not-a-backend')
        assert ctrl.backend_name == 'energy'


def _ror_series(timex: list[float], temp: list[float], window_s: float = 30.0) -> list[float]:
    n = len(timex)
    ror = [float('nan')] * n
    j = 0
    for i in range(n):
        while j < i and timex[i] - timex[j] > window_s:
            j += 1
        if i == j:
            continue
        dt = timex[i] - timex[j]
        if dt > 0:
            ror[i] = (temp[i] - temp[j]) / dt * 60.0
    return ror


def _idx(ti: list[int], k: int) -> int | None:
    return ti[k] if len(ti) > k and ti[k] and ti[k] > 0 else None


def _replay_prediction_rmse(horizon_s: float = 30.0) -> tuple[float, float, int]:
    """Open-loop twin vs accel-only RMSE predicting BT RoR horizon_s ahead."""
    config = HybridControllerConfig()
    twin_sq = 0.0
    accel_sq = 0.0
    n = 0
    alogs = sorted(ROASTS_DIR.glob('*.alog'))
    assert alogs, f'no roast logs in {ROASTS_DIR}'

    for path in alogs:
        if path.name.startswith('_'):
            continue
        data = ast.literal_eval(path.read_text(encoding='utf-8', errors='replace'))
        timex = data['timex']
        et = data['temp1']
        bt = data['temp2']
        hp = data['extratemp1'][0]
        fc = data['extratemp2'][0]
        ti = data['timeindex']
        charge = _idx(ti, 0)
        drop = _idx(ti, 6)
        if charge is None or drop is None or drop <= charge + 40:
            continue

        bt_ror = _ror_series(timex, bt)
        et_ror = _ror_series(timex, et)
        twin = ThermalStateEstimator(config)
        prev_bt_ror: float | None = None

        for i in range(charge, drop):
            if not math.isfinite(bt_ror[i]) or not math.isfinite(et_ror[i]):
                prev_bt_ror = bt_ror[i] if math.isfinite(bt_ror[i]) else prev_bt_ror
                continue
            dt = timex[i] - timex[i - 1] if i > charge else 1.0
            dt = max(0.05, dt)
            accel = 0.0
            if prev_bt_ror is not None and math.isfinite(prev_bt_ror):
                accel = (bt_ror[i] - prev_bt_ror) / dt
            phase = detect_roast_phase(
                # progressive timeindex: only events that have occurred by index i
                [
                    charge if i >= charge else -1,
                    ti[1] if len(ti) > 1 and ti[1] and i >= ti[1] else 0,
                    ti[2] if len(ti) > 2 and ti[2] and i >= ti[2] else 0,
                    ti[3] if len(ti) > 3 and ti[3] and i >= ti[3] else 0,
                    0,
                    0,
                    0,
                    0,
                ],
                bt[i],
                config,
            )
            target = interpolate_ror_target(bt[i], phase, config)
            state = twin.update(
                bt[i], et[i], bt_ror[i], et_ror[i],
                hp[i], fc[i], phase, dt, target_ror=target,
            )
            accel_pred = predict_ror(bt_ror[i], accel, horizon_s)

            # Find sample ≈ horizon_s ahead
            t_target = timex[i] + horizon_s
            j = i
            while j < drop and timex[j] < t_target:
                j += 1
            if j >= drop or not math.isfinite(bt_ror[j]):
                prev_bt_ror = bt_ror[i]
                continue
            if abs(timex[j] - t_target) > 3.0:
                prev_bt_ror = bt_ror[i]
                continue

            twin_sq += (state.pred_ror - bt_ror[j]) ** 2
            accel_sq += (accel_pred - bt_ror[j]) ** 2
            n += 1
            prev_bt_ror = bt_ror[i]

    assert n > 100, f'too few replay samples: {n}'
    return math.sqrt(twin_sq / n), math.sqrt(accel_sq / n), n


class TestTwinReplayGate:
    def test_twin_beats_accel_only_on_m6_logs(self) -> None:
        twin_rmse, accel_rmse, n = _replay_prediction_rmse(30.0)
        # Gate from spec §5A: twin must beat accel-only before high twin authority
        assert twin_rmse <= accel_rmse, (
            f'twin RMSE {twin_rmse:.3f} should be <= accel RMSE {accel_rmse:.3f} (n={n})'
        )
        # Documented authority: twin_pred_blend default is elevated only when gate passes
        assert HybridControllerConfig().twin_pred_blend >= 0.5
