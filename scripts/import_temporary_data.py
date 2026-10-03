"""Import validated roadworks JSON into the existing SQLite database."""

import argparse
import json
from pathlib import Path

from hackyeah.models import TemporaryDataSnapshot
from hackyeah.temporary_store import import_snapshots


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=Path("data/krakow.sqlite3"))
    parser.add_argument(
        "--input",
        type=Path,
        nargs="+",
        default=[Path("data/temporary/construction.json")],
    )
    parser.add_argument(
        "--missing-only",
        action="store_true",
        help="Add absent records; preserve existing rows and timestamps.",
    )
    args = parser.parse_args()
    snapshots = [
        TemporaryDataSnapshot.model_validate_json(path.read_text())
        for path in args.input
    ]
    print(
        json.dumps(
            import_snapshots(args.database, snapshots, missing_only=args.missing_only),
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
