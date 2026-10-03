"""Recalculate persisted credibility scores; intended for a daily schedule."""

import argparse
import os
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    args = parser.parse_args()
    os.environ["DATABASE_PATH"] = str(args.database.resolve())

    from hackyeah.confidence import recalculate_all

    recalculate_all()


if __name__ == "__main__":
    main()
