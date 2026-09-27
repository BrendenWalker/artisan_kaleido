# Kaleido Scope

An [Artisan](https://github.com/artisan-roaster-scope/artisan) fork for **Kaleido hybrid electric/convection roasters** (M1 / M2 / M6 / M10).

Artisan already **connects** to Kaleido. This fork exists because connection is not control. Stock Artisan logs BT/ET, moves HP/FC/RC sliders, and can run a **single** PID. Kaleido is not a gas drum: **airflow is a second heat-transfer actuator**, not just exhaust. Kaleido Scope drives **heater and fan together** to follow a declining RoR shape.

You still get Artisan graphs, `.alog` / `.aset` files, and the usual roast workflow (GPL-2/3).

If you only log, drive sliders by hand, or roast a machine that is not a Kaleido, stay on [Artisan](https://github.com/artisan-roaster-scope/artisan).

## vs Artisan

| | Artisan | Kaleido Scope |
|---|---|---|
| Connect, log, sliders | Yes | Yes |
| Machine PID (`AH`/`TS`) or Artisan software PID | Yes | Yes |
| Coordinated **HP + FC** | No (one actuator) | **Hybrid Controller** |
| Built-in declining **RoR shape** by phase | No | Yes (planner drives both actuators) |
| After-roast **cooldown** | Manual sliders | **COOLDOWN** (air 100% / drum 10% until BT &lt; 50°C, then all off) |
| Config | Every Artisan machine and logger | **Kaleido Network / Serial** only. Extra loggers (Phidget / TC4 / Yocto / Virtual) stay |

Hybrid does **not** follow a background profile. Background is for eyes only.

## What you get today

**Hybrid Controller (recommended).** After CHARGE it tracks a baked-in declining RoR plan and moves HP (slow energy) and FC (fast heat transfer) together. After first crack it prefers airflow over hard power cuts. Optional **MPC** backend in Device settings; Energy is the default and the timeout fallback. Details: [kaleido_mpc_spec.md](docs/kaleido_mpc_spec.md).

**Machine PID warmup.** Before CHARGE, Hybrid uses the roaster’s own PID (`AH=1`, SV→`TS`) so the drum is hot. CHARGE flips to Hybrid (`AH=0`).

**COOLDOWN.** After DROP (or any idle ON session) a main-bar button holds air 100% / drum 10% until BT < 50°C, then shuts everything off. Visible only while connected and not recording; press again to cancel.

**Default M6 plan** (600 g, medium/light). Other models still run this schedule until per-machine presets exist.

| Phase | RoR (°C/min) | HP % | FC % |
|-------|--------------|------|------|
| Drying | 22 → 15.5 | 90 | 30 |
| Yellow | 15 → 14 | 85 | 35 |
| Maillard | 14 → 10 | 80 | 40 |
| First crack | 10 → 7 | 40 | 60 |
| Development | 7 → 3.5 | 25 | 70 |

Phases follow DRY / FCs / FCe, with BT fallbacks. After FCs, Development starts around 190°C BT even if FCe is unmarked.

## Roast flow (Hybrid)

1. **Config → Machine → Kaleido Network** or **Kaleido Serial**. The menu checkmarks the live connection (Serial vs WiFi/Network).
2. **Config → Device:** Meter = Kaleido BT/ET, Control on, **Hybrid Controller** (Energy unless you are testing MPC). Extra Devices can add Kaleido channels 139–141 and a logger (Phidget / TC4 / Yocto / Virtual).
3. **ON**, set warmup **SV** on the left slider (Machine PID `TS`), **Start Heating**. **START** only records; it does not change control.
4. **CHARGE** → Hybrid takes HP + FC.
5. **DROP**, then **COOLDOWN**.

Manual fallback: PID off, sliders (FC = 1, HP = 4 in the Kaleido preset).

## Roadmap

Full sequence and exit criteria: [docs/ROADMAP.md](docs/ROADMAP.md).

**Now:** Hybrid Energy, optional Lite MPC, COOLDOWN, Artisan logging. Config → Machine is Kaleido Network / Serial only (checkmark on the live connection). Extra loggers (Phidget / TC4 / Yocto / Virtual) can plot beside Kaleido. Preheat **SV** slider drives Machine PID `TS` until CHARGE.

**Next:** M1 presets/schedule editor → M2 diagnostics + quiet MPC, then gated MPC default.

**Later:** drum RC, `.alog` calibration, learned plant.

Control architecture: [kaleido_mpc_spec.md](docs/kaleido_mpc_spec.md). Field notes: [hybrid_field_ab_plan.md](docs/hybrid_field_ab_plan.md).

## Run from source

```bash
cd src
pip install -r requirements.txt
python artisan.py
```

Python 3.10+, Kaleido on WebSocket (`host` / port `80` / `/ws`) or serial. Load **Kaleido Network** or **Kaleido Serial** (Config → Machine checkmarks Serial vs Network from the Device WiFi/serial flag). Extra Devices can add Kaleido channels 139–141 and a generic logger (Phidget / Arduino TC4 / Yocto / Virtual). After **ON**, the left **SV** slider is the warmup set value.

## Help Fund Artisan Scope

Kaleido Scope stands on [Artisan](https://github.com/artisan-roaster-scope/artisan). If this is useful, support the people who built that project:

**[Donate to Artisan Scope](https://artisan-scope.org/donate/)**

## License

GNU General Public License v2 or later, consistent with Artisan.
