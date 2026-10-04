# Kontrakt frontend–backend: Swoją Drogą / By the Way

Wersja: **0.1 — kontrakt prototypu**. Podstawa: [opis projektu](opis.md) i [technologie](technologies.md). Repozytorium zawiera modele danych i szkielet endpointów FastAPI. Poprawne żądania zwracają na razie `501 NOT_IMPLEMENTED` w formacie błędu z sekcji 9. Opisane poniżej odpowiedzi sukcesu, logowanie i logika biznesowa są docelowym zachowaniem do implementacji; aktywna jest walidacja struktury żądań.

## 1. Zakres

**Prototyp:** Kraków, anonimowe wyszukiwanie miejsc i tras, opis potrzeb zamieniany na edytowalny profil, konta i zapisane profile, szczegóły dostępności, zgłoszenia ze zdjęciami, deklaracje właścicieli i weryfikacja moderatora. Źródła: OSM, właściciele i użytkownicy; AI przygotowuje propozycje wymagające weryfikacji.

**Dane czasowe tras:** upał, ryzyko oblodzenia, śnieg i remonty mają modele i skrypty; remonty są importowane do SQLite, pogoda jest pobierana w locie przy planowaniu tras; szczegóły w sekcji 7.1.

**Rozszerzenia:** misje i naliczanie punktów są zaimplementowane zgodnie z sekcją 12. Wymiana punktów na zniżki, powiadomienia dla osób w okolicy i panel samorządu pozostają kierunkiem rozwoju z sekcji 10.

## 2. Zasady komunikacji

| Element | Ustalenie |
| --- | --- |
| Transport | HTTPS, REST, prefiks `/api/v1` |
| Format | JSON UTF-8, `Content-Type: application/json`; wyjątek: upload zdjęć |
| Nazwy pól | `snake_case`; wartości enum po angielsku; teksty dla użytkownika po polsku |
| Identyfikatory | Nieprzezroczyste stringi; frontend nie interpretuje ich struktury |
| Daty | ISO 8601 w UTC, np. `2026-10-03T12:00:00Z` |
| Współrzędne | WGS84; obiekt `{ "lat": 50.0614, "lon": 19.9366 }`; GeoJSON: `[lon, lat]` |
| Jednostki | Odległość w metrach, szerokość i wysokość w cm, nachylenie w %, czas w sekundach |
| Brak wartości | `null` oznacza brak wiedzy; `false` i `0` są konkretnymi wartościami |
| Listy | `{ "items": [], "next_cursor": null }`; `limit` domyślnie 20, maksymalnie 100; nieprzezroczysty `cursor` |
| Wersjonowanie | Nowe opcjonalne pola w v1; usunięcie pola, zmiana typu lub znaczenia wymagają nowej wersji API |

Frontend ignoruje nieznane pola i pokazuje neutralną etykietę dla nieznanych wartości enum. Backend odrzuca nieznane pola w żądaniach zapisu i zwraca błędy walidacji. Pola w odpowiedziach opisane poniżej są wymagane, chyba że oznaczono je jako opcjonalne; nullable nie oznacza opcjonalne.

Listy przyjmują `limit` i `cursor`, oprócz list z jawnie określonym formatem odpowiedzi. Kontynuacja zachowuje pozostałe filtry i kolejność. Lista miejsc jest sortowana według dopasowania, obecności zdjęcia, kompletności danych, odległości i ID; zgłoszenia według daty malejąco i ID.

## 3. Uwierzytelnianie i uprawnienia

Propozycja: frontend i API działają pod jednym originem. Backend zarządza sesją w cookie `HttpOnly`, `Secure`, `SameSite=Lax`. Frontend wysyła cookie w żądaniach, nie zapisuje tokenów sesji w `localStorage`. Sesja zwraca `csrf_token`; frontend dodaje go jako `X-CSRF-Token` do żądań zmieniających stan. Backend dodatkowo sprawdza `Origin`, w tym przy rejestracji i logowaniu. Odpowiedzi zawierające dane prywatne mają `Cache-Control: no-store`.

| Rola | Uprawnienia |
| --- | --- |
| Gość | Interpretacja opisu, wyszukiwanie, szczegóły miejsc i tras |
| `user` | Jak gość oraz własne profile, zdjęcia i zgłoszenia |
| `owner` | Jak użytkownik oraz deklaracje obiektów z potwierdzonym przypisaniem właściciela |
| `moderator` | Weryfikacja zgłoszeń i propozycji AI |

`User = { id: string, display_name: string, roles: string[] }`. Rejestracja nadaje wyłącznie rolę `user`. Nadawanie ról i potwierdzanie właściciela odbywa się poza publicznym API prototypu. Backend sprawdza własność każdego zasobu; ukrycie przycisku we frontendzie nie zastępuje autoryzacji. Cudzy prywatny zasób zwraca `404`.

| Metoda i ścieżka | Żądanie | Odpowiedź |
| --- | --- | --- |
| `POST /auth/register` | `{ email, password, display_name }` | `201`, `User`; nie zakłada sesji |
| `POST /auth/login` | `{ email, password }` | `200`, `{ user: User, csrf_token: string }` i cookie |
| `GET /auth/session` | — | `200`, `{ user: User, csrf_token: string }`; brak sesji: `401` |
| `POST /auth/logout` | — | `204`, unieważnienie sesji i cookie |

Email musi mieć poprawny format; hasło: 12–128 znaków; nazwa: 1–100 znaków. Logowanie zwraca jednakowy błąd `INVALID_CREDENTIALS` dla nieznanego konta i błędnego hasła. Rejestracja i logowanie podlegają limitom żądań.

## 4. Modele wspólne

### 4.1. Profil potrzeb

