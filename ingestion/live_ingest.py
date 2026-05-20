"""
ingestion/live_ingest.py — Section 2: Live Phyphox HTTP API ingestion.

Streams real-time accelerometer data from a phone running Phyphox,
runs step detection on the collected buffer, and optionally compares
against Apple Health data in the database.

CLI usage:
    python -m ingestion.live_ingest 192.168.1.42
    python -m ingestion.live_ingest 192.168.1.42 60 2026-04-15 8 10

Programmatic usage:
    from ingestion.live_ingest import run
    result = run('192.168.1.42', duration_s=30, date_str='2026-04-15')

Phone setup:
    1. Open Phyphox -> any acceleration experiment -> press Play
    2. 3-dot menu -> Allow remote access
    3. Use the IP shown (e.g. 192.168.1.42) as the argument
"""

import sys
import time
from datetime import datetime

import requests
import pandas as pd

import step_detection as sd

PHYPHOX_PORT  = 8080
POLL_INTERVAL = 0.5   # seconds between HTTP polls
MIN_SAMPLES   = 100   # ~2 s at 50 Hz — minimum to run detection


# ── Channel discovery ─────────────────────────────────────────────────────────

def discover_channels(root_url):
    """
    Query Phyphox /config to find the correct buffer names for this experiment.
    Handles both 'Acceleration (without g)' (accX/Y/Z) and
    'Linear Acceleration' (linX/Y/Z) automatically.
    """
    resp = requests.get(f'{root_url}/config', timeout=5)
    resp.raise_for_status()
    cfg     = resp.json()
    buffers = list(cfg.get('buffers', {}).keys())

    if not buffers:
        raise RuntimeError('Phyphox /config returned no buffers. Is the experiment running?')

    def find(keywords):
        for k in keywords:
            for b in buffers:
                if k in b.lower():
                    return b
        return None

    ch_t = find(['time', 't'])
    ch_x = find(['accx', 'linx', 'acc_x', 'lin_x', 'x'])
    ch_y = find(['accy', 'liny', 'acc_y', 'lin_y', 'y'])
    ch_z = find(['accz', 'linz', 'acc_z', 'lin_z', 'z'])

    missing = [n for n, c in [('time', ch_t), ('x', ch_x), ('y', ch_y), ('z', ch_z)] if not c]
    if missing:
        raise RuntimeError(
            f'Could not auto-detect channels for: {missing}\n'
            f'Available buffers: {buffers}'
        )

    print(f'  Channels: time={ch_t}  x={ch_x}  y={ch_y}  z={ch_z}')
    return ch_x, ch_y, ch_z, ch_t


# ── Data collection ───────────────────────────────────────────────────────────

def _poll(get_url, ch_x, ch_y, ch_z, ch_t, last_t):
    resp = requests.get(
        get_url,
        params={ch_x: last_t, ch_y: last_t, ch_z: last_t, ch_t: last_t},
        timeout=3,
    )
    resp.raise_for_status()
    data   = resp.json()
    t_buf  = data.get(ch_t, {}).get('buffer', [])
    ax_buf = data.get(ch_x, {}).get('buffer', [])
    ay_buf = data.get(ch_y, {}).get('buffer', [])
    az_buf = data.get(ch_z, {}).get('buffer', [])
    return t_buf, ax_buf, ay_buf, az_buf


