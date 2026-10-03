"""Fetch public ZDMK roadworks into a local JSON file; no database writes."""

from hackyeah.temporary_data import main

if __name__ == "__main__":
    main("construction")
