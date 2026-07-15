#
# ABOUT
# Lite lumped thermal model for Kaleido Hybrid / MPC (docs/kaleido_mpc_spec.md sec 11)
#
# State x = [T_bean, T_chamber, E_element]
# Input u = [HP%, FC%]
#
# LICENSE
# This program or module is free software: you can redistribute it and/or
# modify it under the terms of the GNU General Public License as published
# by the Free Software Foundation, either version 2 of the License, or
# version 3 of the License, or (at your option) any later version.

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

import numpy as np

_STATE_DIM: Final[int] = 3
_INPUT_DIM: Final[int] = 2


@dataclass
class KaleidoModelParams:
    """Lite plant params; defaults are M6-corpus fitted (docs/roasts/kaleido_model_m6.json)."""

    tau_element: float = 15.0  # s; log-prior ~12-20 (heater delay)
    tau_chamber: float = 25.0
    tau_bean: float = 120.0
    K_hp: float = 1.0
    K_ec: float = 0.397  # degC/s per unit E (E ~ 0-100); corpus-fitted
    K_loss: float = 0.124
    k_fc0: float = 0.08
    k_fc1: float = 0.08
    K_beans: float = 0.05
    T_amb: float = 25.0


def _clip(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def transfer_coeff(fc: float, params: KaleidoModelParams) -> float:
    return params.k_fc0 + params.k_fc1 * _clip(fc, 0.0, 100.0) / 100.0


def derivatives(
    x: np.ndarray,
    u: np.ndarray,
    params: KaleidoModelParams,
) -> np.ndarray:
    """Continuous-time dx/dt for x=[T_bean, T_chamber, E_element], u=[HP, FC]."""
    t_bean = float(x[0])
    t_chamber = float(x[1])
    e_el = float(x[2])
    hp = _clip(float(u[0]), 0.0, 100.0)
    fc = _clip(float(u[1]), 0.0, 100.0)

    k_fc = transfer_coeff(fc, params)
    q_transfer = k_fc * (t_chamber - t_bean)

    de = (params.K_hp * hp - e_el) / max(1e-3, params.tau_element)
    dtc = (
        params.K_ec * e_el
        - params.K_loss * (t_chamber - params.T_amb)
        - q_transfer
    ) / max(1e-3, params.tau_chamber)
    dtb = (
        q_transfer - params.K_beans * (t_bean - params.T_amb)
    ) / max(1e-3, params.tau_bean)

    return np.array([dtb, dtc, de], dtype=float)


def step(
    x: np.ndarray,
    u: np.ndarray,
    dt: float,
    params: KaleidoModelParams,
) -> np.ndarray:
    """Euler integrate one sample. Returns next state (copy)."""
    if dt <= 0:
        return np.asarray(x, dtype=float).copy()
    dx = derivatives(x, u, params)
    x_next = np.asarray(x, dtype=float) + dx * dt
    # Soft clamp energy; temperatures unconstrained in open sim
    x_next[2] = _clip(float(x_next[2]), 0.0, 120.0)
    return x_next


def linearize(
    x: np.ndarray,
    u: np.ndarray,
    dt: float,
    params: KaleidoModelParams,
    eps: float = 1e-3,
) -> tuple[np.ndarray, np.ndarray]:
    """Finite-difference discrete A, B for x[k+1] = A x[k] + B u[k]."""
    x0 = np.asarray(x, dtype=float)
    u0 = np.asarray(u, dtype=float)
    x1 = step(x0, u0, dt, params)

    a = np.zeros((_STATE_DIM, _STATE_DIM), dtype=float)
    for i in range(_STATE_DIM):
        xp = x0.copy()
        xp[i] += eps
        a[:, i] = (step(xp, u0, dt, params) - x1) / eps

    b = np.zeros((_STATE_DIM, _INPUT_DIM), dtype=float)
    for j in range(_INPUT_DIM):
        up = u0.copy()
        up[j] += eps
        b[:, j] = (step(x0, up, dt, params) - x1) / eps

    return a, b


def estimate_state(
    bt: float,
    et: float,
    hp: float,
    params: KaleidoModelParams,
    e_element: float | None = None,
) -> np.ndarray:
    """Lite estimator: measured BT/ET; E_element from filtered HP or prior."""
    if e_element is None:
        e = params.K_hp * _clip(hp, 0.0, 100.0)
    else:
        e = float(e_element)
    return np.array([bt, et, _clip(e, 0.0, 120.0)], dtype=float)


def ror_c_per_min(t_bean_prev: float, t_bean: float, dt: float) -> float:
    if dt <= 0:
        return 0.0
    return (t_bean - t_bean_prev) / dt * 60.0


def seed_from_machine(heater_response_delay_s: float) -> KaleidoModelParams:
    """Seed element tau from Hybrid MachineCharacteristics.heater_response_delay_s."""
    params = KaleidoModelParams()
    # Map observed heater->RoR delay (~25 s) into slightly faster element tau
    params.tau_element = _clip(heater_response_delay_s * 0.6, 8.0, 25.0)
    params.tau_chamber = _clip(heater_response_delay_s, 15.0, 40.0)
    return params