def collect(phone_ip, duration_s=60):
    """
    Stream accelerometer data from Phyphox for `duration_s` seconds.
    Returns a DataFrame (time, ax, ay, az) or None on failure.
    """
    root_url = f'http://{phone_ip}:{PHYPHOX_PORT}'
    get_url  = f'{root_url}/get'

    print(f'\n[Live Ingestion] Connecting to {phone_ip}:{PHYPHOX_PORT} ...')

    try:
        requests.get(root_url, timeout=3)
    except requests.exceptions.ConnectionError:
        print('  ERROR: Cannot reach the phone.')
        print('  - Both devices must be on the same WiFi')
        print('  - Phyphox must be running with remote access enabled')
        return None
    except requests.exceptions.Timeout:
        print('  ERROR: Connection timed out. Check the IP address.')
        return None

    try:
        ch_x, ch_y, ch_z, ch_t = discover_channels(root_url)
    except RuntimeError as e:
        print(f'  ERROR: {e}')
        return None

    all_t, all_ax, all_ay, all_az = [], [], [], []
    last_t   = 0
    deadline = time.time() + duration_s

    print(f'  Recording for {duration_s}s — start walking now.')
    print('  Press Ctrl+C to stop early.\n')

    try:
        while time.time() < deadline:
            remaining = deadline - time.time()
            try:
                t_buf, ax_buf, ay_buf, az_buf = _poll(get_url, ch_x, ch_y, ch_z, ch_t, last_t)
                if t_buf:
                    all_t.extend(t_buf)
                    all_ax.extend(ax_buf)
                    all_ay.extend(ay_buf)
                    all_az.extend(az_buf)
                    last_t = t_buf[-1]
            except requests.exceptions.RequestException as e:
                print(f'\r  Warning: poll failed ({e}) — retrying...', end='')

            print(
                f'\r  [{duration_s - remaining:.0f}s / {duration_s}s]  '
                f'{len(all_t)} samples  (t={last_t:.2f}s)   ',
                end='', flush=True,
            )
            time.sleep(POLL_INTERVAL)

    except KeyboardInterrupt:
        print('\n\n  Stopped early.')

    print(f'\n  Done: {len(all_t)} samples over {last_t:.1f}s')

    if len(all_t) < MIN_SAMPLES:
        print(f'  Not enough data ({len(all_t)} samples). Walk longer or check connection.')
        return None

    return pd.DataFrame({'time': all_t, 'ax': all_ax, 'ay': all_ay, 'az': all_az})


# ── Full pipeline ─────────────────────────────────────────────────────────────

def run(phone_ip, duration_s=60, date_str=None, hour_start=None, hour_end=None, save_plot=True):
    """
    Full live ingestion pipeline.

    1. Connect  →  2. Stream  →  3. Detect  →  4. Compare vs Apple Health (optional)

    Returns a dict with detection results and comparison (if date_str given).
    """
    df = collect(phone_ip, duration_s)
    if df is None:
        return None

    ts       = datetime.now().strftime('%Y%m%d_%H%M%S')
    csv_path = f'phyphox_live_{ts}.csv'
    df.to_csv(csv_path, index=False)
    print(f'  Raw data saved -> {csv_path}')

    print('\n[Live Ingestion] Running step detection...')
    detection = sd.detect_steps_from_df(df)

    output = {
        'source':     'live',
        'phone_ip':   phone_ip,
        'session_csv': csv_path,
        'steps':      detection['steps'],
        'duration_s': detection['duration_s'],
        'cadence':    detection['cadence'],
        'fs':         detection['fs'],
    }

    print(f'  Steps detected : {detection["steps"]}')
    print(f'  Duration       : {detection["duration_s"]} s')
    print(f'  Cadence        : {detection["cadence"]} steps/min')

    cadence = detection['cadence']
    verdict = 'GOOD' if 80 <= cadence <= 140 else 'ACCEPTABLE' if 60 <= cadence <= 180 else 'NEEDS TUNING'
    output['validation'] = {
        'cadence':      cadence,
        'normal_range': '80-140 steps/min',
        'verdict':      verdict,
        'note':         'Cadence validation — normal walking is 80-140 steps/min',
    }
    print(f'  Cadence {cadence} steps/min -> {verdict}')

    if date_str:
        window = f' ({hour_start}h-{hour_end}h)' if hour_start is not None else ' (full day)'
        apple  = sd.apple_health_count(date_str, hour_start, hour_end)
        print(f'\n[Live Ingestion] vs Apple Health {date_str}{window}')

        if apple is not None and apple > 0:
            print(f'  Apple Health total : {apple} steps (reference — different time window)')
            output['apple_health'] = {
                'date':    date_str,
                'steps':   apple,
                'verdict': output.get('validation', {}).get('verdict', 'GOOD'),
                'note':    'Apple Health total shown for reference. Verdict based on cadence.',
            }
        else:
            print(f'  No Apple Health data for {date_str}{window}.')

    if save_plot:
        sd.plot_steps(detection, output=f'step_detection_live_{ts}.png')

    return output


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
