# Swoją Drogą — API

Szkielet FastAPI na Pythonie 3.13 z modelami Pydantic i 23 operacjami prototypu
pod prefiksem `/api/v1`. Endpointy i docelowe odpowiedzi są opisane w OpenAPI.
Modele są w `src/hackyeah/models.py`, endpointy w `src/hackyeah/api.py`.
Kontrakt API: [docs/kontrakt-frontend-backend.md](docs/kontrakt-frontend-backend.md).

## Uruchomienie lokalne

```bash
uv sync
uv run uvicorn hackyeah.main:app --app-dir src --reload
```

## Docker

```bash
docker compose up --build -d --wait
```

Frontend demonstracyjny: http://localhost:5173. Compose buduje obie aplikacje;
frontend nadal używa przykładowych danych. Ścieżka `/api/` na porcie frontendu
przekazuje żądania do backendu.
Dokumentacja Swagger: http://localhost:8000/docs.
ReDoc: http://localhost:8000/redoc. Schemat: http://localhost:8000/openapi.json.
`POST /api/v1/routes/plan` planuje trasę na grafie demonstracyjnym w pamięci.
Auth, profile, zdjęcia, zgłoszenia i deklaracje właścicieli mają logikę
prototypową oraz trwałe magazyny SQLite. Wyszukiwanie i szczegóły miejsc korzystają z lokalnej bazy OSM, a interpretacja potrzeb korzysta z OpenAI
przez PydanticAI. Zdjęcia są odrzucane, bo przetwarzanie
chroniące prywatność nie jest dostępne.
Niepoprawne dane zwracają `422 VALIDATION_ERROR`, a błędny JSON — `400 INVALID_REQUEST`.
Błędy mają format `{ "error": { "code", "message", "details", "request_id" } }`.
Ścieżka `/` zwraca `404`.
Kontener uruchamia aplikację jako użytkownik bez uprawnień roota.

Konta, sesje, profile, zdjęcia, zgłoszenia, przypisania właścicieli i historie
zmian są zapisywane w tej samej bazie SQLite co dane OSM. Backend dodaje tabelę
`backend_records`, zachowując istniejący schemat i dane. Zdjęcia są przechowywane
jako prywatne BLOB-y; brak przetwarzania zdjęć nadal skutkuje ich odrzuceniem.
Zapis zgłoszenia i jego powiązań ze zdjęciami odbywa się w jednej transakcji.
Wyszukiwanie i szczegóły miejsc udostępniają dane OSM z atrybucją i oceną wymagań.

Compose tworzy wolumen `backend_data`, początkowo wypełniony kopią
`data/krakow.sqlite3` z obrazu. Restart, ponowny build i `docker compose down`
zachowują dane; `docker compose down -v` usuwa wolumen. Późniejsze zmiany
hostowego pliku nie zastępują działającej bazy w wolumenie. Nie uruchamiaj
przebudowy OSM równolegle z backendem; importer zachowuje tabele backendu,
lecz wymiana całego pliku wymaga zatrzymania API.

Lokalnie backend domyślnie korzysta z `data/krakow.sqlite3`; ścieżkę można
zmienić zmienną `DATABASE_PATH`. Plik musi istnieć. Compose wczytuje opcjonalny
plik `.env` i dla lokalnego HTTP ustawia `SESSION_COOKIE_SECURE=false`.
Przy HTTPS ustaw `SESSION_COOKIE_SECURE=true`. Poza Compose bezpieczne cookie
jest domyślnie włączone. Rola właściciela/moderatora i przypisania obiektów
nadal wymagają zaufanego bootstrapu poza publicznym API.

Uruchomienie bez Compose:

```bash
docker build -t hackyeah-api .
docker run --rm -p 8000:8000 -e SESSION_COOKIE_SECURE=false \
  -v hackyeah_backend_data:/app/data hackyeah-api
```
Rozszerzenia z sekcji 10 kontraktu pozostają poza zakresem szkieletu prototypu.

## Interpretacja potrzeb

`POST /api/v1/needs/interpret` przyjmuje `{"description": "Bez schodów, odpoczynek co 300 m"}`.
Agent zwraca `constraints`, `summary`, `questions` i `requires_confirmation: true`.
Nie zapisuje profilu ani opisu; wynik należy zatwierdzić przed wyszukiwaniem.

