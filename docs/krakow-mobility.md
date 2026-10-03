# Krakowska komunikacja i parkingi OZN

Planer (`/route`) obsługuje ikonki pieszego, komunikacji miejskiej i samochodu.
API `POST /api/v1/routes/plan` przyjmuje `mode: "walk" | "transit" | "car"`
(domyślnie `walk`), opcjonalne `departure_at` z określoną strefą czasową oraz
`accessible_parking: true` wyłącznie dla samochodu.

## Dane miejskie

- [ZTP Kraków](https://gtfs.ztp.krakow.pl/): wszystkie trzy rozkłady
  `GTFS_KRK_A.zip`, `GTFS_KRK_M.zip`, `GTFS_KRK_T.zip`; przystanki, kalendarze,
  wyjątki, kursy i przebiegi tras.
- Te same oficjalne źródła publikują `TripUpdates_{A,M,T}.pb` i
  `VehiclePositions_{A,M,T}.pb`. Prognozy opóźnień zmieniają czasy odjazdu,
  przyjazdu i możliwość przesiadki. Anulowane kursy oraz przystanki z zakazem
  wsiadania/wysiadania są wykluczane. Brak prognozy oznacza czas rozkładowy,
  a nie punktualny kurs. Dane starsze niż 180 sekund są pomijane.
- [Oficjalna mapa miejskich miejsc postojowych OZN](https://gmk-2.maps.arcgis.com/apps/instant/nearby/index.html?appid=57ff3986574a4c26a9d0466e0870b9b3)
  i jej publiczna warstwa `Miejsca_postojowe_OZN/FeatureServer/0` są źródłem
  adresów i współrzędnych parkingów. Pobieranie jest stronicowane, a `outSR=4326`
  zapewnia współrzędne zgodne z mapą. Stary link z
  [katalogu MSIP](https://msip.krakow.pl/dataset/3101) zwracał 404 podczas integracji.
  Dane nie określają zajętości miejsca ani indywidualnego uprawnienia do parkowania.

Zbiory pobiera backend; przeglądarka nie zależy od CORS źródeł. Atrybucja jest
zwracana przez API i wyświetlana przy mapie oraz zapisanej trasie.

## Pobranie i aktualizacja

```bash
uv sync
PYTHONPATH=src uv run python -m scripts.import_mobility_data
```

Pliki trafiają do `data/mobility/` (pomijane w Git). Można zmienić katalog przez
`MOBILITY_DATA_PATH`. Rozkład jest indeksowany w osobnej bazie SQLite;
import nie zmienia danych miejsc, kont ani grafu pieszego.
API pobiera brakujące zbiory przy pierwszym użyciu i odświeża je po 12 godzinach.
Nowa kopia zastępuje poprzednią dopiero po pełnym udanym imporcie.
Błąd odświeżenia zostawia dotychczasową kopię i komunikat; kopia starsza niż
24 godziny jest oznaczana. Niepowodzenia ponawiane są po pięciu minutach.
Pierwsze pobranie i indeksowanie dużego GTFS może zająć około minuty;
przed uruchomieniem demonstracji warto wykonać powyższy importer.

Telemetria ma pamięć podręczną przez 30 sekund; mapa odświeża pozycje co
30 sekund, tylko gdy wybrano komunikację miejską. Endpoint warstw:
`GET /api/v1/routes/mobility?kind=stops|parking|vehicles`.

## Wyznaczanie tras

Pieszo działa dotychczasowy graf miasta. Komunikacja używa najwcześniejszych
przyjazdów z rozkładu, uwzględniając przesiadki, wyjątki kalendarza, strefę
`Europe/Warsaw`, zmianę czasu i kursy po północy (`25:00:00` w GTFS).
Dojścia do sześciu najbliższych przystanków w promieniu 900 m są liczone
na istniejącym grafie pieszym z potrzebami użytkownika. Poszukiwanie obejmuje
najbliższe sześć godzin. Przejścia między pobliskimi peronami tego samego
zespołu (do 180 m) oraz jawne przesiadki GTFS są weryfikowane w grafie pieszym;
zbyt długie lub niedostępne dojście powoduje ponowne wyznaczenie połączenia.
Gdy wybrano unikanie schodów, jawnie niedostępne przystanki i kursy GTFS są
pomijane, a nieznana dostępność jest nadal sygnalizowana jako niepewna.

Samochód korzysta z [OSRM](https://github.com/Project-OSRM/osrm-backend/blob/master/docs/http.md)
i rzeczywistej geometrii drogowej. Domyślny serwer publiczny to
`https://router.project-osrm.org`; w konfiguracji można wskazać własny przez
`OSRM_URL`. Do produkcji należy użyć własnej instancji lub usługi z odpowiednią
gwarancją dostępności. Nie ma danych o bieżących korkach.

Bez zaznaczenia parkingu cel dojazdu pozostaje wybranym miejscem. Z zaznaczeniem
planer szuka najbliższego drogowo osiągalnego miejskiego parkingu OZN spośród
ośmiu najbliższych w promieniu 1 km. Trasa kończy się przy tym parkingu,
który jest oznaczony na mapie; komunikat podaje odległość od pierwotnego celu.
Brak parkingu lub danych źródła nie powoduje cichego dojazdu do innego celu.

Nie ma potwierdzenia dostępności konkretnego pojazdu na podstawie samej pozycji
GPS. Rozkładowy `wheelchair_accessible` jest używany ostrożnie. Brak geometrii
przejazdu GTFS daje odcinek przez przystanki wraz z jawnym komunikatem.

## Weryfikacja

```bash
PYTHONPATH=src uv run python -m unittest discover -s tests -p 'test_mobility.py'
cd frontend
npm run build
npx playwright test tests/e2e/mobility.spec.ts
```
