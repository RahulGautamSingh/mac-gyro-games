# TiltRide

Two browser games steered by tilting your MacBook. A small Python server reads
the Mac's built-in IMU (gyroscope + accelerometer) and streams roll/pitch over
WebSocket; the games subscribe and use it as input.

Tested on a MacBook Air M4 (Apple Silicon, macOS).

## Files

- `imu_server.py` — reads the Bosch BMI286 IMU via [`macimu`](https://pypi.org/project/macimu/) and broadcasts tilt at 60 Hz on `ws://localhost:8765`
- `bike_game.html` — endless bike-riding game; lean left/right to steer
- `marble_tilt.html` — marble-in-a-maze game; tilt in any direction to roll

Both pages also accept keyboard input (arrow keys) so they work without the
server running.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install macimu websockets
```

## Run

The IMU server needs root to open the IOKit HID device:

```bash
sudo .venv/bin/python3 imu_server.py
```

Hold the Mac flat during the ~1 s calibration, then open one of the HTML files
directly in a browser. The page connects to the WebSocket automatically.

## Controls

**bike_game.html**
- Tilt left/right (or arrow keys) to steer
- `Space` — action (see in-game prompt)
- `I` — invert tilt direction

**marble_tilt.html**
- Tilt in any direction (or arrow keys) to roll the marble

## Axis reference

With the MacBook lying flat, screen up, hinge away from you:

| axis     | meaning                                   |
|----------|-------------------------------------------|
| accel.x  | left/right (positive = right side down)   |
| accel.y  | front/back (positive = front tilted down) |
| accel.z  | up/down (≈ -1 g when flat)                |

Roll and pitch are derived from the accelerometer; raw gyro values are also
included in the WebSocket payload for future use.
