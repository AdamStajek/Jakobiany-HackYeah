# Uzupełnianie miejsc i zdjęcia

Stan sprawdzenia: 2026-10-03. Baza: `data/krakow.sqlite3`.
Kopia przed uzupełnianiem: `data/krakow.before-enrichment.sqlite3`.

## Wynik rzeczywistego uruchomienia

Katalog zachowuje 7314 obiektów OSM. Dodatkowe dane lub zdjęcia ma **1307 miejsc**.
Liczby źródeł nie sumują się, bo miejsca występują w kilku zbiorach.

| Dane | Przed | Po uzupełnieniu braków |
| --- | ---: | ---: |
| Strona WWW | 1066 | 1115 |
| Telefon | 335 | 381 |
| Godziny otwarcia | 1288 | 1302 |
| Ulica | 1227 | 1276 |
| Miejsca ze zdjęciami w API | 0 | 667 |

- **MSIP**: 10694 rekordy źródłowe, dopasowane do 255 miejsc OSM.
- **BIP Biblioteki Kraków**: 54 rekordy, dopasowane do 45 miejsc; telefony, e-maile, godziny, również komunikaty o zamknięciu.
- **Wikidata**: 550 miejsc; opisy, adresy stron, datowanie, autorzy/architekci, identyfikatory zabytków, odnośniki do Wikipedii i plików Commons.
- **Strony miejsc**: 664 zapisane strony z tytułem i dostępnymi metadanymi. Nie każda zawiera opis, telefon lub godziny w danych strukturalnych. Ostatni przebieg zgłosił 149 nieudanych pobrań (m.in. HTTP 403/404, timeout, TLS, zbyt duża odpowiedź). Nie obchodzimy blokad; dotychczasowe dane pozostają zachowane.
- **Commons**: 726 różnych plików, 742 powiązania plik–miejsce, 667 miejsc. API może zwrócić kilka zdjęć miejsca. Licznik pobranych rekordów 745 obejmował aliasy, które zostały scalone przy zapisie.

Aktualizowany raport: [osm-coverage.md](osm-coverage.md), `data/coverage.json`.
Niedopasowane rekordy miejskie są zachowane do dalszego uzgadniania w bazie,
lecz nie są automatycznie nowymi wynikami wyszukiwania. Część dotyczy obiektów
poza obecnymi kategoriami (np. apartamentów) lub innych reprezentacji budynków.

## Uruchamianie

Każdy scraper domyślnie **aktualizuje istniejącą bazę**, bez osobnego importera:

```bash
PYTHONPATH=src uv run python -m scripts.scrape_public_places
PYTHONPATH=src uv run python -m scripts.scrape_place_websites
PYTHONPATH=src uv run python -m scripts.scrape_place_photos
PYTHONPATH=src uv run --group data python -m scripts.report_places
```

Wszędzie można wskazać `--database /ścieżka/baza.sqlite3`.
`--snapshot-only` pobiera dane do JSON bez importu rekordów.
`--cached` w scraperach publicznych danych i zdjęć używa zapisanych odpowiedzi;
czas pobrania pozostaje oryginalny. Przy braku cache następuje pobranie z sieci.
`--source msip`, `--source bip` lub `--source wikidata` ogranicza źródła.
Snapshoty są zapisem danego przebiegu, a baza zawiera także wcześniejsze wyniki.

Scraper witryn domyślnie obejmuje wszystkie dostępne strony (`--limit 0`),
pomija udane pobrania młodsze niż 7 dni i ponawia nieudane. `--refresh`
wymusza odświeżenie. Obsługuje `--limit`, `--place-id`, `--workers` (domyślnie 8)
i `--delay` (1 s między pobraniami tego samego hosta). Wspólne strony główne
sieci sklepów/banków są pomijane: dane centrali nie są danymi każdej placówki.

