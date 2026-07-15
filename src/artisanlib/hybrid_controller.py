#
# ABOUT
# Hybrid Heater + Airflow Controller for Kaleido roasters
#
# Architecture (see docs/kaleido_mpc_spec.md):
#   Layer 1   - RoastPlanner: machine-independent target RoR from phase + shape
#   Layer 1.5 - ThermalStateEstimator: digital twin (air/drum/beans/moisture)
#   Layer 2   - EnergyController: HP/FC from RoR error/trend, twin, prediction
#
# Bean temperature is used for phase detection; RoR is the primary feedback variable.

# LICENSE
# This program or module is free software: you can redistribute it and/or
# modify it under the terms of the GNU General Public License as published
# by the Free Software Foundation, either version 2 of the License, or
# version 3 of the License, or (at your option) any later version.

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Final, Protocol

_log: Final[logging.Logger] = logging.getLogger(__name__)

# Supported Hybrid Layer-2 / Layer-3 backend names (QSetting hybridControlBackend)
VALID_CONTROL_BACKENDS: Final[frozenset[str]] = frozenset({'energy', 'mpc'})
DEFAULT_CONTROL_BACKEND: Final[str] = 'energy'


class RoastPhase(IntEnum):
    Charge = 0
    Drying = 1
    Yellow = 2
    Maillard = 3
    FirstCrack = 4
    Development = 5
    Cooling = 6


# Log-refined M6 600g medium/light defaults (docs/kaleido_mpc_spec.md sec 6)
DEFAULT_ET_BT_OFFSETS: Final[dict[RoastPhase, float]] = {
    RoastPhase.Charge: 85.0,
    RoastPhase.Drying: 85.0,
    RoastPhase.Yellow: 65.0,
    RoastPhase.Maillard: 45.0,
    RoastPhase.FirstCrack: 30.0,
    RoastPhase.Development: 10.0,
    RoastPhase.Cooling: 25.0,
}

DEFAULT_BASELINE_FAN: Final[dict[RoastPhase, float]] = {
    RoastPhase.Charge: 30.0,
    RoastPhase.Drying: 30.0,
    RoastPhase.Yellow: 35.0,
    RoastPhase.Maillard: 40.0,
    RoastPhase.FirstCrack: 50.0,
    RoastPhase.Development: 55.0,
    RoastPhase.Cooling: 80.0,
}

DEFAULT_BASELINE_HEATER: Final[dict[RoastPhase, float]] = {
    RoastPhase.Charge: 90.0,
    RoastPhase.Drying: 90.0,
    RoastPhase.Yellow: 85.0,
    RoastPhase.Maillard: 80.0,
    RoastPhase.FirstCrack: 50.0,
    RoastPhase.Development: 40.0,
    RoastPhase.Cooling: 0.0,
}

DEFAULT_ROR_SHAPE: Final[dict[RoastPhase, tuple[float, float]]] = {
    RoastPhase.Charge: (22.0, 22.0),
    RoastPhase.Drying: (22.0, 15.5),
    RoastPhase.Yellow: (15.0, 14.0),
    RoastPhase.Maillard: (14.0, 10.0),
    RoastPhase.FirstCrack: (11.0, 9.0),
    RoastPhase.Development: (9.0, 5.5),
    RoastPhase.Cooling: (0.0, 0.0),
}

DEFAULT_ROR_BT_BOUNDS: Final[dict[RoastPhase, tuple[float, float]]] = {
    RoastPhase.Charge: (80.0, 100.0),
    RoastPhase.Drying: (100.0, 150.0),
    RoastPhase.Yellow: (150.0, 170.0),
    RoastPhase.Maillard: (170.0, 195.0),
    RoastPhase.FirstCrack: (180.0, 205.0),
    RoastPhase.Development: (190.0, 210.0),
    RoastPhase.Cooling: (100.0, 100.0),
}

DEFAULT_PHASE_HEATER_WEIGHT: Final[dict[RoastPhase, float]] = {
    RoastPhase.Charge: 0.85,
    RoastPhase.Drying: 0.85,
    RoastPhase.Yellow: 0.70,
    RoastPhase.Maillard: 0.45,
    RoastPhase.FirstCrack: 0.20,
    RoastPhase.Development: 0.15,
    RoastPhase.Cooling: 0.0,
}

