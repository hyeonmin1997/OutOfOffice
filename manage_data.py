"""python3 manage_data.py load | show"""

import argparse, json, os
from app import Service
from seed_data import load_seed

p = argparse.ArgumentParser(
    description="Import JSON fixtures or inspect the current SQLite DB"
)
p.add_argument("command", choices=["load", "show"])
args = p.parse_args()
if args.command == "load":
    load_seed()
s = Service(os.getenv("DB_PATH", "data/demo.sqlite"))
try:
    result = s.import_seed() if args.command == "load" else s.state()
    print(json.dumps(result, ensure_ascii=False, indent=2))
finally:
    s.db.close()