`Constraints` zawiera wszystkie poniższe pola podstawowe. Nowe opcjonalne pola dla tras: `max_kerb_height_cm` (liczba ≥ 0 lub `null`), `allowed_smoothness` (niepusta lista enum stanu nawierzchni lub `null`) i `require_lighting` (boolean lub `null`); domyślnie `null`. `require_lighting=true` wymaga oświetlenia, `false/null` nie nakłada tego wymagania. Enum stanu: `excellent | good | intermediate | bad | very_bad | horrible | very_horrible | impassable`. `null` oznacza, że użytkownik nie określił wymagania; brak profilu nie oznacza potwierdzonej dostępności dla wszystkich.

```json
{
  "max_steps": 2,
  "max_threshold_cm": 2,
  "max_slope_percent": 6,
  "min_entrance_width_cm": 90,
  "max_distance_without_rest_m": 300,
  "require_step_free_access": false,
  "require_accessible_toilet": null,
  "allowed_surfaces": ["paved", "asphalt"]
}
```

`max_steps`: nieujemna liczba całkowita. Pozostałe pola liczbowe: nieujemne liczby, z wyjątkiem szerokości i odległości odpoczynku, które muszą być dodatnie. Pola `require_*`: boolean lub `null`. `allowed_surfaces`: niepusta lista wartości `paved | asphalt | gravel | cobblestone | ground | other` albo `null`. `require_step_free_access=true` z `max_steps>0` daje `422`; brak wartości `max_steps` przy dostępie bez stopni backend interpretuje jako zero.

`Profile = { id, name, description, constraints: Constraints, created_at, updated_at }`. Nazwa: 1–100 znaków, opis: do 4000 znaków. Opis nie musi zawierać diagnozy ani informacji o niepełnosprawności.

### 4.2. Fakt o dostępności

```json
{
  "id": "fact_123",
  "attribute": "entrance_width_cm",
  "value": 92,
  "unit": "cm",
  "status": "confirmed",
  "confidence_score": 15,
  "confidence_level": "certain",
  "confidence_percent": 95,
  "confidence_calculated_at": "2026-10-03T10:00:00Z",
  "observed_at": "2026-10-02T10:00:00Z",
  "updated_at": "2026-10-03T10:00:00Z",
  "valid_until": null,
  "sources": [
    {
      "type": "owner",
      "label": "Deklaracja właściciela",
      "url": null,
      "license": null,
      "retrieved_at": "2026-10-03T10:00:00Z"
    }
  ],
  "unconfirmed_reason": null
}
```

| `attribute` | Typ `value` / `unit` |
| --- | --- |
| `steps_count` | integer ≥ 0 / `count` |
| `threshold_height_cm`, `kerb_height_cm`, `entrance_width_cm` | number ≥ 0 / `cm` |
| `slope_percent` | number ≥ 0 / `percent` |
| `steps_present`, `raised_kerb`, `lighting_available`, `ramp_available`, `elevator_available`, `accessible_toilet`, `rest_area_available` | boolean / `null` |
| `surface` | enum nawierzchni jak w profilu / `null` |
| `smoothness` | enum stanu nawierzchni jak w profilu / `null` |
| `distance_without_rest_m` | number ≥ 0 / `m` |
| `heat_risk`, `icing_risk`, `snow_risk`, `construction_present` | boolean lub `null` / `null` |

Każdy typ `value` dopuszcza też `null`. `status`: `confirmed | unconfirmed`. `unconfirmed_reason`: `missing | conflicting | stale | pending_verification` lub `null`; dla `unconfirmed` powód jest wymagany. `confidence_score` to nieujemny wynik punktowy, `confidence_level`: `certain | probable | uncertain`, a `confidence_calculated_at` wskazuje ostatnie przeliczenie. `confidence_percent` pozostaje opcjonalną wartością 0–100 przeznaczoną do prezentacji i nie służy do wyznaczania poziomu. `observed_at` i `valid_until` mogą być `null`; `updated_at` jest wymagane. `sources` może być puste tylko przy braku danych.

Źródło: `owner | user | ai | osm | weather | other`. OSM wymaga `license: "ODbL"` i odnośnika do źródła. Dane osobowe zgłaszających nie trafiają do publicznych źródeł. Backend wylicza punkty, poziom i starzenie według dokumentu [Wiarygodność informacji](wiarygodnosc-danych.md); frontend ich nie oblicza. Sama propozycja AI ma status `unconfirmed` i nie dodaje punktów przed przyjęciem zgłoszenia.

### 4.3. Dopasowanie i bariery

`Assessment = { status, summary, reasons }`, gdzie `status` to `meets_requirements | does_not_meet_requirements | uncertain`, `summary` jest tekstem, a `reasons` listą `{ code: string, message: string, fact_ids: string[] }`.

- `meets_requirements`: każde określone wymaganie ma aktualne, potwierdzone dane i jest spełnione.
- `does_not_meet_requirements`: co najmniej jedno wymaganie jest naruszone przez potwierdzony fakt; powody zawierają też znane braki danych.
- `uncertain`: brak potwierdzonego naruszenia, ale brakuje danych potrzebnych do oceny, są sprzeczne lub nieaktualne. Także wynik bez określonych wymagań ma ten status.

Wysoki procent wiarygodności nie zmienia niepotwierdzonego faktu w potwierdzony. Dostępny podjazd lub winda może zapewniać alternatywne wejście; backend ocenia konkretną ścieżkę dostępu, a nie tylko liczbę schodów w obiekcie. Ocena oznacza dopasowanie do podanych wymagań, nie gwarancję bezpiecznego przejścia.

