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

4. Load a **background profile** with a desired RoR curve (ΔBT).
5. Start sampling and press **PID ON** — Artisan disables machine PID (`AH=0`) and drives **HP** + **FC** directly.
6. With PID off, use event sliders for manual control (FC = slider 1, HP = slider 4 in the Kaleido preset).

### How It Works

```
Desired RoR (background ΔBT)
         │
         ▼
  Heater Controller ──► HP (slow, RoR PID)

ET − BT offset schedule ──► Fan Controller ──► FC (fast, offset PID + baseline + RoR accel trim)
```

**Phase schedules** (defaults):

| Phase | ET−BT offset | Baseline fan |
|-------|--------------|--------------|
| Drying | 60°C | 30% |
| Yellow | 50°C | 40% |
| Maillard | 45°C | 50% |
| First crack | 35°C | 70% |
| Development | 25°C | 80% |

Phases are detected from roast events (DRY, FCs, FCe) with BT fallbacks when events are not marked.

## Configuration

Settings persist in Artisan's QSettings / machine `.aset` files:

| Key | Default | Purpose |
|-----|---------|---------|
| `hybridHeaterKp/Ki/Kd` | 3.0 / 0.5 / 0.1 | Slow RoR PID |
| `hybridFanKp/Ki/Kd` | 2.0 / 0.3 / 0.05 | Fast offset PID |
| `hybridHeaterSlew` | 5 %/s | Max heater change rate |
| `hybridFanSlew` | 20 %/s | Max fan change rate |
| `hybridRorAccelGain` | 2.0 | Predictive fan boost on RoR acceleration |
| `hybridDefaultRorTarget` | 10.0 | Fallback RoR when no background loaded |

## Development

### Project layout

```
src/artisanlib/
  hybrid_controller.py   # Dual-actuator controller logic
  kaleido.py             # Kaleido WebSocket/serial protocol
  pid_control.py         # PID mode routing (incl. hybrid mode 5)
  canvas.py              # Sample loop integration
```

### Tests

```bash
pytest src/test/unitary/artisanlib/test_hybrid_controller.py -v
pytest src/test/unitary/artisanlib/test_kaleido.py -v
```

## Roadmap

- Model Predictive Control (MPC) with thermal prediction horizon
- Full schedule editor UI in PID dialog
- Live diagnostic curves (commanded HP/FC, phase, ET−BT error)
- Drum speed (RC) coordination

## License

GNU General Public License v2 or later, consistent with Artisan.
