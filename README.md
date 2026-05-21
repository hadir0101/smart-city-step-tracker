<div align="center">

# StepTrack
### Smart City Activity Dashboard

![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.1-000000?style=flat-square&logo=flask&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-3-003B57?style=flat-square&logo=sqlite&logoColor=white)
![Chart.js](https://img.shields.io/badge/Chart.js-4-FF6384?style=flat-square&logo=chartdotjs&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)

*A full-stack accelerometer step tracker — from raw iPhone sensor data to a live, colour-coded activity dashboard*

**Team:** Hadir Helali & Balkis Karoui — Smart City Project B1

---

![StepTrack Dashboard](docs/dashboard.png)

</div>

---

## What it does

StepTrack turns raw smartphone accelerometer readings into actionable fitness insights without any third-party cloud service.
The pipeline runs entirely on your machine:

```
iPhone accelerometer (Phyphox)
         │
         ▼
  Butterworth low-pass filter
  + scipy peak detection
         │
         ▼
   SQLite database  ◄──── Apple Health XML export
         │
         ▼
  Flask REST API
         │
         ▼
  Chart.js dashboard  (live-updating, dark-mode)
```

---

## Features

| Category | Detail |
|---|---|
| **Ingestion** | Apple Health XML export, Phyphox CSV upload, live WiFi stream from phone |
| **Step Detection** | Custom Butterworth-filtered peak detection (`scipy.signal`) validated against ground truth |
| **Dashboard** | 30-day colour-coded bar chart, today's goal ring, summary stats, live session panel |
| **Algorithm Validation** | Side-by-side comparison of our detector vs Apple Health on the same time window |
| **REST API** | 6 endpoints — GET stats, POST records, ingest from CSV or live Phyphox stream |
| **Storage** | Local SQLite — no account, no cloud dependency |

---

## Dashboard Panels

```
┌─────────────────┬──────────────────┬─────────────────┬────────────────┐
│  Avg Daily      │  Best Day        │  Days Tracked   │  Goal Days     │
│  8,236 steps    │  13,200          │  30             │  7             │
└─────────────────┴──────────────────┴─────────────────┴────────────────┘
┌──────────────────────────────────────────────────────────────────────┐
│  Today's Goal Progress  ████░░░░░░░░░░░░░░░░░  0 / 10,000 steps     │
└──────────────────────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────────────────────┐
│  Daily Steps — Last 30 Days                                          │
│  🟢 >10k  🔵 5k–10k  🟠 <5k                                         │
└──────────────────────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────────────────────┐
│  Step Detection & Algorithm Validation                               │
│  [ CSV FILE ]  [ LIVE API ]                                          │
│  Phyphox IP: ___  Duration: __ s  Date: ____  [ Start Live ]        │
│  Steps: 216 · Cadence: 108 steps/min · Duration: 120 s              │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Quick Start

### 1 — Clone & install

```bash
git clone https://github.com/bekitos101/smart-city-step-tracker.git
cd smart-city-step-tracker

python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS / Linux

pip install -r requirements.txt
```

### 2 — Add your Apple Health data

Export from the iPhone Health app:
**Health → profile picture → Export All Health Data**

```bash
# Unzip and place export.xml in the project root
unzip export.zip
# smart-city-step-tracker/export.xml   ← must be here
```

### 3 — Run

```bash
python app.py
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000)

The database is created and seeded automatically on first launch.

---

## Live Phyphox Integration

Stream accelerometer data directly from your phone over WiFi:

1. Install **[Phyphox](https://phyphox.org)** on your iPhone or Android
2. Open the *Acceleration (without g)* experiment
3. Tap the menu → **Allow remote access** → note the IP shown
4. Enter that IP in the dashboard's Live API panel and press **Start Live**

The server polls the phone, runs step detection in real time, and compares against your Apple Health ground truth for that date.

---

## REST API

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Dashboard HTML |
| `GET` | `/api/today` | Today's steps + goal progress |
| `GET` | `/api/daily` | Daily totals — last 30 days |
| `GET` | `/api/hourly` | Average steps by hour |
| `GET` | `/api/stats` | Summary statistics |
| `GET` | `/api/ingest/csv` | Detect steps from a Phyphox CSV file |
| `POST` | `/api/ingest/live` | Detect steps from a live Phyphox stream |
| `POST` | `/api/ingest` | Push step records directly (JSON) |

### Example — push records

```bash
curl -X POST http://127.0.0.1:5000/api/ingest \
  -H "Content-Type: application/json" \
  -d '{"data": [{"date": "2026-04-23", "hour": 14, "steps": 1200, "source": "iPhone"}]}'
```

### Example — run CSV detection

```bash
curl "http://127.0.0.1:5000/api/ingest/csv?file=phyphox_data.csv&date=2026-04-15"
```

### Example — live stream (POST)

```bash
curl -X POST http://127.0.0.1:5000/api/ingest/live \
  -H "Content-Type: application/json" \
  -d '{"ip": "192.168.1.42", "duration": 30, "date": "2026-04-15"}'
```

---

## Project Structure

```
smart-city-step-tracker/
├── app.py                        # Entry point — Flask app factory
├── database.py                   # SQLite helpers: init, seed from XML
├── routes.py                     # All Flask routes (Blueprint)
├── step_detection.py             # Butterworth filter + scipy peak detection
├── phyphox_live.py               # Live WiFi polling from Phyphox
├── ingestion/
│   ├── csv_ingest.py             # CSV → detect → compare
│   ├── live_ingest.py            # Live stream → detect → compare
│   └── mock_server.py            # Local Phyphox mock for offline testing
├── static/
│   ├── style.css                 # Dark-mode dashboard styles
│   └── app.js                    # Chart.js + fetch API client
├── templates/
│   └── index.html                # Dashboard HTML template
├── docs/
│   └── dashboard.png             # Dashboard screenshot
├── SmartCity_DataAnalysis.ipynb  # Exploratory analysis (Colab)
├── requirements.txt
└── steps.db                      # SQLite database (auto-created)
```

---

## Algorithm Details

Step detection runs on the 3-axis acceleration magnitude:

```
magnitude = √(ax² + ay² + az²)
     ↓
Butterworth low-pass filter  (cutoff = 3 Hz, order = 4)
     ↓
scipy.signal.find_peaks
  height    = mean + 0.4 × std
  distance  = 0.3 s  (≈ 200 steps/min max)
     ↓
step count, cadence (steps/min), duration
```

Validation against Apple Health on a matched time window typically yields **< 10 % error**.

---

## Data Source

Step data is collected by the iPhone's built-in accelerometer via **Apple Health**
(`HKQuantityTypeIdentifierStepCount`) and the **Phyphox** app.
All timestamps are converted to **Europe/Paris** timezone before storage.

---

<div align="center">

*Smart City Project B1 · 2026*

</div>
