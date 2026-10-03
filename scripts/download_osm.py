"""Download public OSM extracts; retain a local cache and provenance manifest."""

import argparse
import hashlib
import json
import shutil
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    "malopolskie-latest.osm.pbf": "https://download.geofabrik.de/europe/poland/malopolskie-latest.osm.pbf",
    "krakow-boundary.json": "https://www.openstreetmap.org/api/0.6/relation/449696/full.json",
}
USER_AGENT = "hackyeah-osm-import/0.1 (read-only Krakow accessibility dataset)"


def sha256(path: Path) -> str:
    with path.open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


def download(url: str, destination: Path) -> dict:
    temporary = destination.with_suffix(destination.suffix + ".part")
    for attempt in range(3):
        try:
            request = Request(url, headers={"User-Agent": USER_AGENT})
            with urlopen(request, timeout=60) as response, temporary.open("wb") as file:
                shutil.copyfileobj(response, file)
                expected = response.headers.get("Content-Length")
                if expected and file.tell() != int(expected):
                    raise OSError("Niepełne pobranie pliku.")
                modified = response.headers.get("Last-Modified")
            if temporary.stat().st_size == 0:
                raise OSError("Pusty plik źródłowy.")
            temporary.replace(destination)
            return {
                "url": url,
                "retrieved_at": datetime.now(UTC).isoformat(),
                "last_modified": modified,
                "sha256": sha256(destination),
                "bytes": destination.stat().st_size,
            }
        except (OSError, URLError):
            temporary.unlink(missing_ok=True)
            if attempt == 2:
                raise
            time.sleep(2 ** (attempt + 1))
    raise RuntimeError("Pobieranie nie powiodło się.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "data/raw")
    parser.add_argument(
        "--refresh", action="store_true", help="Odśwież pliki zamiast używać cache."
    )
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = args.output_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    for filename, url in SOURCES.items():
        path = args.output_dir / filename
        if args.refresh or not path.exists():
            print(f"Pobieranie {filename} z {url}", flush=True)
            manifest[filename] = download(url, path)
        else:
            digest = sha256(path)
            if manifest.get(filename, {}).get("sha256") not in (None, digest):
                raise ValueError(
                    f"Checksum pliku {filename} różni się od manifestu; użyj --refresh."
                )
            manifest.setdefault(
                filename,
                {
                    "url": url,
                    "retrieved_at": datetime.fromtimestamp(
                        path.stat().st_mtime, UTC
                    ).isoformat(),
                    "last_modified": None,
                    "sha256": digest,
                    "bytes": path.stat().st_size,
                },
            )
            print(f"Cache: {filename}", flush=True)
        temporary = manifest_path.with_suffix(".json.part")
        temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
        temporary.replace(manifest_path)


if __name__ == "__main__":
    main()