# Soften ET?BT PID early when hot-drum charge makes huge offsets normal
DEFAULT_PHASE_OFFSET_WEIGHT: Final[dict[RoastPhase, float]] = {
    RoastPhase.Charge: 0.15,
    RoastPhase.Drying: 0.20,
    RoastPhase.Yellow: 0.55,
    RoastPhase.Maillard: 1.0,
    RoastPhase.FirstCrack: 1.0,
    RoastPhase.Development: 0.70,
    RoastPhase.Cooling: 0.3,
}


@dataclass
class MachineCharacteristics:
    """Per-model parameters so the controller algorithm stays machine-independent."""

    heater_response_delay_s: float = 25.0
    heater_gain: float = 1.0
    airflow_response_delay_s: float = 5.0
    airflow_gain: float = 0.6
    thermal_mass: float = 1.4
    max_ror: float = 24.0
    recommended_fc_ror: float = 8.0


@dataclass
class HybridControllerConfig:
    heater_kp: float = 3.0
    heater_ki: float = 0.5
    heater_kd: float = 0.1
    fan_kp: float = 2.0
    fan_ki: float = 0.3
    fan_kd: float = 0.05
    heater_slew_pct_per_sec: float = 5.0
    fan_slew_pct_per_sec: float = 20.0
    ror_accel_gain: float = 2.0
    ror_accel_threshold: float = 0.5
    heater_trim_limit: float = 20.0
    crash_ror_margin: float = 1.5
    crash_fc_gain: float = 4.0
    # Predictive / trend
    ror_predict_horizon_s: float = 30.0
    predict_blend: float = 0.55  # weight on predicted vs current RoR error
    twin_pred_blend: float = 0.65  # weight on twin pred vs accel-only pred
    declining_error_scale: float = 0.35
    # Legacy energy bias weights (fallback / EnergyBiasEstimator)
    energy_heater_weight: float = 0.02
    energy_air_weight: float = 0.015
    energy_leak: float = 0.05
    energy_bias_fc_gain: float = 8.0
    energy_bias_hp_scale: float = 0.15
    # Twin gains
    twin_meas_gain: float = 0.12
    twin_transfer_gain: float = 0.08
    twin_moisture_decay: float = 0.004
    twin_drum_weight: float = 0.45
    twin_air_weight: float = 0.25
    twin_beans_weight: float = 0.45
    twin_moisture_weight: float = 0.35
    yellow_bt: float = 150.0
    maillard_bt: float = 170.0
    drying_bt: float = 100.0
    et_bt_offsets: dict[RoastPhase, float] = field(default_factory=lambda: dict(DEFAULT_ET_BT_OFFSETS))
    baseline_fan: dict[RoastPhase, float] = field(default_factory=lambda: dict(DEFAULT_BASELINE_FAN))
    baseline_heater: dict[RoastPhase, float] = field(default_factory=lambda: dict(DEFAULT_BASELINE_HEATER))
    ror_shape: dict[RoastPhase, tuple[float, float]] = field(default_factory=lambda: dict(DEFAULT_ROR_SHAPE))
    ror_bt_bounds: dict[RoastPhase, tuple[float, float]] = field(default_factory=lambda: dict(DEFAULT_ROR_BT_BOUNDS))
    phase_heater_weight: dict[RoastPhase, float] = field(default_factory=lambda: dict(DEFAULT_PHASE_HEATER_WEIGHT))
    phase_offset_weight: dict[RoastPhase, float] = field(default_factory=lambda: dict(DEFAULT_PHASE_OFFSET_WEIGHT))
    machine: MachineCharacteristics = field(default_factory=MachineCharacteristics)


class SimplePID:
    """Lightweight PID without Qt dependencies."""

    __slots__ = ('kp', 'ki', 'kd', 'out_min', 'out_max', '_integral', '_last_error', '_last_time')

    def __init__(self, kp: float, ki: float, kd: float, out_min: float = 0.0, out_max: float = 100.0) -> None:
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.out_min = out_min
        self.out_max = out_max
        self._integral = 0.0
        self._last_error: float | None = None
        self._last_time: float | None = None

    def reset(self) -> None:
        self._integral = 0.0
        self._last_error = None
        self._last_time = None

    def update(self, setpoint: float, measurement: float, dt: float) -> float:
        if dt <= 0:
            dt = 0.001
        error = setpoint - measurement
        self._integral += error * dt
        i_max = self.out_max
        i_min = self.out_min
        if self.ki > 0:
            self._integral = max(i_min / self.ki, min(i_max / self.ki, self._integral))
        derivative = 0.0
        if self._last_error is not None:
            derivative = (error - self._last_error) / dt
        self._last_error = error
        output = self.kp * error + self.ki * self._integral + self.kd * derivative
        return max(self.out_min, min(self.out_max, output))