Klucz `OPENAI_API_KEY` jest wczytywany z `.env` w katalogu projektu.
Zmienne środowiskowe mają pierwszeństwo. Opcjonalne `OPENAI_MODEL` wybiera model
(domyślnie `gpt-6-luna`, przez Responses API). W Dockerze przekaż konfigurację przez `--env-file .env`; Compose wczytuje `.env` automatycznie.
Brak klucza lub błąd dostawcy zwraca `503 DEPENDENCY_UNAVAILABLE`.

## Sprawdzenie

```bash
uv run --group data ruff check src scripts tests
uv run pyright
PYTHONPATH=src uv run --group data python -m unittest discover -s tests
```

## Dane tras bez bazy danych

```bash
uv sync --group data
PYTHONPATH=src uv run python -m hackyeah.route_data
# Odświeżenie wyciągu OSM z BBBike:
PYTHONPATH=src uv run python -m hackyeah.route_data --download
```

Wynik: `data/routes/network.geojsonl` i manifest pokrycia danych. Schody, progi,
krawężniki, podjazdy, nawierzchnia i oświetlenie mają modele faktów i ograniczeń
API. Brak danych pozostaje nieznany. Szczegóły: [dane tras](docs/dane-tras.md).
Eksport nie jest podłączony do prototypu planowania tras.

## Baza miejsc Krakowa z OSM

Importer danych OSM do pliku SQLite współdzielonego z backendem:

```bash
uv sync --group data
uv run --group data python -m scripts.download_osm
uv run --group data python -m scripts.build_places_db
uv run --group data python -m scripts.report_places
```

Wynik: `data/krakow.sqlite3` oraz raporty pokrycia. Kolejne pobrania używają
cache; odświeżenie: `python -m scripts.download_osm --refresh`.
Instrukcje, reguły importu i źródła uzupełniające: [baza OSM](docs/osm-data.md).
Rzeczywiste pokrycie pól: [raport](docs/osm-coverage.md).

## Prototyp planowania tras pieszych

Endpoint obsługuje również własne zapisane profile przez `profile_id`; wymaga
wtedy aktywnej sesji.

`src/hackyeah/routing.py` korzysta wyłącznie z modeli API oraz biblioteki
standardowej. Graf w pamięci zawiera syntetyczne połączenia Rynek–Wawel
(12 stopni) i Rynek–Planty–Wawel (bez stopni), w obu kierunkach.
Geometrie i fakty są demonstracyjne, a nie zweryfikowanymi trasami ulicznymi.

```bash
curl -X POST http://localhost:8000/api/v1/routes/plan \
  -H 'Content-Type: application/json' \
  -d '{"origin":{"place_id":"rynek"},"destination":{"place_id":"wawel"},"constraints":{"max_steps":0,"max_threshold_cm":null,"max_slope_percent":null,"min_entrance_width_cm":null,"max_distance_without_rest_m":null,"require_step_free_access":true,"require_accessible_toilet":null,"allowed_surfaces":null}}'
```

Wynik zawiera jedną najszybszą dopuszczalną trasę, odcinki, geometrię GeoJSON,
długość i szacowany czas przejścia. Bez ograniczeń wybierane jest
połączenie bezpośrednie; profil bez schodów wybiera odcinki przez Planty.
Punkty można podać przez identyfikatory `rynek`, `planty`, `wawel` lub ich
współrzędne z `demo_graph()` (tolerancja 1 m). Poza grafem wynik to pusta lista
tras z wyjaśnieniem; prototyp nie tworzy niesprawdzonych dojść.

Funkcja `plan_route(request, nodes, edges, profiles)` przyjmuje skierowane
krawędzie `(id_początku, id_końca, RouteSegment)` i opcjonalny słownik modeli
`Profile`. Endpoint pobiera zapisany profil z SQLite. Sama funkcja nie pobiera
profili, więc `profile_id` bez przekazanego słownika zwraca pusty wynik.
Nieznane identyfikatory również zwracają pusty wynik z ostrzeżeniem.