`Barrier = { id, kind, description, location, fact_ids, starts_at, ends_at, status }`. Opcjonalne `category` (domyślnie `null`): `heat | icing | snow | construction`. `kind`: `permanent | temporary`; daty mogą być `null`; `status`: `confirmed | unconfirmed`. Lokalizacja to obiekt współrzędnych. Backend uwzględnia okres obowiązywania; nieznany koniec utrudnienia nie oznacza, że ono zniknęło.

## 5. Interpretacja potrzeb i profile

| Metoda i ścieżka | Dostęp | Żądanie / wynik |
| --- | --- | --- |
| `POST /needs/interpret` | Publiczny | `{ description: string }` → `200`, odpowiedź poniżej |
| `GET /profiles` | Konto | Lista własnych `Profile` |
| `POST /profiles` | Konto | `{ name, description, constraints }` → `201`, `Profile` |
| `GET /profiles/{id}` | Właściciel profilu | `200`, `Profile` |
| `PATCH /profiles/{id}` | Właściciel profilu | Dowolny niepusty podzbiór `{ name, description, constraints }` → `200`, `Profile` |
| `DELETE /profiles/{id}` | Właściciel profilu | `204` |

Interpretacja przyjmuje 1–4000 znaków i zwraca:

```json
{
  "constraints": {
    "max_steps": 2,
    "max_threshold_cm": null,
    "max_slope_percent": null,
    "min_entrance_width_cm": null,
    "max_distance_without_rest_m": 300,
    "require_step_free_access": null,
    "require_accessible_toilet": null,
    "allowed_surfaces": null
  },
  "summary": "Do dwóch stopni; odpoczynek co najwyżej co 300 metrów.",
  "questions": [],
  "requires_confirmation": true
}
```

Frontend umożliwia poprawienie i zatwierdzenie pól przed użyciem. Interpretacja nie zapisuje profilu. `questions` to lista stringów dotyczących niejasności. Backend nie dopowiada niepodanych ograniczeń. W `PATCH` przekazane `constraints` zastępuje cały obiekt. Opis anonimowego użytkownika nie jest utrwalany jako profil ani zapisywany w logach żądań.

## 6. Miejsca i wyszukiwanie

`POST /places/search` jest publiczne. Żądanie:

```json
{
  "query": "Apteka blisko Rynku",
  "near": { "lat": 50.0614, "lon": 19.9366 },
  "radius_m": 2000,
  "constraints": {
    "max_steps": 0,
    "max_threshold_cm": null,
    "max_slope_percent": null,
    "min_entrance_width_cm": null,
    "max_distance_without_rest_m": null,
    "require_step_free_access": true,
    "require_accessible_toilet": null,
    "allowed_surfaces": null
  },
  "include_uncertain": true,
  "limit": 20,
  "cursor": null
}
```

`query`: 1–1000 znaków. `near` opcjonalne; bez niego wyszukiwanie obejmuje Kraków. `radius_m`: opcjonalne, domyślnie 2000, zakres 100–20000, wymaga `near`. `constraints` i `profile_id` są opcjonalne i wzajemnie wykluczające; użycie `profile_id` wymaga sesji i własnego profilu. `include_uncertain` domyślnie `true`; `false` pozostawia wyłącznie `meets_requirements`. Wyniki niespełniające wymagań nie trafiają do listy rekomendacji. Surowy opis potrzeb należy najpierw przetworzyć przez `/needs/interpret`.

Odpowiedź `200`: `{ items: PlaceSummary[], next_cursor, warnings: string[], attribution: Source[] }`. `Source` ma pola jak element `sources` z sekcji 4.2.

`PlaceSummary = { id, name, category, address, location, distance_m, assessment, facts, website, phone, opening_hours, operator, access }`. `address`, `distance_m` i dane kontaktowe mogą być `null`; odległość jest odległością w linii prostej od `near`, a nie długością trasy. `facts` zawiera dostępne fakty OSM, nadal oznaczone jako niepotwierdzone. Pusta lista wyników jest prawidłowa. `warnings` informuje o źródle i aktualności danych.

`GET /places/{id}` zwraca publicznie `200`, `PlaceDetails = PlaceSummary + { barriers, updated_at, attribution, website_title, website_description, website_telephone, website_opening_hours, accessibility_summary, website_source }`. Pola strony internetowej pochodzą ze skryptu `scripts.scrape_place_websites` i importu `scripts.import_place_web_data`; pozostają oddzielone od faktów dostępności. Opcjonalny parametr `profile_id` daje ocenę dla własnego profilu; bez niego ocena ma status `uncertain` i wyjaśnienie braku wymagań. Wszystkie kategorie faktów z sekcji 4.2 występują w szczegółach; brak wiedzy jest reprezentowany faktem z `value=null`, a nie pominięciem kategorii.

Specyfikacja dostępności każdego miejsca obejmuje następujące niedogodności i udogodnienia:

| Kategoria | Atrybut w `facts` | Znaczenie wartości | Jednostka |
| --- | --- | --- | --- |
| Schody | `steps_count` | Liczba stopni; `0` oznacza brak stopni | `count` |
| Progi | `threshold_height_cm` | Wysokość progu; `0` oznacza brak progu | `cm` |
| Windy | `elevator_available` | `true` — winda dostępna, `false` — brak dostępnej windy | `null` |
| Szerokość wejść | `entrance_width_cm` | Szerokość wejścia w centymetrach | `cm` |
| Łazienki dla osób z niepełnosprawnościami | `accessible_toilet` | `true` — dostępna łazienka dostosowana, `false` — brak takiej łazienki | `null` |

