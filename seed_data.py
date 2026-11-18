"""Human-editable synthetic fixtures. Validate all files before changing the DB."""

import json
from pathlib import Path

SEED_DIR = Path(__file__).resolve().parent / "data" / "seed"
FIELDS = {
    "users": ("id", "name"),
    "mails": ("id", "owner", "body"),
    "events": ("id", "owner", "title", "time"),
}


def load_seed(directory=SEED_DIR):
    data = {}
    for table, fields in FIELDS.items():
        path = Path(directory) / (table + ".json")
        try:
            rows = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            raise ValueError(f"{path.name}: {e}") from e
        if not isinstance(rows, list):
            raise ValueError(f"{path.name}: expected JSON array")
        seen = set()
        for n, row in enumerate(rows, 1):
            if not isinstance(row, dict) or set(row) != set(fields):
                raise ValueError(f"{path.name} row {n}: required fields {fields}")
            if any(
                (
                    not isinstance(row[k], str)
                    or not row[k].strip()
                    or len(row[k]) > 8000
                    for k in fields
                )
            ):
                raise ValueError(
                    f"{path.name} row {n}: nonempty strings required, max 8000 characters"
                )
            if row["id"] in seen:
                raise ValueError(f"{path.name}: duplicate id {row['id']}")
            seen.add(row["id"])
        data[table] = rows
    users = {r["id"] for r in data["users"]}
    if not {"M", "A", "B"} <= users:
        raise ValueError("Keep demo users M, A, B")
    for table in ["mails", "events"]:
        if any((row["owner"] not in users for row in data[table])):
            raise ValueError(f"{table}: owner must exist in users.json")
    if not any((r["id"] == "mail1" and r["owner"] == "M" for r in data["mails"])):
        raise ValueError("Keep mail1 owned by M for the onboarding demo")
    return data


def apply_seed(db, data):
    for table, fields in FIELDS.items():
        updates = ",".join((f"{k}=excluded.{k}" for k in fields if k != "id"))
        sql = f"INSERT INTO {table} ({','.join(fields)}) VALUES ({','.join(('?' for _ in fields))}) ON CONFLICT(id) DO UPDATE SET {updates}"
        db.executemany(sql, [tuple((row[k] for k in fields)) for row in data[table]])
