# Planowanie tras pieszych w całym Krakowie

`POST /api/v1/routes/plan` korzysta z rzeczywistej topologii OpenStreetMap,
zaimportowanej z pełnego wyciągu Małopolski. Obejmuje granicę administracyjną
Krakowa (relacja 449696) i niewielki bufor ulic w sąsiedztwie. Import z 3 października
2026 zawiera 535 128 węzłów, 143 045 dróg i 593 427 połączeń przed dodaniem
przeciwnych kierunków. Rozmiar gotowego grafu SQLite wynosi około 73 MB.

## Przygotowanie danych i uruchomienie

```bash
uv sync --group data
PYTHONPATH=src uv run --group data python -m scripts.download_osm
PYTHONPATH=src uv run --group data python -m scripts.build_route_graph
```

Skrypt korzysta z `data/raw/malopolskie-latest.osm.pbf` oraz
`data/raw/krakow-boundary.json`. Odrzuca wyciąg o zasięgu, który nie pokrywa
całego miasta. Publikuje `data/routes/city.sqlite3` dopiero po udanym imporcie
oraz kontroli integralności; nieudana przebudowa zachowuje poprzedni plik.
Graf jest generowany i ignorowany przez Git. Grupa `data` jest potrzebna do
importu, a nie do obsługi żądań API.

Pełna aktualizacja przez `scripts.update_database` przebudowuje również graf.
`--missing-only` pozostawia go bez zmian. `ROUTE_GRAPH_PATH` pozwala wskazać
inny gotowy plik. Graf jest ładowany raz na proces i ponownie po zmianie pliku.
Brak grafu daje `503`; nie ma zastępczej trasy demonstracyjnej.

Obraz Docker kopiuje graf do `/app/routes/city.sqlite3`, poza woluminem bazy
miejsc. Po aktualizacji grafu na hoście trzeba przebudować obraz API.

## Punkty i profil

Punkt początku i celu to `{lat, lon}` albo `{place_id}`. Obsługiwane są ID
miejsc z katalogu miasta, np. `node/1506803231`, oraz starsze skróty
`rynek`, `planty`, `wawel`. `GET /api/v1/routes/points?query=...` zwraca do 20
miejsc pasujących nazwą lub adresem, niezależnie od oceny ich dostępności.
Frontend pozwala wyszukać oba punkty lub wskazać je na mapie.

`constraints` zawiera zatwierdzone potrzeby. Alternatywnie `profile_id`
wskazuje własny zapisany profil i wymaga sesji. Opis tekstowy profilu trafia
do istniejącego `/needs/interpret`; propozycję trzeba zatwierdzić. Przy awarii
interpretacji można wybrać wymagania ręcznie.

Punkt jest rzutowany na najbliższy odcinek sieci w odległości do 100 m.
Dojście do sieci jest jawnie orientacyjne: nie jest potwierdzonym przejściem
przez teren ani wejściem do budynku. Dane miejsc mogą zawierać punkt
reprezentatywny budynku zamiast wejścia. Punkty zbyt odległe i rozłączone
części sieci zwracają pusty wynik z wyjaśnieniem.

## Wybór trasy

Algorytm A* wybiera trasę o najmniejszym koszcie obejmującym czas przejścia
oraz niedogodności wskazane w profilu. Węzły są łączone przez wspólne ID OSM,
a nie geometryczne przecięcie linii; most i droga pod mostem nie tworzą
przez sam fakt przecięcia nowego przejścia. Kierunki `oneway:foot` są
respektowane. Samochodowe `oneway` nie ogranicza kierunku pieszego.
Drogi z zakazem dostępu pieszego i drogi rowerowe bez jawnej zgody na ruch
pieszy są odrzucane podczas importu.

- Wymóg bez stopni lub `max_steps=0` wyklucza zmapowane schody, stopnie
  punktowe, przeszkody takie jak stile/turnstile oraz `wheelchair=no`.
- `smoothness=impassable`, ściany, ogrodzenia, blokady i jawne zakazy
  dostępu na węzłach wykluczają przejście.
- Znane naruszenia limitów nachylenia, krawężnika, progu i szerokości,
  niedozwolone nawierzchnie, nierówności i wymagany brak oświetlenia wykluczają odcinek.
- Limit stopni i odległości bez odpoczynku nie może zostać przekroczony.
  `step_count` całej drogi nie jest mnożony przez liczbę jej fragmentów.
- Wymagana dostępna toaleta musi być zmapowana przy wybranej trasie.
  Miejsca odpoczynku i toalety są przypisywane do węzłów w promieniu 25 m;
  rzeczywiste dojście i prawo dostępu wymagają sprawdzenia.

Jeśli nie ma trasy spełniającej wymagania, odpowiedź zawiera pustą listę tras
oraz komunikat dla użytkownika. Nie zwracamy wtedy zastępczej najszybszej trasy.
Nieznane parametry nadal oznaczają niepewność, a nie potwierdzoną dostępność.
Nieznany aktywny parametr dodaje 0,15 mnożnika kosztu; brak informacji
o stopniach przy profilu bez stopni dodaje 0,1. Czas przejścia jest osobnym
szacunkiem prędkości 1,2 m/s, nawierzchni, nachylenia i zmapowanych stopni.

Etykiety A* przechowują liczbę stopni, odległość od odpoczynku i obecność toalety;
dominowane stany są odrzucane. Odległość bez odpoczynku jest konserwatywnie
zaokrąglana do 10 m. Wynik pokazuje długości rzeczywistej geometrii.

## Wiarygodność i zakres

Fakty OSM zachowują `unconfirmed / pending_verification` albo `missing`.
Brak nachylenia, progu, szerokości czy krawężnika nie jest zastępowany zerem
ani oznaczany jako potwierdzony. Trasa bez zmapowanych naruszeń nadal ma
ocenę `uncertain`. Geometria, instrukcje, źródła i odcinki pochodzą z tego
samego wyniku. Podgląd nawigacji jest ręczny i nie śledzi pozycji.

Do odpowiedzi API nadal dołączana jest prognoza dla początku trasy.
Remonty i pogoda nie wpływają jeszcze na koszt wyszukiwania. Warunki
nieznane lub nieobecne w OSM nie mogą być automatycznie ominięte.

Na lokalnej maszynie załadowanie grafu trwało około 9–10 s i zajęło około
700 MiB. Przykładowe żądania po załadowaniu trwały około 0,5–4,8 s;
profil z kilkoma ograniczeniami zwiększył szczytowe użycie pamięci do około
815 MiB. To pomiar kilku żądań, nie gwarancja czasu dla każdej pary punktów.

## Sprawdzenie

```bash
PYTHONPATH=src uv run --group data python -m unittest discover -s tests -p '*routing.py'
PYTHONPATH=src uv run --group data python -m unittest discover -s tests -p test_route_graph_build.py
cd frontend
npm run build
npm run test:e2e -- routes.spec.ts map.spec.ts
```
