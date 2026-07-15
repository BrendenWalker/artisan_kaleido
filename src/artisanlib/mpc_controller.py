#
# ABOUT
# Lite Model Predictive Control backend for Kaleido Hybrid
# (docs/kaleido_mpc_spec.md secs 10-14). Falls back to EnergyBackend on
# solver timeout / failure.
#
# LICENSE
# This program or module is free software: you can redistribute it and/or
# modify it under the terms of the GNU General Public License as published
# by the Free Software Foundation, either version 2 of the License, or
# version 3 of the License, or (at your option) any later version.

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Final

import numpy as np
from scipy.optimize import minimize

from artisanlib.hybrid_controller import (
    HybridController,
    HybridControllerConfig,
    RoastPhase,
    detect_roast_phase,
    interpolate_ror_target,
)
from artisanlib.kaleido_model import (
    KaleidoModelParams,
    estimate_state,
    ror_c_per_min,
    seed_from_machine,
    step as model_step,
)

_log: Final[logging.Logger] = logging.getLogger(__name__)


@dataclass
class MpcConfig:
    horizon: int = 20
    dt: float = 1.0
    w_ror: float = 3.0
    w_accel: float = 2.0
    w_dhp: float = 0.5
    w_dfc: float = 0.5
    w_offset: float = 1.0
    solver_timeout_ms: float = 50.0
    hp_block: int = 5
    fc_block: int = 2
    maxiter: int = 40
    model: KaleidoModelParams = field(default_factory=KaleidoModelParams)


