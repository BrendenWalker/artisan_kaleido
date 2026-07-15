# Hybrid Energy vs MPC — Live Field A/B Plan

**Audience:** Operator roasting ~weekly (not back-to-back).  
**Goal:** Decide whether Lite MPC beats (or at least matches) Energy on a real M6 plant.  
**Canonical control docs:** [kaleido_mpc_spec.md](kaleido_mpc_spec.md) §19.4, [README.md](../README.md).

Offline replay cannot answer this — BT is from the log, so RoR tracking looks identical. Live closed-loop pairs are required.

---

## 1. Success criteria (decide this before roast 1)

After **at least 3 matched pairs** (6 Hybrid roasts: 3 Energy + 3 MPC), score each pair and then the set average.

| Outcome | Decision |
|---------|----------|
| MPC RoR RMSE **≤ Energy** (or within ~10%) **and** actuator travel **≤ Energy** (or within ~15%), with no worse FC peaks | Keep MPC as a viable option; consider more pairs or default later |
| Tracking similar, travel clearly worse on MPC | Prefer Energy; treat MPC as experimental only |
| MPC worse tracking or unsafe behavior (oscillation, runaway HP, late FC flick) | Stay on Energy; file notes / abort MPC on machine |
| Incomplete pairs / major confounders | Do not decide; continue until 3 clean pairs |

**Primary metrics (CHARGE → DROP):**

1. **RoR RMSE vs schedule** — measured RoR vs built-in M6 target (by phase/BT)  
2. **max |RoR|** — especially from ~1 min before FCs through DROP  
3. **HP travel / FC travel** — sum of absolute command steps (∑|Δ|)

**Secondary (note, don’t over-weight early):** DROP BT & time, FCs RoR, development time, cup notes if you cup.

---

## 2. Why weekly spacing changes the design

Back-to-back pairs kill ambient / machine / bean aging noise. You don’t have that, so the study must:

- **Freeze everything else** harder than a same-day A/B.
- **Alternate backends** so seasonal/ambient drift isn’t mistaken for MPC.
- Treat each roast as a **labeled trial**, not a vibe check.
- Require **≥3 pairs** before any product decision (one lucky day is not evidence).

### Recommended order (write this into the scorecard)

| Session # | Backend | Pair ID |
|-----------|---------|---------|
| 1 | Energy | P1-A |
| 2 | MPC | P1-B |
| 3 | Energy | P2-A |
| 4 | MPC | P2-B |
| 5 | Energy | P3-A |
| 6 | MPC | P3-B |

Always start a pair with Energy (known baseline), then MPC the next roast week. If you miss a week, **do not skip** — resume at the next row; do not “make up” by doing two MPC weeks in a row unless you explicitly restart pairing.

Optional later: reverse order for pairs 4–6 (MPC then Energy) to check order bias.

---

## 3. Freeze list (do not change mid-study)

Lock these before Session 1 and leave them alone until 3 pairs are done:

| Variable | Rule |
|----------|------|
| Green lot | Same SKU / lot code; portion from one blended bag if possible |
| Charge weight | Same grams every trial (corpus ~600 g; use your usual M6 charge) |
| Machine | Same roaster, drum, probe paths |
| Control mode | **Hybrid Controller** only (not Machine PID / Software PID for the comparison window) |
| Hybrid gains / slews | Do not retune Device Hybrid PID / slew / crash gains mid-study |
| Schedule | Built-in M6 shape only (no schedule editor yet) |
| Background profile | Optional for eyes only; must **not** change control intent. Use the **same** background every trial or none |
| Artisan build | Prefer one `hybrid_control` build across the study; note commit/date if you update |
| Target profile | Same intended DROP BT / development habit (e.g. “drop at FCs+… or BT …”) |

**Allowed to vary (record them):** ambient temp, humidity, bean age (days since roast of green bag open), roast date/time.

---

## 4. Per-session prep (night before or morning of)

Copy this onto a sticky note / phone note:

1. **Look up next session #** in the table above → set backend **before** connecting if possible.  
2. **Config → Device → Kaleido Control → Hybrid Controller → Hybrid backend** = Energy *or* MPC.  
3. Confirm Control checkbox on; ET/BT = Kaleido.  
4. Portion greens to the locked charge weight; write bag open date / lot on the scorecard.  
5. Ensure enough disk for `.alog` save; choose a fixed save folder (e.g. `docs/roasts/ab/` or your usual Artisan folder).  
6. Filename convention (critical for week-spaced work):

```text
YYYY-MM-DD_P{pair}-{A|B}_{energy|mpc}_{lot}_{weight}g.alog
```

Example: `2026-07-20_P1-A_energy_eth_600g.alog`

7. Optional: load the same background profile used for all trials.

---

## 5. Roast-day checklist (same every session)

### 5.1 Before ON

- [ ] Backend matches today’s row (Energy / MPC)  
- [ ] Hybrid gains untouched  
- [ ] Charge weight confirmed  
- [ ] Scorecard row started (date, ambient, lot age, backend)

### 5.2 Warmup → Hybrid (standard Kaleido Hybrid flow)

1. **ON** — monitor; set warmup **SV** (same target every trial)  
2. **Start Heating** — Machine PID warmup (`AH=1`)  
3. **START** — recording  
4. **CHARGE** at the usual charge condition — Hybrid takes over (`AH=0`, HP+FC)  
5. Mark **DRY / FCs / FCe / DROP** as you normally do (BT fallback exists, but consistent marks help scoring)

Do **not** manually fight Hybrid with sliders unless aborting (see §7).

### 5.3 During roast — glance notes only

Write short notes if something is “off”; don’t try to interpret mid-roast:

