#
# ABOUT
# Offline calibration of KaleidoModelParams from Artisan .alog roast logs
# (docs/kaleido_mpc_spec.md sec 17 / Phase C).
#
# LICENSE
# This program or module is free software: you can redistribute it and/or
# modify it under the terms of the GNU General Public License as published
# by the Free Software Foundation, either version 2 of the License, or
# version 3 of the License, or (at your option) any later version.

from __future__ import annotations

import ast
import json
import math
import pathlib
from dataclasses import fields
from typing import Any, Iterable

import numpy as np
from scipy.optimize import minimize

from artisanlib.kaleido_model import (
    KaleidoModelParams,
    estimate_state,
    step,
)

# Free parameters optimized during fit (T_amb left fixed)
_FIT_KEYS: tuple[str, ...] = (
    'tau_element',
    'tau_chamber',
    'tau_bean',
    'K_hp',
    'K_ec',
    'K_loss',
    'k_fc0',
    'k_fc1',
    'K_beans',
)

_BOUNDS: dict[str, tuple[float, float]] = {
    'tau_element': (6.0, 40.0),
    'tau_chamber': (10.0, 60.0),
    'tau_bean': (40.0, 240.0),
    'K_hp': (0.4, 1.6),
    'K_ec': (0.05, 1.2),
    'K_loss': (0.001, 0.15),
    'k_fc0': (0.002, 0.08),
    'k_fc1': (0.005, 0.20),
    'K_beans': (0.001, 0.05),
}


def params_to_dict(params: KaleidoModelParams) -> dict[str, float]:
    return {f.name: float(getattr(params, f.name)) for f in fields(params)}


def params_from_dict(data: dict[str, Any]) -> KaleidoModelParams:
    base = KaleidoModelParams()
    kwargs = {f.name: float(data[f.name]) for f in fields(base) if f.name in data}
    return KaleidoModelParams(**kwargs)


def save_params_json(params: KaleidoModelParams, path: pathlib.Path | str) -> None:
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(params_to_dict(params), indent=2) + '\n', encoding='utf-8')


def load_params_json(path: pathlib.Path | str) -> KaleidoModelParams:
    data = json.loads(pathlib.Path(path).read_text(encoding='utf-8'))
    return params_from_dict(data)


def load_alog_trace(path: pathlib.Path | str) -> dict[str, Any] | None:
    """Load BT/ET/HP/FC/timeindex from an Artisan .alog profile."""
    path = pathlib.Path(path)
    d = ast.literal_eval(path.read_text(encoding='utf-8', errors='replace'))
    timex = d.get('timex') or []
    et = d.get('temp1') or []
    bt = d.get('temp2') or []
    if not timex or not bt or not et or len(timex) != len(bt) or len(timex) != len(et):
        return None
    hp = fc = None
    if d.get('extratemp1') and d.get('extratemp2') and d['extratemp1'] and d['extratemp2']:
        hp = list(d['extratemp1'][0])
        fc = list(d['extratemp2'][0])
    if not hp or not fc or len(hp) != len(timex) or len(fc) != len(timex):
        return None
    ti = list(d.get('timeindex') or [])
    charge = ti[0] if len(ti) > 0 and ti[0] and ti[0] > 0 else 0
    drop = ti[6] if len(ti) > 6 and ti[6] and ti[6] > 0 else len(timex) - 1
    drop = min(drop, len(timex) - 1)
    if drop <= charge:
        charge, drop = 0, len(timex) - 1
    return {
        'path': path.name,
        'timex': list(timex),
        'bt': list(bt),
        'et': list(et),
        'hp': hp,
        'fc': fc,
        'timeindex': ti,
        'charge': int(charge),
        'drop': int(drop),
    }


def _finite(v: float) -> bool:
    return isinstance(v, (int, float)) and math.isfinite(v) and abs(v) < 900


