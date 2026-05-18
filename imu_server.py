#!/usr/bin/env python3
"""
TiltRide - IMU Server
=====================
Reads the MacBook Air M4's built-in gyroscope + accelerometer (Bosch BMI286,
managed by the Sensor Processing Unit) and streams tilt data over WebSocket
so the bike game can steer with it.

SETUP
-----
  pip install macimu websockets

RUN (needs sudo to open the IOKit HID device)
-----
  sudo python3 imu_server.py

Then open bike_game.html in your browser and start riding.

AXIS NOTES
----------
  MacBook lying flat, screen up, hinge away from you:
    accel.x  → left/right  (positive = right side down)
    accel.y  → front/back  (positive = front tilted down)
    accel.z  → up/down     (≈ -1g when flat)

  If steering feels inverted in-game, press [I] in the browser to flip it.
"""

import asyncio
import json
import math
import sys
import time

try:
    import websockets
except ImportError:
    print("ERROR: websockets not installed. Run:  pip install websockets")
    sys.exit(1)

try:
    from macimu import IMU
except ImportError:
    print("ERROR: macimu not installed. Run:  pip install macimu")
    sys.exit(1)


# ── Config ────────────────────────────────────────────────────────────────────

HOST        = "localhost"
PORT        = 8765
TARGET_HZ   = 60          # broadcast rate
CAL_FRAMES  = 60          # frames to average for baseline calibration


# ── State ─────────────────────────────────────────────────────────────────────

clients: set = set()


# ── Math helpers ──────────────────────────────────────────────────────────────

def compute_roll(ax, ay, az):
    """Roll = left/right tilt in degrees. 0 when flat."""
    return math.atan2(ax, -az) * 180.0 / math.pi


def compute_pitch(ax, ay, az):
    """Pitch = front/back tilt in degrees. 0 when flat."""
    return math.atan2(ay, -az) * 180.0 / math.pi


# ── Broadcast loop ────────────────────────────────────────────────────────────

async def imu_loop():
    interval = 1.0 / TARGET_HZ

    with IMU() as imu:
        print(f"  IMU opened — calibrating over {CAL_FRAMES} frames…")

        # Calibration: collect baseline offsets while the Mac is (hopefully) flat
        cal_ax = cal_ay = cal_az = 0.0
        collected = 0
        while collected < CAL_FRAMES:
            s = imu.latest_accel()
            if s is None:
                await asyncio.sleep(interval)
                continue
            cal_ax += s.x
            cal_ay += s.y
            cal_az += s.z
            collected += 1
            await asyncio.sleep(interval)

        cal_ax /= CAL_FRAMES
        cal_ay /= CAL_FRAMES
        # Don't zero out az fully — keep gravity reference, only remove x/y bias
        print(f"  Calibration done. Bias  x={cal_ax:.4f}g  y={cal_ay:.4f}g")
        print(f"  Broadcasting on ws://{HOST}:{PORT}  ({TARGET_HZ} Hz)")
        print()
        print("  Open bike_game.html → hold Mac like a steering wheel → ride!")
        print("  Press Ctrl-C to stop.\n")

        while True:
            t0 = time.monotonic()

            accel = imu.latest_accel()
            gyro  = imu.latest_gyro()

            if accel is None or gyro is None:
                await asyncio.sleep(interval)
                continue

            # Remove bias from x/y (in-plane drift)
            ax = accel.x - cal_ax
            ay = accel.y - cal_ay
            az = accel.z   # keep z as-is (gravity reference)

            roll  = compute_roll(ax, ay, az)
            pitch = compute_pitch(ax, ay, az)

            payload = json.dumps({
                "roll":  round(roll,  2),   # degrees, ± → left/right
                "pitch": round(pitch, 2),   # degrees, ± → front/back
                "gyro":  {                  # raw deg/s for future use
                    "x": round(gyro.x, 1),
                    "y": round(gyro.y, 1),
                    "z": round(gyro.z, 1),
                },
            })

            if clients:
                dead = set()
                for ws in clients:
                    try:
                        await ws.send(payload)
                    except Exception:
                        dead.add(ws)
                clients.difference_update(dead)

            # Sleep just long enough to maintain target Hz
            elapsed = time.monotonic() - t0
            await asyncio.sleep(max(0, interval - elapsed))


# ── WebSocket handler ─────────────────────────────────────────────────────────

async def handler(websocket):
    addr = websocket.remote_address
    print(f"  ✓ Browser connected from {addr}")
    clients.add(websocket)
    try:
        await websocket.wait_closed()
    finally:
        clients.discard(websocket)
        print(f"  ✗ Browser disconnected from {addr}")


# ── Entry point ───────────────────────────────────────────────────────────────

async def main():
    print()
    print("╔══════════════════════════════════╗")
    print("║     TiltRide  –  IMU Server      ║")
    print("╚══════════════════════════════════╝")
    print()

    async with websockets.serve(handler, HOST, PORT):
        await imu_loop()   # runs forever


if __name__ == "__main__":
    if sys.platform != "darwin":
        print("ERROR: This only works on macOS (Apple Silicon).")
        sys.exit(1)

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n  Server stopped. Good ride.")
    except PermissionError:
        print("\nERROR: Permission denied opening IOKit HID device.")
        print("Re-run with:  sudo python3 imu_server.py")