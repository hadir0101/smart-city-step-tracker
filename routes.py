from flask import Blueprint, jsonify, render_template, request
from datetime import datetime
from database import get_db, PARIS

bp = Blueprint('main', __name__)


@bp.route('/')
def index():
    return render_template('index.html')


@bp.route('/api/today')
def today():
    today_str = datetime.now(PARIS).date().isoformat()
    conn = get_db()
    row = conn.execute(
        'SELECT COALESCE(CAST(SUM(steps) AS INTEGER), 0) AS steps FROM step_records WHERE date = ?',
        (today_str,)
    ).fetchone()
    conn.close()
    steps = row['steps']
    return jsonify({
        'date':  today_str,
        'steps': steps,
        'goal':  10000,
        'pct':   min(100, round(steps / 10000 * 100, 1)),
    })


@bp.route('/api/daily')
def daily():
    conn = get_db()
    rows = conn.execute('''
        SELECT date, CAST(SUM(steps) AS INTEGER) AS steps
        FROM step_records
        GROUP BY date
        ORDER BY date DESC
        LIMIT 30
    ''').fetchall()
    conn.close()
    rows = list(reversed(rows))
    return jsonify({
        'labels': [r['date'] for r in rows],
        'values': [r['steps'] for r in rows],
    })


@bp.route('/api/hourly')
def hourly():
    conn = get_db()
    rows = conn.execute('''
        SELECT hour, ROUND(AVG(steps), 1) AS steps
        FROM step_records
        GROUP BY hour
        ORDER BY hour
    ''').fetchall()
    conn.close()
    return jsonify({
        'labels': [r['hour'] for r in rows],
        'values': [r['steps'] for r in rows],
    })


@bp.route('/api/stats')
def stats():
    conn = get_db()
    total_records = conn.execute('SELECT COUNT(*) FROM step_records').fetchone()[0]
    daily_rows = conn.execute(
        'SELECT SUM(steps) AS s FROM step_records GROUP BY date'
    ).fetchall()
    peak_hour = conn.execute('''
        SELECT hour FROM step_records
        GROUP BY hour
        ORDER BY AVG(steps) DESC
        LIMIT 1
    ''').fetchone()
    conn.close()

    totals = [r['s'] for r in daily_rows]
    return jsonify({
        'total_records': total_records,
        'days_tracked':  len(totals),
        'avg_daily':     int(sum(totals) / len(totals)) if totals else 0,
        'best_day':      int(max(totals)) if totals else 0,
        'goal_days':     sum(1 for s in totals if s >= 10000),
        'peak_hour':     f"{peak_hour['hour']}:00" if peak_hour else 'N/A',
    })


@bp.route('/api/ingest', methods=['POST'])
def ingest():
    body = request.get_json(silent=True)
    if not body:
        return jsonify({'error': 'Expected JSON body'}), 400

    records = body if isinstance(body, list) else body.get('data', [])
    if not records:
        return jsonify({'error': 'No records in payload'}), 400

    inserted = 0
    conn = get_db()
    for r in records:
        try:
            start_str = r.get('start_date') or r.get('startDate')
            date      = r.get('date', start_str[:10] if start_str else None)
            hour      = int(r.get('hour', 0))
            steps     = float(r['steps'])
            source    = r.get('source', 'manual')
            if not date or steps <= 0:
                continue
            conn.execute(
                'INSERT OR IGNORE INTO step_records (start_date, date, hour, steps, source) VALUES (?,?,?,?,?)',
                (start_str or date, date, hour, steps, source),
            )
            inserted += conn.execute('SELECT changes()').fetchone()[0]
        except (KeyError, ValueError, TypeError):
            continue

    conn.commit()
    conn.close()
    return jsonify({'inserted': inserted, 'received': len(records)})
