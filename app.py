from flask import Flask, jsonify, render_template
import xml.etree.ElementTree as ET
import pandas as pd
from datetime import datetime

app = Flask(__name__)

def load_steps():
    print("Parsing XML...")
    tree = ET.parse('export.xml')
    root = tree.getroot()

    steps = []
    for record in root.findall('Record'):
        if record.attrib.get('type') == 'HKQuantityTypeIdentifierStepCount':
            steps.append({
                'startDate': record.attrib.get('startDate'),
                'steps': float(record.attrib.get('value'))
            })

    df = pd.DataFrame(steps)
    df['startDate'] = pd.to_datetime(df['startDate'], utc=True).dt.tz_convert('Europe/Paris')
    df['date'] = df['startDate'].dt.date
    df['hour'] = df['startDate'].dt.hour
    print(f"Loaded {len(df)} records")
    return df

DF = load_steps()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/daily')
def daily():
    daily = DF.groupby('date')['steps'].sum().reset_index()
    daily['date'] = daily['date'].astype(str)
    daily = daily.tail(30)
    return jsonify({
        'labels': daily['date'].tolist(),
        'values': daily['steps'].astype(int).tolist()
    })

@app.route('/api/hourly')
def hourly():
    hourly = DF.groupby('hour')['steps'].mean().reset_index()
    return jsonify({
        'labels': hourly['hour'].tolist(),
        'values': hourly['steps'].round(1).tolist()
    })

@app.route('/api/stats')
def stats():
    daily = DF.groupby('date')['steps'].sum()
    peak_hour = int(DF.groupby('hour')['steps'].mean().idxmax())
    return jsonify({
        'total_records': len(DF),
        'days_tracked': len(daily),
        'avg_daily': int(daily.mean()),
        'best_day': int(daily.max()),
        'goal_days': int((daily >= 10000).sum()),
        'peak_hour': f"{peak_hour}:00"
    })

if __name__ == '__main__':
    app.run(debug=True)