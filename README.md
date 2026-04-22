# StepTrack — Smart City Activity Dashboard

A web dashboard that ingests smartphone accelerometer step data, stores it in a local database, and visualises daily activity trends.

**Team:** Hadir Helali & Balkis Karoui — Smart City Project B1

---

## Features

- Parses and stores Apple Health step records into a SQLite database
- Live goal progress bar (today's steps vs. 10,000-step target)
- Daily step chart for the last 30 days with colour-coded activity levels
- Summary statistics: average, best day, days tracked, goal days reached
- REST API for ingesting new step data from any device
- Responsive layout for desktop and mobile

---

## Project Structure

```
├── app.py               # Entry point — creates Flask app and runs startup
├── database.py          # DB helpers: init, seed from XML, get_db
├── routes.py            # All API and view routes (Flask Blueprint)
├── static/
│   ├── style.css        # Styles
│   └── app.js           # Frontend logic (Chart.js charts, API calls)
├── templates/
│   └── index.html       # Dashboard HTML
├── requirements.txt
└── SmartCity_DataAnalysis.ipynb  # Exploratory analysis (Google Colab)
```

---

## Setup

**1. Clone the repo**
```bash
git clone <repo-url>
cd smart-city-step-tracker
```

**2. Create a virtual environment and install dependencies**
```bash
python -m venv venv
venv/Scripts/activate        # Windows
# source venv/bin/activate   # macOS / Linux
pip install -r requirements.txt
```

**3. Add your Apple Health data**

Export your data from the iPhone Health app:
*Health → your profile picture → Export All Health Data*

Unzip the export and place `export.xml` in the project root:
```bash
unzip export.zip
# export.xml must be at: smart-city-step-tracker/export.xml
```

**4. Run**
```bash
python app.py
```

On first run the database is created and seeded from `export.xml` automatically.
Open **http://127.0.0.1:5000** in your browser.

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Dashboard |
| `GET` | `/api/today` | Today's step count and goal progress |
| `GET` | `/api/daily` | Daily step totals for the last 30 days |
| `GET` | `/api/hourly` | Average steps by hour of day |
| `GET` | `/api/stats` | Summary statistics |
| `POST` | `/api/ingest` | Push new step records |

### Ingest payload example

```bash
curl -X POST http://127.0.0.1:5000/api/ingest \
  -H "Content-Type: application/json" \
  -d '{"data": [{"date": "2026-04-23", "hour": 14, "steps": 1200, "source": "iPhone"}]}'
```

---

## Data Source

Step data is collected by the iPhone's built-in accelerometer via Apple Health
(`HKQuantityTypeIdentifierStepCount`). Records are timestamped and converted to
the Europe/Paris timezone before storage.