- Sawtooth HP / FC?  
- Status / diagnostics show `fallback=True` on MPC? (MPC → Energy on solver timeout)  
- Scary RoR peak near FCs?  
- Had to intervene manually? → mark trial **INVALID** (§7)

`aw.hybridDiagnostics` fields (when you can see them later / via status):  
`backend`, `phase`, `target_ror`, `current_ror`, `pred_ror`, `energy_bias`, `hp`, `fc`, `fallback`.

### 5.4 After DROP

- [ ] Save `.alog` with the naming convention  
- [ ] Fill scorecard qualitative notes (1–3 bullets)  
- [ ] Confirm next session’s planned backend on the schedule table  
- [ ] Do **not** change gains “because today felt wrong” until the study ends

---

## 6. Scorecard (one row per roast)

Keep a spreadsheet or copy this table into a notes file. Fill immediately after save while memory is fresh.

| Field | Example |
|-------|---------|
| session # | 3 |
| pair ID | P2-A |
| date | 2026-08-03 |
| backend | energy |
| .alog filename | `2026-08-03_P2-A_energy_...` |
| lot / bag open day | Lot X / day 12 |
| charge (g) | 600 |
| ambient (°C) / RH% | 22 / 45 |
| Artisan build / commit | `hybrid_control` @ ed51235 |
| DROP BT / time | 198 °C / 9:40 |
| FCs BT / time | 188 °C / 7:55 |
| manual intervention? | N |
| invalid? | N |
| qualitative | “smooth FC; slight ET hang mid” |

**Numeric metrics** (fill same day or next desk day — §8):

| Metric | Value |
|--------|-------|
| ror_rmse | |
| max_abs_ror | |
| hp_travel | |
| fc_travel | |
| notes (fallback seen, etc.) | |

**Per-pair delta** (after both A and B exist):

| Pair | Δ RoR RMSE (MPC − Energy) | Δ max\|RoR\| | Δ HP travel | Δ FC travel |
|------|---------------------------|-------------|-------------|-------------|
| P1 | | | | |
| P2 | | | | |
| P3 | | | | |

Negative Δ RoR RMSE / travel = MPC better.

---

## 7. Invalid trials & abort rules

Mark **INVALID** and **do not count toward the 3 pairs** if any of:

- Wrong backend (discovered after roast)  
- Charge weight or lot wrong  
- Manual slider overrides during Hybrid window  
- Machine fault / disconnect / restart mid-roast  
- Huge confounder you wouldn’t accept in production (power outage, wrong SV, different probe)

**Abort immediately (kill Hybrid / switch to safe manual or Machine PID):**

- Runaway heater or stalled fan command  
- Rapid oscillation that looks unsafe  
- Beans / equipment risk — safety always wins over the study

If you abort: save the log if useful, label INVALID, **repeat that session’s backend** next week (do not advance the schedule as if it counted).

---

## 8. Desk work between roast weeks (15–30 min)

1. Confirm `.alog` landed in the right folder with the right name.  
2. Score CHARGE→DROP metrics. Until a dedicated live-score helper exists, you can:

```bash
python scripts/compare_hybrid_backends.py --input path/to/THAT_roast.alog
```

**Interpret carefully:** that script replays *recorded* BT through both controllers. For a **live** closed-loop log, the useful numbers from a *single* live `.alog` are those computed from **that roast’s measured RoR vs schedule** and **that roast’s recorded HP/FC travel** — not “Energy vs MPC on the same BT.” Prefer a small spreadsheet formula or a one-off notebook that:

- loads the live `.alog`  
- computes measured RoR from BT/timex  
- compares to `interpolate_ror_target` / phase detection  
- sums |ΔHP|, |ΔFC| on the **logged** actuator series  

If you ask in a coding session, a `scripts/score_live_hybrid_alog.py` can be added to match the offline metric definitions without the dual-backend replay confusion.

3. Update the pair delta table.  
4. Glance at next week’s prep (§4).

After **3 valid pairs**, compute mean Δ metrics and apply §1 decision table. Optionally continue to 5–6 pairs if results are noisy.

---

## 9. Study timeline example (~6–8 weeks)

| Week | Action |
|------|--------|
| 0 | Freeze lot, weight, gains; create scorecard file + save folder; do one non-study practice roast if rusty |
| 1 | P1-A Energy — roast + score |
| 2 | P1-B MPC — roast + score + pair delta |
| 3 | P2-A Energy |
| 4 | P2-B MPC |
| 5 | P3-A Energy |
| 6 | P3-B MPC → **decision** (§1) |
| 7+ | Optional: reverse-order pairs, cupping, or stop |

Gaps longer than ~2–3 weeks: note bean age carefully; still OK if lot/charge/gains frozen.

---

## 10. Minimal physical kit

- This doc (printed or phone)  
- Scorecard (sheet or notes app)  
- Fixed green lot / scale  
- Thermometer for ambient (optional but useful)  
- Artisan build known-good on `hybrid_control` with Hybrid + backend selector  
- Backup plan: if MPC misbehaves, Device → Hybrid backend → Energy (or Machine PID for warmup recovery)

---

## 11. What not to do

- Don’t retune Hybrid PID mid-study “to help MPC.”  
- Don’t judge after one week — weekly noise is large.  
- Don’t compare MPC live roast to an **old** Energy log from a different lot.  
- Don’t rely on offline `compare_hybrid_backends.py` RoR RMSE as proof MPC tracked better (BT isn’t closed-loop).  
- Don’t change charge weight to “fix” a slow/fast day.

---

## 12. Handoff back to software (after you have data)

Bring to a coding session:

- 3+ pair `.alog`s (or paths)  
- Filled scorecard + pair deltas  
- Decision from §1  

Then useful follow-ons: live score script, diagnostic curves on canvas, or gain/model tweaks **only if** the field data shows a clear, consistent gap.
