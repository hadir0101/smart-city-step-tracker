import sys
import os
import numpy as np
import pandas as pd
from scipy.signal import find_peaks, butter, filtfilt

CSV_PATH = 'phyphox_data.csv'
DB_PATH  = 'steps.db'


# ── Signal processing ────────────────────────────────────────────────────────

def _butter_lowpass(data, cutoff=3.0, fs=50.0, order=4):
    nyq = 0.5 * fs
    b, a = butter(order, cutoff / nyq, btype='low', analog=False)
    return filtfilt(b, a, data)


def load_phyphox(path=CSV_PATH):
    df = pd.read_csv(path)

    # Normalise column names — handles both Phyphox experiments:
    #   "Acceleration (without g)"  -> "Acceleration x (m/s^2)"
    #   "Linear Acceleration"       -> "Linear Acceleration x (m/s^2)"
    rename = {}
    for col in df.columns:
        c = col.strip().lower()
        if 'time' in c:
            rename[col] = 'time'
        elif 'x' in c and 'acceleration' in c:
            rename[col] = 'ax'
        elif 'y' in c and 'acceleration' in c:
            rename[col] = 'ay'
        elif 'z' in c and 'acceleration' in c:
            rename[col] = 'az'
        elif c in ('ax', 'x'):
            rename[col] = 'ax'
        elif c in ('ay', 'y'):
            rename[col] = 'ay'
        elif c in ('az', 'z'):
            rename[col] = 'az'
    df = df.rename(columns=rename)

    required = {'time', 'ax', 'ay', 'az'}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"CSV missing columns: {missing}. Found: {list(df.columns)}")

    return df.astype(float)


def _run_detection(df):
    """Core detection logic — operates on a DataFrame with time/ax/ay/az columns."""
    df = df.copy()
    df['magnitude'] = np.sqrt(df['ax']**2 + df['ay']**2 + df['az']**2)

    dt = df['time'].diff().median()
    fs = round(1.0 / dt) if dt > 0 else 50.0

    df['filtered'] = _butter_lowpass(df['magnitude'], cutoff=3.0, fs=fs)

    threshold = df['filtered'].mean() + df['filtered'].std() * 0.4
    min_gap   = int(fs * 0.3)

    peaks, _ = find_peaks(df['filtered'], height=threshold, distance=min_gap)

    step_count = len(peaks)
    duration   = float(df['time'].iloc[-1] - df['time'].iloc[0])
    cadence    = step_count / (duration / 60.0) if duration > 0 else 0.0

    return {
        'df':         df,
        'peaks':      peaks,
        'steps':      step_count,
        'duration_s': round(duration, 1),
        'cadence':    round(cadence, 1),
        'fs':         fs,
        'threshold':  round(threshold, 4),
    }


def detect_steps(path=CSV_PATH):
    """Load a Phyphox CSV file and run step detection."""
    return _run_detection(load_phyphox(path))


def detect_steps_from_df(df):
    """Run step detection on an already-loaded DataFrame (time, ax, ay, az)."""
    return _run_detection(df)


# ── Apple Health comparison ───────────────────────────────────────────────────

def apple_health_count(date_str, hour_start=None, hour_end=None):
    """Return Apple Health step total from the DB for a given date (+ optional hour range)."""
    import sqlite3
    if not os.path.exists(DB_PATH):
        return None
    conn = sqlite3.connect(DB_PATH)
    if hour_start is not None and hour_end is not None:
        row = conn.execute(
            'SELECT COALESCE(SUM(steps),0) FROM step_records WHERE date=? AND hour>=? AND hour<?',
            (date_str, hour_start, hour_end)
        ).fetchone()
    else:
        row = conn.execute(
            'SELECT COALESCE(SUM(steps),0) FROM step_records WHERE date=?',
            (date_str,)
        ).fetchone()
    conn.close()
    return int(row[0]) if row else None


# ── Plot (optional — only when matplotlib is available) ──────────────────────

def plot_steps(result, output='step_detection.png'):
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not installed — skipping plot.")
        return

    df     = result['df']
    peaks  = result['peaks']
    steps  = result['steps']

    fig, axes = plt.subplots(2, 1, figsize=(14, 8), sharex=True)

    # Top: raw magnitude vs filtered
    axes[0].plot(df['time'], df['magnitude'], color='#718096', linewidth=0.6,
                 alpha=0.6, label='Raw magnitude')
    axes[0].plot(df['time'], df['filtered'],  color='#63B3ED', linewidth=1.4,
                 label='Filtered (low-pass)')
    axes[0].axhline(result['threshold'], color='#FC8181', linestyle='--',
                    linewidth=1, label='Detection threshold')
    axes[0].set_ylabel('Acceleration magnitude (m/s²)')
    axes[0].set_title('Raw vs Filtered Acceleration Signal')
    axes[0].legend(fontsize=9)
    axes[0].grid(alpha=0.2)

    # Bottom: detected steps overlaid on filtered signal
    axes[1].plot(df['time'], df['filtered'], color='#63B3ED', linewidth=1.2)
    axes[1].plot(df['time'].iloc[peaks], df['filtered'].iloc[peaks],
                 'v', color='#68D391', markersize=7, label=f'Steps detected ({steps})')
    axes[1].axhline(result['threshold'], color='#FC8181', linestyle='--',
                    linewidth=1, label='Threshold')
    axes[1].set_xlabel('Time (s)')
    axes[1].set_ylabel('Filtered magnitude')
    axes[1].set_title(f'Step Detection — {steps} steps | '
                      f'{result["duration_s"]}s | {result["cadence"]} steps/min')
    axes[1].legend(fontsize=9)
    axes[1].grid(alpha=0.2)

    plt.tight_layout()
    plt.savefig(output, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"Plot saved -> {output}")


# ── CLI entry point ───────────────────────────────────────────────────────────

if __name__ == '__main__':
    csv_path   = sys.argv[1] if len(sys.argv) > 1 else CSV_PATH
    date_str   = sys.argv[2] if len(sys.argv) > 2 else None   # e.g. 2026-04-15
    hour_start = int(sys.argv[3]) if len(sys.argv) > 3 else None
    hour_end   = int(sys.argv[4]) if len(sys.argv) > 4 else None

    print(f"\nLoading: {csv_path}")
    result = detect_steps(csv_path)

    print(f"\n-- Detection Results ------------------")
    print(f"  Steps detected : {result['steps']}")
    print(f"  Duration       : {result['duration_s']} s")
    print(f"  Cadence        : {result['cadence']} steps/min")
    print(f"  Sampling rate  : {result['fs']} Hz")
    print(f"  Threshold      : {result['threshold']}")

    if date_str:
        apple = apple_health_count(date_str, hour_start, hour_end)
        window = f" ({hour_start}h-{hour_end}h)" if (hour_start is not None and hour_end is not None) else " (full day)"
        if apple is not None:
            diff = result['steps'] - apple
            pct  = abs(diff) / apple * 100 if apple else 0
            print(f"\n-- vs Apple Health ({date_str}{window}) ----------")
            print(f"  Apple Health   : {apple} steps")
            print(f"  Our algorithm  : {result['steps']} steps")
            print(f"  Difference     : {diff:+d} ({pct:.1f}%)")
            if hour_start is None:
                print(f"  Note: Phyphox session = {result['duration_s']}s, Apple = full day.")
                print(f"        Use --hour_start / --hour_end to compare the same window.")
        else:
            print(f"\nNo Apple Health data found for {date_str}.")

    plot_steps(result)
    print()
