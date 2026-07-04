#
# ABOUT
# Hybrid Heater + Airflow Controller for Kaleido roasters

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
from typing import Final

_log: Final[logging.Logger] = logging.getLogger(__name__)


class RoastPhase(IntEnum):
    Charge = 0
    Drying = 1
    Yellow = 2
    Maillard = 3
    FirstCrack = 4
    Development = 5
    Cooling = 6


# Default ET-BT offset (°C) and baseline fan (%) per roast phase
DEFAULT_ET_BT_OFFSETS: Final[dict[RoastPhase, float]] = {
    RoastPhase.Charge: 60.0,
    RoastPhase.Drying: 60.0,
    RoastPhase.Yellow: 50.0,
    RoastPhase.Maillard: 45.0,
    RoastPhase.FirstCrack: 35.0,
    RoastPhase.Development: 25.0,
    RoastPhase.Cooling: 25.0,
}

DEFAULT_BASELINE_FAN: Final[dict[RoastPhase, float]] = {
    RoastPhase.Charge: 20.0,
    RoastPhase.Drying: 30.0,
    RoastPhase.Yellow: 40.0,
    RoastPhase.Maillard: 50.0,
    RoastPhase.FirstCrack: 70.0,
    RoastPhase.Development: 80.0,
    RoastPhase.Cooling: 80.0,
}


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
    default_ror_target: float = 10.0
    yellow_bt: float = 150.0
    maillard_bt: float = 170.0
    drying_bt: float = 100.0
    et_bt_offsets: dict[RoastPhase, float] = field(default_factory=lambda: dict(DEFAULT_ET_BT_OFFSETS))
    baseline_fan: dict[RoastPhase, float] = field(default_factory=lambda: dict(DEFAULT_BASELINE_FAN))


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
        # Anti-windup: clamp integral contribution
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


def compute_ror_acceleration(ror_samples: list[float], dt: float) -> float:
    """Finite-difference RoR acceleration from recent samples."""
    if len(ror_samples) < 2 or dt <= 0:
        return 0.0
    return (ror_samples[-1] - ror_samples[-2]) / dt


def apply_slew(current: float, target: float, max_rate_per_sec: float, dt: float) -> float:
    if dt <= 0:
        return target
    max_change = max_rate_per_sec * dt
    delta = target - current
    if abs(delta) <= max_change:
        return target
    return current + math.copysign(max_change, delta)


class HybridController:
    """Coordinated slow heater (RoR) and fast fan (ET-BT offset) controller."""

    __slots__ = ('config', '_heater_pid', '_fan_pid', '_last_hp', '_last_fc', '_last_update_time', 'active')

    def __init__(self, config: HybridControllerConfig | None = None) -> None:
        self.config = config or HybridControllerConfig()
        self._heater_pid = SimplePID(
            self.config.heater_kp, self.config.heater_ki, self.config.heater_kd, 0.0, 100.0)
        self._fan_pid = SimplePID(
            self.config.fan_kp, self.config.fan_ki, self.config.fan_kd, -30.0, 30.0)
        self._last_hp = 0.0
        self._last_fc = 0.0
        self._last_update_time: float | None = None
        self.active = False

    def reset(self) -> None:
        self._heater_pid.reset()
        self._fan_pid.reset()
        self._last_hp = 0.0
        self._last_fc = 0.0
        self._last_update_time = None
        self.active = False

    def activate(self) -> None:
        self.reset()
        self.active = True

    def get_schedule(self, phase: RoastPhase) -> tuple[float, float]:
        offset = self.config.et_bt_offsets.get(phase, DEFAULT_ET_BT_OFFSETS.get(phase, 45.0))
        baseline = self.config.baseline_fan.get(phase, DEFAULT_BASELINE_FAN.get(phase, 50.0))
        return offset, baseline

    def update(
        self,
        bt: float,
        et: float,
        ror: float | None,
        ror_accel: float,
        timeindex: list[int],
        bg_ror_target: float | None,
        now: float,
    ) -> tuple[int, int]:
        if not self.active:
            return int(round(self._last_hp)), int(round(self._last_fc))

        dt = 1.0
        if self._last_update_time is not None:
            dt = max(0.05, now - self._last_update_time)
        self._last_update_time = now

        phase = detect_roast_phase(timeindex, bt, self.config)
        target_offset, baseline_fan = self.get_schedule(phase)

        # --- Heater: slow RoR PID ---
        ror_target = bg_ror_target if bg_ror_target is not None else self.config.default_ror_target
        current_ror = ror if ror is not None else 0.0
        hp_raw = self._heater_pid.update(ror_target, current_ror, dt)

        # --- Fan: fast ET-BT offset PID + baseline + RoR acceleration trim ---
        et_bt = et - bt
        fan_correction = self._fan_pid.update(target_offset, et_bt, dt)
        accel_trim = 0.0
        if ror_accel > self.config.ror_accel_threshold:
            accel_trim = self.config.ror_accel_gain * ror_accel
            if phase == RoastPhase.FirstCrack:
                accel_trim *= 1.5
        fc_raw = baseline_fan + fan_correction + accel_trim

        hp_slewed = apply_slew(self._last_hp, hp_raw, self.config.heater_slew_pct_per_sec, dt)
        fc_slewed = apply_slew(self._last_fc, fc_raw, self.config.fan_slew_pct_per_sec, dt)

        hp = int(round(max(0.0, min(100.0, hp_slewed))))
        fc = int(round(max(0.0, min(100.0, fc_slewed))))

        self._last_hp = float(hp)
        self._last_fc = float(fc)
        return hp, fc
