# Dane do planowania tras w Krakowie

Moduł `hackyeah.route_data` pobiera wyciąg OpenStreetMap z BBBike i eksportuje
sieć dróg oraz punktowe bariery do GeoJSON Lines. Nie tworzy bazy danych i nie
zapisuje danych miejsc. Korzysta z istniejących zależności grupy `data`.
Eksport jest wejściem dla przyszłego silnika planowania tras; `/routes/plan`
pozostaje szkieletem zwracającym `501`.

## Uruchomienie i aktualizacja

```bash
uv sync --group data --group dev
# Przetworzenie istniejącego wyciągu, bez połączenia z internetem:
PYTHONPATH=src uv run python -m hackyeah.route_data
# Pobranie nowego wyciągu i ponowne przetworzenie:
PYTHONPATH=src uv run python -m hackyeah.route_data --download
# Własne ścieżki:
PYTHONPATH=src uv run python -m hackyeah.route_data --input data/raw/Cracow.osm.pbf --output data/routes/network.geojsonl
```

Źródło: [wyciąg BBBike dla Krakowa](https://download.bbbike.org/osm/bbbike/Cracow/).
Opcja `--download` pobiera pełny plik PBF, a nie replikuje zmian. Można uruchamiać
ją codziennie z harmonogramu systemowego; aktualność zależy od wyciągu źródłowego.
Nie uruchamiać dwóch eksportów do tej samej ścieżki jednocześnie.
Błąd pobierania lub parsowania zgłasza niezerowy kod zakończenia.
Błąd eksportu zachowuje poprzedni plik sieci. Nieudane pobranie/parsowanie
zachowuje poprzedni plik wejściowy. API nie odpyta automatycznie sieci zewnętrznej.

Zakres przestrzenny to prostokąt `[19.76, 49.96, 20.16, 50.14]`, zgodny
z istniejącym `data/raw/Cracow.poly`, **nie granica administracyjna Krakowa**.
Przebieg dróg przecinających prostokąt jest zachowany w całości dla utrzymania
identyfikatorów węzłów; geometria może wychodzić poza obszar.

## Format i integracja

`data/routes/network.geojsonl`: jedna cecha GeoJSON `Feature` na wiersz,
walidowana przez model `RouteDataFeature`:

- `id`: identyfikator źródłowy `osm/way/<id>` albo `osm/node/<id>`.
- `geometry`: `LineString` dla drogi lub `Point` dla oznaczonego punktu;
  współrzędne WGS84 `[lon, lat]`.
- `properties.node_ids`: dla drogi identyfikatory węzłów w tej samej kolejności
  co współrzędne; dla punktu jego identyfikator. Umożliwia powiązanie bariery
  z drogą i połączenie sieci bez bazy danych.
- `properties.tags`: wybrane tagi OSM potrzebne do interpretacji drogi,
  również surowe informacje o ograniczeniach dostępu, schodach, podjazdach,
  nawierzchni, chodnikach, kierunku ruchu pieszego, poziomach, mostach i tunelach.
  Nie eksportujemy nazw użytkowników OSM ani pozostałych danych edytorów.
- `properties.facts`: wszystkie kategorie trasy, zgodne z modelem `Fact`;
  nieznane wartości występują jako `null`.

`data/routes/network.manifest.json`: czas eksportu, obszar, liczby dróg,
punktów, schodów, obiektów bez oświetlenia, pokrycie poszczególnych faktów,
licencja i ostrzeżenia. `known_facts` liczy jawne wartości, także `false` i `0`,
a nie zweryfikowane informacje. Nie sumować faktów punktów i dróg jako liczby
unikalnych utrudnień w mieście.

Silnik tras powinien dzielić drogi w węzłach wspólnych, wiązać bariery przez
`node_ids`, respektować ograniczenia ruchu oraz oceniać fakty zarówno drogi,
jak i węzłów na niej. Przecięcie geometrii bez wspólnego węzła nie ustanawia
połączenia (np. most). Schody bez liczby stopni nadal mają `steps_present=true`.
Podjazd nie znosi automatycznie schodów: konieczna jest ocena konkretnego
przebiegu i możliwości użytkownika.

Eksport pomija drogi z jawnym zakazem ruchu pieszego, niedostępne prywatne drogi,
obszary `area=yes`, autostrady i drogi bez pełnej geometrii. Zwykłe ulice
pozostają kandydatami; ich obecność **nie potwierdza chodnika ani bezpiecznego
przejścia**. Poligony placów, relacje tras i osobne tagowanie stron chodnika
nie są przekształcane w graf. Te przypadki wymagają obsługi w silniku tras.

## Mapowanie niedogodności

| Kategoria | Fakty | Reguła OSM |
| --- | --- | --- |
| Schody | `steps_present`, `steps_count` | `highway=steps` lub `barrier=step` potwierdza wyłącznie obecność w źródle; `step_count` daje liczbę |
| Progi | `threshold_height_cm` | Brak wiarygodnego pomiaru w tym źródle; zawsze `null` |
| Wysokie krawężniki | `raised_kerb`, `kerb_height_cm` | `kerb=raised` daje `true`; `kerb=flush/no` daje `false`; `kerb:height` daje wysokość; `height` tylko na `barrier=kerb` |
| Podjazdy | `ramp_available` | `ramp:wheelchair=yes/no`; `ramp=no` daje `false`; samo `ramp=yes` lub podjazd rowerowy nie wystarcza |
| Słaba nawierzchnia | `surface`, `smoothness` | Rodzaj materiału oddzielony od stanu; wartości OSM `smoothness` zachowane bez zamiany na arbitralną ocenę dostępności |
| Brak oświetlenia | `lighting_available` | `lit=yes/no`; `no` oznacza brak oświetlenia, nie aktualną awarię |

Wysokość bez jednostki jest w metrach i jest przeliczana na cm; obsługujemy
również `m`, `cm`, `mm`. Niejasne lub przybliżone wartości pozostają nieznane.
`kerb=lowered` nie oznacza zerowej wysokości. Nie wyliczamy cm z kategorii
krawężnika ani liczby stopni z samego `highway=steps`.

`surface` normalizuje znane materiały do enum API; nieznany materiał ma `other`,
a oryginał pozostaje w tagach. `smoothness` ma wartości `excellent`, `good`,
`intermediate`, `bad`, `very_bad`, `horrible`, `very_horrible`, `impassable`.
Kostka nie oznacza automatycznie uszkodzonej nawierzchni, a asfalt dobrej.

Każdy pobrany fakt ma `status=unconfirmed`, `confidence_percent=null`,
`unconfirmed_reason=pending_verification`; brak wartości ma powód `missing`.
Nie wymyślamy procentowej wiarygodności. `updated_at` to czas ostatniej edycji
obiektu OSM, **nie data pomiaru**; `observed_at=null`. Źródło znanej wartości
ma adres obiektu, `license=ODbL` i czas pobrania/odczytu. Przy prezentacji należy
zachować [atrybucję OSM i warunki licencji](https://www.openstreetmap.org/copyright).

Dokumentacja tagów: [schody](https://wiki.openstreetmap.org/wiki/Tag:highway%3Dsteps),
[krawężniki](https://wiki.openstreetmap.org/wiki/Key:kerb),
[podjazdy](https://wiki.openstreetmap.org/wiki/Key:ramp),
[stan nawierzchni](https://wiki.openstreetmap.org/wiki/Key:smoothness),
[oświetlenie](https://wiki.openstreetmap.org/wiki/Key:lit).

Dane czasowe (pogoda i remonty), pobierane osobno bez bazy danych: [dokumentacja](dane-czasowe.md).