Każda z tych pięciu kategorii musi wystąpić w `PlaceDetails.facts`, także gdy wartość jest nieznana. Wtedy fakt ma `value: null`, `status: "unconfirmed"` i `unconfirmed_reason: "missing"`. Każdy fakt zachowuje źródła, datę i informacje o weryfikacji zgodnie z sekcją 4.2. Dostępna winda lub łazienka jest udogodnieniem; ich brak może stanowić niedogodność zależnie od profilu potrzeb.

Frontend nie pokazuje dokładnych wartości liczbowych stopni ani wymiarów. Liczbę stopni prezentuje jako `Less than 5`, `5–10` lub `10 or more`. Próg i krawężnik do 2 cm oraz wejście o szerokości co najmniej 90 cm otrzymują etykietę `Accessible for wheelchairs`; pozostałe wartości otrzymują `Inaccessible for wheelchairs`. Surowe wartości pozostają w API na potrzeby oceny profilu i tras. `slope_percent` jest nadal prezentowane liczbowo.

Frontend prezentuje osobno status dopasowania i wiarygodność faktów. Każdy fakt ma widoczne źródło, datę i procent albo informację o braku oceny. Mapa i lista korzystają z tych samych wyników; lista nie wymaga włączonej geolokalizacji.

## 7. Wyznaczanie tras

Aktualna implementacja korzysta z grafu pieszej sieci całego Krakowa z pełnego wyciągu OSM.
Import, zasady minimalizacji niedogodności oraz niepewność danych opisuje [planowanie miejskie](city-routing.md).
`GET /routes/points?query=...` zwraca do 20 punktów katalogu pasujących nazwą lub adresem.
Wymagane co najmniej dwa znaki. Odpowiedź to `Page<PlaceSummary>`.

Dane wejściowe sieci tras są eksportowane bez bazy danych przez `hackyeah.route_data`;
format `RouteDataFeature`, źródła, uruchomienie i ograniczenia opisuje
[dokumentacja danych tras](dane-tras.md). Samo wyznaczanie tras pozostaje do implementacji.

Każdy `RouteSegment.facts` musi zawierać kategorie:

| Kategoria | Atrybuty |
| --- | --- |
| Schody | `steps_present`, `steps_count` |
| Progi | `threshold_height_cm` |
| Wysokie krawężniki | `raised_kerb`, `kerb_height_cm` |
| Podjazdy | `ramp_available` |
| Słaba nawierzchnia | `surface`, `smoothness` |
| Brak oświetlenia | `lighting_available` |

Wartość nieznana jest jawnie reprezentowana przez `value=null`, `status=unconfirmed`,
`unconfirmed_reason=missing`. `raised_kerb=true` nie określa wysokości w cm;
`steps_present=true` nie określa liczby stopni. Podjazd jest udogodnieniem,
a jego brak może stanowić barierę zależnie od profilu. Stan nawierzchni i materiał
są odrębnymi faktami. Brak oświetlenia jest cechą infrastruktury, nie informacją
o czasowej awarii. Dane OSM są niepotwierdzone i nie gwarantują dostępności.

`POST /routes/plan` jest publiczne. Wymagane: `origin`, `destination`. Każdy punkt to dokładnie `{ lat, lon }` albo `{ place_id: string }`. Opcjonalne: `constraints` lub `profile_id` na zasadach wyszukiwania miejsc, `departure_at` (domyślnie czas żądania).

Odpowiedź `200`:

```json
{
  "routes": [
    {
      "id": "route_123",
      "distance_m": 850,
      "estimated_duration_s": 1200,
      "assessment": {
        "status": "uncertain",
        "summary": "Brakuje informacji o szerokości przejścia na jednym odcinku.",
        "reasons": [
          { "code": "MISSING_DATA", "message": "Nieznana szerokość przejścia.", "fact_ids": ["fact_456"] }
        ]
      },
      "geometry": {
        "type": "LineString",
        "coordinates": [[19.9366, 50.0614], [19.94, 50.064]]
      },
      "segments": [
        {
          "id": "segment_1",
          "distance_m": 850,
          "instruction": "Idź wzdłuż ulicy do celu.",
          "geometry": {
            "type": "LineString",
            "coordinates": [[19.9366, 50.0614], [19.94, 50.064]]
          },
          "assessment": {
            "status": "uncertain",
            "summary": "Nieznana szerokość przejścia.",
            "reasons": [{ "code": "MISSING_DATA", "message": "Nieznana szerokość przejścia.", "fact_ids": ["fact_456"] }]
          },
          "facts": [
            {"id": "fact_steps_present", "attribute": "steps_present", "value": null, "unit": null, "status": "unconfirmed", "confidence_percent": null, "observed_at": null, "updated_at": "2026-10-03T12:00:00Z", "valid_until": null, "sources": [], "unconfirmed_reason": "missing"},
            {"id": "fact_steps_count", "attribute": "steps_count", "value": null, "unit": "count", "status": "unconfirmed", "confidence_percent": null, "observed_at": null, "updated_at": "2026-10-03T12:00:00Z", "valid_until": null, "sources": [], "unconfirmed_reason": "missing"},
            {"id": "fact_threshold_height_cm", "attribute": "threshold_height_cm", "value": null, "unit": "cm", "status": "unconfirmed", "confidence_percent": null, "observed_at": null, "updated_at": "2026-10-03T12:00:00Z", "valid_until": null, "sources": [], "unconfirmed_reason": "missing"},
            {"id": "fact_raised_kerb", "attribute": "raised_kerb", "value": null, "unit": null, "status": "unconfirmed", "confidence_percent": null, "observed_at": null, "updated_at": "2026-10-03T12:00:00Z", "valid_until": null, "sources": [], "unconfirmed_reason": "missing"},
            {"id": "fact_kerb_height_cm", "attribute": "kerb_height_cm", "value": null, "unit": "cm", "status": "unconfirmed", "confidence_percent": null, "observed_at": null, "updated_at": "2026-10-03T12:00:00Z", "valid_until": null, "sources": [], "unconfirmed_reason": "missing"},
            {"id": "fact_ramp_available", "attribute": "ramp_available", "value": null, "unit": null, "status": "unconfirmed", "confidence_percent": null, "observed_at": null, "updated_at": "2026-10-03T12:00:00Z", "valid_until": null, "sources": [], "unconfirmed_reason": "missing"},
            {"id": "fact_surface", "attribute": "surface", "value": null, "unit": null, "status": "unconfirmed", "confidence_percent": null, "observed_at": null, "updated_at": "2026-10-03T12:00:00Z", "valid_until": null, "sources": [], "unconfirmed_reason": "missing"},
            {"id": "fact_smoothness", "attribute": "smoothness", "value": null, "unit": null, "status": "unconfirmed", "confidence_percent": null, "observed_at": null, "updated_at": "2026-10-03T12:00:00Z", "valid_until": null, "sources": [], "unconfirmed_reason": "missing"},
            {"id": "fact_lighting_available", "attribute": "lighting_available", "value": null, "unit": null, "status": "unconfirmed", "confidence_percent": null, "observed_at": null, "updated_at": "2026-10-03T12:00:00Z", "valid_until": null, "sources": [], "unconfirmed_reason": "missing"}
          ],
          "barriers": [],
          "rest_points": []
        }
      ],
      "facts": [
        {
          "id": "fact_456", "attribute": "entrance_width_cm", "value": null,
          "unit": "cm", "status": "unconfirmed", "confidence_percent": null,
          "observed_at": null, "updated_at": "2026-10-03T12:00:00Z",
          "valid_until": null, "sources": [], "unconfirmed_reason": "missing"
        }
      ],
      "computed_at": "2026-10-03T12:00:00Z"
    }
  ],
  "warnings": [],
  "attribution": []
}
```

