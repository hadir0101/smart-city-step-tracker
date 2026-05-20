"""
phyphox_live.py — Poll Phyphox HTTP API, detect steps, validate against Apple Health DB.

Works with ANY Phyphox acceleration experiment (auto-detects channel names).

Usage:
    python phyphox_live.py <phone-ip> [duration_seconds] [date] [hour_start] [hour_end]

Examples:
    python phyphox_live.py 192.168.1.5
    python phyphox_live.py 192.168.1.5 60 2026-04-15
    python phyphox_live.py 192.168.1.5 60 2026-04-15 8 10

How to get the phone IP:
    1. Open Phyphox on iPhone (any acceleration experiment)
    2. Press play to start recording
    3. Tap the 3-dot menu -> "Allow remote access"
    4. The IP address is shown on screen (e.g. 192.168.1.5:8080)
"""

import sys
import time
from datetime import datetime

import requests
import pandas as pd

from step_detection import detect_steps_from_df, apple_health_count, plot_steps

PHYPHOX_PORT  = 8080
POLL_INTERVAL = 0.5   # seconds between polls
MIN_SAMPLES   = 100   # ~2s at 50 Hz


# ── Channel auto-discovery ───────────────────────────────────────────────────

def discover_channels(root_url):
    """
    Query Phyphox /config to find which buffer names hold x, y, z acceleration
    and time. Returns (ch_x, ch_y, ch_z, ch_t) or raises RuntimeError.
    """
    resp = requests.get(f"{root_url}/config", timeout=5)
    resp.raise_for_status()
    cfg = resp.json()

    # /config returns {"buffers": {"bufferName": {...}, ...}, ...}
    buffers = list(cfg.get('buffers', {}).keys())
    if not buffers:
        raise RuntimeError("Phyphox /config returned no buffers. Is the experiment running?")

    def find(keywords, candidates):
        for k in keywords:
            for b in candidates:
                if k in b.lower():
                    return b
        return None

    ch_t = find(['time', 't'],                          buffers)
    ch_x = find(['accx', 'linx', 'acc_x', 'lin_x', 'x'], buffers)
    ch_y = find(['accy', 'liny', 'acc_y', 'lin_y', 'y'], buffers)
    ch_z = find(['accz', 'linz', 'acc_z', 'lin_z', 'z'], buffers)

    missing = [name for name, ch in [('time', ch_t), ('x', ch_x), ('y', ch_y), ('z', ch_z)] if not ch]
    if missing:
        raise RuntimeError(
            f"Could not find channels for: {missing}\n"
            f"Available buffers: {buffers}\n"
            "Open an issue or switch to the 'Acceleration (without g)' experiment."
        )

    print(f"  Channels found: time={ch_t}  x={ch_x}  y={ch_y}  z={ch_z}")
    return ch_x, ch_y, ch_z, ch_t


# ── Data polling ─────────────────────────────────────────────────────────────

def _fetch_chunk(get_url, ch_x, ch_y, ch_z, ch_t, last_t):
    """Pull new samples since last_t using the discovered channel names."""
    resp = requests.get(
        get_url,
        params={ch_x: last_t, ch_y: last_t, ch_z: last_t, ch_t: last_t},
        timeout=3,
    )
    resp.raise_for_status()
    data = resp.json()

    t_buf  = data.get(ch_t, {}).get('buffer', [])
    ax_buf = data.get(ch_x, {}).get('buffer', [])
    ay_buf = data.get(ch_y, {}).get('buffer', [])
    az_buf = data.get(ch_z, {}).get('buffer', [])

    return t_buf, ax_buf, ay_buf, az_buf


