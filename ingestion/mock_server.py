"""
ingestion/mock_server.py — Simulates the Phyphox HTTP API using a local CSV file.

Streams the CSV data in real-time chunks at the correct sampling rate,
identical to what a real phone running Phyphox would serve.

Usage:
    Terminal 1:  python -m ingestion.mock_server
    Terminal 2:  python -m ingestion.live_ingest 127.0.0.1 30
"""

import sys
import time
import pandas as pd
from flask import Flask, jsonify, request as flask_request

app   = Flask(__name__)
_df   = None
_fs   = 50.0
_t0   = None   # wall-clock time the stream started


def _load(csv_path):
    global _df, _fs, _t0
    df = pd.read_csv(csv_path)
    df.columns = ['time', 'ax', 'ay', 'az']
    _df  = df.reset_index(drop=True)
    _fs  = round(1.0 / df['time'].diff().median())
    _t0  = time.time()
    print(f'  Loaded {len(df)} samples at {_fs} Hz — {df["time"].iloc[-1]:.1f}s of data')


def _available_until(since):
    """Return rows that a real phone would have recorded so far, after `since`."""
    elapsed = time.time() - _t0
    cutoff  = min(elapsed, _df['time'].iloc[-1])
    mask    = (_df['time'] > since) & (_df['time'] <= cutoff)
    return _df[mask]


# ── Phyphox HTTP API ──────────────────────────────────────────────────────────

@app.route('/config')
def config():
    return jsonify({
        'buffers': {
            'linX': {'size': 0},
            'linY': {'size': 0},
            'linZ': {'size': 0},
            'time': {'size': 0},
        },
        'experiment': {'title': 'Linear Acceleration (mock)'},
    })


@app.route('/get')
def get():
    since  = float(flask_request.args.get('time', 0))
    chunk  = _available_until(since)
    return jsonify({
        'time': {'buffer': chunk['time'].tolist()},
        'linX': {'buffer': chunk['ax'].tolist()},
        'linY': {'buffer': chunk['ay'].tolist()},
        'linZ': {'buffer': chunk['az'].tolist()},
    })


@app.route('/')
def status():
    elapsed  = time.time() - _t0
    served   = _available_until(-1)
    return jsonify({
        'status':         'streaming',
        'elapsed_s':      round(elapsed, 1),
        'samples_served': len(served),
        'total_samples':  len(_df),
        'progress_pct':   round(len(served) / len(_df) * 100, 1),
    })


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == '__main__':
    csv_path = sys.argv[1] if len(sys.argv) > 1 else 'phyphox_data.csv'

    print(f'\nPhyphox Mock Server')
    print(f'===================')
    _load(csv_path)
    print(f'\n  Serving on http://127.0.0.1:8080')
    print(f'  In another terminal run:')
    print(f'    python -m ingestion.live_ingest 127.0.0.1 30\n')

    app.run(host='0.0.0.0', port=8080, debug=False)
