#!/usr/bin/env python3
"""Fit Kaleido Lite thermal model params from Artisan .alog roast logs.

Example:
  python scripts/fit_kaleido_model.py --input docs/roasts --output docs/roasts/kaleido_model_m6.json
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

# Allow running without installing the package when invoked from repo root / scripts
_ROOT = pathlib.Path(__file__).resolve().parents[1]
_SRC = _ROOT / 'src'
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from artisanlib.kaleido_model import KaleidoModelParams  # noqa: E402
from artisanlib.kaleido_model_fit import (  # noqa: E402
    fit_params,
    load_alog_dir,
    load_alog_trace,
    params_to_dict,
    replay_rmse,
    save_params_json,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--input',
        required=True,
        help='Path to a .alog file or a directory of .alog files',
    )
    parser.add_argument(
        '--output',
        required=True,
        help='Output JSON path for fitted KaleidoModelParams',
    )
    parser.add_argument('--horizon', type=float, default=15.0, help='Replay horizon seconds')
    parser.add_argument('--stride', type=int, default=8, help='Sample stride during fit/replay')
    parser.add_argument('--maxiter', type=int, default=60)
    parser.add_argument('--limit', type=int, default=None, help='Optional max number of logs')
    args = parser.parse_args()

    src = pathlib.Path(args.input)
    if src.is_dir():
        traces = load_alog_dir(src, limit=args.limit)
    else:
        tr = load_alog_trace(src)
        traces = [tr] if tr is not None else []

    if not traces:
        print('No usable .alog traces with HP/FC channels found.', file=sys.stderr)
        return 1

    baseline = KaleidoModelParams()
    base_m = replay_rmse(baseline, traces, horizon_s=args.horizon, stride=args.stride)
    print(f'Loaded {len(traces)} traces')
    print(f'Default params 15s RMSE: BT={base_m["bt_rmse"]:.3f} ET={base_m["et_rmse"]:.3f} n={int(base_m["n"])}')

    fitted, metrics = fit_params(
        traces,
        seed=baseline,
        horizon_s=args.horizon,
        stride=args.stride,
        maxiter=args.maxiter,
    )
    print(
        f'Fitted params 15s RMSE: BT={metrics["bt_rmse"]:.3f} '
        f'ET={metrics["et_rmse"]:.3f} n={int(metrics["n"])} success={bool(metrics["success"])}'
    )
    out = pathlib.Path(args.output)
    save_params_json(fitted, out)
    meta = {
        'params': params_to_dict(fitted),
        'metrics': metrics,
        'baseline_metrics': base_m,
        'n_traces': len(traces),
        'horizon_s': args.horizon,
    }
    meta_path = out.with_suffix(out.suffix + '.meta.json')
    meta_path.write_text(json.dumps(meta, indent=2) + '\n', encoding='utf-8')
    print(f'Wrote {out}')
    print(f'Wrote {meta_path}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