def _clip(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _expand_blocked(values: np.ndarray, horizon: int, block: int) -> np.ndarray:
    """Expand low-rate decision coeffs to per-step sequence of length horizon."""
    out = np.zeros(horizon, dtype=float)
    for k in range(horizon):
        out[k] = float(values[min(k // block, len(values) - 1)])
    return out


class MPCBackend:
    """Horizon optimizer satisfying ControllerBackend; Energy fallback on failure."""

    __slots__ = (
        'config', 'mpc', 'energy', 'backend_name', 'active',
        '_last_update_time', '_last_hp', '_last_fc', '_e_element',
        '_u_warm', '_fallback_count',
    )

    def __init__(
        self,
        config: HybridControllerConfig | None = None,
        mpc: MpcConfig | None = None,
    ) -> None:
        self.config = config or HybridControllerConfig()
        self.mpc = mpc or MpcConfig(
            model=seed_from_machine(self.config.machine.heater_response_delay_s))
        self.energy = HybridController(self.config)
        self.backend_name = 'mpc'
        self.active = False
        self._last_update_time: float | None = None
        self._last_hp = 0.0
        self._last_fc = 0.0
        self._e_element = 0.0
        self._u_warm: np.ndarray | None = None
        self._fallback_count = 0

    def reset(self) -> None:
        self.energy.reset()
        self._last_update_time = None
        self._last_hp = 0.0
        self._last_fc = 0.0
        self._e_element = 0.0
        self._u_warm = None
        self._fallback_count = 0
        self.active = False

    def activate(self) -> None:
        self.reset()
        self.energy.activate()
        self.active = True

    def get_schedule(self, phase: RoastPhase) -> tuple[float, float, float]:
        return self.energy.get_schedule(phase)

    def update(
        self,
        bt: float,
        et: float,
        ror: float | None,
        ror_accel: float,
        timeindex: list[int],
        now: float,
        et_ror: float | None = None,
    ) -> tuple[int, int]:
        if not self.active:
            return int(round(self._last_hp)), int(round(self._last_fc))

        dt = self.mpc.dt
        if self._last_update_time is not None:
            dt = max(0.05, now - self._last_update_time)
        self._last_update_time = now

        # Keep Energy path warm for seamless fallback
        self.energy.active = True
        energy_hp, energy_fc = self.energy.update(
            bt, et, ror, ror_accel, timeindex, now, et_ror=et_ror)

        phase = detect_roast_phase(timeindex, bt, self.config)
        x0 = estimate_state(bt, et, self._last_hp, self.mpc.model, self._e_element)
        self._e_element = float(x0[2])

        solved = self._solve(x0, phase, dt)
        if solved is None:
            self._fallback_count += 1
            _log.warning('MPC fallback to Energy (count=%s)', self._fallback_count)
            self._last_hp = float(energy_hp)
            self._last_fc = float(energy_fc)
            return energy_hp, energy_fc

        hp, fc = solved
        self._last_hp = float(hp)
        self._last_fc = float(fc)
        # Soft-update energy filter state toward commanded HP
        alpha = dt / (self.mpc.model.tau_element + dt)
        self._e_element = (1.0 - alpha) * self._e_element + alpha * self.mpc.model.K_hp * hp
        return hp, fc

    def _decision_dims(self) -> tuple[int, int]:
        n = self.mpc.horizon
        n_hp = max(1, (n + self.mpc.hp_block - 1) // self.mpc.hp_block)
        n_fc = max(1, (n + self.mpc.fc_block - 1) // self.mpc.fc_block)
        return n_hp, n_fc

    def _pack_u(self, z: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        n_hp, n_fc = self._decision_dims()
        hp_seq = _expand_blocked(z[:n_hp], self.mpc.horizon, self.mpc.hp_block)
        fc_seq = _expand_blocked(z[n_hp:n_hp + n_fc], self.mpc.horizon, self.mpc.fc_block)
        return hp_seq, fc_seq

    def _simulate_cost(self, z: np.ndarray, x0: np.ndarray, phase0: RoastPhase, dt: float) -> float:
        cfg = self.config
        mpc = self.mpc
        hp_seq, fc_seq = self._pack_u(z)
        x = x0.copy()
        cost = 0.0
        prev_ror = 0.0
        prev_hp = self._last_hp
        prev_fc = self._last_fc
        t_bean_prev = float(x[0])

        for k in range(mpc.horizon):
            u = np.array([hp_seq[k], fc_seq[k]], dtype=float)
            x_next = model_step(x, u, dt, mpc.model)
            t_bean = float(x_next[0])
            t_chamber = float(x_next[1])
            ror = ror_c_per_min(t_bean_prev, t_bean, dt)
            # BT-threshold phase (never regress relative to measured phase0)
            phase_bt = detect_roast_phase([0] * 8, t_bean, cfg)
            phase = phase0 if phase0.value >= phase_bt.value else phase_bt
            ror_ref = interpolate_ror_target(t_bean, phase, cfg)
            offset_ref = cfg.et_bt_offsets.get(phase, 45.0)

            d_ror = ror - prev_ror if k > 0 else 0.0
            d_hp = hp_seq[k] - prev_hp
            d_fc = fc_seq[k] - prev_fc
            offset_err = (t_chamber - t_bean) - offset_ref

            cost += mpc.w_ror * (ror - ror_ref) ** 2
            cost += mpc.w_accel * d_ror ** 2
            cost += mpc.w_dhp * d_hp ** 2
            cost += mpc.w_dfc * d_fc ** 2
            cost += mpc.w_offset * offset_err ** 2

            # Soft slew penalties (hard constraints enforced via bounds expansion)
            hp_slew = cfg.heater_slew_pct_per_sec * dt
            fc_slew = cfg.fan_slew_pct_per_sec * dt
            if abs(d_hp) > hp_slew:
                cost += 20.0 * (abs(d_hp) - hp_slew) ** 2
            if abs(d_fc) > fc_slew:
                cost += 10.0 * (abs(d_fc) - fc_slew) ** 2

            prev_ror = ror
            prev_hp = hp_seq[k]
            prev_fc = fc_seq[k]
            t_bean_prev = t_bean
            x = x_next

        return float(cost)

    def _solve(
        self,
        x0: np.ndarray,
        phase: RoastPhase,
        dt: float,
    ) -> tuple[int, int] | None:
        mpc = self.mpc
        n_hp, n_fc = self._decision_dims()
        dim = n_hp + n_fc

        # Warm start from baseline schedule, or previous solution
        offset, base_fc, base_hp = self.energy.get_schedule(phase)
        _ = offset
        z0 = np.concatenate([
            np.full(n_hp, base_hp, dtype=float),
            np.full(n_fc, base_fc, dtype=float),
        ])
        if self._u_warm is not None and len(self._u_warm) == dim:
            z0 = 0.7 * self._u_warm + 0.3 * z0

        # Box bounds 0-100; first-step slew as tightened box relative to last command
        hp_slew = self.config.heater_slew_pct_per_sec * max(dt, mpc.dt)
        fc_slew = self.config.fan_slew_pct_per_sec * max(dt, mpc.dt)
        if phase in (RoastPhase.FirstCrack, RoastPhase.Development):
            hp_slew = min(hp_slew, 3.0 * max(dt, mpc.dt))

        bounds: list[tuple[float, float]] = []
        for i in range(n_hp):
            if i == 0:
                lo = _clip(self._last_hp - hp_slew, 0.0, 100.0)
                hi = _clip(self._last_hp + hp_slew, 0.0, 100.0)
            else:
                lo, hi = 0.0, 100.0
            bounds.append((lo, hi))
        for i in range(n_fc):
            if i == 0:
                lo = _clip(self._last_fc - fc_slew, 0.0, 100.0)
                hi = _clip(self._last_fc + fc_slew, 0.0, 100.0)
            else:
                lo, hi = 0.0, 100.0
            bounds.append((lo, hi))

        # Clamp warm start inside bounds
        for i, (lo, hi) in enumerate(bounds):
            z0[i] = _clip(float(z0[i]), lo, hi)

        t0 = time.perf_counter()
        timeout_s = max(0.001, mpc.solver_timeout_ms / 1000.0)
        timed_out = False

        def objective(z: np.ndarray) -> float:
            nonlocal timed_out
            if (time.perf_counter() - t0) > timeout_s:
                timed_out = True
                return 1e12
            return self._simulate_cost(z, x0, phase, mpc.dt)

        try:
            result = minimize(
                objective,
                z0,
                method='L-BFGS-B',
                bounds=bounds,
                options={'maxiter': mpc.maxiter, 'ftol': 1e-3},
            )
        except Exception as exc:  # pylint: disable=broad-except
            _log.warning('MPC solver exception: %s', exc)
            return None

        if timed_out or not result.success:
            # Accept imperfect solution if we got a usable vector under timeout budget
            if timed_out or result.x is None:
                return None
            # Soft accept: use result if finite and bounded
            if not np.all(np.isfinite(result.x)):
                return None

        z_star = np.asarray(result.x, dtype=float)
        self._u_warm = z_star.copy()
        hp_seq, fc_seq = self._pack_u(z_star)
        hp = int(round(_clip(float(hp_seq[0]), 0.0, 100.0)))
        fc = int(round(_clip(float(fc_seq[0]), 0.0, 100.0)))
        return hp, fc