Pełny istniejący proces `scripts.update_database` obejmuje teraz także te trzy
scrapery, po imporcie OSM. `--cached-osm` dotyczy wyłącznie OSM.
Proces nadal buduje bazę roboczą, kontroluje integralność i publikuje wynik
z kopią poprzedniej bazy; pojedyncze błędy witryn pozostają w raporcie błędów.
Scraper remontów też domyślnie importuje do SQLite, a `--snapshot-only` wyłącza
import. Pogoda nadal pozostaje danymi pobieranymi w locie.

Przebudowę całego pliku SQLite uruchamiaj przy zatrzymanym backendzie, zgodnie
z instrukcją istniejącego importera. Baza w wolumenie Dockera jest osobnym
plikiem: aktualizacja hostowego `data/krakow.sqlite3` nie aktualizuje automatycznie
istniejącego wolumenu. Wskaż właściwy plik przez `--database`.

## Model i ostrożność dopasowania

`places` i `osm_objects` zachowują oryginalne wartości OSM. Uzupełnienia są
w `external_place_data`, a metadane witryn w istniejącym `place_web_data`.
Każdy rekord zewnętrzny ma źródło, ID źródła, URL, datę pobrania, informację
licencyjną, metodę dopasowania, dane JSON i opcjonalne powiązanie `place_id`.
Nie deklarujemy wszystkich miejskich danych jako CC0: zachowujemy ich źródło
oraz warunki portalu. Dane Wikidata są CC0; licencja obrazu Commons jest osobna.

Dopasowanie MSIP wymaga zgodności nazwy i położenia (zwykle do 60 m),
ewentualnie adresu i strony lub numeru rejestru zabytków oraz położenia
(do 150 m). Niejednoznaczne dopasowania pozostają puste. BIP wymaga numeru
filii we właściwej bibliotece oraz sprawdzenia dostępnego adresu.
Wikidata wykorzystuje jawny tag `wikidata` konkretnego obiektu OSM, bez
przenoszenia danych osoby upamiętnionej na dane miejsca.

API korzysta z uzupełnień tylko przy brakach OSM, a następnie z metadanych
witryny. Źródła są zwracane w `attribution`. Godziny mogą być tekstem źródłowym
lub JSON Schema.org; nie są automatyczną oceną „teraz otwarte”. Daty pobrania
nie dowodzą aktualności samych informacji; starsze miejskie zbiory zachowują
ich własne daty aktualizacji. Nie potwierdzamy pomiarów dostępności na podstawie
opisu, zdjęcia, nazwy ani bliskości innego obiektu.

Przebudowa OSM zachowuje dane zewnętrzne. Jeśli obiekt zniknie, rekord źródłowy
pozostaje, ale jego powiązanie jest usuwane. Wielokrotny import nie tworzy
duplikatów. Błąd klucza obcego wycofuje transakcję danej paczki.

```sql
SELECT source, source_id, source_url, match_method, data_json
FROM external_place_data WHERE place_id = 'node/123';

SELECT source, COUNT(*) AS records, COUNT(DISTINCT place_id) AS matched_places
FROM external_place_data GROUP BY source;
```

## Zdjęcia

`scrape_place_photos` odczytuje powiązania `wikimedia_commons=File:...`,
linki Commons z `image` i zdjęcia P18 z Wikidata. Pobiera metadane przez API Commons,
sprawdza format obrazu i jawną licencję CC BY, CC BY-SA, CC0 lub public domain.
Zapisuje URL miniatury i oryginału, autora, podpis, licencję i link do strony
pliku. Nie zapisuje binarnych obrazów i nie importuje nieoznaczonych zdjęć
z witryn komercyjnych. Brak zdjęcia pozostaje brakiem — bez obrazu sąsiedniej
placówki ani grafiki wygenerowanej jako rzekoma fotografia.

