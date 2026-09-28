"""Unit tests for Lite MPC (kaleido_model + mpc_controller)."""

from __future__ import annotations

import math

import numpy as np
import pytest

from artisanlib.hybrid_controller import (
    HybridController,
    HybridControllerConfig,
    RoastPhase,
    create_controller_backend,
)
from artisanlib.kaleido_model import (
    KaleidoModelParams,
    estimate_state,
    linearize,
    ror_c_per_min,
    seed_from_machine,
    step,
)
from artisanlib.mpc_controller import (
    MPCBackend,
    MpcConfig,
    phase_cost_scales,
    predict_horizon_phase,
    smooth_fc_command,
)


@pytest.fixture
def params() -> KaleidoModelParams:
    return KaleidoModelParams()


@pytest.fixture
def config() -> HybridControllerConfig:
    return HybridControllerConfig()


class TestKaleidoModel:
    def test_step_keeps_energy_bounded(self, params: KaleidoModelParams) -> None:
        x = np.array([150.0, 200.0, 50.0])
        u = np.array([80.0, 40.0])
        for _ in range(60):
            x = step(x, u, 1.0, params)
        assert 0.0 <= x[2] <= 120.0
        assert np.all(np.isfinite(x))

    def test_hp_raises_chamber_over_time(self, params: KaleidoModelParams) -> None:
        x = np.array([100.0, 120.0, 0.0])
        u = np.array([90.0, 30.0])
        et0 = float(x[1])
        for _ in range(90):
            x = step(x, u, 1.0, params)
        assert float(x[1]) > et0

    def test_fan_increases_bean_transfer(self, params: KaleidoModelParams) -> None:
        x0 = np.array([150.0, 220.0, 70.0])
        low = x0.copy()
        high = x0.copy()
        for _ in range(40):
            low = step(low, np.array([70.0, 20.0]), 1.0, params)
            high = step(high, np.array([70.0, 80.0]), 1.0, params)
        assert float(high[0]) > float(low[0])

    def test_linearize_shapes(self, params: KaleidoModelParams) -> None:
        a, b = linearize(np.array([160.0, 200.0, 60.0]), np.array([70.0, 40.0]), 1.0, params)
        assert a.shape == (3, 3)
        assert b.shape == (3, 2)

    def test_estimate_and_ror(self, params: KaleidoModelParams) -> None:
        x = estimate_state(180.0, 220.0, 75.0, params)
        assert list(x[:2]) == [180.0, 220.0]
        assert ror_c_per_min(180.0, 181.0, 1.0) == pytest.approx(60.0)

    def test_seed_from_machine(self) -> None:
        p = seed_from_machine(25.0)
        assert 8.0 <= p.tau_element <= 25.0


class TestMpcConstraints:
    def test_outputs_clamped_and_slewed(self, config: HybridControllerConfig) -> None:
        mpc = MPCBackend(config, MpcConfig(horizon=12, maxiter=25, solver_timeout_ms=200.0))
        mpc.activate()
        mpc._last_hp = 50.0
        mpc._last_fc = 40.0
        timeindex = [0, 1, 0, 0, 0, 0, 0, 0]  # DRY marked
        hp_prev, fc_prev = 50, 40
        for t in range(1, 8):
            hp, fc = mpc.update(160.0, 210.0, 14.0, 0.0, timeindex, float(t))
            assert 0 <= hp <= 100
            assert 0 <= fc <= 100
            assert abs(hp - hp_prev) <= config.heater_slew_pct_per_sec + 1
            assert abs(fc - fc_prev) <= mpc.mpc.fc_slew_pct_per_sec + 1
            hp_prev, fc_prev = hp, fc

    def test_timeout_falls_back_to_energy(self, config: HybridControllerConfig) -> None:
        energy = HybridController(config)
        energy.activate()
        mpc = MPCBackend(config, MpcConfig(horizon=30, maxiter=200, solver_timeout_ms=0.01))
        mpc.activate()
        timeindex = [0, 1, 0, 0, 0, 0, 0, 0]
        # Warm both with same first ticks then compare fallback path
        bt, et = 170.0, 215.0
        e_hp, e_fc = energy.update(bt, et, 12.0, 0.0, timeindex, 1.0)
        m_hp, m_fc = mpc.update(bt, et, 12.0, 0.0, timeindex, 1.0)
        assert isinstance(m_hp, int) and isinstance(m_fc, int)
        assert 0 <= m_hp <= 100 and 0 <= m_fc <= 100
        mpc.update(bt, et, 12.0, 0.1, timeindex, 2.0)
        assert mpc._fallback_count >= 1
        _ = (e_hp, e_fc)

    def test_factory_returns_mpc(self) -> None:
        ctrl = create_controller_backend('mpc')
        assert isinstance(ctrl, MPCBackend)
        assert ctrl.backend_name == 'mpc'

    def test_diagnostics_populated(self, config: HybridControllerConfig) -> None:
        energy = HybridController(config)
        energy.activate()
        energy.update(170.0, 220.0, 12.0, 0.0, [0, 1, 0, 0, 0, 0, 0, 0], 1.0)
        assert energy.diagnostics.hp >= 0
        assert energy.diagnostics.backend == 'energy'
        assert energy.diagnostics.target_ror > 0

        mpc = MPCBackend(config, MpcConfig(horizon=10, maxiter=15, solver_timeout_ms=200.0))
        mpc.activate()
        mpc.update(170.0, 220.0, 12.0, 0.0, [0, 1, 0, 0, 0, 0, 0, 0], 1.0)
        assert mpc.diagnostics.backend == 'mpc'
        assert isinstance(mpc.diagnostics.pred_ror, float)