`estimated_duration_s` może być `null`; podana wartość jest szacunkiem. `rest_points` to lista `{ id, location, description, fact_ids }`; frontend pokazuje ich wiarygodność przez wskazane fakty. Fakty odcinków i trasy wspólnie tworzą zbiór wskazywany przez `fact_ids`.

Backend obecnie zwraca jeden wariant minimalizujący koszt czasu i niedogodności z profilu. Znane nieprzejezdne odcinki oraz schody przy wymogu bez stopni są wykluczane. Wariant kompromisowy może zawierać inne niedogodności wg OSM; ma jawne ostrzeżenia oraz ocenę `does_not_meet_requirements`, a trasa bez zmapowanych naruszeń pozostaje `uncertain`. Brak wariantu: `200`, `{ routes: [], warnings: ["Nie znaleziono trasy dla podanych wymagań."], attribution: [] }`. Brak danych zwiększa niepewność; nie usuwa bariery. Błędny punkt lub punkt poza obsługiwanym obszarem daje `422`. Ocena trasy uwzględnia wszystkie odcinki, wejście do celu i odległości pomiędzy miejscami odpoczynku również przez granice odcinków.

Frontend wyświetla `segments` w kolejności jako tekstowe kroki, wraz z barierami, odpoczynkiem i powodami oceny. Backend dostarcza zarówno geometrię, jak i tekst; frontend nie musi odczytywać kroków z mapy.

### 7.1. Czasowe utrudnienia: pogoda i remonty

`RouteSegment` ma nowe opcjonalne pole `temporary_difficulties: TemporaryDifficulty[]`,
domyślnie `[]`. Opcjonalne `RoutePlanResponse.weather` ma typ `TemporaryDataSnapshot | null`, domyślnie `null`. Jest pobierane w locie dla początku niepustej trasy bez zapisu do bazy lub pliku. Kategorie: `heat` (upał), `icing` (ryzyko oblodzenia), `snow`
(śnieg), `construction` (remonty i prace drogowe). Pusta lista nie jest
potwierdzeniem pokrycia źródeł czasowych. Geometria pochodzi z miejskiego grafu OSM; do trasy dołączana jest rzeczywista prognoza.
Remonty w SQLite nie są jeszcze powiązane z grafem.

`TemporaryDifficulty = { id, kind: "temporary", category, description, geometry,
location_text, starts_at, ends_at, updated_at, valid_until, status,
unconfirmed_reason, confidence_percent, sources, pedestrian_access, weather,
source_fields }`. `geometry` to GeoJSON `Point | LineString | null`; lokalizacja
tekstowa może być `null`. Daty UTC `starts_at`/`ends_at` mogą być `null`;
`updated_at` i `valid_until` są wymagane. Koniec znanego okresu jest późniejszy
niż początek. Zakres `[starts_at, ends_at)` obejmuje momenty obowiązywania,
a `valid_until` określa osobno świeżość danych. Nieznany koniec nie oznacza
zakończenia prac. `sources` jest niepuste. `confidence_percent` może być `null`.

`status`: `confirmed | unconfirmed`; `unconfirmed_reason`:
`forecast | pending_verification | stale | null`. Niepotwierdzony rekord wymaga
powodu, potwierdzony ma powód `null`. Prognozy są zawsze niepotwierdzone.
`pedestrian_access`: `unknown | restricted | closed | open`, domyślnie `unknown`;
sam remont jezdni nie potwierdza zamknięcia dla pieszych. `source_fields`
(domyślnie `{}`) zachowuje oryginalne pola źródła, a `weather` (domyślnie `null`)
jest obiektem `WeatherHour`.

