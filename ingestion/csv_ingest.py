"""
ingestion/csv_ingest.py — Section 1: CSV-based data ingestion.

Loads a Phyphox CSV export, runs step detection, and optionally
compares the result against Apple Health data in the database.

CLI usage:
    python -m ingestion.csv_ingest
    python -m ingestion.csv_ingest phyphox_data.csv 2026-04-15 8 10

Programmatic usage:
    from ingestion.csv_ingest import run
    result = run('phyphox_data.csv', date_str='2026-04-15')
"""

import os
import sys
import step_detection as sd


def run(csv_path='phyphox_data.csv', date_str=None, hour_start=None, hour_end=None, save_plot=True):
    """
    Full CSV ingestion pipeline.

    1. Load CSV  →  2. Detect steps  →  3. Compare vs Apple Health (optional)

    Returns a dict with detection results and comparison (if date_str given).
    """
    if not os.path.exists(csv_path):
        raise FileNotFoundError(
            f'"{csv_path}" not found.\n'
            'Export your Phyphox data: share icon -> Export -> CSV, '
            'then place the file in the project root.'
        )

    print(f'\n[CSV Ingestion] Loading: {csv_path}')
    detection = sd.detect_steps(csv_path)

    output = {
        'source':     'csv',
        'file':       csv_path,
        'steps':      detection['steps'],
        'duration_s': detection['duration_s'],
        'cadence':    detection['cadence'],
        'fs':         detection['fs'],
    }

    print(f'  Steps detected : {detection["steps"]}')
    print(f'  Duration       : {detection["duration_s"]} s')
    print(f'  Cadence        : {detection["cadence"]} steps/min')

    # Cadence-based validation — checks if detected walking pace is physiologically realistic
    cadence = detection['cadence']
    if cadence >= 80 and cadence <= 140:
        verdict = 'GOOD'
    elif cadence >= 60 and cadence <= 180:
        verdict = 'ACCEPTABLE'
    else:
        verdict = 'NEEDS TUNING'

    output['validation'] = {
        'cadence':     cadence,
        'normal_range': '80-140 steps/min',
        'verdict':     verdict,
        'note':        'Cadence validation — normal walking is 80-140 steps/min',
    }
    print(f'  Cadence {cadence} steps/min -> {verdict}')

    if date_str:
        window = f' ({hour_start}h-{hour_end}h)' if hour_start is not None else ' (full day)'
        apple  = sd.apple_health_count(date_str, hour_start, hour_end)
        print(f'\n[CSV Ingestion] Apple Health reference {date_str}{window}')
        if apple is not None and apple > 0:
            print(f'  Apple Health total : {apple} steps (reference only — different time window)')
            output['apple_health'] = {
                'date':    date_str,
                'steps':   apple,
                'verdict': verdict,
                'note':    'Apple Health total shown for reference. Verdict based on cadence.',
            }
        else:
            print(f'  No Apple Health data for {date_str}{window}.')

    if save_plot:
        sd.plot_steps(detection, output='step_detection_csv.png')

    return output


if __name__ == '__main__':
    csv_path   = sys.argv[1] if len(sys.argv) > 1 else 'phyphox_data.csv'
    date_str   = sys.argv[2] if len(sys.argv) > 2 else None
    hour_start = int(sys.argv[3]) if len(sys.argv) > 3 else None
    hour_end   = int(sys.argv[4]) if len(sys.argv) > 4 else None

    run(csv_path, date_str, hour_start, hour_end)