def collect(phone_ip, duration_s=60):
    """
    Stream accelerometer data from Phyphox for `duration_s` seconds.
    Returns a DataFrame with columns: time, ax, ay, az
    """
    root_url = f"http://{phone_ip}:{PHYPHOX_PORT}"
    get_url  = f"{root_url}/get"

    print(f"\nConnecting to Phyphox at {phone_ip}:{PHYPHOX_PORT} ...")

    # Verify connection
    try:
        requests.get(root_url, timeout=3)
    except requests.exceptions.ConnectionError:
        print(f"\n  ERROR: Cannot reach {phone_ip}:{PHYPHOX_PORT}")
        print("  Check:")
        print("    1. Phone and laptop are on the same WiFi")
        print("    2. Phyphox experiment is running (press play)")
        print("    3. 'Allow remote access' is enabled in the 3-dot menu")
        return None
    except requests.exceptions.Timeout:
        print(f"\n  ERROR: Connection timed out. Is the IP correct?")
        return None

    # Discover correct channel names for this experiment
    try:
        ch_x, ch_y, ch_z, ch_t = discover_channels(root_url)
    except RuntimeError as e:
        print(f"\n  ERROR discovering channels: {e}")
        return None

    all_t, all_ax, all_ay, all_az = [], [], [], []
    last_t   = 0
    deadline = time.time() + duration_s

    print(f"  Connected! Recording for {duration_s}s — start walking now.")
    print(f"  Press Ctrl+C to stop early.\n")

    try:
        while time.time() < deadline:
            remaining = deadline - time.time()
            try:
                t_buf, ax_buf, ay_buf, az_buf = _fetch_chunk(
                    get_url, ch_x, ch_y, ch_z, ch_t, last_t
                )
                if t_buf:
                    all_t.extend(t_buf)
                    all_ax.extend(ax_buf)
                    all_ay.extend(ay_buf)
                    all_az.extend(az_buf)
                    last_t = t_buf[-1]

            except requests.exceptions.RequestException as e:
                print(f"\r  Warning: poll failed ({e}) — retrying...", end='')

            print(
                f"\r  [{duration_s - remaining:.0f}s / {duration_s}s]  "
                f"{len(all_t)} samples  (last_t = {last_t:.2f}s)   ",
                end='', flush=True,
            )
            time.sleep(POLL_INTERVAL)

    except KeyboardInterrupt:
        print("\n\n  Stopped early by user.")

    print(f"\n  Collection done: {len(all_t)} samples over {last_t:.1f}s")

    if len(all_t) < MIN_SAMPLES:
        print(f"  Not enough data ({len(all_t)} samples). Walk longer or check connection.")
        return None

    return pd.DataFrame({'time': all_t, 'ax': all_ax, 'ay': all_ay, 'az': all_az})


# ── Main run ─────────────────────────────────────────────────────────────────

def run(phone_ip, duration_s=60, date_str=None, hour_start=None, hour_end=None):
    df = collect(phone_ip, duration_s)
    if df is None:
        return

    ts       = datetime.now().strftime('%Y%m%d_%H%M%S')
    csv_path = f'phyphox_live_{ts}.csv'
    df.to_csv(csv_path, index=False)
    print(f"  Raw data saved -> {csv_path}")

    print("\nRunning step detection...")
    result = detect_steps_from_df(df)

    print(f"\n-- Detection Results ------------------")
    print(f"  Steps detected : {result['steps']}")
    print(f"  Duration       : {result['duration_s']} s")
    print(f"  Cadence        : {result['cadence']} steps/min")
    print(f"  Sampling rate  : {result['fs']} Hz")
    print(f"  Threshold      : {result['threshold']}")

    if date_str:
        window_label = f" ({hour_start}h-{hour_end}h)" if hour_start is not None else " (full day)"
        apple = apple_health_count(date_str, hour_start, hour_end)
        print(f"\n-- vs Apple Health ({date_str}{window_label}) ----")
        if apple is not None and apple > 0:
            diff    = result['steps'] - apple
            pct     = abs(diff) / apple * 100
            verdict = "GOOD" if pct < 10 else "ACCEPTABLE" if pct < 20 else "NEEDS TUNING"
            print(f"  Apple Health   : {apple} steps")
            print(f"  Our algorithm  : {result['steps']} steps")
            print(f"  Difference     : {diff:+d} ({pct:.1f}%) -> {verdict}")
        else:
            print(f"  No Apple Health data for that window.")
    else:
        print(f"\n  Tip: pass a date to compare vs Apple Health:")
        print(f"       python phyphox_live.py {phone_ip} {duration_s} 2026-04-15 8 10")

    plot_path = f'step_detection_live_{ts}.png'
    plot_steps(result, output=plot_path)
    print()


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    phone_ip   = sys.argv[1]
    duration_s = int(sys.argv[2]) if len(sys.argv) > 2 else 60
    date_str   = sys.argv[3]      if len(sys.argv) > 3 else None
    hour_start = int(sys.argv[4]) if len(sys.argv) > 4 else None
    hour_end   = int(sys.argv[5]) if len(sys.argv) > 5 else None

    run(phone_ip, duration_s, date_str, hour_start, hour_end)
