#!/usr/bin/env python3
"""Offline Energy vs MPC field A/B comparison on Artisan .alog roast logs.

Reports RoR RMSE vs the M6 shape schedule, peak |RoR|, and actuator travel.

Example:
  python scripts/compare_hybrid_backends.py --input docs/roasts --limit 5
"""
from __future__ import annotations

import argparse
import json
import math
import pathlib
import sys

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_SRC = _ROOT / 'src'
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import numpy as np  # noqa: E402

from artisanlib.hybrid_controller import (  # noqa: E402
    HybridController,
    HybridControllerConfig,
    create_controller_backend,
    detect_roast_phase,
    interpolate_ror_target,
)
from artisanlib.kaleido_model import ror_c_per_min  # noqa: E402
from artisanlib.kaleido_model_fit import load_alog_dir, load_alog_trace  # noqa: E402


def _finite(v: float) -> bool:
    return isinstance(v, (int, float)) and math.isfinite(v) and abs(v) < 900


def _score_trace(backend_name: str, tr: dict, config: HybridControllerConfig) -> dict[str, float]:
    if backend_name == 'mpc':
        from artisanlib.mpc_controller import MPCBackend, MpcConfig
        ctrl = MPCBackend(
            config,
            MpcConfig(horizon=12, maxiter=25, solver_timeout_ms=250.0),
        )
    else:
        ctrl = HybridController(config)
    ctrl.activate()
    # Seed actuators near first sample
    i0 = int(tr['charge'])
    i1 = int(tr['drop'])
    ctrl._last_hp = float(tr['hp'][i0]) if _finite(tr['hp'][i0]) else 70.0  # noqa: SLF001
    ctrl._last_fc = float(tr['fc'][i0]) if _finite(tr['fc'][i0]) else 40.0  # noqa: SLF001

    ror_err_sq = 0.0
    n = 0
    max_ror = 0.0
    hp_travel = 0.0
    fc_travel = 0.0
    prev_hp = ctrl._last_hp  # noqa: SLF001
    prev_fc = ctrl._last_fc  # noqa: SLF001
    prev_bt = float(tr['bt'][i0])

    for i in range(i0 + 1, i1 + 1):
        if not (_finite(tr['bt'][i]) and _finite(tr['et'][i])):
            continue
        dt = float(tr['timex'][i] - tr['timex'][i - 1])
        if dt <= 0 or dt > 5:
            continue
        bt = float(tr['bt'][i])
        et = float(tr['et'][i])
        ror = ror_c_per_min(prev_bt, bt, dt)
        # Build progressive timeindex snapshot for this sample index
        ti = list(tr.get('timeindex') or [])
        # Flatten future marks: only keep marks at/before i
        ti_now = []
        for k, v in enumerate(ti):
            ti_now.append(v if (isinstance(v, int) and v > 0 and v <= i) else 0)
        while len(ti_now) < 8:
            ti_now.append(0)
        hp, fc = ctrl.update(bt, et, ror, 0.0, ti_now, float(tr['timex'][i]))
        phase = detect_roast_phase(ti_now, bt, config)
        target = interpolate_ror_target(bt, phase, config)
        ror_err_sq += (ror - target) ** 2
        n += 1
        max_ror = max(max_ror, abs(ror))
        hp_travel += abs(hp - prev_hp)
        fc_travel += abs(fc - prev_fc)
        prev_hp, prev_fc = float(hp), float(fc)
        prev_bt = bt

    return {
        'ror_rmse': math.sqrt(ror_err_sq / n) if n else float('nan'),
        'max_abs_ror': max_ror,
        'hp_travel': hp_travel,
        'fc_travel': fc_travel,
        'n': float(n),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True, help='.alog file or directory')
    parser.add_argument('--limit', type=int, default=None)
    parser.add_argument('--output', default=None, help='Optional JSON summary path')
    args = parser.parse_args()

    src = pathlib.Path(args.input)
    if src.is_dir():
        traces = load_alog_dir(src, limit=args.limit)
    else:
        tr = load_alog_trace(src)
        traces = [tr] if tr else []
    if not traces:
        print('No usable traces', file=sys.stderr)
        return 1

    config = HybridControllerConfig()
    rows = []
    for tr in traces:
        e = _score_trace('energy', tr, config)
        m = _score_trace('mpc', tr, config)
        rows.append({
            'path': tr['path'],
            'energy': e,
            'mpc': m,
            'ror_rmse_delta': (m['ror_rmse'] - e['ror_rmse']) if e['n'] and m['n'] else float('nan'),
        })
        print(
            f"{tr['path']}: Energy RoR RMSE={e['ror_rmse']:.2f} "
            f"MPC={m['ror_rmse']:.2f} dRMSE={rows[-1]['ror_rmse_delta']:+.2f} "
            f"| HP travel E={e['hp_travel']:.0f} M={m['hp_travel']:.0f} "
            f"FC travel E={e['fc_travel']:.0f} M={m['fc_travel']:.0f}"
        )

    # Aggregate
    e_rmse = [r['energy']['ror_rmse'] for r in rows if math.isfinite(r['energy']['ror_rmse'])]
    m_rmse = [r['mpc']['ror_rmse'] for r in rows if math.isfinite(r['mpc']['ror_rmse'])]
    summary = {
        'n_traces': len(rows),
        'energy_ror_rmse_mean': float(np.mean(e_rmse)) if e_rmse else None,
        'mpc_ror_rmse_mean': float(np.mean(m_rmse)) if m_rmse else None,
        'rows': rows,
    }
    print(
        f"\nMean profile RoR RMSE (open-loop on recorded BT) — "
        f"Energy={summary['energy_ror_rmse_mean']:.3f} "
        f"MPC={summary['mpc_ror_rmse_mean']:.3f}"
    )
    print(
        'Note: RoR RMSE matches across backends offline because BT comes from the log; '
        'compare HP/FC travel here, then validate tracking on live identical lots.'
    )
    if args.output:
        out = pathlib.Path(args.output)
        out.write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
        print(f'Wrote {out}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
