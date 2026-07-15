"""One-shot analysis of docs/roasts/*.alog for schedule + plant response.

Run: python docs/roasts/_analyze_m6_logs.py
"""
from __future__ import annotations

import ast
import math
import pathlib
from collections import defaultdict

ROOT = pathlib.Path(__file__).resolve().parent


def se_to_pct(v: float) -> float:
    return (v - 1.0) * 10.0


def finite(xs):
    return [
        x
        for x in xs
        if x is not None
        and isinstance(x, (int, float))
        and math.isfinite(x)
        and abs(x) < 900
    ]


def quantiles(xs, qs=(0.1, 0.25, 0.5, 0.75, 0.9)):
    xs = sorted(finite(xs))
    if not xs:
        return None

    def q(p):
        if len(xs) == 1:
            return xs[0]
        pos = (len(xs) - 1) * p
        lo = int(math.floor(pos))
        hi = int(math.ceil(pos))
        if lo == hi:
            return xs[lo]
        return xs[lo] * (hi - pos) + xs[hi] * (pos - lo)

    out = {f"p{int(p * 100)}": round(q(p), 2) for p in qs}
    out["mean"] = round(sum(xs) / len(xs), 2)
    out["n"] = len(xs)
    return out


def ror_series(timex, bt, window_s=30.0):
    n = len(timex)
    ror = [float("nan")] * n
    j = 0
    for i in range(n):
        t = timex[i]
        while j < i and t - timex[j] > window_s:
            j += 1
        if i == j or timex[i] == timex[j]:
            continue
        dt = timex[i] - timex[j]
        if dt > 0:
            ror[i] = (bt[i] - bt[j]) / dt * 60.0
    return ror


def idx_at(ti, k):
    return ti[k] if len(ti) > k and ti[k] and ti[k] > 0 else None


def phase_slices(ti, bt, yellow_bt=150.0, maillard_bt=170.0):
    charge = idx_at(ti, 0)
    dry = idx_at(ti, 1)
    fcs = idx_at(ti, 2)
    fce = idx_at(ti, 3)
    drop = idx_at(ti, 6)
    if charge is None or drop is None or drop <= charge:
        return {}

    out = {}
    # Early drying vs yellow: split by BT if DRY event after yellow
    # Charge→Yellow: from charge while BT < yellow (or until dry/fcs)
    yellow_i = None
    maillard_i = None
    for i in range(charge, drop + 1):
        if yellow_i is None and bt[i] >= yellow_bt:
            yellow_i = i
        if maillard_i is None and bt[i] >= maillard_bt:
            maillard_i = i
            break

    end_pre_fc = fcs if fcs else drop
    dry_end = dry if dry and dry < end_pre_fc else end_pre_fc

    # charge / early drying
    early_end = yellow_i if yellow_i and yellow_i < dry_end else dry_end
    if early_end > charge:
        out["charge_drying"] = (charge, early_end)
    if yellow_i and yellow_i < dry_end:
        out["yellow"] = (yellow_i, dry_end)
    # if no yellow split, charge_drying covers to dry
    if dry_end > early_end and "yellow" not in out and early_end == dry_end:
        pass

    # Maillard: dry (or yellow->maillard BT) to FCs
    m_start = dry_end
    if maillard_i and maillard_i > m_start and maillard_i < end_pre_fc:
        # stretch from dry_end already includes post-yellow; if yellow used, maillard after dry event
        pass
    if end_pre_fc > m_start:
        # if dry marked before maillard BT, still call interval maillard (Artisan DRY)
        out["maillard"] = (m_start, end_pre_fc)

    if fcs and drop > fcs:
        if fce and fcs < fce < drop:
            out["firstcrack"] = (fcs, fce)
            out["development"] = (fce, drop)
        else:
            mid = min(drop, fcs + 25)
            out["firstcrack"] = (fcs, mid)
            if drop > mid:
                out["development"] = (mid, drop)
    return out


def load(path: pathlib.Path):
    d = ast.literal_eval(path.read_text(encoding="utf-8", errors="replace"))
    timex = d["timex"]
    et = d["temp1"]
    bt = d["temp2"]
    ti = d.get("timeindex") or []
    hp = fc = None
    if d.get("extratemp1") and d.get("extratemp2") and d["extratemp1"]:
        hp = d["extratemp1"][0]
        fc = d["extratemp2"][0]
    events = []
    for i, t, v, s in zip(
        d.get("specialevents") or [],
        d.get("specialeventstype") or [],
        d.get("specialeventsvalue") or [],
        d.get("specialeventsStrings") or [],
    ):
        events.append((int(i), int(t), se_to_pct(float(v)), s))
    weight = d.get("weight") or [None]
    return {
        "path": path.name,
        "weight": weight[0] if weight else None,
        "timex": timex,
        "et": et,
        "bt": bt,
        "hp": hp,
        "fc": fc,
        "timeindex": ti,
        "events": events,
        "computed": d.get("computed") or {},
    }