def replay_rmse(
    params: KaleidoModelParams,
    traces: Iterable[dict[str, Any]],
    horizon_s: float = 15.0,
    stride: int = 5,
) -> dict[str, float]:
    """Open-loop multi-step BT/ET prediction RMSE feeding measured HP/FC."""
    bt_sq = 0.0
    et_sq = 0.0
    n = 0
    for tr in traces:
        timex = tr['timex']
        bt = tr['bt']
        et = tr['et']
        hp = tr['hp']
        fc = tr['fc']
        i0 = int(tr.get('charge', 0))
        i1 = int(tr.get('drop', len(timex) - 1))
        for i in range(i0, i1 - 1, max(1, stride)):
            if not (_finite(bt[i]) and _finite(et[i]) and _finite(hp[i]) and _finite(fc[i])):
                continue
            x = estimate_state(float(bt[i]), float(et[i]), float(hp[i]), params)
            t_end = timex[i] + horizon_s
            j = i
            ok = True
            while j + 1 <= i1 and timex[j + 1] <= t_end:
                dt = float(timex[j + 1] - timex[j])
                if dt <= 0 or dt > 5.0:
                    ok = False
                    break
                if not (_finite(hp[j]) and _finite(fc[j])):
                    ok = False
                    break
                u = np.array([float(hp[j]), float(fc[j])], dtype=float)
                x = step(x, u, dt, params)
                j += 1
            if not ok or j <= i:
                continue
            if not (_finite(bt[j]) and _finite(et[j])):
                continue
            bt_sq += (float(x[0]) - float(bt[j])) ** 2
            et_sq += (float(x[1]) - float(et[j])) ** 2
            n += 1
    if n == 0:
        return {'bt_rmse': float('inf'), 'et_rmse': float('inf'), 'n': 0}
    return {
        'bt_rmse': float(math.sqrt(bt_sq / n)),
        'et_rmse': float(math.sqrt(et_sq / n)),
        'n': float(n),
    }


def _vector_from_params(params: KaleidoModelParams) -> np.ndarray:
    return np.array([getattr(params, k) for k in _FIT_KEYS], dtype=float)


def _params_from_vector(z: np.ndarray, template: KaleidoModelParams) -> KaleidoModelParams:
    d = params_to_dict(template)
    for i, k in enumerate(_FIT_KEYS):
        d[k] = float(z[i])
    return params_from_dict(d)


def fit_params(
    traces: list[dict[str, Any]],
    seed: KaleidoModelParams | None = None,
    horizon_s: float = 15.0,
    stride: int = 8,
    maxiter: int = 60,
) -> tuple[KaleidoModelParams, dict[str, float]]:
    """Minimize BT+ET replay RMSE over free model parameters."""
    seed = seed or KaleidoModelParams()
    if not traces:
        raise ValueError('No traces to fit')

    def objective(z: np.ndarray) -> float:
        p = _params_from_vector(z, seed)
        m = replay_rmse(p, traces, horizon_s=horizon_s, stride=stride)
        if m['n'] < 10:
            return 1e6
        return float(m['bt_rmse'] + 0.5 * m['et_rmse'])

    z0 = _vector_from_params(seed)
    bounds = [_BOUNDS[k] for k in _FIT_KEYS]
    result = minimize(
        objective,
        z0,
        method='L-BFGS-B',
        bounds=bounds,
        options={'maxiter': maxiter, 'ftol': 1e-4},
    )
    fitted = _params_from_vector(np.asarray(result.x, dtype=float), seed)
    metrics = replay_rmse(fitted, traces, horizon_s=horizon_s, stride=stride)
    metrics['cost'] = float(result.fun) if result.fun is not None else float('nan')
    metrics['success'] = 1.0 if result.success else 0.0
    return fitted, metrics


def load_alog_dir(directory: pathlib.Path | str, limit: int | None = None) -> list[dict[str, Any]]:
    directory = pathlib.Path(directory)
    traces: list[dict[str, Any]] = []
    for path in sorted(directory.glob('*.alog')):
        tr = load_alog_trace(path)
        if tr is not None:
            traces.append(tr)
        if limit is not None and len(traces) >= limit:
            break
    return traces
