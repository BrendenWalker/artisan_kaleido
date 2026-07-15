# Artisan Kaleido

Artisan fork tailored for **Kaleido hybrid electric/convection roasters**, with coordinated heater and airflow control.

Kaleido roasters differ from traditional drum roasters: airflow actively changes heat transfer from the heating elements to the beans, not just exhaust. This fork adds a **Hybrid Roaster Controller** that treats heater power and fan speed as two coordinated actuators.

Based on [Artisan](https://github.com/artisan-roaster-scope/artisan) (GPL-2/3).

## Why Kaleido Needs Dual Control

| Actuator | Role | Response |
|----------|------|----------|
| **Heater (HP)** | Supplies energy; tracks desired RoR | Slow (10–20 s) |
| **Fan (FC)** | Controls heat transfer via ET−BT offset | Fast (2–5 s) |

The heater sets long-term energy trend. The fan adjusts how efficiently that energy reaches the beans.

## Requirements

- Python 3.10+ (see upstream Artisan docs)
- Dependencies from upstream Artisan (`src/README.txt`)
- Kaleido roaster with network (WebSocket) or serial connection

## Running from Source

See [src/README.txt](src/README.txt) for full Artisan setup. In brief:

```bash
cd src
pip install -r requirements.txt   # if available
python artisan.py
```

Load the Kaleido machine preset: **Roast → Machine → Kaleido Network** (or **Kaleido Serial**).

## Kaleido Connection

| Setting | Default | Notes |
|---------|---------|-------|
| Host | `127.0.0.1` | Roaster IP or localhost bridge |
| Port | `80` | WebSocket path `/ws` |
| WiFi | checked | Uncheck to use main serial port |

Extra device channels (preset defaults): Heater/Fan (141), SV/AT (139), Drum/AH (140).

## Control Modes

Configure under **Config → Device** (Ctrl+D):

1. On the **ET/BT** tab, select **Meter** and choose **Kaleido BT/ET** from the device list.
2. Enable the **Control** checkbox (required for PID ON).
3. A **Kaleido Control** section appears below with three options:
   - **Machine PID** — roaster-native PID via `AH`/`TS`
   - **Software PID** — single Artisan PID slider
   - **Hybrid Controller** — coordinated HP + FC (recommended)

Network host/port settings remain on the **Networks** tab in the Kaleido group box.

### Hybrid roast flow (recommended)

With **Hybrid Controller** selected:

1. Optionally load a **background profile** for visual comparison (Hybrid does **not** follow background RoR).
2. Press **ON** — monitoring starts; set **SV** for warmup temperature.
3. Press **Start Heating** — heaters on (`HS`) and Machine PID warmup (`AH=1`, SV→`TS`).
4. Press **START** — recording only; roaster control is unchanged.
5. Press **CHARGE** (or auto-detect) — switch to Hybrid (`AH=0`, drive HP + FC from the M6 RoR-shape plan).

CONTROL / PIDon before CHARGE also uses Machine PID warmup (same as Start Heating). After CHARGE, CONTROL / PIDon activates Hybrid.

With PID off, use event sliders for manual control (FC = slider 1, HP = slider 4 in the Kaleido preset).

### How It Works

Hybrid tracks a built-in declining **RoR shape** by roast phase and drives **heater + fan together** to follow it. After first crack it prefers airflow (damping) over hard power cuts.

```
Phase + BT → target RoR → Energy Controller → HP% + FC%
```

Full architecture (planner, thermal twin, MPC roadmap): [kaleido_mpc_spec.md](docs/kaleido_mpc_spec.md).

**Default M6 shape plan (600g medium/light):**

| Phase | RoR (°C/min) | HP % | FC % |
|-------|--------------|------|------|
| Drying | 22 → 15.5 | 90 | 30 |
| Yellow | 15 → 14 | 85 | 35 |
| Maillard | 14 → 10 | 80 | 40 |
| First crack | 11 → 9 | 50 | 50 |
| Development | 9 → 5.5 | 40 | 55 |

Phases are detected from roast events (DRY, FCs, FCe) with BT fallbacks when events are not marked.

## Configuration

Settings persist in Artisan's QSettings / machine `.aset` files:

| Key | Default | Purpose |
|-----|---------|---------|
| `hybridHeaterKp/Ki/Kd` | 3.0 / 0.5 / 0.1 | RoR PID trim around HP baseline |
| `hybridFanKp/Ki/Kd` | 2.0 / 0.3 / 0.05 | Fast ET−BT offset PID |
| `hybridHeaterSlew` | 5 %/s | Max heater change rate (≤3 %/s post-FC) |
| `hybridFanSlew` | 20 %/s | Max fan change rate |
| `hybridRorAccelGain` | 2.0 | Fan boost on RoR acceleration (flick) |
| `hybridHeaterTrimLimit` | ±20 % | Cap RoR PID trim around HP baseline |
| `hybridCrashRorMargin` | 1.5 °C/min | Under-target margin before crash FC boost |
| `hybridCrashFcGain` | 4.0 | FC % per °C/min under RoR target |

RoR shape schedule and related priors are baked-in M6 defaults (not editable in the Device dialog yet).
Hybrid control backend defaults to `energy` (`hybridControlBackend`). Set `hybridControlBackend=mpc`
in QSettings to try Lite MPC (no Device dialog radio yet; falls back to Energy on solver timeout).

## Development

### Project layout

```
src/artisanlib/
  hybrid_controller.py   # Dual-actuator Energy controller + backend factory
  kaleido_model.py       # Lite 3-state thermal plant (MPC)
  kaleido_model_fit.py   # Offline fit / replay RMSE from .alog
  mpc_controller.py      # Lite MPC backend (hybridControlBackend=mpc)
  kaleido.py             # Kaleido WebSocket/serial protocol
  pid_control.py         # PID mode routing (incl. hybrid mode 5)
  canvas.py              # Sample loop integration
```

### Tests

```bash
pytest src/test/unitary/artisanlib/test_hybrid_controller.py -v
pytest src/test/unitary/artisanlib/test_mpc_controller.py -v
pytest src/test/unitary/artisanlib/test_kaleido.py -v
pytest src/test/unitary/artisanlib/test_pid_control.py -v -k kaleido
```

## Roadmap

**Done**

- Hybrid Controller (Machine PID warmup → CHARGE → coordinated HP/FC RoR shape)
- MPC Phases A–C (backend protocol, Lite MPC, M6 log calibration; Energy still default)

**Next** — [MPC Phases D–E](docs/kaleido_mpc_spec.md#18-roadmap)

- **D** — Event-aware horizon references
- **E** — Diagnostics UI + field A/B (Energy vs MPC)

**Later**

- Machine profile presets (M1–M10) and schedule editor UI
- Live diagnostic curves (commanded HP/FC, phase, Energy Bias, predicted RoR)
- Drum speed (RC) coordination

## License

GNU General Public License v2 or later, consistent with Artisan.