def series_slice(xs, a, b):
    return [xs[i] for i in range(a, b) if i < len(xs)]


def detect_steps(series, timex, min_delta=5.0, min_hold_s=8.0):
    """Detect sustained level changes in HP/FC command series."""
    steps = []
    if not series or len(series) < 3:
        return steps
    # find change points
    i = 1
    while i < len(series):
        if not (math.isfinite(series[i]) and math.isfinite(series[i - 1])):
            i += 1
            continue
        d = series[i] - series[i - 1]
        if abs(d) >= min_delta:
            # new level from i
            level = series[i]
            j = i
            while j + 1 < len(series) and abs(series[j + 1] - level) < 2.0:
                j += 1
            hold = timex[j] - timex[i] if j > i else 0
            if hold >= min_hold_s:
                steps.append(
                    {
                        "i": i,
                        "t": timex[i],
                        "delta": d,
                        "from": series[i - 1],
                        "to": level,
                        "hold_s": hold,
                    }
                )
            i = max(i + 1, j)
        else:
            i += 1
    return steps


def response_metrics(r, step, channel: str, look_s=90.0):
    """After an HP or FC step, measure delayed ET/BT/RoR response."""
    i0 = step["i"]
    timex, et, bt = r["timex"], r["et"], r["bt"]
    ror = r["_ror"]
    t0 = timex[i0]
    # baseline 10s before
    pre = [j for j in range(i0) if t0 - 15 <= timex[j] < t0 - 2]
    if len(pre) < 3:
        return None
    et0 = sum(et[j] for j in pre) / len(pre)
    bt0 = sum(bt[j] for j in pre) / len(pre)
    ror0 = sum(ror[j] for j in pre if math.isfinite(ror[j])) / max(
        1, sum(1 for j in pre if math.isfinite(ror[j]))
    )

    post = [j for j, t in enumerate(timex) if t0 < t <= t0 + look_s]
    if len(post) < 5:
        return None

    # sign expected: HP up -> ET/RoR up; FC up -> often ET-BT shrinks / cooling effect on RoR
    sign = 1.0 if step["delta"] > 0 else -1.0

    def first_significant(series_vals, baseline, thresh):
        for j in post:
            v = series_vals[j]
            if not math.isfinite(v):
                continue
            if sign * (v - baseline) >= thresh:
                return timex[j] - t0, v - baseline
        return None, None

    if channel == "hp":
        et_lag, et_d = first_significant(et, et0, 1.0)
        # BT slower
        bt_lag, bt_d = first_significant(bt, bt0, 0.5)
        ror_lag, ror_d = first_significant(ror, ror0, 0.4)
        # peak RoR change in window
        ror_changes = [(ror[j] - ror0) for j in post if math.isfinite(ror[j])]
        peak = max(ror_changes, key=lambda x: sign * x) if ror_changes else None
        return {
            "et_lag_s": et_lag,
            "bt_lag_s": bt_lag,
            "ror_lag_s": ror_lag,
            "et_d": et_d,
            "bt_d": bt_d,
            "ror_d": ror_d,
            "ror_peak_d": peak,
            "delta_u": step["delta"],
        }
    else:
        # FC: look at offset et-bt and ror
        offs = [et[j] - bt[j] for j in pre]
        off0 = sum(offs) / len(offs)
        off_series = et  # placeholder misuse; compute inline
        off_lag = None
        off_d = None
        for j in post:
            off = et[j] - bt[j]
            # FC up often reduces offset or BT RoR; look for offset drop when FC up
            if step["delta"] > 0 and (off0 - off) >= 1.0:
                off_lag = timex[j] - t0
                off_d = off - off0
                break
            if step["delta"] < 0 and (off - off0) >= 1.0:
                off_lag = timex[j] - t0
                off_d = off - off0
                break
        ror_lag, ror_d = first_significant(ror, ror0, 0.3)
        # for FC up, significant ror change is often negative; flip for detection
        if ror_lag is None and step["delta"] > 0:
            for j in post:
                if math.isfinite(ror[j]) and (ror0 - ror[j]) >= 0.4:
                    ror_lag = timex[j] - t0
                    ror_d = ror[j] - ror0
                    break
        return {
            "offset_lag_s": off_lag,
            "offset_d": off_d,
            "ror_lag_s": ror_lag,
            "ror_d": ror_d,
            "delta_u": step["delta"],
            "off0": off0,
        }