class TestFanSmoothing:
    def test_deadband_holds_small_moves(self) -> None:
        assert smooth_fc_command(40.0, 41.5, slew_pct_per_sec=8.0, deadband_pct=3.0, dt=1.0) == 40.0
        moved = smooth_fc_command(40.0, 50.0, slew_pct_per_sec=8.0, deadband_pct=3.0, dt=1.0)
        assert moved == pytest.approx(48.0)
        assert moved != 40.0

    def test_slew_caps_large_jumps(self) -> None:
        # 8 %/s * 1.5 s = 12 points max
        out = smooth_fc_command(20.0, 100.0, slew_pct_per_sec=8.0, deadband_pct=3.0, dt=1.5)
        assert out == pytest.approx(32.0)

    def test_noisy_ror_fc_travel_below_legacy_weights(
        self, config: HybridControllerConfig,
    ) -> None:
        """Field A/B P2/P3: default MPC must not bang-bang the fan on noisy RoR."""
        plant = KaleidoModelParams()
        timeindex = [0, 1, 0, 0, 0, 0, 0, 0]

        def fc_travel(mpc_cfg: MpcConfig) -> float:
            backend = MPCBackend(config, mpc_cfg)
            backend.activate()
            backend._last_hp = 80.0
            backend._last_fc = 40.0
            x = np.array([175.0, 220.0, 70.0], dtype=float)
            prev_bt = float(x[0])
            prev_fc = 40
            travel = 0.0
            for t in range(1, 46):
                bt = float(x[0])
                et = float(x[1])
                ror = ror_c_per_min(prev_bt, bt, 1.0) if t > 1 else 12.0
                ror += 3.0 * math.sin(t * 0.9) + (2.0 if t % 2 == 0 else -2.0)
                _hp, fc = backend.update(bt, et, ror, 0.0, timeindex, float(t))
                travel += abs(fc - prev_fc)
                prev_fc = fc
                prev_bt = bt
                x = step(x, np.array([float(_hp), float(fc)]), 1.0, plant)
            return travel

        calm = MpcConfig(
            horizon=12, maxiter=20, solver_timeout_ms=250.0, model=plant)
        twitchy = MpcConfig(
            horizon=12, maxiter=20, solver_timeout_ms=250.0, model=plant,
            w_dfc=0.5, w_fc_base=0.025, w_fc_reverse=0.0,
            fc_block=2, fc_slew_pct_per_sec=20.0, fc_deadband_pct=0.0)
        calm_travel = fc_travel(calm)
        twitchy_travel = fc_travel(twitchy)
        assert calm_travel < twitchy_travel, (
            f'calm FC travel {calm_travel:.0f} should beat twitchy {twitchy_travel:.0f}')
        assert calm_travel < 220.0


def _closed_loop_ror_rmse(
    backend: HybridController | MPCBackend,
    plant: KaleidoModelParams,
    steps: int = 80,
    ror_target: float = 12.0,
) -> float:
    """Simulate plant under controller; RMSE of RoR vs constant target in Maillard."""
    backend.activate()
    x = np.array([175.0, 220.0, 70.0], dtype=float)
    timeindex = [0, 1, 0, 0, 0, 0, 0, 0]
    hp, fc = 70, 40
    prev_bt = float(x[0])
    err_sq = 0.0
    n = 0
    for t in range(1, steps + 1):
        bt = float(x[0])
        et = float(x[1])
        ror = ror_c_per_min(prev_bt, bt, 1.0) if t > 1 else ror_target
        hp, fc = backend.update(bt, et, ror, 0.0, timeindex, float(t))
        prev_bt = bt
        x = step(x, np.array([float(hp), float(fc)]), 1.0, plant)
        new_ror = ror_c_per_min(bt, float(x[0]), 1.0)
        # Score after transient
        if t > 20:
            err_sq += (new_ror - ror_target) ** 2
            n += 1
    return float(np.sqrt(err_sq / max(1, n)))