`GET /api/v1/places/{id}` zwraca `photos`. Strona miejsca pokazuje zdjęcie główne
oraz galerię w zakładce „Zdjęcia”, wraz z wymaganymi podpisami. Pliki są ładowane
z Commons; awaria zewnętrznego obrazu pokazuje komunikat. Zdjęcia nie dowodzą
aktualnego stanu wejścia. [Warunki ponownego użycia Commons](https://commons.wikimedia.org/wiki/Commons:Reusing_content_outside_Wikimedia).

## Źródła

- [Publiczne usługi MSIP](https://msip.um.krakow.pl/arcgis/rest/services/Obserwatorium): biblioteki, miejskie instytucje kultury, rejestry hotelarskie/noclegowe, zabytki, jestemAKTYWNY. Starsze warstwy nie obsługują stronicowania: importer pobiera ID i małe paczki rekordów.
- [Otwarte dane Krakowa](https://msip.krakow.pl/aktualnosci/324198,2053,komunikat,nowa_usluga_pobierania_danych_msip.html): katalog GeoJSON/SHP i usługi WFS; [warunki MSIP](https://msip.krakow.pl/getHtml?dok_id=288055).
- [Filie Biblioteki Kraków — BIP](https://www.bip.krakow.pl/?dok_id=83400).
- [Wikidata — dostęp i CC0](https://www.wikidata.org/wiki/Wikidata:Data_access).
- OSM/Geofabrik pozostaje podstawą katalogu; [dotychczasowy importer i licencja](osm-data.md).

## Google Maps: możliwości i ograniczenia

Google Places API (New) udostępnia nazwy, adresy, współrzędne, typy miejsc,
status działalności, strony, telefony, oceny, wybrane informacje o dostępności
oraz `regularOpeningHours`, `currentOpeningHours` i dodatkowe godziny usług.
Pola są opcjonalne: bez próby na krakowskich placówkach nie można podać uczciwego
procentu pokrycia. Godziny wymagają poziomu **Enterprise**, informacje o dostępności
— **Pro**. [Pola i poziomy rozliczeń](https://developers.google.com/maps/documentation/places/web-service/data-fields).

To nie jest kompletny eksport miasta: [Text Search](https://developers.google.com/maps/documentation/places/web-service/text-search)
zwraca do 60 wyników łącznie, a [Nearby Search](https://developers.google.com/maps/documentation/places/web-service/nearby-search)
do 20. Place Photos może zwrócić do 10 odnośników do zdjęć miejsca. Ich identyfikatory
wygasają i nie mogą być cache'owane; wyświetlanie wymaga uwzględnienia autorów.
[Dokumentacja zdjęć](https://developers.google.com/maps/documentation/places/web-service/place-photos).

**Nie włączono trwałego importu Google do SQLite.** Ogólne zasady Places zabraniają
prefetch/cache/przechowywania treści poza określonymi wyjątkami; `place_id` można
przechowywać bezterminowo. [Zasady Places](https://developers.google.com/maps/documentation/places/web-service/policies).
Dla klientów z adresem rozliczeniowym w EOG dochodzą szczególne zasady użycia
Places z mapą i dozwolonych zastosowań. Wyjątek 30 dni dotyczy współrzędnych,
nie daje ogólnego prawa do przechowywania godzin i zdjęć. Places UI Kit ma
odrębne zasady. Dlatego nie zakładamy, że zwykła karta Places obok mapy OSM
jest dopuszczalna. [Warunki EOG, punkt 15](https://cloud.google.com/terms/maps-platform/eea/maps-service-terms).

Cennik sprawdzony 2026-10-03: Place Details Enterprise ma 1000 bezpłatnych
wywołań miesięcznie, potem 20 USD/1000 w pierwszym płatnym progu. Gdybyśmy
mieli już 7314 poprawnych place_id i każde sprawdzili raz, same szczegóły
kosztowałyby **126,28 USD**, zakładając niewykorzystany darmowy limit.
Wyszukiwanie ID i pobrania zdjęć mogą zwiększyć koszt; to wyliczenie przykładowe,
nie wykonany import ani zgoda na przechowywanie wyników.
[Cennik Google Maps](https://developers.google.com/maps/billing-and-pricing/pricing).

Do rzetelnego pilotażu pokrycia Google potrzebny jest klucz z aktywnym
**Places API (New)**, włączone rozliczenia i określony limit kosztu. Klucz należy
umieścić lokalnie w `.env` jako `GOOGLE_MAPS_API_KEY`, bez wklejania go do czatu
ani repozytorium. Obecne scrapery go nie używają i nie generują opłat Google.
Najpierw trzeba wybrać dozwolony sposób prezentowania danych na żywo; otwartą,
trwałą bazę nadal uzupełniamy źródłami powyżej.

## Sprawdzenie wdrożenia

Przeszło 19 testów Python (nowe uzupełnienia, miejsca, import OSM, magazyn danych
czasowych), 8 testów jednostkowych frontendu, 2 testy galerii Playwright
(komputer i telefon), Ruff, kontrola typów zmienionych modułów i build frontendu.
Sprawdzono odpowiedzi API wszystkich 1307 wzbogaconych miejsc oraz integralność
bazy i klucze obce. Trzy rzeczywiste URL-e miniatur zwróciły HTTP 200/image/jpeg.

## Karta Google Places UI Kit

Karta Google Maps znajduje się bezpośrednio pod adresem na stronie miejsca.
Otwarcie strony ładuje pełną kartę Place Details na podstawie współrzędnych;
Google automatycznie dopasowuje lokalizację do swoich danych. Karta może
zawierać zdjęcia, opinie i dostępne podsumowania.
Treści i powiązania Google nie są zapisywane do SQLite, eksportów ani ocen
dostępności. Podsumowania AI mogą nie być dostępne dla danego miejsca/języka.

Vite odczytuje `GOOGLE_MAPS_BROWSER_API_KEY` z głównego `.env` lub środowiska,
z fallbackiem do istniejącego `GOOGLE_API_KEY`. Compose przekazuje ten sam
wybór do buildu frontendu. Po zmianie klucza trzeba ponownie zbudować frontend
(`docker compose build frontend`) lub zrestartować Vite. Brak klucza wyświetla
komunikat bez ładowania SDK. Do produkcji użyj osobnego klucza przeglądarkowego
z ograniczeniami HTTP referrer do swoich domen i ograniczeniami API zgodnymi
z konfiguracją Google Maps JavaScript/Places UI Kit. Taki klucz jest publiczny
w bundle przeglądarki; nie używaj wspólnego, nieograniczonego klucza serwerowego.
Inne zmienne `.env`, w tym `OPENAI_API_KEY`, nie są przekazywane do frontendu.

Projekt Cloud wymaga rozliczeń i włączonego Places UI Kit. Integracja nie
włącza usług ani nie zmienia ograniczeń klucza. Karta i wyszukiwanie generują
osobne zdarzenia rozliczeniowe; nie tworzymy Google Map. Błędy SDK/usługi
wyświetlają komunikat i nie blokują lokalnych informacji miejsca.

Dla komercyjnego użycia zachowujemy oryginalne komponenty, atrybucje i linki
Google, bez modyfikowania ich wnętrza. Wyjątek EOG dla UI Kit umożliwia użycie
z mapą Leaflet/OSM; nie daje prawa do trwałego kopiowania treści Google do bazy.
Przed publikacją uwzględnij usługę w regulaminie i polityce prywatności aplikacji.

Źródła: [konfiguracja UI Kit](https://developers.google.com/maps/documentation/javascript/places-ui-kit/get-started),
[Place Search](https://developers.google.com/maps/documentation/javascript/places-ui-kit/place-search),
[Place Details](https://developers.google.com/maps/documentation/javascript/places-ui-kit/place-details),
[warunki EOG, punkty 15–16](https://cloud.google.com/terms/maps-platform/eea/maps-service-terms),
[zabezpieczenia kluczy](https://developers.google.com/maps/api-security-best-practices).