def bt_noise_metrics(r, i0, i1, win=5):
    """High-freq BT variation: residual vs short moving average."""
    bt = r["bt"]
    seg = bt[i0:i1]
    if len(seg) < win * 3:
        return None
    resid = []
    for i in range(win, len(seg) - win):
        ma = sum(seg[i - win : i + win + 1]) / (2 * win + 1)
        resid.append(seg[i] - ma)
    if not resid:
        return None
    # robust scale
    ar = sorted(abs(x) for x in resid)
    mad = ar[len(ar) // 2]
    rms = math.sqrt(sum(x * x for x in resid) / len(resid))
    # spike rate: |resid| > 0.8 C
    spikes = sum(1 for x in resid if abs(x) > 0.8) / len(resid)
    return {"mad": mad, "rms": rms, "spike_frac": spikes, "n": len(resid)}


def main():
    roasts = []
    for f in sorted(ROOT.glob("*.alog")):
        if f.name.startswith("_"):
            continue
        try:
            roasts.append(load(f))
        except Exception as e:
            print("FAIL", f.name, e)

    print(f"loaded {len(roasts)} roasts\n")

    # ---- corpus summary ----
    for r in roasts:
        c = r["computed"]
        print(
            f"{r['path'][:52]:52} w={r['weight']} "
            f"CHARGE={c.get('CHARGE_BT')} DRY={c.get('DRY_BT')} "
            f"FCs={c.get('FCs_BT')} DROP={c.get('DROP_BT')} t={c.get('DROP_time')}"
        )

    # ---- per-phase aggregates ----
    phase_ror = defaultdict(list)
    phase_hp = defaultdict(list)
    phase_fc = defaultdict(list)
    phase_off = defaultdict(list)
    phase_bt = defaultdict(list)
    noise_by_phase = defaultdict(list)
    # BT-binned RoR for shape
    bt_bin_ror = defaultdict(list)  # bin 10C -> ror

    for r in roasts:
        r["_ror"] = ror_series(r["timex"], r["bt"], 30.0)
        phases = phase_slices(r["timeindex"], r["bt"])
        for name, (a, b) in phases.items():
            if b <= a + 3:
                continue
            for i in range(a, b):
                if math.isfinite(r["_ror"][i]) and 0 < r["_ror"][i] < 40:
                    phase_ror[name].append(r["_ror"][i])
                if r["hp"] and math.isfinite(r["hp"][i]):
                    phase_hp[name].append(r["hp"][i])
                if r["fc"] and math.isfinite(r["fc"][i]):
                    phase_fc[name].append(r["fc"][i])
                if math.isfinite(r["et"][i]) and math.isfinite(r["bt"][i]):
                    phase_off[name].append(r["et"][i] - r["bt"][i])
                    phase_bt[name].append(r["bt"][i])
                # bins
                if math.isfinite(r["bt"][i]) and math.isfinite(r["_ror"][i]):
                    if 0 < r["_ror"][i] < 40:
                        bin_lo = int(r["bt"][i] // 10) * 10
                        bt_bin_ror[bin_lo].append(r["_ror"][i])
            n = bt_noise_metrics(r, a, b)
            if n:
                noise_by_phase[name].append(n)

        # also early post-charge peak RoR window (first 60s after TP-ish)
        ti = r["timeindex"]
        charge = idx_at(ti, 0)
        drop = idx_at(ti, 6)
        if charge is not None and drop is not None:
            # finding TP as min BT after charge within 90s
            end = charge
            while end < drop and r["timex"][end] - r["timex"][charge] < 90:
                end += 1
            if end > charge + 2:
                tp_i = min(range(charge, end), key=lambda i: r["bt"][i])
                # 30-90s after TP
                for i in range(tp_i, drop):
                    if r["timex"][i] - r["timex"][tp_i] > 90:
                        break
                    if r["timex"][i] - r["timex"][tp_i] < 20:
                        continue
                    if math.isfinite(r["_ror"][i]) and r["_ror"][i] > 0:
                        phase_ror["post_tp_rise"].append(r["_ror"][i])
                        if r["hp"]:
                            phase_hp["post_tp_rise"].append(r["hp"][i])
                        if r["fc"]:
                            phase_fc["post_tp_rise"].append(r["fc"][i])

    print("\n=== PHASE RoR (°C/min, 30s window) ===")
    for name in [
        "post_tp_rise",
        "charge_drying",
        "yellow",
        "maillard",
        "firstcrack",
        "development",
    ]:
        print(f"  {name:16} {quantiles(phase_ror[name])}")

    print("\n=== PHASE HP % ===")
    for name in ["charge_drying", "yellow", "maillard", "firstcrack", "development", "post_tp_rise"]:
        print(f"  {name:16} {quantiles(phase_hp[name])}")

    print("\n=== PHASE FC % ===")
    for name in ["charge_drying", "yellow", "maillard", "firstcrack", "development", "post_tp_rise"]:
        print(f"  {name:16} {quantiles(phase_fc[name])}")

    print("\n=== PHASE ET-BT °C ===")
    for name in ["charge_drying", "yellow", "maillard", "firstcrack", "development"]:
        print(f"  {name:16} {quantiles(phase_off[name])}")

    print("\n=== RoR by BT bin (median) ===")
    for bin_lo in sorted(bt_bin_ror):
        if bin_lo < 90 or bin_lo > 220:
            continue
        q = quantiles(bt_bin_ror[bin_lo])
        if q:
            print(f"  BT {bin_lo:3d}-{bin_lo+10}: median={q['p50']} mean={q['mean']} n={q['n']}")

    print("\n=== BT probe noise (residual vs 11pt MA) ===")
    for name in ["charge_drying", "yellow", "maillard", "firstcrack", "development"]:
        ms = noise_by_phase[name]
        if not ms:
            print(f"  {name}: none")
            continue
        print(
            f"  {name:16} mad_med={statistics_median([m['mad'] for m in ms]):.3f} "
            f"rms_med={statistics_median([m['rms'] for m in ms]):.3f} "
            f"spike_frac_med={statistics_median([m['spike_frac'] for m in ms]):.3f} "
            f"roasts={len(ms)}"
        )

    # ---- step response ----
    hp_resp = []
    fc_resp = []
    for r in roasts:
        if not r["hp"] or not r["fc"]:
            continue
        ti = r["timeindex"]
        charge = idx_at(ti, 0)
        drop = idx_at(ti, 6)
        if charge is None or drop is None:
            continue
        # only analyze charge→drop
        for step in detect_steps(r["hp"], r["timex"], min_delta=8.0, min_hold_s=12.0):
            if not (charge <= step["i"] < drop):
                continue
            m = response_metrics(r, step, "hp")
            if m:
                m["path"] = r["path"]
                m["kind"] = "hp"
                hp_resp.append(m)
        for step in detect_steps(r["fc"], r["timex"], min_delta=8.0, min_hold_s=12.0):
            if not (charge <= step["i"] < drop):
                continue
            m = response_metrics(r, step, "fc")
            if m:
                m["path"] = r["path"]
                m["kind"] = "fc"
                fc_resp.append(m)

    def lag_summary(rows, key):
        vals = [r[key] for r in rows if r.get(key) is not None]
        return quantiles(vals)

    print(f"\n=== HP STEP RESPONSES (n={len(hp_resp)}) ===")
    print("  ET lag s:", lag_summary(hp_resp, "et_lag_s"))
    print("  BT lag s:", lag_summary(hp_resp, "bt_lag_s"))
    print("  RoR lag s:", lag_summary(hp_resp, "ror_lag_s"))
    # gain-ish: ror_peak / delta_u
    gains = []
    for m in hp_resp:
        if m.get("ror_peak_d") is not None and abs(m["delta_u"]) >= 8:
            gains.append(m["ror_peak_d"] / m["delta_u"])
    print("  dRoR_peak / dHP:", quantiles(gains))

    print(f"\n=== FC STEP RESPONSES (n={len(fc_resp)}) ===")
    print("  offset lag s:", lag_summary(fc_resp, "offset_lag_s"))
    print("  RoR lag s:", lag_summary(fc_resp, "ror_lag_s"))
    # typical signed ror change when FC increases
    fc_up = [m for m in fc_resp if m["delta_u"] > 0]
    print("  FC-up RoR delta:", quantiles([m["ror_d"] for m in fc_up if m.get("ror_d") is not None]))
    print("  FC-up offset delta:", quantiles([m["offset_d"] for m in fc_up if m.get("offset_d") is not None]))

    # atypical HP trajectories: list median HP trajectory by phase for each roast briefly
    print("\n=== PER-ROAST MEDIAN HP/FC BY PHASE (compact) ===")
    for r in roasts:
        phases = phase_slices(r["timeindex"], r["bt"])
        bits = []
        for name in ["charge_drying", "yellow", "maillard", "firstcrack", "development"]:
            if name not in phases or not r["hp"]:
                continue
            a, b = phases[name]
            hps = finite(r["hp"][a:b])
            fcs = finite(r["fc"][a:b]) if r["fc"] else []
            if hps and fcs:
                bits.append(f"{name[0:3]} H{median(hps):.0f}/F{median(fcs):.0f}")
        print(f"  {r['path'][:48]:48} {' '.join(bits)}")


def statistics_median(xs):
    xs = sorted(xs)
    if not xs:
        return float("nan")
    return xs[len(xs) // 2]


def median(xs):
    return statistics_median(xs)


if __name__ == "__main__":
    main()
