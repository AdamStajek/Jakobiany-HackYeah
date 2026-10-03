"""Generate coverage reports from the standalone OSM SQLite database."""

import argparse
import json
import sqlite3
from contextlib import closing
from pathlib import Path

from hackyeah.place_enrichment import effective_places
from scripts.build_places_db import CATEGORIES, FIELDS
from scripts.download_osm import ROOT


def coverage(database: Path) -> dict:
    with closing(
        sqlite3.connect(f"{database.resolve().as_uri()}?mode=ro", uri=True)
    ) as db:
        db.row_factory = sqlite3.Row
        metadata = {
            row["key"]: json.loads(row["value_json"])
            for row in db.execute("SELECT * FROM metadata")
        }
        total = db.execute("SELECT COUNT(*) FROM places").fetchone()[0]
        categories = []
        for category, label in CATEGORIES.items():
            row = db.execute(
                """
                SELECT COUNT(*) AS total, COUNT(p.name) AS named,
                    SUM(EXISTS (SELECT 1 FROM accessibility_facts f WHERE f.place_id=p.id AND f.value_json IS NOT NULL)) AS with_accessibility
                FROM places p JOIN place_categories c ON c.place_id=p.id WHERE c.category_id=?
            """,
                (category,),
            ).fetchone()
            categories.append(
                {
                    "id": category,
                    "label": label,
                    "total": row["total"],
                    "named": row["named"],
                    "with_accessibility": row["with_accessibility"] or 0,
                }
            )
        fields = []
        for attribute, (label, unit) in FIELDS.items():
            row = db.execute(
                """
                SELECT SUM(value_json IS NOT NULL) AS known,
                    SUM(unconfirmed_reason='missing') AS missing,
                    SUM(unconfirmed_reason='conflicting') AS conflicting,
                    SUM(value_json='true') AS yes, SUM(value_json='false') AS no
                FROM accessibility_facts WHERE attribute=?
            """,
                (attribute,),
            ).fetchone()
            provenance = db.execute(
                """
                SELECT COUNT(DISTINCT CASE WHEN scope='place' AND method!='explicit_description' THEN place_id END) AS direct,
                    COUNT(DISTINCT CASE WHEN scope!='place' THEN place_id END) AS linked,
                    COUNT(DISTINCT CASE WHEN method='explicit_description' THEN place_id END) AS description
                FROM fact_evidence WHERE attribute=? AND place_id IN
                    (SELECT place_id FROM accessibility_facts WHERE attribute=? AND value_json IS NOT NULL)
            """,
                (attribute, attribute),
            ).fetchone()
            fields.append(
                {
                    "attribute": attribute,
                    "label": label,
                    "unit": unit,
                    **dict(row),
                    **dict(provenance),
                    "coverage_percent": round(100 * row["known"] / total, 2)
                    if total
                    else 0,
                }
            )
        primary = [
            "steps_count",
            "threshold_height_cm",
            "elevator_available",
            "entrance_width_cm",
            "accessible_toilet",
        ]
        placeholders = ",".join("?" for _ in primary)
        all_five = db.execute(
            f"""
            SELECT COUNT(*) FROM (SELECT place_id FROM accessibility_facts
            WHERE attribute IN ({placeholders}) AND value_json IS NOT NULL
            GROUP BY place_id HAVING COUNT(*)=5)
        """,
            primary,
        ).fetchone()[0]
        examples = [
            dict(row)
            for row in db.execute("""
            WITH examples AS (SELECT p.id, p.name, f.attribute, json_extract(f.value_json, '$') AS value,
                e.scope, e.method, o.source_url, e.tag_key, e.raw_value
                , ROW_NUMBER() OVER (PARTITION BY f.attribute ORDER BY p.id) AS ordinal
            FROM places p JOIN accessibility_facts f ON f.place_id=p.id
            JOIN fact_evidence e ON e.place_id=f.place_id AND e.attribute=f.attribute
            JOIN osm_objects o ON o.id=e.object_id
            WHERE f.value_json IS NOT NULL AND f.attribute IN ('steps_count', 'threshold_height_cm', 'elevator_available', 'entrance_width_cm', 'accessible_toilet')
            ) SELECT * FROM examples WHERE ordinal <= 5 ORDER BY attribute, id
        """)
        ]
        linked = [
            dict(row)
            for row in db.execute(
                "SELECT link_method, COUNT(*) AS links, COUNT(DISTINCT place_id) AS places FROM place_features GROUP BY link_method"
            )
        ]
        extra = {
            "named": db.execute("SELECT COUNT(name) FROM places").fetchone()[0],
            "with_street_and_number": db.execute(
                "SELECT COUNT(*) FROM places WHERE street IS NOT NULL AND housenumber IS NOT NULL"
            ).fetchone()[0],
            "with_website": db.execute("SELECT COUNT(website) FROM places").fetchone()[
                0
            ],
            "with_phone": db.execute("SELECT COUNT(phone) FROM places").fetchone()[0],
            "with_opening_hours": db.execute(
                "SELECT COUNT(opening_hours) FROM places"
            ).fetchone()[0],
            "explicitly_private_or_no_access": db.execute(
                "SELECT COUNT(*) FROM places WHERE access IN ('private','no')"
            ).fetchone()[0],
        }
        enrichment_report = {}
        if db.execute(
            "SELECT 1 FROM sqlite_master WHERE name='external_place_data'"
        ).fetchone():
            effective = effective_places(db)
            enrichment_report = {
                "sources": [
                    dict(row)
                    for row in db.execute(
                        "SELECT source, COUNT(*) AS records, COUNT(DISTINCT place_id) AS matched_places FROM external_place_data GROUP BY source"
                    )
                ],
                "website_pages": db.execute(
                    "SELECT COUNT(*) FROM place_web_data"
                ).fetchone()[0],
                "effective_fields": {
                    key: sum(bool(row.get(key)) for row in effective)
                    for key in (
                        "website",
                        "phone",
                        "opening_hours",
                        "street",
                        "postcode",
                    )
                },
                "places_with_photos": db.execute(
                    "SELECT COUNT(DISTINCT place_id) FROM external_place_data WHERE source='commons' AND place_id IS NOT NULL"
                ).fetchone()[0],
                "enriched_places": db.execute(
                    "SELECT COUNT(*) FROM (SELECT place_id FROM external_place_data WHERE place_id IS NOT NULL UNION SELECT place_id FROM place_web_data)"
                ).fetchone()[0],
            }
    return {
        "enrichment": enrichment_report,
        "metadata": metadata,
        "total_places": total,
        "all_five_primary_fields": all_five,
        "basic_fields": extra,
        "categories": categories,
        "fields": fields,
        "feature_links": linked,
        "examples": examples,
    }


