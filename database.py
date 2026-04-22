import sqlite3
import xml.etree.ElementTree as ET
from datetime import datetime
from zoneinfo import ZoneInfo

DB_PATH = 'steps.db'
PARIS = ZoneInfo('Europe/Paris')


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS step_records (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            start_date  TEXT NOT NULL,
            date        TEXT NOT NULL,
            hour        INTEGER NOT NULL,
            steps       REAL NOT NULL,
            source      TEXT,
            UNIQUE(start_date, source)
        )
    ''')
    conn.commit()
    conn.close()


def seed_from_xml():
    conn = get_db()
    count = conn.execute('SELECT COUNT(*) FROM step_records').fetchone()[0]
    conn.close()
    if count > 0:
        print(f"Database already has {count} records — skipping XML seed.")
        return

    print("Seeding database from export.xml…")
    tree = ET.parse('export.xml')
    root = tree.getroot()

    records = []
    for record in root.findall('Record'):
        if record.attrib.get('type') == 'HKQuantityTypeIdentifierStepCount':
            start_str = record.attrib.get('startDate')
            dt = datetime.strptime(start_str, '%Y-%m-%d %H:%M:%S %z').astimezone(PARIS)
            records.append((
                start_str,
                dt.date().isoformat(),
                dt.hour,
                float(record.attrib.get('value')),
                record.attrib.get('sourceName', ''),
            ))

    conn = get_db()
    conn.executemany(
        'INSERT OR IGNORE INTO step_records (start_date, date, hour, steps, source) VALUES (?,?,?,?,?)',
        records,
    )
    conn.commit()
    conn.close()
    print(f"Seeded {len(records)} records into steps.db.")
