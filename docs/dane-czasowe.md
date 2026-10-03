# Dane czasowe: pogoda w locie, remonty w SQLite

Zakres: upał, ryzyko oblodzenia, śnieg i remonty. Pogoda jest pobierana na
bieżąco przy każdym zapytaniu zwracającym trasę, bez zapisu do bazy lub pliku.
Remonty są pobierane z publicznej mapy ZDMK i importowane do istniejącej SQLite.
Dane są walidowane modelami Pydantic przed użyciem.

## Jedna komenda aktualizacji bazy

```bash
# Szybkie uzupełnienie brakujących rekordów z lokalnej kopii remontów:
PYTHONPATH=src uv run --group data python -m scripts.update_database --missing-only
# Pełna aktualizacja wszystkich źródeł utrwalanych w bazie:
PYTHONPATH=src uv run --group data python -m scripts.update_database
# Pełna przebudowa z istniejących, zweryfikowanych plików OSM:
PYTHONPATH=src uv run --group data python -m scripts.update_database --cached-osm
```

`--missing-only` wymaga istniejącej bazy miejsc. Nie pobiera OSM i nie
przebudowuje bazy. Uruchamia importer z lokalnym `construction.json`; tylko
przy braku tego pliku uruchamia również scraper ZDMK. Dopisuje nieobecne ID,
zachowując istniejące rekordy, ich wartości i terminy. Nie jest to pełna
synchronizacja: istniejące rekordy mogą pozostać nieaktualne. Terminów
świeżości nie przedłuża sam import.

Pełny proces kolejno uruchamia wcześniejsze skrypty i nowy importer:
`download_osm`, `scrape_construction`, `build_places_db`,
`import_temporary_data`, `report_places`. Pogoda nie jest etapem aktualizacji
bazy. Eksport sieci tras pozostaje osobnym artefaktem plikowym.

W pełnym procesie nowa baza powstaje obok docelowej i zastępuje ją atomowo
po udanych etapach oraz kontroli integralności i kluczy obcych. Wcześniej
powstaje kopia `data/krakow.previous.sqlite3`. Awaria przed publikacją
zachowuje poprzednią bazę. Źródłowe pliki OSM mogą już być odświeżone.
Raporty i plik remontów są publikowane po bazie; awaria ich publikacji nie
wycofuje opublikowanej bazy. Ponowne uruchomienie odtwarza raporty.

Nie uruchamiać równolegle samodzielnych importerów i orkiestratora. Blokada
zapobiega równoległym uruchomieniom orkiestratora. Po zastąpieniu pliku
czytelnicy powinni ponownie otworzyć połączenia. Rollback pełnego procesu:
przy zatrzymanych czytelnikach/pisarzach przywrócić `krakow.previous.sqlite3`
jako `krakow.sqlite3`.

## Samodzielne skrypty

```bash
# Prognoza na stdout, bez zapisu:
PYTHONPATH=src uv run python scripts/scrape_weather.py
# Remonty do pliku:
PYTHONPATH=src uv run python scripts/scrape_construction.py
# Remonty do pliku i SQLite:
PYTHONPATH=src uv run python scripts/scrape_construction.py --database data/krakow.sqlite3
# Import wcześniej pobranych remontów:
PYTHONPATH=src uv run python -m scripts.import_temporary_data --missing-only
```

Remonty domyślnie trafiają do `data/temporary/construction.json`; `--output`
zmienia tę ścieżkę. Pogoda odrzuca `--output` i `--database`. `--input` pozwala
przetworzyć lokalny JSON prognozy lub KML mapy bez połączenia z internetem.
Próg upału: `--heat-c 30`; punkt: `--lat 50.0614 --lon 19.9366`;
horyzont: `--days 3` (1–7). Domyślny punkt to centrum Krakowa.

## Model danych i SQLite

`TemporaryDataSnapshot` zawiera `generated_at`, `valid_until`,
`source=weather|construction`, `heat_threshold_c`, `items`, `weather_hours`,
`attribution` i `warnings`. Dla remontów nie zapisujemy pól pogodowych w
metadanych bazy. `TemporaryDifficulty` zachowuje kategorię, opis, geometrię
GeoJSON (`Point | LineString | null`), lokalizację tekstową, okres, czas
aktualizacji i świeżości, status, powód niepotwierdzenia, źródła oraz oryginalne
pola źródła. Daty są świadome strefy czasowej; wartości nieznane mają `null`.

| Tabela | Zawartość |
| --- | --- |
| `temporary_imports` | Najnowszy import remontów, daty pobrania i ważności, atrybucja i ostrzeżenia |
| `temporary_difficulties` | Remonty: ID, kategoria, okres i pełny JSON modelu, w tym geometria oraz źródła |

Normalny import zastępuje aktualną kopię remontów w jednej transakcji,
bez duplikatów; starsza kopia nie może zastąpić nowszej. `--missing-only`
używa `INSERT OR IGNORE` i niczego nie usuwa. Błąd importu wycofuje całą
transakcję. Dane miejsc nie są modyfikowane, a przebudowa OSM zachowuje
tabele remontów. Importer i ograniczenia SQL odrzucają dane pogodowe.

