# Database and collected data summary

Current snapshot: **3 October 2026**. Counts below were read from
`data/krakow.sqlite3`, `data/coverage.json`, and the scrape artifacts in
`data/temporary/`. The OSM database was imported at `2026-10-03T14:55:51Z`
from the Geofabrik Małopolskie extract, whose data snapshot is dated
`2026-10-02T20:21:34Z`.

## What is in the SQLite database

`data/krakow.sqlite3` is a 31.7 MB SQLite database. It holds the Kraków places
dataset and temporary construction data, and is also the configured store for
backend records.

| Data | Count | Notes |
| --- | ---: | --- |
| Places | 7,314 | OSM places in the Kraków administrative boundary |
| Named places | 3,122 | Remaining places have no name in OSM |
| OSM objects | 11,602 | 7,026 nodes, 4,483 ways, 93 relations |
| Place-to-feature links | 6,245 | Linked entrances, buildings, or related features |
| Accessibility facts | 160,908 | Per-place attribute records; most represent missing or unconfirmed data |
| Fact evidence records | 4,102 | Source tags or mapped features supporting facts |
| Temporary construction records | 68 | Imported from ZDMK; status is unconfirmed |
| Backend records | 0 | No accounts, profiles, reports, or other API state currently stored |
| Website metadata records | 0 | `place_web_data` is not present in this database snapshot |

Each place has 22 accessibility attributes represented in `accessibility_facts`.
These are not 160,908 confirmed accessibility measurements: for most attributes
the database records that information is missing. For example, OSM has a
wheelchair value for 585 places (8.0%), toilet availability for 42 (0.57%),
and step count for one (0.01%). All five primary accessibility fields are
populated for zero places. Fact statuses are deliberately unconfirmed pending
verification.

## Places by category

Places can have multiple categories, so category counts overlap. The 14
categories total 7,333 category assignments across 7,314 places.

| Category | Places |
| --- | ---: |
| Gardens | 3,032 |
| Historic places | 1,947 |
| Grocery stores | 1,303 |
| Hotels | 266 |
| Government offices | 138 |
| Banks | 136 |
| Post offices | 130 |
| Community centres | 94 |
| Museums | 90 |
| Libraries | 87 |
| Viewpoints | 63 |
| Theatres | 33 |
| Cinemas | 12 |
| Senior clubs | 2 |

## What has been downloaded or scraped

- **OpenStreetMap:** This is a bulk download and import, not a scrape of the
  map website. The source is the full Małopolskie PBF extract plus OSM relation
  449696 for the Kraków boundary. The downloaded extract is about 202 MB. The
  place database contains the 7,314 in-boundary places listed above. OSM data
  is under ODbL with attribution to OpenStreetMap contributors.
- **ZDMK roadworks:** The scraper produced 68 temporary construction items,
  stored in `data/temporary/construction.json` and imported into
  `temporary_difficulties`. The scrape was generated on 3 October 2026 and is
  marked valid until 4 October 2026. Records contain source descriptions,
  locations, and reported dates; they do not establish the exact pedestrian
  closure area or confirmed sidewalk access.
- **Weather:** `data/temporary/weather.json` has a 57-hour forecast and zero
  current heat, ice, or snow alert items. It was generated on 3 October 2026
  and is valid for three hours. Weather is held as a file and served at query
  time; it is not stored in the SQLite database.
- **Place websites:** No website metadata has been imported. The scraper can
  collect page titles, descriptions, contact details, opening hours, and
  accessibility summaries, but this database has no `place_web_data` table.
- **Pedestrian route extract:** A separate generated artifact,
  `data/routes/network.manifest.json`, describes a rectangular area around
  Kraków: 175,411 ways and 7,886 nodes, with OSM-derived surface, lighting,
  stairs, kerbs, ramps, and smoothness facts. It is not part of the SQLite
  database and is not a verified accessible route network.

The detailed field and category coverage report is [osm-coverage.md](osm-coverage.md),
with the machine-readable counts in [`data/coverage.json`](../data/coverage.json).
