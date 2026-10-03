"""Download the current ZTP GTFS schedule and the official ZDMK parking map."""

from hackyeah.mobility_data import ensure_data


def main():
    for kind in ("schedule", "parking"):
        path, warnings = ensure_data(kind, force=True)
        print(f"{kind}: {path}")
        for warning in warnings:
            print(warning)


if __name__ == "__main__":
    main()
