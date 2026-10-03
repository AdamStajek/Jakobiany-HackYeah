# Rozszerzenie danych o przeszkodach — 3 października 2026

Zaktualizowano `data/krakow.sqlite3`. Kopia sprzed importu:
`data/krakow.before-obstacles.sqlite3`.

| Miara | Przed | Po |
| --- | ---: | ---: |
| Miejsca | 7 314 | 34 469 |
| Niepuste obserwacje w atrybutach modelu `Attribute`, z OSM | 140 | 33 015 |
| Rekordy źródeł zewnętrznych | 12 040 | 12 090 |
| Pobrane strony miejsc | 664 | 664 |
| Remonty ZDMK | 68 | 68, odświeżone |

W katalogu znajduje się teraz 7 113 obiektów schodów, 5 851 obiektów
krawężników, 231 toalet, 140 wind oraz 13 825 miejsc odpoczynku.
Kategorie mogą się nakładać. Obserwacje obejmują wartości dodatnie i ujemne;
ich liczba nie jest liczbą unikalnych barier ani liczbą pomiarów terenowych.
Zachowano wszystkie wcześniejsze identyfikatory miejsc, dane stron,
wzbogacenia oraz tabelę danych użytkowników.

## Źródła

- [OpenStreetMap / Geofabrik, Małopolska](https://download.geofabrik.de/europe/poland.html):
  wykorzystano pobrany 3 października wyciąg, po sprawdzeniu sum kontrolnych.
  Import ogranicza obiekty do granicy administracyjnej Krakowa. Licencja ODbL.
- [MSIP Kraków — toalety publiczne](https://msip.um.krakow.pl/arcgis/rest/services/Obserwatorium/WT_WC_2023/MapServer/0):
  pobrano 50 rekordów z geometrią, deklaracją dostępności, opisem dostosowania
  i godzinami działania; 46 przypisano do jednoznacznej toalety OSM w promieniu
  25 metrów. Cztery bez jednoznacznego dopasowania pozostają w
  `external_place_data` z `place_id=NULL`. Nie przypisuje się ich sąsiednim lokalom.
  Zachowano pełne pola źródła i URL; nie zakładamy licencji ODbL dla danych miejskich.
- [ZDMK — zestawienie prac](https://zdmk.krakow.pl/zestawienie-prac-w-miescie/):
  odświeżono 68 rekordów z mapy KML. Liczba nie wzrosła; nie tworzymy sztucznych
  dodatkowych remontów. Termin ważności migawki wynosi 24 godziny.

## Zmiany importu i API

Importer obejmuje samodzielne obiekty schodów, krawężników, wind, toalet
i odpoczynku. Odczytuje wysokości krawężników, stan nawierzchni i oświetlenie.
Przekazuje obecność schodów do kanonicznego `steps_present`; dawne
`stairs_present` pozostaje w danych historycznych. Normalizuje nawierzchnie
do enum API, zachowując oryginalne tagi jako materiał źródłowy.

MSIP przechowuje deklaracje jako walidowane `Observation` w
`accessibility_observations`. Szczegóły miejsca łączą je z faktami OSM.
Sprzeczność daje `value=null` i `unconfirmed_reason=conflicting`.
Deklaracje źródeł nie otrzymują statusu weryfikacji terenowej ani wymyślonej
pewności procentowej. Opis wskazuje m.in. część damską/męską i sposób dostępu.
Godziny i sezonowość są opisem źródłowym, nie dowodem bieżącego otwarcia.

`PlaceDetails.barriers` zawiera odniesienia do faktów o schodach, podniesionych
krawężnikach, złej nawierzchni, braku światła i dostępnej toalety. Punkt miejsca
nie wyznacza przebiegu wszystkich wejść ani geometrii zamkniętego chodnika.
Nie dopisano brakujących pomiarów progów, szerokości ani nachylenia.

## Powtarzanie aktualizacji

```bash
PYTHONPATH=src uv run --group data python -m scripts.download_osm --refresh
PYTHONPATH=src uv run --group data python -m scripts.build_places_db --additive
PYTHONPATH=src uv run --group data python -m scripts.scrape_public_places --source toilets --output data/toilet-accessibility.json
PYTHONPATH=src uv run python -m scripts.scrape_construction
PYTHONPATH=src uv run --group data python -m scripts.report_places
```

Tryb `--additive` zachowuje dawne miejsca spoza aktualnego katalogu; nie służy
do usuwania nieistniejących już obiektów. Standardowy `update_database`
również używa tego trybu, a domyślny scraping MSIP obejmuje teraz toalety.
Opcja `--cached` w scraperze pozwala ponownie przetworzyć zapisane odpowiedzi
bez zmiany czasu ich pobrania. Klucze API nie są wymagane.

## Weryfikacja

- SQLite: `integrity_check=ok`, brak naruszeń kluczy obcych, zero utraconych miejsc.
- Wszystkie 33 015 niepustych obserwacji OSM w atrybutach API przeszły model `Observation`.
- Sprawdzono `PlaceDetails` dla każdej nowej kategorii oraz fakt i opis MSIP.
- Testy importu, zachowania starszych miejsc, normalizacji, konfliktów źródeł
  i danych czasowych; Ruff oraz Pyright dla zmienionych modułów API.
- Testy HTTP nie ukończyły się: środowisko blokuje się w wykonaniu wątku AnyIO.
  Ten sam timeout wystąpił dla niezależnego `anyio.to_thread.run_sync(lambda: 42)`.
  Walidacja danych i bezpośrednie wywołania katalogu przeszły; nie deklarujemy
  ukończenia testów HTTP.