Algorytm przegląda proste ścieżki w kolejności szacowanego czasu. Ograniczenia aktywne
wymagają potwierdzonych, niewygasłych faktów. Limity wysokości i nachylenia,
szerokość, oświetlenie, nawierzchnia oraz gładkość sprawdzane są na odcinkach;
liczba stopni sumuje się na całej trasie. Dostępna toaleta, jeśli wymagana,
musi być potwierdzona na każdym odcinku (konserwatywna reguła prototypu).
Odległość bez odpoczynku jest liczona po geometrii i zerowana w punktach
odpoczynku pokrywających się z wierzchołkami geometrii. Punkty odpoczynku
przekazane w grafie muszą być sprawdzone przez jego autora.
Bariery obowiązujące w `departure_at` (domyślnie teraz) wykluczają odcinek;
prototyp nie przewiduje zmiany warunków podczas przejścia. Rampa ani winda
nie znosi automatycznie zakazu schodów. Graf jest mały; przegląd prostych
ścieżek nie jest przeznaczony do całej sieci miasta.

### Szacowanie czasu przejścia

Bazowy czas odcinka to `distance_m / 1.2`. Mnożymy go przez współczynniki
nawierzchni (asfalt/utwardzona 1, żwir 1,25, bruk 1,3, grunt/inne 1,4),
gładkości (od 1 dla excellent/good do 2,5 dla very_horrible) i nachylenia
`1 + 0.06 * slope_percent`. Dodajemy 1,5 sekundy na stopień.
Potwierdzone `impassable` wyklucza odcinek niezależnie od profilu.
To założenia prototypu, wymagające kalibracji, a nie pomiary tempa użytkownika.
Model nie rozróżnia podejścia i zejścia; ten sam procent nachylenia daje
jednakową karę w obu kierunkach. Nie uwzględnia pogody, tłumu ani świateł.

Przy braku potwierdzonych i aktualnych danych czasu stosujemy współczynniki
1,4 dla nawierzchni, 1,35 dla gładkości, nachylenie 5% i 20 stopni oraz
zwracamy ostrzeżenie. Przy kilku faktach wybieramy największy koszt.
Wymagane przez profil dane nadal podlegają wcześniejszym regułom wykluczania.
Jeśli profil ogranicza dystans bez odpoczynku, każdy punkt odpoczynku użyty
po drodze dolicza 60 sekund; osiągnięcie celu nie dolicza odpoczynku.
Długość pozostaje sumą metrów, a `estimated_duration_s` zawiera czas marszu
oraz odpoczynków. Dłuższa, łatwiejsza trasa może wygrać z krótszą.

## Jedna komenda aktualizacji SQLite

```bash
# Szybko: dopisz wyłącznie brakujące remonty z lokalnej kopii:
PYTHONPATH=src uv run --group data python -m scripts.update_database --missing-only
# Pełne odświeżenie źródeł i przebudowa bazy:
PYTHONPATH=src uv run --group data python -m scripts.update_database
```

Pełny proces uruchamia pobranie OSM, scraper ZDMK, importer miejsc, importer
remontów i raport pokrycia. Publikuje bazę po udanych etapach i kontrolach;
poprzednia kopia pozostaje w `data/krakow.previous.sqlite3`.
`--cached-osm` pozwala ponownie wykorzystać pliki OSM.

Pogoda jest pobierana w locie przy każdym zapytaniu zwracającym trasę,
bez zapisu do SQLite lub pliku. Odpowiedź ma `weather` i sygnały ryzyka
w odcinkach; awaria daje ostrzeżenie i `weather=null`.
Dokumentacja: [dane czasowe](docs/dane-czasowe.md).

## Frontend

Responsywny interfejs React + TypeScript znajduje się w [frontend](frontend/README.md).
Wyszukiwanie i szczegóły miejsc pobierają dane z API; trasy i część profilu
pozostają demonstracyjne.

```bash
cd frontend
npm ci
npm run dev
```

Wymagane Node.js >=22.12. Aplikacja: http://localhost:5173.


## Uzupełnianie informacji ze stron miejsc

OSM zawiera adresy stron, telefony, godziny, operatorów i ograniczenia dostępu.
Dodatkowe publiczne metadane z podanych tam stron można pobrać i zaimportować
bezpośrednio do SQLite:

```bash
uv run python -m scripts.scrape_place_websites --limit 100
uv run python -m scripts.import_place_web_data
```

Scraper czyta tytuł, opis i dane Schema.org JSON-LD. Ogranicza pobranie do
1 MB na stronę, stosuje timeout i przerwę między witrynami oraz odrzuca
prywatne adresy sieciowe. Dane trafiają do `place_web_data` z adresem źródła
i czasem pobrania. Opis strony jest informacją źródłową, nie potwierdzeniem
dostępności. Szczegóły są dostępne w `GET /api/v1/places/{id}`.