`WeatherHour = { location, starts_at, ends_at, temperature_c,
apparent_temperature_c, precipitation_starts_at, precipitation_ends_at,
precipitation_mm, snowfall_cm, snow_depth_cm, weather_code, heat_risk,
icing_risk, snow_risk }`. Wartości pomiarowe i ryzyka dopuszczają `null`.
Temperatury są skończonymi liczbami i mogą być ujemne; opady i pokrywa są
nieujemne, kod WMO jest nieujemną liczbą całkowitą. Opad dotyczy wskazanej
poprzedniej godziny, a wartości chwilowe początku godziny prognozy.
Boolean `false` oznacza brak sygnału w modelu, nie gwarancję stanu chodnika.

Prognoza i plik remontów mają format `TemporaryDataSnapshot = { generated_at, valid_until,
source: "weather" | "construction", heat_threshold_c: number | null, items: TemporaryDifficulty[],
weather_hours: WeatherHour[], attribution: Source[], warnings: string[] }`.
Pogoda pochodzi z Open-Meteo (CC-BY-4.0), remonty z publicznej mapy ZDMK
(licencja zbioru nieokreślona, `license=null`). Świeżość: pogoda 3 godziny,
remonty 24 godziny. Awaria remontów zachowuje ostatnią kopię bez przedłużania ważności;
konsument wygasłych danych oznacza `stale`. Awaria pogody daje `weather=null`
i ostrzeżenie; backend nie zapisuje prognozy w bazie ani na dysku.

Reguły ryzyk, aktualizacja, źródła, licencje oraz ograniczenia geometrii:
[dokumentacja danych czasowych](dane-czasowe.md). Remonty zapisuje importer SQLite i wspólny orkiestrator. Pogoda jest pobierana
ponownie przy każdym zapytaniu zwracającym trasę; sygnały z okresu przejścia
są dołączane do odcinków bez automatycznego wykluczania tras. Nie dodajemy
endpointu synchronizacji. Fakty `heat_risk`, `icing_risk`, `snow_risk`,
`construction_present` mogą trafić do `Fact`, ale nie należą do obowiązkowych
kategorii stałych każdego odcinka.

## 8. Zgłoszenia, zdjęcia i deklaracje

### 8.1. Zdjęcia

`POST /photos`: konto, `multipart/form-data`, jedno pole `file`; JPEG, PNG lub WebP, maksymalnie 10 MiB i 20 mln pikseli po dekodowaniu. Backend sprawdza rzeczywisty format, usuwa metadane EXIF i przygotowuje kopię z ochroną danych osób przed jakimkolwiek publicznym udostępnieniem. Oryginały pozostają prywatne.

Odpowiedź `201`: `{ id, status: "ready", created_at }`. Implementacja dekoduje plik, usuwa metadane i lokalnym modelem Grounding DINO wykrywa ludzi, twarze, tablice, dokumenty, ekrany oraz tekst. Zamazuje tylko wykryte prostokąty; pozostałe piksele zachowuje w bezstratnej kopii PNG. Błąd detekcji zwraca `503 PHOTO_ANALYSIS_UNAVAILABLE` bez zapisu zdjęcia. Detektor może przeoczyć dane; tekst jest traktowany ostrożnościowo jako potencjalne dane osobowe. `GET /photos/{id}` dla autora lub moderatora: `{ id, status, preview_url, error_code }`, gdzie `status` to `processing | ready | rejected`, a dwa ostatnie pola są nullable. `preview_url` prowadzi do `/photos/{id}/content`, prywatnego obrazu PNG wymagającego sesji autora lub moderatora. Nie ma publicznej galerii. `DELETE /photos/{id}` usuwa własny niepowiązany plik (`204`); powiązany daje `409 PHOTO_IN_USE`.

### 8.2. Zgłoszenia użytkowników

| Metoda i ścieżka | Cel |
| --- | --- |
| `POST /reports` | Utworzenie zgłoszenia, `201`, `Report` |
| `GET /reports?mine=true` | Stronicowana lista własnych zgłoszeń |
| `GET /reports/{id}` | Szczegóły dla autora lub moderatora |
| `PATCH /reports/{id}` | Poprawienie własnego zgłoszenia, `200`, `Report` |
| `POST /reports/{id}/review` | Decyzja moderatora, `200`, `Report` |

Utworzenie wymaga `target`, `kind`; pozostałe pola są opcjonalne:

```json
{
  "target": { "type": "place", "id": "place_123" },
  "kind": "correction",
  "fact_id": "fact_123",
  "description": "Wejście jest węższe niż podano.",
  "observations": [{ "attribute": "entrance_width_cm", "value": 78 }],
  "photo_ids": ["photo_123"]
}
```

`target.type`: `place | segment`; ID odcinka jest stabilne i wskazuje odcinek grafu routingu. `kind`: `correction | confirmation | missing_data`. `fact_id` jest wymagane dla korekty lub potwierdzenia i musi należeć do celu. Wymagany jest co najmniej jeden element: niepusty opis, obserwacja lub zdjęcie. Opis do 4000 znaków, maksymalnie pięć własnych zdjęć w stanie `ready`. Obserwacje używają typów z sekcji 4.2; źródło, status i wiarygodność ustala backend.

`Report = { id, author_id, target, kind, fact_id, description, observations, photo_ids, status, ai_status, ai_proposals, review_comment, created_at, updated_at, observed_at }`. Opcjonalne `observed_at` przy utworzeniu przyjmuje datę z czasem i strefą lub `null`; data nie może wskazywać przyszłości. `fact_id`, `description`, `review_comment` mogą być `null`; pozostałe kolekcje są listami. `status`: `pending | accepted | rejected`; `ai_status`: `not_requested | pending | completed | failed`; `ai_proposals`: lista `{ attribute, value, confidence_percent, explanation }`.

