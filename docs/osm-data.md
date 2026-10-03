# Baza miejsc Krakowa z OpenStreetMap

Gotowa lokalna baza: `data/krakow.sqlite3`. FastAPI zapisuje w tym samym pliku
stan zaimplementowanych endpointów w dodatkowej tabeli `backend_records`.
Endpointy wyszukiwania i szczegółów miejsc udostępniają dane OSM.
Wynik rzeczywistego importu: [raport pokrycia](osm-coverage.md) oraz
[raport JSON](../data/coverage.json).

## Powtórzenie pobrania i importu

Z katalogu głównego repozytorium:

```bash
uv sync --group data
uv run --group data python -m scripts.download_osm
uv run --group data python -m scripts.build_places_db
uv run --group data python -m scripts.report_places
```

Pierwszy skrypt pobiera [pełny wyciąg Małopolski z Geofabrik](https://download.geofabrik.de/europe/poland/malopolskie.html)
(format PBF, około 192 MB) i pełną [relację granicy administracyjnej Krakowa](https://www.openstreetmap.org/relation/449696)
z API OpenStreetMap. Geofabrik dostarcza kopię danych OSM, a nie drugi zbiór danych.
Korzystamy z masowego pobrania danych zamiast scrapingu strony mapy.
Publiczne instancje Overpass nie odpowiadały podczas tego importu. Początkowo
sprawdzony wyciąg BBBike pomijał wschodni skraj Krakowa, więc finalny import
korzysta z pełnego wyciągu województwa. Importer odrzuca wyciąg, którego zapisany
zasięg nie pokrywa całej granicy miasta; niepełna geometria granicy również
przerywa import. Dla własnych plików bez metadanych zasięgu trzeba zapewnić
pełne pokrycie miasta przed uruchomieniem importu.

Pobrane pliki pozostają w `data/raw/`; domyślnie kolejne uruchomienie używa cache.
Odświeżenie:

```bash
uv run --group data python -m scripts.download_osm --refresh
uv run --group data python -m scripts.build_places_db
uv run --group data python -m scripts.report_places
```

Importer i generator raportu działają także bez sieci. Importer obsługuje PBF
oraz OSM XML, np. inny wyciąg obejmujący całe miasto:

```bash
uv run --group data python -m scripts.build_places_db \
  --source /path/to/extract.osm.pbf \
  --boundary data/raw/krakow-boundary.json \
  --database data/krakow.sqlite3
```

Baza jest przebudowywana z pełnego snapshotu. Powstaje plik tymczasowy,
sprawdzana jest integralność i klucze obce, a dopiero potem zastępowany jest
poprzedni plik bazy. Zmiany i usunięcia OSM nie pozostawiają starych rekordów.
Pobieranie ma trzy próby, timeout, pliki tymczasowe i manifest z SHA-256.
Surowe pliki i baza są ignorowane przez Git; raporty i skrypty są wersjonowane.
Grupa zależności `data` nie jest potrzebna do startu API ani instalowana w jego kontenerze.

## Zakres kategorii

| Kategoria | Reguła OSM |
| --- | --- |
| Hotele | `tourism=hotel` |
| Muzea | `tourism=museum` |
| Urzędy | `office=government` lub `amenity=townhall` |
| Sklepy spożywcze | `shop=supermarket/convenience/grocery/greengrocer` |
| Poczty | `amenity=post_office` |
| Banki | `amenity=bank`; bez samych bankomatów |
| Zabytki | `historic=*` lub `heritage=*`, z wyłączeniem wartości `no` |
| Punkty widokowe | `tourism=viewpoint` |
| Biblioteki | `amenity=library` |
| Kina | `amenity=cinema` |
| Teatry | `amenity=theatre` |
| Domy kultury | `amenity=community_centre/arts_centre/social_centre`, poza centrami seniora |
| Kluby seniora | `club=senior/seniors`, `community_centre:for=senior`, dzienne/środowiskowe placówki dla seniorów; także jawne nazwy „Klub Seniora”, „Centrum Aktywności Seniora” i „Centrum Aktywizacji Seniora” na centrach społecznych |
| Paczkomaty | `amenity=parcel_locker` |
| Kościoły | `amenity=place_of_worship` i `religion=christian` |

Nazwa sama w sobie nie jest wystarczająca do zaklasyfikowania dowolnego budynku.
Dom opieki nie jest automatycznie klubem seniora. Każda kategoria pozostaje
w tabeli `categories`, nawet gdy nowy snapshot nie zawiera jej obiektów.
Kategorie mogą się nakładać. Obiekt identyfikuje para typu i ID OSM:
`node/123`, `way/123`, `relation/123`. Ponowna reprezentacja way jako geometrii
area nie tworzy duplikatu. Osobne punkty i obrysy tej samej placówki nie są
automatycznie scalane na podstawie podobnej nazwy.

W bazie pozostają pomniki, nagrobki i inne obiekty z powyższymi tagami. To
szeroki katalog obiektów OSM, a nie wyłącznie lista nazwanych atrakcji
turystycznych. Pole `access` zachowuje ograniczenia
wejścia, w tym `private` i `no`; brak tego tagu nie gwarantuje dostępu publicznego.
Do kwalifikacji do miasta używany jest punkt reprezentatywny geometrii
wewnątrz pełnej granicy Krakowa, a nie tag `addr:city` ani prostokąt wyciągu.
Punkt reprezentatywny obszaru nie jest pozycją wejścia do obiektu.

## Co zapisuje baza

- `places`: nazwa, współrzędne, części adresu, strona, telefon, godziny otwarcia,
  operator i ograniczenia dostępu. Brakujące dane pozostają `NULL`.
- `categories` i `place_categories`: kategorie miejsc i ich przypisania.
- `osm_objects`: oryginalne tagi, geometria GeoJSON, ID, typ, URL, wersja
  i czas modyfikacji OSM, jeżeli występują w wyciągu.
- `accessibility_facts`: jeden rekord na każde obsługiwane pole każdego miejsca,
  także gdy wartość jest nieznana. JSON zachowuje różnicę między `false`, `0` i `null`.
- `fact_evidence`: dokładny obiekt, tag, surowa wartość, wartość znormalizowana,
  sposób odczytu i zakres cechy.
- `place_features`: oddzielnie zmapowane wejścia, schody, windy, toalety i ławki
  oraz sposób ich powiązania z miejscem.
- `metadata`: data importu, stan wyciągu, checksumy i pochodzenie danych.
- `place_accessibility`: widok SQL z pięcioma podstawowymi polami i `wheelchair`.

Odczyt najważniejszych danych:

```sql
SELECT name, steps_count, threshold_height_cm, elevator_available,
       entrance_width_cm, accessible_toilet, wheelchair
FROM place_accessibility
WHERE name IS NOT NULL;

SELECT p.name, f.attribute, f.value_json, f.unconfirmed_reason,
       o.source_url, e.tag_key, e.raw_value, e.scope
FROM places p
JOIN accessibility_facts f ON f.place_id = p.id
LEFT JOIN fact_evidence e ON e.place_id = f.place_id AND e.attribute = f.attribute
LEFT JOIN osm_objects o ON o.id = e.object_id
WHERE p.id = 'node/2817951266';
```

## Zasady interpretacji dostępności

| Pole | Źródło lub sposób odczytu |
| --- | --- |
| `steps_count` | `entrance:step_count`; `step_count` na wejściu; ściśle rozpoznany opis w rodzaju `1 step at entrance` |
| `threshold_height_cm` | `entrance:threshold:height`, `door:threshold:height`, `threshold:height`; liczby dodatnie wymagają jawnej jednostki |
| `elevator_available` | `elevator=yes/no`, `wheelchair:elevator=yes/no`; osobny `highway=elevator` w obrysie miejsca |
| `entrance_width_cm` | `entrance:width`, `wheelchair:entrance_width`; na zmapowanym wejściu także `door:width`, `width`, `maxwidth:physical` |
| `accessible_toilet` | `toilets:wheelchair=yes/no/designated`; `toilets=no`; osobne `amenity=toilets` z `wheelchair=yes/no/designated` w obrysie miejsca |
| Pozostałe pola | Jawne tagi `wheelchair`, opisy dla osób z niepełnosprawnościami, dostępność toalet, podjazdy dla wózków, nawierzchnia, nachylenie, ławki, automatyczne drzwi i oznaczenia dotykowe |

Długości z jawną jednostką są przeliczane na cm. Dla szerokości bez jednostki
stosujemy metry zgodnie z konwencją OSM; nie zgadujemy, że `90` oznacza 90 cm.
Dla słabo ustandaryzowanych wysokości bez jednostki zachowujemy tylko jawne
zero. `high`, przedziały i listy wartości nie stają się pomiarem liczbowym.
`wheelchair:step_height` trafia do osobnego `entrance_step_height_cm`:
wysokość stopnia nie jest wysokością progu.

`wheelchair=yes` **nie** uzupełnia liczby stopni, wysokości progu, szerokości
wejścia ani obecności windy. `toilets:wheelchair=limited` zostaje zapisane jako
`toilet_wheelchair=limited`, bez zamiany na pełną dostępność. Opisy tekstowe są
zachowane; poza bardzo wąskim wzorcem liczby stopni nie próbujemy zgadywać pomiarów.
Surowa nawierzchnia OSM pozostaje w bazie bez redukowania jej do enumów API.
Odległość między miejscami odpoczynku wymaga wyznaczenia konkretnej trasy,
więc importer miejsc jej nie wymyśla.

Wejścia muszą leżeć na obrysie miejsca. Schody, windy, toalety i ławki muszą
być w całości objęte jego geometrią. Sama bliskość nie tworzy powiązania.
Cechy we wspólnym budynku przy POI zmapowanym jako punkt pozostają
`building_context`; nie są przypisywane jako dostępność danego sklepu lub lokalu.
Wejścia służbowe, wyjścia ewakuacyjne oraz obiekty `access=private/no` nie
uzupełniają zbiorczych faktów dostępności.

Wartość wejścia dotyczy zmapowanego wejścia, a nie wszystkich wejść do obiektu.
Schody wewnętrzne zapisujemy jako `stairs_present`, a nie jako liczbę stopni
na wejściu; liczby stopni poszczególnych biegów pozostają w surowych tagach
powiązanych obiektów. Winda w obrysie nie dowodzi dostępności jej kabiny,
prowadzącego do niej dojścia lub wszystkich kondygnacji.
Sprzeczne pomiary pozostają `value_json=NULL / conflicting`, z zachowanymi
wartościami źródłowymi. Toaleta dostosowana i brak takiej toalety są rozróżniane:
liczby w raporcie liczą zarówno `true`, jak i `false` jako dane uzupełnione.

Import z OSM nie jest weryfikacją terenową. Wszystkie fakty mają status
`unconfirmed`; znane wartości — `pending_verification`, brakujące — `missing`.
Nie generujemy procentów wiarygodności ani dat pomiaru. Czas modyfikacji OSM
pozostaje osobną metadaną źródła. Aktualność całego snapshotu jest podana w raporcie.

## Darmowe źródła do uzupełnienia braków — sprawdzone 2026-10-03

Te źródła **nie zostały zaimportowane**. Baza powstała wyłącznie z OSM.

| Źródło | Dostęp | Co może uzupełnić | Ograniczenie |
| --- | --- | --- | --- |
| [Deklaracja Muzeum Krakowa](https://muzeumkrakowa.pl/deklaracja-dostepnosci) | Publiczny HTML, możliwy scraping poszczególnych sekcji oddziałów | Windy, toalety, schody, wymiary wejść i kabin; informacje o pomocy i pętlach indukcyjnych | Trzeba rozdzielić oddziały i połączyć je z konkretnymi obiektami OSM; schodołaz nie oznacza windy |
| [Krakowskie Forum Kultury — dostępność budynków i klubów](https://bip.krakow.pl/?mmi=20433) | Publiczny HTML w BIP | Szerokości wejść, schody, toalety, podjazdy, piętra i ograniczenia dostępu | Opisy wielu budynków w jednym dokumencie; brak jednolitego API pomiarów |
| [BIP — MOPS, Na Kozłówce 27](https://www.bip.krakow.pl/?dok_id=167279&metka=1) i deklaracje pozostałych jednostek | Publiczny HTML/PDF, scraping | Przykładowo podana szerokość wejścia 120 cm oraz 200 cm przy otwarciu drugiego skrzydła; windy, schody, toalety w innych deklaracjach | Odrębne warunki użycia wejść i wielu skrzydeł; opisu „dostosowane” nie wolno zastępować wymyślonym wymiarem |
| [accessibility.cloud — dokumentacja API autorów](https://github.com/sozialhelden/accessibility-cloud/blob/main/app/docs/json-api.md) | JSON API; rejestracja i token; dokumentacja przewiduje darmowy dostęp dla zastosowań niekomercyjnych | Dane dostępności miejsc i urządzeń, czasem szczegółowe informacje o wejściach i toaletach | Pokrycie Krakowa i licencję trzeba sprawdzić dla poszczególnych źródeł; część rekordów może powielać OSM. Dla organizacji/komercyjnego użycia warunki należy ustalić z operatorem |
| [MSIP Kraków — otwarte dane](https://msip.krakow.pl/aktualnosci/324198,2053,komunikat,nowa_usluga_pobierania_danych_msip.html) i [publiczne usługi WFS](https://www.bip.krakow.pl/?id=12838&metka=1) | Bez logowania: GeoJSON/SHP dla otwartych zbiorów, WFS dla większości | Uzupełnienie adresów, geometrii i łączenie z miejskimi obiektami | Potwierdzono dostęp do geodanych, nie do kompletu pięciu parametrów dostępności budynków |

Największą szansę na uzupełnienie szczegółów dają sekcje **dostępności
architektonicznej** na stronach właścicieli, muzeów, bibliotek, teatrów i BIP,
a nie sam opis dostępności cyfrowej strony. Dla hoteli, sklepów, banków i poczt
potrzebne są informacje o konkretnej placówce; ogólne zapewnienie sieci nie
określa szerokości jej drzwi ani wysokości progu. Nie potwierdzono jednego
darmowego API dostarczającego wszystkie pięć parametrów dla całego Krakowa.
Braki poza udokumentowanymi miejscami mogą wymagać zgłoszeń lub pomiarów w terenie.

## Źródła reguł OSM

- [wheelchair](https://wiki.openstreetmap.org/wiki/Key:wheelchair): ogólna dostępność i brak wartości domyślnej.
- [entrance:step_count](https://wiki.openstreetmap.org/wiki/Key:entrance:step_count): liczba stopni na wejściu.
- [entrance:width](https://wiki.openstreetmap.org/wiki/Key:entrance:width) i [door:width](https://wiki.openstreetmap.org/wiki/Key:door:width): szerokość wejścia/drzwi.
- [toilets:wheelchair](https://wiki.openstreetmap.org/wiki/Key:toilets:wheelchair): `yes`, `no`, `limited`, `designated` i brak wiedzy.
- [pyosmium — geometrie](https://docs.osmcode.org/pyosmium/latest/user_manual/03-Working-with-Geometries/): budowanie geometrii węzłów, ways i multipolygonów.
- [OSM — prawa do danych](https://www.openstreetmap.org/copyright): atrybucja i licencja ODbL.

## Testy

```bash
uv run --group data ruff check scripts tests/test_osm_import.py
uv run --group data python -m unittest discover -s tests -p test_osm_import.py
```

Testy obejmują import rzeczywistej struktury OSM XML, granicę miasta, komplet
pięciu pól, brak przypisywania cech sąsiednich obiektów i najemców wspólnego
budynku, brak zgadywania pomiarów z `wheelchair`, sprzeczności, przeliczenie
jednostek i powtarzalne przebudowanie bazy bez utraty poprzedniego wyniku przy błędzie.

## Wspólna aktualizacja

`PYTHONPATH=src uv run --group data python -m scripts.update_database` uruchamia
pełny proces OSM, remontów ZDMK, importu SQLite i raportu. `--missing-only`
dopisuje tylko brakujące remonty, bez przebudowy OSM. Importer OSM zachowuje
tabele remontów. Pogoda jest pobierana w locie przez API, bez zapisu do bazy.
Szczegóły: [dane czasowe](dane-czasowe.md).