def markdown(report: dict) -> str:
    metadata = report["metadata"]
    total = report["total_places"]
    lines = [
        "# Pokrycie danych OSM — Kraków",
        "",
        f"Import: `{metadata['imported_at']}`. Stan wyciągu OSM: `{metadata['extract_stats']['snapshot_at']}`.",
        "",
        f"Baza zawiera **{total} obiektów OSM** w granicach administracyjnych Krakowa (relacja 449696).",
        f"Nazwę ma {report['basic_fields']['named']} obiektów. Wszystkie pięć podstawowych pól dostępności ma **{report['all_five_primary_fields']}** obiektów.",
        "",
        "Źródło danych: © OpenStreetMap contributors, ODbL. Pełny wyciąg Małopolski dostarcza Geofabrik; granica pochodzi z API OSM.",
        "Każde znane pole pozostaje `unconfirmed / pending_verification`; dane nie zostały zweryfikowane w terenie.",
        "Daty pobrania i zmiany obiektu nie są datami pomiarów. `observed_at` i `confidence_percent` pozostają puste.",
        "",
        "## Kategorie",
        "",
        "| Kategoria | Obiekty | Z nazwą | Z jakimkolwiek polem dostępności |",
        "| --- | ---: | ---: | ---: |",
    ]
    for category in report["categories"]:
        lines.append(
            f"| {category['label']} | {category['total']} | {category['named']} | {category['with_accessibility']} |"
        )
    lines.extend(
        [
            "",
            "Kategorie mogą się nakładać, np. muzeum i zabytek. Nie utożsamiamy liczby obiektów OSM z liczbą unikalnych placówek.",
            f"Obiekty z `access=private/no`: {report['basic_fields']['explicitly_private_or_no_access']}.",
            "",
            "## Pola dostępności",
            "",
            "| Pole | Uzupełnione | Pokrycie | Brak wiedzy | Sprzeczne | Bezpośrednie tagi POI | Powiązane obiekty | Jawny opis |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for field in report["fields"]:
        lines.append(
            f"| `{field['attribute']}` — {field['label']} | {field['known']} | {field['coverage_percent']}% | {field['missing']} | {field['conflicting']} | {field['direct']} | {field['linked']} | {field['description']} |"
        )
    lines.extend(
        [
            "",
            "Kolumny pochodzenia mogą się nakładać. `false` i `0` liczą się jako dane uzupełnione; `null` oznacza brak wiedzy albo sprzeczność.",
            "Powiązania przestrzenne są kandydatami: winda lub toaleta w obrysie miejsca nie gwarantuje prawa dostępu ani dopasowania do potrzeb.",
            "Cechy we wspólnym budynku (`building_context`) są zapisane osobno i nie uzupełniają pól najemcy.",
            "",
            "## Metadane miejsc",
            "",
            "| Pole | Uzupełnione |",
            "| --- | ---: |",
        ]
    )
    for key, value in report["basic_fields"].items():
        lines.append(f"| `{key}` | {value} |")
    lines.extend(
        [
            "",
            "## Powiązania z osobno zmapowanymi obiektami",
            "",
            "| Metoda | Powiązania | Miejsca |",
            "| --- | ---: | ---: |",
        ]
    )
    for item in report["feature_links"]:
        lines.append(
            f"| `{item['link_method']}` | {item['links']} | {item['places']} |"
        )
    lines.extend(
        [
            "",
            "## Przykłady pochodzenia danych",
            "",
            "| Miejsce | Pole | Wartość | Tag źródłowy | Zakres |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for example in report["examples"]:
        name = (example["name"] or example["id"]).replace("|", "\\|")
        tag = f"{example['tag_key']}={example['raw_value']}".replace("|", "\\|")
        lines.append(
            f"| [{name}]({example['source_url']}) | `{example['attribute']}` | `{example['value']}` | `{tag}` | `{example['scope']}` |"
        )
    lines.extend(
        [
            "",
            "Metody importu, ograniczenia i darmowe źródła dla brakujących danych: [osm-data.md](osm-data.md).",
            "Raport w JSON: [data/coverage.json](../data/coverage.json).",
            "",
        ]
    )
    if report.get("enrichment"):
        enriched = report["enrichment"]
        lines.extend(
            [
                "",
                "## Uzupełnienie z innych źródeł",
                "",
                f"Miejsca z dodatkowymi danymi lub zdjęciami: **{enriched['enriched_places']}**. Zdjęcia Commons: **{enriched['places_with_photos']} miejsc**.",
                f"Metadane stron miejsc: {enriched['website_pages']}.",
                "",
                "| Źródło | Rekordy źródłowe | Dopasowane miejsca OSM |",
                "| --- | ---: | ---: |",
            ]
        )
        for item in enriched["sources"]:
            lines.append(
                f"| {item['source']} | {item['records']} | {item['matched_places']} |"
            )
        lines.extend(
            [
                "",
                "Pokrycie po uzupełnieniu braków OSM (tak jak w API):",
                "",
                "| Pole | Miejsca |",
                "| --- | ---: |",
            ]
        )
        for key, value in enriched["effective_fields"].items():
            lines.append(f"| `{key}` | {value} |")
        lines.extend(
            [
                "",
                "Rekordy niedopasowane pozostają w `external_place_data` z `place_id=NULL`; nie są automatycznie nowymi punktami katalogu. Zdjęcia to URL-e i metadane licencyjne, bez plików binarnych.",
                "",
            ]
        )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=ROOT / "data/krakow.sqlite3")
    parser.add_argument("--json-output", type=Path, default=ROOT / "data/coverage.json")
    parser.add_argument(
        "--markdown-output", type=Path, default=ROOT / "docs/osm-coverage.md"
    )
    args = parser.parse_args()
    report = coverage(args.database)
    for path, content in [
        (args.json_output, json.dumps(report, ensure_ascii=False, indent=2) + "\n"),
        (args.markdown_output, markdown(report)),
    ]:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    print(
        f"Miejsca: {report['total_places']}; komplet pięciu pól: {report['all_five_primary_fields']}"
    )
    for field in report["fields"]:
        print(f"{field['attribute']}: {field['known']} ({field['coverage_percent']}%)")


if __name__ == "__main__":
    main()