def detect_roast_phase(timeindex: list[int], bt: float, config: HybridControllerConfig) -> RoastPhase:
    """Derive roast phase from Artisan event indices with BT fallbacks."""
    if len(timeindex) > 6 and timeindex[6] > 0:
        return RoastPhase.Cooling
    if len(timeindex) > 3 and timeindex[3] > 0:
        return RoastPhase.Development
    if len(timeindex) > 2 and timeindex[2] > 0:
        return RoastPhase.FirstCrack
    if len(timeindex) > 1 and timeindex[1] > 0:
        if bt >= config.maillard_bt:
            return RoastPhase.Maillard
        if bt >= config.yellow_bt:
            return RoastPhase.Yellow
        return RoastPhase.Drying
    if bt >= config.maillard_bt:
        return RoastPhase.Maillard
    if bt >= config.yellow_bt:
        return RoastPhase.Yellow
    if bt >= config.drying_bt:
        return RoastPhase.Drying
    return RoastPhase.Charge


def interpolate_ror_target(bt: float, phase: RoastPhase, config: HybridControllerConfig) -> float:
    """Declining RoR target from the shape schedule, interpolated by BT within phase."""
    start_ror, end_ror = config.ror_shape.get(phase, DEFAULT_ROR_SHAPE.get(phase, (10.0, 10.0)))
    bt_lo, bt_hi = config.ror_bt_bounds.get(phase, DEFAULT_ROR_BT_BOUNDS.get(phase, (bt, bt)))
    if bt_hi <= bt_lo:
        return start_ror
    t = max(0.0, min(1.0, (bt - bt_lo) / (bt_hi - bt_lo)))
    return start_ror + t * (end_ror - start_ror)


def compute_ror_acceleration(ror_samples: list[float], dt: float) -> float:
    """Finite-difference RoR acceleration from recent samples."""
    if len(ror_samples) < 2 or dt <= 0:
        return 0.0
    return (ror_samples[-1] - ror_samples[-2]) / dt


def predict_ror(current_ror: float, ror_accel: float, horizon_s: float) -> float:
    """Simple linear RoR prediction over a short horizon."""
    return current_ror + ror_accel * max(0.0, horizon_s)


def apply_slew(current: float, target: float, max_rate_per_sec: float, dt: float) -> float:
    if dt <= 0:
        return target
    max_change = max_rate_per_sec * dt
    delta = target - current
    if abs(delta) <= max_change:
        return target
    return current + math.copysign(max_change, delta)


