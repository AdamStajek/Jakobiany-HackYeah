"""Import a scraped place website snapshot into SQLite."""

import argparse
import json
import sqlite3
from contextlib import closing
from pathlib import Path

from pydantic import BaseModel, HttpUrl, ValidationError

ROOT = Path(__file__).resolve().parents[1]


class WebRecord(BaseModel):
    place_id: str
    source_url: HttpUrl
    retrieved_at: str
    title: str | None = None
    description: str | None = None
    telephone: str | None = None
    opening_hours: str | None = None
    accessibility_summary: str | None = None


def import_snapshot(database: Path, snapshot: Path) -> int:
    records = [WebRecord.model_validate(item) for item in json.loads(snapshot.read_text())]
    with closing(sqlite3.connect(database)) as db, db:
        db.execute("""CREATE TABLE IF NOT EXISTS place_web_data (
            place_id TEXT PRIMARY KEY REFERENCES places(id), source_url TEXT NOT NULL,
            retrieved_at TEXT NOT NULL, title TEXT, description TEXT, telephone TEXT,
            opening_hours TEXT, accessibility_summary TEXT)""")
        for item in records:
            if not db.execute("SELECT 1 FROM places WHERE id=?", (item.place_id,)).fetchone():
                raise ValueError(f"Unknown place: {item.place_id}")
            db.execute("""INSERT INTO place_web_data VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(place_id) DO UPDATE SET source_url=excluded.source_url,
                retrieved_at=excluded.retrieved_at, title=excluded.title,
                description=excluded.description, telephone=excluded.telephone,
                opening_hours=excluded.opening_hours,
                accessibility_summary=excluded.accessibility_summary""",
                (item.place_id, str(item.source_url), item.retrieved_at, item.title,
                 item.description, item.telephone, item.opening_hours,
                 item.accessibility_summary))
    return len(records)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=ROOT / "data/krakow.sqlite3")
    parser.add_argument("--input", type=Path, default=ROOT / "data/place-web.json")
    args = parser.parse_args()
    try:
        count = import_snapshot(args.database, args.input)
    except (ValidationError, json.JSONDecodeError) as error:
        parser.error(str(error))
    print(f"Zaimportowano {count} rekordów do {args.database}")


if __name__ == "__main__":
    main()
