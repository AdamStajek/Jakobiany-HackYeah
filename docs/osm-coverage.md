# Pokrycie danych OSM — Kraków

Import: `2026-10-03T14:55:51.575431+00:00`. Stan wyciągu OSM: `2026-10-02T20:21:34Z`.

Baza zawiera **7314 obiektów OSM** w granicach administracyjnych Krakowa (relacja 449696).
Nazwę ma 3122 obiektów. Wszystkie pięć podstawowych pól dostępności ma **0** obiektów.

Źródło danych: © OpenStreetMap contributors, ODbL. Pełny wyciąg Małopolski dostarcza Geofabrik; granica pochodzi z API OSM.
Każde znane pole pozostaje `unconfirmed / pending_verification`; dane nie zostały zweryfikowane w terenie.
Daty pobrania i zmiany obiektu nie są datami pomiarów. `observed_at` i `confidence_percent` pozostają puste.

## Kategorie

| Kategoria | Obiekty | Z nazwą | Z jakimkolwiek polem dostępności |
| --- | ---: | ---: | ---: |
| Hotele | 266 | 261 | 44 |
| Muzea | 90 | 90 | 25 |
| Urzędy | 138 | 135 | 22 |
| Sklepy spożywcze | 1303 | 1099 | 322 |
| Poczty | 130 | 127 | 40 |
| Banki | 136 | 136 | 37 |
| Ogrody | 3032 | 24 | 75 |
| Zabytki | 1947 | 1041 | 99 |
| Punkty widokowe | 63 | 6 | 4 |
| Biblioteki | 87 | 85 | 26 |
| Kina | 12 | 12 | 5 |
| Teatry | 33 | 28 | 12 |
| Domy kultury | 94 | 93 | 14 |
| Kluby seniora | 2 | 2 | 0 |

Kategorie mogą się nakładać, np. muzeum i zabytek. Nie utożsamiamy liczby obiektów OSM z liczbą unikalnych placówek.
Ogrody obejmują także nienazwane ogródki i zieleń ozdobną z `leisure=garden`; dostęp publiczny nie jest domyślnie zakładany.
Obiekty z `access=private/no`: 88.

## Pola dostępności

| Pole | Uzupełnione | Pokrycie | Brak wiedzy | Sprzeczne | Bezpośrednie tagi POI | Powiązane obiekty | Jawny opis |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `steps_count` — Liczba stopni wejściowych | 1 | 0.01% | 7313 | 0 | 0 | 0 | 1 |
| `threshold_height_cm` — Wysokość progu | 0 | 0.0% | 7314 | 0 | 0 | 0 | 0 |
| `elevator_available` — Winda | 3 | 0.04% | 7311 | 0 | 0 | 3 | 0 |
| `entrance_width_cm` — Szerokość wejścia | 2 | 0.03% | 7312 | 0 | 0 | 2 | 0 |
| `accessible_toilet` — Toaleta dostosowana | 30 | 0.41% | 7283 | 1 | 16 | 14 | 0 |
| `wheelchair` — Ogólna ocena wheelchair | 585 | 8.0% | 6729 | 0 | 585 | 0 | 0 |
| `wheelchair_description` — Opis dostępności na wózku | 6 | 0.08% | 7308 | 0 | 6 | 0 | 0 |
| `toilet_wheelchair` — Ocena dostępności toalety (także limited) | 12 | 0.16% | 7302 | 0 | 12 | 0 | 0 |
| `toilets_available` — Obecność toalety | 42 | 0.57% | 7272 | 0 | 15 | 27 | 0 |
| `stairs_present` — Obecność schodów | 35 | 0.48% | 7279 | 0 | 0 | 34 | 1 |
| `entrance_step_height_cm` — Wysokość stopnia wejściowego (nie progu) | 0 | 0.0% | 7314 | 0 | 0 | 0 | 0 |
| `ramp_available` — Podjazd dla wózków | 0 | 0.0% | 7314 | 0 | 0 | 0 | 0 |
| `surface` — Nawierzchnia | 13 | 0.18% | 7301 | 0 | 13 | 0 | 0 |
| `slope_percent` — Nachylenie | 0 | 0.0% | 7314 | 0 | 0 | 0 | 0 |
| `rest_area_available` — Miejsce odpoczynku | 91 | 1.24% | 7223 | 0 | 5 | 86 | 0 |
| `distance_without_rest_m` — Odległość bez odpoczynku | 0 | 0.0% | 7314 | 0 | 0 | 0 | 0 |
| `automatic_door` — Automatyczne drzwi wejściowe | 3 | 0.04% | 7311 | 0 | 0 | 3 | 0 |
| `tactile_paving` — Nawierzchnia dotykowa | 0 | 0.0% | 7314 | 0 | 0 | 0 | 0 |
| `hearing_loop` — Pętla indukcyjna | 0 | 0.0% | 7314 | 0 | 0 | 0 | 0 |
| `blind_description` — Opis dla osób niewidomych | 1 | 0.01% | 7313 | 0 | 1 | 0 | 0 |
| `deaf_description` — Opis dla osób niesłyszących | 1 | 0.01% | 7313 | 0 | 1 | 0 | 0 |
| `tactile_writing_braille` — Oznaczenia Braille'a | 1 | 0.01% | 7313 | 0 | 1 | 0 | 0 |