Analiza zdjęć działa asynchronicznie; odczyt zgłoszenia udostępnia wynik. Awaria AI nie usuwa zgłoszenia i nie blokuje ręcznej weryfikacji. Wynik AI nie nadpisuje faktów samodzielnie. `PATCH` dopuszcza `description`, `observations`, `photo_ids`; kolekcje zastępuje w całości. Korekta przyjętego zgłoszenia przywraca `pending`, zachowuje historię i unieważnia wcześniejszą analizę; backend ponownie wylicza fakty z pozostałych źródeł.

Decyzja moderatora: `{ decision: "accepted" | "rejected", comment: string }`; komentarz 1–4000 znaków. Zatwierdzane są obserwacje autora. Propozycje AI można przyjąć przez opcjonalne `accepted_ai_proposal_indexes: integer[]`; backend waliduje indeksy i typy. Powtórzona identyczna decyzja zwraca aktualny wynik bez ponownego naliczania skutków; inna decyzja dla rozpatrzonego zgłoszenia daje `409`. Zapis decyzji, historii i aktualizacja faktów są atomowe. `GET /reports?status=pending` jest dostępne wyłącznie moderatorowi.

### 8.3. Właściciel obiektu

- `GET /owner/places`: stronicowana lista przypisanych `PlaceSummary`.
- `PUT /owner/places/{id}/declaration`: `{ observations: [{ attribute, value }], observed_at }` → `200`, `{ place_id, facts: Fact[], updated_at }`.

Deklaracja wymaga niepustej listy obserwacji bez powtarzających się atrybutów; zastępuje aktywną deklarację właściciela dla obiektu, zachowując historię. Pominięte atrybuty tracą potwierdzenie tego źródła. Właściciel może zaakceptować dane automatyczne, przesyłając ich wartości jako deklarację. Backend nadaje źródło `owner` dopiero po sprawdzeniu przypisania obiektu. Dane właściciela mają pierwszeństwo, ale nie ukrywają konfliktów ani nieaktualności — backend oznacza je w faktach.

## 9. Błędy i zachowanie podczas awarii

