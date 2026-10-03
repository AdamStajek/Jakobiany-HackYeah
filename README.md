# Swoją Drogą — API

API FastAPI na Pythonie 3.13 z modelami Pydantic
pod prefiksem `/api/v1`. Endpointy i docelowe odpowiedzi są opisane w OpenAPI.
Modele są w `src/hackyeah/models.py`, endpointy w `src/hackyeah/api.py`.
Kontrakt API: [docs/kontrakt-frontend-backend.md](docs/kontrakt-frontend-backend.md).

## Uruchomienie lokalne

```bash
uv sync
SESSION_COOKIE_SECURE=false uv run uvicorn hackyeah.main:app --app-dir src --reload
```

## Docker

```bash
PYTHONPATH=src uv run python -m scripts.import_mobility_data
docker compose up --build -d --wait
```

Frontend: http://localhost:5173. Compose buduje obie aplikacje;
frontend korzysta z API. Ścieżka `/api/` na porcie frontendu
przekazuje żądania do backendu.
Dokumentacja Swagger: http://localhost:8000/docs.
ReDoc: http://localhost:8000/redoc. Schemat: http://localhost:8000/openapi.json.
`POST /api/v1/routes/plan` planuje trasę na sieci pieszej całego Krakowa z OSM, uwzględniając potrzeby z profilu. Przed startem przygotuj graf: [planowanie miejskie](docs/city-routing.md).
Planer obsługuje też komunikację miejską z aktualnym rozkładem ZTP, opóźnieniami i pozycjami pojazdów oraz dojazd samochodem, opcjonalnie do miejskiego miejsca postojowego OZN. Źródła, aktualizacja i konfiguracja: [komunikacja i parkingi Krakowa](docs/krakow-mobility.md).
Konta, profile, zdjęcia, zgłoszenia, misje i deklaracje właścicieli korzystają
z trwałych magazynów SQLite. Wyszukiwanie i szczegóły miejsc korzystają z lokalnej bazy OSM, a interpretacja potrzeb korzysta z OpenAI
przez PydanticAI. Zdjęcia są dekodowane i pozbawiane metadanych; dostęp do nich ma autor i moderator.
Niepoprawne dane zwracają `422 VALIDATION_ERROR`, a błędny JSON — `400 INVALID_REQUEST`.
Błędy mają format `{ "error": { "code", "message", "details", "request_id" } }`.
Ścieżka `/` zwraca `404`.
Kontener uruchamia aplikację jako użytkownik bez uprawnień roota.

Konta, sesje, profile, zdjęcia, zgłoszenia, przypisania właścicieli i historie
zmian są zapisywane w tej samej bazie SQLite co dane OSM. Backend dodaje tabelę
`backend_records`, zachowując istniejący schemat i dane. Zdjęcia są przechowywane
jako prywatne BLOB-y po usunięciu metadanych. Postępy misji i przyznane punkty również są trwałe.
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
wymagają zaufanego nadania poza publiczną rejestracją. Moderator może weryfikować zgłoszenia i misje na stronie `/review`.

Po zarejestrowaniu konta nadaj rolę moderatora na serwerze:

```bash
PYTHONPATH=src uv run python -m hackyeah.auth moderator@example.com
# Compose:
docker compose exec api python -m hackyeah.auth moderator@example.com
```

Użyj adresu istniejącego konta administratora. Polecenie unieważnia jego sesje; po ponownym logowaniu pojawi się panel weryfikacji. Dodanie `--revoke` odbiera rolę. Użytkownik nie może sam nadać sobie roli przez API. Moderator nie może zatwierdzać własnej misji. Punkty są zapisywane w tej samej transakcji co decyzja (również automatyczna); ponowienie identycznej decyzji nie zwiększa salda.

Uruchomienie bez Compose:

```bash
docker build -t hackyeah-api .
docker run --rm -p 8000:8000 -e SESSION_COOKIE_SECURE=false \
  -v hackyeah_backend_data:/app/data hackyeah-api
```
Wymiana punktów na zniżki, powiadomienia i panel samorządu pozostają poza zakresem obecnego interfejsu.

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

## Planowanie tras pieszych w całym mieście

Planer korzysta z pełnego wyciągu Małopolski i granicy administracyjnej Krakowa.
Punkty mogą pochodzić z katalogu miejsc lub być dowolnymi współrzędnymi
wybranymi na mapie. A* minimalizuje czas i niedogodności określone w profilu;
znane nieprzejezdne odcinki oraz schody przy wymogu bez stopni są wykluczane.
Pozostałe naruszenia i braki danych są widoczne w wyniku.