Kolumny pochodzenia mogą się nakładać. `false` i `0` liczą się jako dane uzupełnione; `null` oznacza brak wiedzy albo sprzeczność.
Powiązania przestrzenne są kandydatami: winda lub toaleta w obrysie miejsca nie gwarantuje prawa dostępu ani dopasowania do potrzeb.
Cechy we wspólnym budynku (`building_context`) są zapisane osobno i nie uzupełniają pól najemcy.

## Metadane miejsc

| Pole | Uzupełnione |
| --- | ---: |
| `named` | 3122 |
| `with_street_and_number` | 1160 |
| `with_website` | 1066 |
| `with_phone` | 335 |
| `with_opening_hours` | 1288 |
| `explicitly_private_or_no_access` | 88 |

## Powiązania z osobno zmapowanymi obiektami

| Metoda | Powiązania | Miejsca |
| --- | ---: | ---: |
| `building_context` | 2386 | 725 |
| `entrance_on_outline` | 424 | 264 |
| `within_place` | 3435 | 120 |

## Przykłady pochodzenia danych

| Miejsce | Pole | Wartość | Tag źródłowy | Zakres |
| --- | --- | --- | --- | --- |
| [Scena Berlin](https://www.openstreetmap.org/node/11984980238) | `accessible_toilet` | `0` | `toilets:wheelchair=no` | `place` |
| [Żabka](https://www.openstreetmap.org/node/12899261283) | `accessible_toilet` | `0` | `toilets=no` | `place` |
| [Szubryt](https://www.openstreetmap.org/node/13463951811) | `accessible_toilet` | `0` | `toilets=no` | `place` |
| [Biedronka](https://www.openstreetmap.org/node/1535053386) | `accessible_toilet` | `0` | `toilets:wheelchair=no` | `place` |
| [Panorama](https://www.openstreetmap.org/node/1772724752) | `accessible_toilet` | `0` | `toilets:wheelchair=no` | `place` |
| [Historyczne centrum Krakowa](https://www.openstreetmap.org/node/12151407637) | `elevator_available` | `1` | `highway=elevator` | `within_place` |
| [Małopolskie Centrum Nauki Cogiteon](https://www.openstreetmap.org/node/12000614637) | `elevator_available` | `1` | `highway=elevator` | `within_place` |
| [Małopolskie Centrum Nauki Cogiteon](https://www.openstreetmap.org/node/12000614638) | `elevator_available` | `1` | `highway=elevator` | `within_place` |
| [Małopolskie Centrum Nauki Cogiteon](https://www.openstreetmap.org/node/12000765075) | `elevator_available` | `1` | `highway=elevator` | `within_place` |
| [Fort 2 "Kościuszko"](https://www.openstreetmap.org/node/12265865851) | `elevator_available` | `1` | `highway=elevator` | `within_place` |
| [Rynek Główny](https://www.openstreetmap.org/node/3090820032) | `entrance_width_cm` | `153.0` | `width=1.53` | `entrance_on_outline` |
| [Pałac Biskupi](https://www.openstreetmap.org/node/2511223457) | `entrance_width_cm` | `300.0` | `width=3` | `entrance_on_outline` |
| [Żabka](https://www.openstreetmap.org/node/2817951266) | `steps_count` | `1` | `wheelchair:description=1 step at entrance` | `place` |

Metody importu, ograniczenia i darmowe źródła dla brakujących danych: [osm-data.md](osm-data.md).
Raport w JSON: [data/coverage.json](../data/coverage.json).