class TestEventAwareHorizon:
    def test_phase_never_regresses_and_uses_events(self, config: HybridControllerConfig) -> None:
        ti_pre = [0, 1, 0, 0, 0, 0, 0, 0]  # DRY only
        ti_fc = [0, 1, 50, 0, 0, 0, 0, 0]  # FCs marked
        p0 = RoastPhase.Maillard
        # BT below FC thresholds still held to Maillard when events say so
        assert predict_horizon_phase(ti_pre, 175.0, p0, config) == RoastPhase.Maillard
        # FCs event lifts to FirstCrack even if BT argument is mid-maillard
        assert predict_horizon_phase(ti_fc, 175.0, p0, config) == RoastPhase.FirstCrack
        # Does not fall back below phase0
        assert predict_horizon_phase(ti_pre, 120.0, RoastPhase.Maillard, config) == RoastPhase.Maillard

    def test_horizon_does_not_bt_advance_during_plunge(
        self, config: HybridControllerConfig,
    ) -> None:
        ti_charge = [10, 0, 0, 0, 0, 0, 0, 0]
        assert predict_horizon_phase(
            ti_charge, 195.0, RoastPhase.Charge, config, post_tp=False,
        ) == RoastPhase.Charge

    def test_mpc_hot_drum_charge_stays_charge(self, config: HybridControllerConfig) -> None:
        backend = MPCBackend(config)
        backend.activate()
        timeindex = [10, 0, 0, 0, 0, 0, 0, 0]
        backend.update(195.0, 149.0, -50.0, 0.0, timeindex, 0.0)
        assert backend.diagnostics.phase == RoastPhase.Charge
        assert backend.post_tp is False

    def test_fc_phase_scales_favor_air(self, config: HybridControllerConfig) -> None:
        dry = phase_cost_scales(RoastPhase.Drying, config)
        fc = phase_cost_scales(RoastPhase.FirstCrack, config)
        assert fc[0] > dry[0]  # accel
        assert fc[1] > dry[1]  # dhp penalty
        assert fc[2] >= dry[2]  # dfc

    def test_variable_length_closed_loop_stable(self, config: HybridControllerConfig) -> None:
        """Short and long roast horizons stay bounded with event progression."""
        plant = KaleidoModelParams()
        mpc = MPCBackend(config, MpcConfig(horizon=12, maxiter=20, solver_timeout_ms=300.0, model=plant))
        mpc.activate()
        x = np.array([140.0, 200.0, 60.0], dtype=float)
        for length, mark_fc_at in ((40, 25), (90, 55)):
            mpc.reset()
            mpc.activate()
            x = np.array([140.0, 200.0, 60.0], dtype=float)
            prev_bt = float(x[0])
            for t in range(1, length + 1):
                ti = [0, 1, 0, 0, 0, 0, 0, 0]
                if t >= mark_fc_at:
                    ti[2] = mark_fc_at
                if t >= mark_fc_at + 15:
                    ti[3] = mark_fc_at + 15
                bt = float(x[0])
                et = float(x[1])
                ror = ror_c_per_min(prev_bt, bt, 1.0) if t > 1 else 14.0
                hp, fc = mpc.update(bt, et, ror, 0.0, ti, float(t))
                assert 0 <= hp <= 100 and 0 <= fc <= 100
                prev_bt = bt
                x = step(x, np.asarray([float(hp), float(fc)]), 1.0, plant)


class TestMpcVsEnergySim:
    def test_mpc_beats_energy_on_step_ror_tracking(self, config: HybridControllerConfig) -> None:
        """Exit criterion Phase B: on the shared Lite plant, MPC RoR RMSE < Energy."""
        plant = KaleidoModelParams()
        # Match controller model to plant (perfect-model case)
        mpc_cfg = MpcConfig(
            horizon=20,
            maxiter=40,
            solver_timeout_ms=800.0,
            model=plant,
            w_ror=8.0,
            w_accel=0.8,
            w_offset=0.3,
            w_dhp=0.3,
            w_dfc=0.3,
        )
        energy = HybridController(config)
        mpc = MPCBackend(config, mpc_cfg)

        e_rmse = _closed_loop_ror_rmse(energy, plant, steps=100, ror_target=12.0)
        m_rmse = _closed_loop_ror_rmse(mpc, plant, steps=100, ror_target=12.0)

        assert m_rmse < e_rmse, f'MPC RMSE {m_rmse:.3f} should beat Energy {e_rmse:.3f}'