def _clip(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


# ---------------------------------------------------------------------------
# Layer 1 - Roast Planner
# ---------------------------------------------------------------------------

class RoastPlanner:
    """Produces target RoR; independent of machine actuator dynamics."""

    __slots__ = ('config',)

    def __init__(self, config: HybridControllerConfig) -> None:
        self.config = config

    def target_ror(self, bt: float, phase: RoastPhase) -> float:
        return interpolate_ror_target(bt, phase, self.config)


# ---------------------------------------------------------------------------
# Layer 1.5 - Thermal Digital Twin
# ---------------------------------------------------------------------------

@dataclass
class ThermalState:
    e_air: float = 0.0
    e_drum: float = 0.0
    e_beans: float = 0.0
    moisture: float = 1.0
    pred_ror: float = 0.0
    energy_bias: float = 0.0


class ThermalStateEstimator:
    """Heuristic multi-compartment twin: air / drum / beans / moisture."""

    __slots__ = ('config', 'state')

    def __init__(self, config: HybridControllerConfig) -> None:
        self.config = config
        self.state = ThermalState()

    def reset(self) -> None:
        self.state = ThermalState()

    def update(
        self,
        bt: float,
        et: float,
        bt_ror: float,
        et_ror: float,
        hp: float,
        fc: float,
        phase: RoastPhase,
        dt: float,
        target_ror: float | None = None,
    ) -> ThermalState:
        if dt <= 0:
            dt = 0.001
        cfg = self.config
        machine = cfg.machine
        max_ror = max(1.0, machine.max_ror)
        s = self.state

        tau_d = max(1.0, machine.heater_response_delay_s)
        tau_a = max(1.0, machine.airflow_response_delay_s)
        alpha_d = dt / (tau_d + dt)
        alpha_a = dt / (tau_a + dt)

        hp_n = _clip(hp / 100.0, 0.0, 1.0)
        fc_n = _clip(fc / 100.0, 0.0, 1.0)
        offset_n = _clip((et - bt) / 100.0, -0.5, 1.5)
        bt_ror_n = _clip(bt_ror / max_ror, -0.5, 1.5)
        et_ror_n = _clip(et_ror / max_ror, -0.5, 1.5)

        # Drum: lagged heater energy (arrives later as BT RoR)
        s.e_drum += alpha_d * (hp_n - s.e_drum)

        # Air: chamber buffer from offset / ET RoR, vented by fan
        air_target = offset_n + 0.35 * et_ror_n - 0.55 * fc_n
        s.e_air += alpha_a * (air_target - s.e_air)

        # Beans: transfer from drum/air toward bean energy, lightly corrected by measured BT RoR
        transfer = cfg.twin_transfer_gain * (0.65 * s.e_drum + 0.55 * s.e_air - s.e_beans)
        s.e_beans += transfer * dt
        s.e_beans += cfg.twin_meas_gain * (bt_ror_n - s.e_beans) * dt

        # Moisture: high early; decays through drying/yellow; rebounds if RoR stalls while heated
        decay = cfg.twin_moisture_decay
        if phase in (RoastPhase.Drying, RoastPhase.Yellow, RoastPhase.Charge):
            decay *= 1.6
        elif phase in (RoastPhase.FirstCrack, RoastPhase.Development, RoastPhase.Cooling):
            decay *= 0.4
        s.moisture = _clip(s.moisture * max(0.0, 1.0 - decay * dt), 0.0, 1.5)
        if target_ror is not None and bt_ror < target_ror - 1.5 and hp_n > 0.4:
            s.moisture = _clip(s.moisture + 0.01 * dt, 0.0, 1.5)

        s.e_air = _clip(s.e_air, -1.0, 1.5)
        s.e_drum = _clip(s.e_drum, 0.0, 1.5)
        s.e_beans = _clip(s.e_beans, -0.5, 1.5)

        # Predicted BT RoR from energy state (not accel alone)
        state_ror = max_ror * (
            cfg.twin_beans_weight * s.e_beans
            + cfg.twin_air_weight * s.e_air
            + cfg.twin_drum_weight * s.e_drum
            - cfg.twin_moisture_weight * s.moisture
        )
        # Horizon blend: what RoR looks like after stored drum energy arrives
        horizon = max(0.0, cfg.ror_predict_horizon_s)
        arrival = (horizon / (tau_d + horizon)) * (s.e_drum - s.e_beans) * max_ror * 0.35
        s.pred_ror = state_ror + arrival
        # Keep prediction attached to current measurement so noise doesn't free-run
        s.pred_ror = 0.55 * bt_ror + 0.45 * s.pred_ror

        s.energy_bias = _clip(
            0.50 * s.e_drum + 0.25 * s.e_air + 0.20 * s.e_beans - 0.40 * s.moisture,
            -1.5,
            1.5,
        )
        return s


class EnergyBiasEstimator:
    """Legacy scalar energy integrator (fallback / unit-test compatibility)."""

    __slots__ = ('config', 'bias')

    def __init__(self, config: HybridControllerConfig) -> None:
        self.config = config
        self.bias = 0.0

    def reset(self) -> None:
        self.bias = 0.0

    def update(self, hp: float, fc: float, dt: float) -> float:
        self.bias += self.config.energy_heater_weight * (hp / 100.0) * dt
        self.bias -= self.config.energy_air_weight * (fc / 100.0) * dt
        decay = max(0.0, 1.0 - self.config.energy_leak * dt)
        self.bias *= decay
        self.bias = _clip(self.bias, -1.5, 1.5)
        return self.bias


# ---------------------------------------------------------------------------
# Layer 2 - Energy Controller
# ---------------------------------------------------------------------------

class EnergyController:
    """Maps RoR error / trend / twin state / phase into HP and FC commands."""

    __slots__ = (
        'config', '_heater_pid', '_fan_pid', '_twin',
        '_last_hp', '_last_fc',
    )

    def __init__(self, config: HybridControllerConfig) -> None:
        self.config = config
        trim = config.heater_trim_limit
        self._heater_pid = SimplePID(config.heater_kp, config.heater_ki, config.heater_kd, -trim, trim)
        self._fan_pid = SimplePID(config.fan_kp, config.fan_ki, config.fan_kd, -30.0, 30.0)
        self._twin = ThermalStateEstimator(config)
        self._last_hp = 0.0
        self._last_fc = 0.0

    def reset(self) -> None:
        self._heater_pid.reset()
        self._fan_pid.reset()
        self._twin.reset()
        self._last_hp = 0.0
        self._last_fc = 0.0

    def get_schedule(self, phase: RoastPhase) -> tuple[float, float, float]:
        offset = self.config.et_bt_offsets.get(phase, DEFAULT_ET_BT_OFFSETS.get(phase, 45.0))
        fc = self.config.baseline_fan.get(phase, DEFAULT_BASELINE_FAN.get(phase, 50.0))
        hp = self.config.baseline_heater.get(phase, DEFAULT_BASELINE_HEATER.get(phase, 70.0))
        return offset, fc, hp

    def _trend_scale(self, ror_error: float, ror_accel: float) -> float:
        """Mute corrections when RoR is already declining toward the target."""
        if ror_error < -0.3 and ror_accel < -0.05:
            return self.config.declining_error_scale
        if ror_error > 0.3 and ror_accel > 0.05:
            return self.config.declining_error_scale
        if ror_error < -0.3 and ror_accel > self.config.ror_accel_threshold:
            return 1.35
        if ror_error > 0.3 and ror_accel < -self.config.ror_accel_threshold:
            return 1.35
        return 1.0

    def update(
        self,
        bt: float,
        et: float,
        current_ror: float,
        target_ror: float,
        ror_accel: float,
        phase: RoastPhase,
        dt: float,
        et_ror: float = 0.0,
    ) -> tuple[int, int]:
        target_offset, baseline_fan, baseline_heater = self.get_schedule(phase)
        machine = self.config.machine

        # Twin uses last commanded HP/FC so lag states stay causal
        twin_state = self._twin.update(
            bt, et, current_ror, et_ror,
            self._last_hp, self._last_fc,
            phase, dt, target_ror=target_ror,
        )

        accel_pred = predict_ror(current_ror, ror_accel, self.config.ror_predict_horizon_s)
        twin_w = _clip(self.config.twin_pred_blend, 0.0, 1.0)
        predicted = (1.0 - twin_w) * accel_pred + twin_w * twin_state.pred_ror
        blend = _clip(self.config.predict_blend, 0.0, 1.0)
        effective_ror = (1.0 - blend) * current_ror + blend * predicted

        ror_error = target_ror - effective_ror
        trend_scale = self._trend_scale(target_ror - current_ror, ror_accel)

        hp_trim_raw = self._heater_pid.update(target_ror, effective_ror, dt) * trend_scale
        heater_w = self.config.phase_heater_weight.get(
            phase, DEFAULT_PHASE_HEATER_WEIGHT.get(phase, 0.5))
        air_w = max(0.0, 1.0 - heater_w)

        bias = twin_state.energy_bias
        # Extra preemptive air when drum energy is high near FC even if scalar bias is modest
        if phase in (RoastPhase.Maillard, RoastPhase.FirstCrack, RoastPhase.Development):
            bias = max(bias, 0.6 * twin_state.e_drum - 0.2)

        hp_authority = max(0.35, 1.0 - max(0.0, bias) * self.config.energy_bias_hp_scale)
        hp_trim = hp_trim_raw * heater_w * machine.heater_gain * hp_authority
        hp_trim = _clip(hp_trim, -self.config.heater_trim_limit, self.config.heater_trim_limit)

        air_ror_trim = (-ror_error) * air_w * 3.0 * machine.airflow_gain * trend_scale

        et_bt = et - bt
        fan_offset_corr = self._fan_pid.update(target_offset, et_bt, dt)
        offset_w = self.config.phase_offset_weight.get(
            phase, DEFAULT_PHASE_OFFSET_WEIGHT.get(phase, 1.0))
        fan_offset_corr *= offset_w

        accel_trim = 0.0
        if ror_accel > self.config.ror_accel_threshold:
            accel_trim = self.config.ror_accel_gain * ror_accel
            if phase in (RoastPhase.FirstCrack, RoastPhase.Development):
                accel_trim *= 1.5

        crash_trim = 0.0
        if phase in (RoastPhase.FirstCrack, RoastPhase.Development):
            under = (target_ror - self.config.crash_ror_margin) - current_ror
            if under > 0.0:
                crash_trim = self.config.crash_fc_gain * under

        bias_air = 0.0
        if phase in (RoastPhase.Maillard, RoastPhase.FirstCrack, RoastPhase.Development) and bias > 0.2:
            bias_air = bias * self.config.energy_bias_fc_gain

        hp_raw = baseline_heater + hp_trim
        fc_raw = baseline_fan + fan_offset_corr + air_ror_trim + accel_trim + crash_trim + bias_air

        heater_slew = self.config.heater_slew_pct_per_sec
        if phase in (RoastPhase.FirstCrack, RoastPhase.Development):
            heater_slew = min(heater_slew, 3.0)
        heater_slew = heater_slew / max(0.8, machine.thermal_mass / 1.4)

        hp_slewed = apply_slew(self._last_hp, hp_raw, heater_slew, dt)
        fc_slewed = apply_slew(self._last_fc, fc_raw, self.config.fan_slew_pct_per_sec, dt)

        hp = int(round(_clip(hp_slewed, 0.0, 100.0)))
        fc = int(round(_clip(fc_slewed, 0.0, 100.0)))

        self._last_hp = float(hp)
        self._last_fc = float(fc)
        return hp, fc

    @property
    def energy_bias(self) -> float:
        return self._twin.state.energy_bias

    @property
    def thermal_state(self) -> ThermalState:
        return self._twin.state

    @property
    def twin(self) -> ThermalStateEstimator:
        return self._twin


# ---------------------------------------------------------------------------
# Backend protocol + Energy facade (Artisan sample-loop API)
# ---------------------------------------------------------------------------

class ControllerBackend(Protocol):
    """Sample-loop interface for Hybrid Energy or future MPC backends."""

    active: bool
    backend_name: str

    def reset(self) -> None: ...
    def activate(self) -> None: ...
    def update(
        self,
        bt: float,
        et: float,
        ror: float | None,
        ror_accel: float,
        timeindex: list[int],
        now: float,
        et_ror: float | None = None,
    ) -> tuple[int, int]: ...


class HybridController:
    """Energy backend: RoastPlanner + EnergyController for the Artisan sample loop.

    Satisfies ControllerBackend. Future MPC backends share this interface.
    """

    __slots__ = (
        'config', 'planner', 'energy', '_last_update_time', 'active',
        '_last_hp', '_last_fc', 'backend_name',
    )

    def __init__(self, config: HybridControllerConfig | None = None) -> None:
        self.config = config or HybridControllerConfig()
        self.planner = RoastPlanner(self.config)
        self.energy = EnergyController(self.config)
        self._last_update_time: float | None = None
        self._last_hp = 0.0
        self._last_fc = 0.0
        self.active = False
        self.backend_name = DEFAULT_CONTROL_BACKEND

    def reset(self) -> None:
        self.energy.reset()
        self._last_update_time = None
        self._last_hp = 0.0
        self._last_fc = 0.0
        self.active = False

    def activate(self) -> None:
        self.reset()
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

        dt = 1.0
        if self._last_update_time is not None:
            dt = max(0.05, now - self._last_update_time)
        self._last_update_time = now

        phase = detect_roast_phase(timeindex, bt, self.config)
        target_ror = self.planner.target_ror(bt, phase)
        current_ror = ror if ror is not None else 0.0
        et_ror_v = et_ror if et_ror is not None else 0.0

        hp, fc = self.energy.update(
            bt, et, current_ror, target_ror, ror_accel, phase, dt, et_ror=et_ror_v)
        self._last_hp = float(hp)
        self._last_fc = float(fc)
        return hp, fc


# Alias: HybridController is the shipped Energy-layer backend
EnergyBackend = HybridController


def normalize_control_backend(backend: str | None) -> str:
    """Return a valid backend name; unknown values fall back to energy."""
    name = (backend or DEFAULT_CONTROL_BACKEND).strip().lower()
    if name not in VALID_CONTROL_BACKENDS:
        _log.warning('Unknown hybridControlBackend %r; using %s', backend, DEFAULT_CONTROL_BACKEND)
        return DEFAULT_CONTROL_BACKEND
    return name


def create_controller_backend(
    backend: str = DEFAULT_CONTROL_BACKEND,
    config: HybridControllerConfig | None = None,
) -> HybridController:
    """Factory for Hybrid sample-loop backends (Energy default; MPC when requested)."""
    name = normalize_control_backend(backend)
    if name == 'mpc':
        from artisanlib.mpc_controller import MPCBackend
        return MPCBackend(config)  # type: ignore[return-value]
    ctrl = HybridController(config)
    ctrl.backend_name = name
    return ctrl