`valid_until` oznacza świeżość danych, a `ends_at` koniec utrudnienia.
Okres jest półotwarty `[starts_at, ends_at)`. Nieznany koniec remontu nie
oznacza zakończenia prac. Pobrane utrudnienia mają `status=unconfirmed`,
`confidence_percent=null`; prognoza ma powód `forecast`, remont
`pending_verification`. Konsument wygasłych remontów powinien oznaczyć
`stale` i dodać ostrzeżenie. Import nie zmienia tych terminów.

## Pogoda: Open-Meteo, pobieranie w locie

[API Open-Meteo](https://open-meteo.com/en/docs) zwraca godzinową prognozę
w UTC dla punktu siatki modelu. Punkt może różnić się od żądanego; to nie
pomiar na ulicy. `WeatherHour` zachowuje temperaturę i odczuwalną w °C,
opad w mm, opad śniegu i pokrywę w cm, kod WMO oraz nullable ryzyka.
Źródłowa pokrywa w metrach jest przeliczana na cm. Opady dotyczą poprzedniej
godziny, jawnie wskazanej przez `precipitation_starts_at` i
`precipitation_ends_at`; wartości chwilowe dotyczą `starts_at`.

| Ryzyko | Reguła |
| --- | --- |
| Upał | Temperatura lub odczuwalna ≥ próg, domyślnie 30°C |
| Oblodzenie | Kod WMO 48, 56, 57, 66, 67 albo temperatura ≤ 0°C i opad lub pokrywa > 0 |
| Śnieg | Opad śniegu lub pokrywa > 0 albo kod WMO 71, 73, 75, 77, 85, 86 |

Bez sygnału oblodzenia wartość pozostaje `null`: nie wykluczamy zamarzania
wcześniejszych opadów. Brak sygnału upału lub śniegu daje `false` tylko przy
komplecie potrzebnych wartości. To brak sygnału w modelu, nie gwarancja
odśnieżenia ani dostępności chodnika. Ryzyka są heurystyką na godzinę
`[starts_at, ends_at)`, a nie pomiarem nawierzchni.

`/routes/plan` pobiera siedem dni prognozy dla początku niepustej trasy.
Odpowiedź zawiera `weather: TemporaryDataSnapshot | null`. Sygnały z okresu
przejścia trafiają do `segments[].temporary_difficulties`; prognoza jest
wspólna dla trasy, nie osobna dla odcinków, i nie wyklucza ich automatycznie.
Geometria prototypu nadal jest syntetyczna. Brak prognozy dla czasu przejścia
lub awaria źródła daje ostrzeżenie; awaria zwraca `weather=null`, bez fallbacku
do pliku lub bazy. Każde nowe zapytanie ponawia pobranie.

Prognoza ma termin świeżości trzy godziny, ale backend jej nie cache'uje.
Licencja danych: CC-BY-4.0; zachowujemy atrybucję Open-Meteo. Bezpłatny
endpoint jest przeznaczony do użytku niekomercyjnego zgodnie z
[warunkami źródła](https://open-meteo.com/en/terms).

## Remonty: mapa ZDMK

Źródło: mapa na [stronie ZDMK](https://zdmk.krakow.pl/zestawienie-prac-w-miescie/),
[publiczny KML](https://www.google.com/maps/d/kml?mid=1_iHhcnIv8THHQSyeLFPArE6k2zhIrtA&forcekml=1).
Odczytujemy nazwę, punkt, lokalizację szczegółową, zmiany ruchu, rodzaj prac,
inwestora i daty. Nie zgadujemy geometrii z nazw ulic. Punkt mapy nie opisuje
pełnego zasięgu robót, a remont jezdni nie oznacza zamknięcia dla pieszych:
`pedestrian_access=unknown`.

Daty `DD.MM.RRRR` są lokalnymi dniami Europe/Warsaw, z uwzględnieniem zmiany
czasu. Koniec obejmuje cały dzień: `ends_at` to początek następnego dnia.
Niejasne terminy, np. „do odwołania”, pozostają `null`. Odwrócony okres daje
nieznane daty i ostrzeżenie. Zakończone znane okresy są pomijane; przyszłe
prace pozostają w zbiorze. ID jest hashem nazwy, lokalizacji i daty początku;
zmiana tych pól zmienia ID. Oryginalne pola pozostają w `source_fields`.

Świeżość remontów: 24 godziny od pobrania. `updated_at` to odczyt mapy, nie
edycja przez ZDMK. Licencja zbioru nie jest zadeklarowana: `license=null`,
zachowujemy odnośnik i autorstwo ZDMK. Awaria pobierania nie przedłuża
świeżości i nie usuwa rekordów. Remonty w SQLite nie są jeszcze powiązane
z odcinkami syntetycznego grafu; takie powiązanie wymaga weryfikacji zasięgu.
