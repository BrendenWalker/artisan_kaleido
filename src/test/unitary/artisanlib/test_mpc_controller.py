"""Unit tests for Lite MPC (kaleido_model + mpc_controller)."""

from __future__ import annotations

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
from artisanlib.mpc_controller import MPCBackend, MpcConfig


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
            assert abs(fc - fc_prev) <= config.fan_slew_pct_per_sec + 1
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


class TestMpcVsEnergySim:
    def test_mpc_beats_energy_on_step_ror_tracking(self, config: HybridControllerConfig) -> None:
        """Exit criterion Phase B: on the shared Lite plant, MPC RoR RMSE < Energy."""
        plant = KaleidoModelParams()
        # Match controller model to plant (perfect-model case)
        mpc_cfg = MpcConfig(
            horizon=16,
            maxiter=30,
            solver_timeout_ms=500.0,
            model=plant,
            w_ror=5.0,
            w_accel=1.0,
            w_offset=0.5,
        )
        energy = HybridController(config)
        mpc = MPCBackend(config, mpc_cfg)

        e_rmse = _closed_loop_ror_rmse(energy, plant)
        m_rmse = _closed_loop_ror_rmse(mpc, plant)

        assert m_rmse < e_rmse, f'MPC RMSE {m_rmse:.3f} should beat Energy {e_rmse:.3f}'