Każdy błąd API, także walidacyjny, ma jednolitą postać:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Sprawdź podane wymagania.",
    "details": [{ "field": "constraints.max_steps", "code": "OUT_OF_RANGE", "message": "Wartość musi być nieujemna." }],
    "request_id": "req_123"
  }
}
```

`details` jest listą, także gdy jest puste. Frontend opiera logikę na `code`, a tekst pokazuje użytkownikowi. Nieznany kod wyświetla z bezpiecznym komunikatem ogólnym. Backend nie zwraca stack trace, haseł ani surowych promptów w błędach.

| HTTP | Przykładowy kod / znaczenie |
| --- | --- |
| `400` | `INVALID_REQUEST`: niepoprawny JSON lub cursor |
| `401` | `AUTH_REQUIRED`, `INVALID_CREDENTIALS` |
| `403` | `FORBIDDEN`, `CSRF_FAILED` |
| `404` | `NOT_FOUND` |
| `409` | `CONFLICT`, `PHOTO_IN_USE`: konflikt stanu |
| `413` | `FILE_TOO_LARGE` |
| `415` | `UNSUPPORTED_MEDIA_TYPE` |
| `422` | `VALIDATION_ERROR`, `OUTSIDE_SUPPORTED_AREA` |
| `429` | `RATE_LIMITED`; nagłówek `Retry-After` w sekundach |
| `500` | `INTERNAL_ERROR` |
| `503` | `DEPENDENCY_UNAVAILABLE`; np. niedostępna interpretacja AI lub routing |

Współrzędne muszą być skończone: szerokość −90…90, długość −180…180. `observed_at` nie może wskazywać przyszłości. Przy awarii źródła wyszukiwanie może użyć danych z ostatniej synchronizacji i zwrócić `warnings`; nieaktualne fakty są `unconfirmed`. Gdy nie da się wykonać obliczenia, backend zwraca `503`, a nie pusty wynik oznaczający brak miejsc lub tras.

Frontend zachowuje formularz przy błędzie. Automatycznie ponawia wyłącznie odczyty po błędzie sieci lub `503`, najwyżej dwa razy; respektuje `Retry-After`. Zapisy nie są automatycznie ponawiane, poza bezpieczną ponowną wysyłką identycznego `PUT`. Po niepewnym wyniku zapisu użytkownik najpierw odświeża listę lub szczegóły. Wygaśnięcie sesji nie blokuje wyszukiwania anonimowego.

## 10. Rozszerzenia poza prototypem

Poniższe interfejsy są kierunkiem rozwoju, **nie gotowym kontraktem v0.1**. Frontend nie wywołuje ich w prototypie i nie pokazuje aktywnych kontrolek zależnych od nich.

| Funkcja | Proponowany interfejs | Warunek przed implementacją |
| --- | --- | --- |
| Wymiana punktów na zniżki | `GET /rewards`, `POST /rewards/{id}/redeem` | Katalog nagród i ochrona przed podwójnym użyciem; saldo punktów za misje jest już dostępne przez `/missions/progress` |
| Powiadomienia | `GET /notifications`, `PATCH /notifications/{id}` | Zgoda na lokalizację, zasięg, retencja i status przeczytania; polling jako początkowy transport |
| Integracja pogody i remontów z routingiem | Modele i skrypty już opisane w sekcji 7.1 | Powiązanie z odcinkami i czasem przejścia; propagowanie świeżości i niepewności |
| Panel samorządu | `GET /municipality/barriers`, `POST /municipality/impact` | Osobna rola, agregacja bez danych osób, metodologia priorytetów i symulacji wpływu naprawy |

## 11. Podział odpowiedzialności i odbiór

**Backend:** walidacja, autoryzacja, interpretacja i analiza AI, źródła i licencje, historia zmian, starzenie danych, wiarygodność, ocena dopasowania, routing, ochrona plików i danych prywatnych. Nie przechowuje anonimowych opisów potrzeb jako profili.

**Frontend:** edycja propozycji profilu, czytelne statusy i błędy, źródła i daty, mapa oraz równoważna lista, tekstowe kroki trasy, obsługa klawiaturą i czytnikiem ekranu. Statusów nie przekazuje wyłącznie kolorem. Cel dostępności to WCAG 2.2 AA; zgodność wymaga osobnego badania interfejsu.

Warunki odbioru integracji:

1. Gość interpretuje opis, poprawia wymagania i wyszukuje bez zakładania konta.
2. `null`, `false` i `0` zachowują różne znaczenia w formularzu i API.
3. Brakujące, sprzeczne i stare dane nigdy nie dają `meets_requirements` dla wymagania, które od nich zależy.
4. Lista miejsc i tekstowe kroki zawierają informacje potrzebne do użycia aplikacji bez mapy.
5. Trasa niepewna ma wyjaśnione braki; niemożliwa trasa daje pustą listę; awaria routingu daje `503`.
6. Cudzego profilu, zgłoszenia i zdjęcia nie da się odczytać ani zmienić; właściciel deklaruje wyłącznie przypisane obiekty.
7. Zdjęcie i propozycja AI nie potwierdzają dostępności przed weryfikacją; odrzucenie zdjęcia i awaria AI mają widoczne stany.
8. Korekta zgłoszenia zachowuje historię, a powtórna decyzja moderatora nie powiela skutków.
9. Awaria zewnętrznego źródła pokazuje ostrzeżenie i daty danych, zamiast pozorować ich aktualność.

Przy implementacji FastAPI schemat OpenAPI i przykłady odpowiedzi powinny odzwierciedlać ten plik. Zmiany kontraktu należy wprowadzać razem ze zmianami API i klienta.

## 12. Integracja kont, zapisów i misji

Frontend korzysta z istniejących endpointów kont, profili, analizy potrzeb, zdjęć i zgłoszeń. Sesja jest odtwarzana przez `/auth/session`; CSRF pozostaje w pamięci aplikacji. Gość może interpretować potrzeby i wyszukiwać miejsca, a zapisy prywatne wymagają zalogowania. Formularze zachowują dane przy błędzie; potwierdzenie wysyłki pojawia się dopiero po odpowiedzi serwera.

`GET /bookmarks` zwraca listę identyfikatorów miejsc własnego konta. `PUT /bookmarks` przyjmuje listę maksymalnie 1000 identyfikatorów, sprawdza istnienie miejsc i zastępuje zapis w SQLite. Wymaga własnej sesji oraz CSRF. Profil potrzeb jest tworzony lub aktualizowany przez `/profiles` i `/profiles/{id}` po zatwierdzeniu ustawień.

Misje są tworzone dla rzeczywistych miejsc z brakującymi faktami i zapisane w SQLite. Katalog zawiera do 12 zadań, po 30 punktów każde. Jedna misja może być wykonana raz przez dane konto.

| Operacja | Odpowiedź / warunki |
| --- | --- |
| `GET /missions`, `GET /missions/{id}` | Publiczny katalog i szczegóły `{ id, place_id, place_name, title, fact_id, attribute, points, time_minutes }` |
| `GET /missions/progress` | Własne `{ items: MissionProgress[], points }`; suma przyznanych punktów |
| `POST /missions/{id}/start` | Wymaga sesji i CSRF; idempotentnie tworzy postęp `in_progress` |
| `POST /missions/{id}/submit` | `{ description?, observations?, photo_ids? }`; opis opcjonalny (do 4000 znaków), maksymalnie 5 własnych zdjęć; znana misja i miejsce tworzą kontekst zgłoszenia, metryka jest opcjonalną obserwacją; dozwolone w `in_progress` lub `rejected` |
| `GET /missions/review-queue` | Stronicowana kolejka `pending`, tylko moderator; pomija własne odpowiedzi |
| `POST /missions/progress/{id}/review` | `{ decision: "accepted" \| "rejected", comment }`, sesja moderatora i CSRF; nie może dotyczyć jego własnej misji |

`MissionProgress = { id, mission_id, user_id, status, report_id, answer, awarded_points, review_comment, created_at, updated_at }`. Statusy: `in_progress | pending | accepted | rejected`. Odpowiedź tworzy zwykłe zgłoszenie z dowodami; jego decyzja i punkty są zapisane w jednej transakcji. Weryfikacja przez `/reports/{id}/review` aktualizuje również misję. Identyczna ponowiona decyzja nie powiela punktów; inna decyzja dla rozpatrzonego zgłoszenia daje `409`. Zgłoszenie misji poprawia się wyłącznie przez ponowne wysłanie odrzuconej odpowiedzi; zwykły `PATCH /reports/{id}` jest dla niego blokowany. Przyjętej misji nie można wysłać ponownie.

Panel `/review` pokazuje moderatorowi opisy i prywatne zdjęcia. Rolę nadaje administrator poleceniem `python -m hackyeah.auth EMAIL` dla istniejącego konta; `--revoke` ją odbiera. Zmiana unieważnia dotychczasowe sesje tego konta. Publiczna rejestracja nigdy nie nadaje roli moderatora.

Odpowiedź „Nie wiem” w formularzu potwierdzenia jest brakiem wiedzy, a nie obserwacją `false`. Zdjęcia do zgłoszeń nie stanowią publicznej galerii miejsca. Mapa i planowanie tras korzystają z API i OSM; podgląd nawigacji nadal wymaga ręcznej zmiany kroków.