```bash
uv sync --group data
PYTHONPATH=src uv run --group data python -m scripts.build_route_graph
```

Gotowy graf: `data/routes/city.sqlite3`. `ROUTE_GRAPH_PATH` zmienia jego lokalizację.
Zapisany `profile_id` wymaga własnej sesji; anonimowo można przekazać
zatwierdzone `constraints`.

```bash
curl -X POST http://localhost:8000/api/v1/routes/plan \
  -H 'Content-Type: application/json' \
  -d '{"origin":{"lat":50.0617,"lon":19.9373},"destination":{"lat":50.072,"lon":20.037},"constraints":{"max_steps":0,"max_threshold_cm":null,"max_slope_percent":null,"min_entrance_width_cm":null,"max_distance_without_rest_m":null,"require_step_free_access":true,"require_accessible_toilet":null,"allowed_surfaces":null}}'
```

Szczegóły importu, wag, ocen niepewności, testów i ograniczeń:
[docs/city-routing.md](docs/city-routing.md).
`routing.py` zachowuje mały graf wyłącznie jako wcześniejszy przykład i fixture testów.

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
PYTHONPATH=src uv run python -m scripts.scrape_public_places
PYTHONPATH=src uv run python -m scripts.scrape_place_websites
PYTHONPATH=src uv run python -m scripts.scrape_place_photos
```

Scraper czyta tytuł, opis i dane Schema.org JSON-LD. Ogranicza pobranie do
1 MB na stronę, stosuje timeout i przerwę między witrynami oraz odrzuca
prywatne adresy sieciowe. Dane trafiają do `place_web_data` z adresem źródła
i czasem pobrania. Opis strony jest informacją źródłową, nie potwierdzeniem
dostępności. Szczegóły są dostępne w `GET /api/v1/places/{id}`.

Scrapery automatycznie aktualizują SQLite. Import publicznych danych obejmuje
MSIP, BIP Biblioteki Kraków i Wikidata; zdjęcia z Commons mają autora i licencję
oraz są widoczne w szczegółach miejsca. `--snapshot-only` wyłącza import rekordów.
Pełny proces `scripts.update_database` obejmuje także te źródła.
Wyniki, komendy, zasady dopasowania i możliwości Google Places:
[uzupełnianie miejsc i zdjęcia](docs/place-enrichment.md).

## Automatyczna weryfikacja zdjęć zgłoszeń

Zgłoszenia zawierające zdjęcia i `observations` są weryfikowane automatycznie
przy utworzeniu i edycji. Lokalny [SmolVLM-256M-Instruct](https://huggingface.co/HuggingFaceTB/SmolVLM-256M-Instruct)
otrzymuje zdjęcia i prompt z nazwą oraz typem metryki, bez wartości użytkownika
ani jego opisu. Inferencja używa wyłącznie CPU (PyTorch float32, eager attention),
bez klucza API. `uv sync` instaluje wariant PyTorch CPU; Docker używa tych samych zależności.

Model jest pobierany z Hugging Face przy pierwszym użyciu i następnie przechowywany
w cache. `REPORT_VLM_MODEL` pozwala wskazać kompatybilny model lub jego lokalny katalog;
`HF_HOME` zmienia katalog cache, a `HF_HUB_OFFLINE=1` umożliwia pracę z wcześniej
pobranymi wagami. `REPORT_VLM_THREADS` ustawia liczbę wątków CPU (domyślnie 4). Pierwsze zgłoszenie trwa dłużej z powodu pobrania i ładowania.
Zdjęcia pozostają lokalne. Model jest ładowany raz na proces, a inferencje są wykonywane kolejno.

Zgodność **wszystkich** wartości daje `status=accepted`, różnica lub nieodczytana
wartość (`null`, także błędny format odpowiedzi) daje `status=rejected`.
Porównanie liczb jest dokładne, bez tolerancji; `3` i `3.0` oznaczają tę samą wartość.
`ai_status=completed`, `ai_proposals` i `review_comment` zawierają wynik weryfikacji.
Propozycje mają `confidence_percent=0`, ponieważ model nie zwraca skalibrowanej pewności.
Metryki wymiarowe wymagają widocznej skali lub pomiaru na zdjęciu.

Brak zdjęcia lub metryk pozostawia `pending` / `not_requested`; awaria modelu
pozostawia `pending` / `failed` do weryfikacji moderatora. Decyzja automatyczna
aktualizuje również misję i punkty. Zmiana treści zwykłego zgłoszenia uruchamia
weryfikację ponownie. Mały VLM może błędnie odczytać zdjęcie; zgodność wyniku
z deklaracją nie gwarantuje poprawności fizycznego pomiaru.
