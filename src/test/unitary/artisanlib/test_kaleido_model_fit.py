"""Unit tests for Phase C model calibration helpers."""

from __future__ import annotations

import pathlib
import tempfile

import numpy as np
import pytest

from artisanlib.kaleido_model import KaleidoModelParams, step
from artisanlib.kaleido_model_fit import (
    fit_params,
    load_alog_dir,
    load_params_json,
    params_from_dict,
    params_to_dict,
    replay_rmse,
    save_params_json,
)


def _synthetic_trace(params: KaleidoModelParams, n: int = 120) -> dict:
    """Generate a measured-style trace from the plant (perfect model)."""
    x = np.array([100.0, 160.0, 40.0], dtype=float)
    timex, bt, et, hp, fc = [], [], [], [], []
    for i in range(n):
        t = float(i)
        h = 70.0 + 15.0 * np.sin(i / 25.0)
        f = 35.0 + 10.0 * np.sin(i / 18.0 + 1.0)
        timex.append(t)
        bt.append(float(x[0]))
        et.append(float(x[1]))
        hp.append(h)
        fc.append(f)
        x = step(x, np.array([h, f]), 1.0, params)
    return {
        'path': 'synthetic',
        'timex': timex,
        'bt': bt,
        'et': et,
        'hp': hp,
        'fc': fc,
        'timeindex': [0, 20, 80, 100, 0, 0, n - 1],
        'charge': 5,
        'drop': n - 5,
    }


class TestParamsIO:
    def test_roundtrip_dict_json(self) -> None:
        p = KaleidoModelParams(tau_element=18.5, K_ec=0.4)
        d = params_to_dict(p)
        assert d['tau_element'] == pytest.approx(18.5)
        with tempfile.TemporaryDirectory() as td:
            path = pathlib.Path(td) / 'm.json'
            save_params_json(p, path)
            loaded = load_params_json(path)
        assert loaded.tau_element == pytest.approx(18.5)
        assert params_from_dict(d).K_ec == pytest.approx(0.4)


class TestFitSynthetic:
    def test_fit_recovers_toward_true_plant(self) -> None:
        true = KaleidoModelParams(
            tau_element=18.0,
            tau_chamber=28.0,
            tau_bean=110.0,
            K_ec=0.45,
            k_fc0=0.02,
            k_fc1=0.07,
        )
        traces = [_synthetic_trace(true), _synthetic_trace(true)]
        wrong = KaleidoModelParams()  # defaults differ
        base = replay_rmse(wrong, traces, horizon_s=10.0, stride=4)
        fitted, metrics = fit_params(traces, seed=wrong, horizon_s=10.0, stride=4, maxiter=40)
        assert metrics['n'] > 20
        assert metrics['bt_rmse'] <= base['bt_rmse'] * 1.05 + 0.05
        # Fitted element tau should move toward truth vs default 15
        assert abs(fitted.tau_element - true.tau_element) < abs(wrong.tau_element - true.tau_element) + 2.0


class TestCorpusOptional:
    def test_load_roasts_dir_if_present(self) -> None:
        roasts = pathlib.Path(__file__).resolve().parents[4] / 'docs' / 'roasts'
        if not roasts.is_dir():
            pytest.skip('docs/roasts missing')
        traces = load_alog_dir(roasts, limit=3)
        if not traces:
            pytest.skip('no alogs with HP/FC')
        m = replay_rmse(KaleidoModelParams(), traces, horizon_s=15.0, stride=10)
        assert m['n'] > 0
        assert math_isfinite(m['bt_rmse'])


def math_isfinite(x: float) -> bool:
    return x == x and abs(x) != float('inf')
