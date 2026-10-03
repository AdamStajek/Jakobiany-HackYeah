## Proponowany spis technologii

- **Aplikacja webowa:** React z TypeScript i Next.js. Mapa w [MapLibre GL JS](https://maplibre.org/maplibre-gl-js/docs/), zawsze z równoważną tekstową listą miejsc, barier i kroków trasy. MapLibre służy do wyświetlania mapy; dostępność całego interfejsu trzeba sprawdzić osobno.
- **API i przetwarzanie danych:** Python i FastAPI. API udostępnia wspólne formaty danych dla wyszukiwarki, tras, zgłoszeń i paneli.
- **Baza danych i wyznaczanie tras:** PostgreSQL z [PostGIS](https://postgis.net/docs/using_postgis_query.html) do danych przestrzennych oraz [pgRouting](https://docs.pgrouting.org/latest/en/) do obliczania tras. Koszt odcinka uwzględnia wymagania profilu, np. schody, nawierzchnię i odległość do miejsca odpoczynku. Brak informacji o odcinku podnosi niepewność trasy; nie staje się potwierdzeniem jej dostępności.
- **Źródła danych:** wyciąg OSM dla Krakowa i codzienne pliki zmian, deklaracje obiektów oraz zgłoszenia użytkowników. Każdy fakt ma źródło, datę, status weryfikacji i historię zmian. Codzienne pliki zmian OSM są dostępne oficjalnie. Ponadto, po sprawdzeniu ich przydatności, można wykorzystać:
  - krakowski MSIP;
  - deklaracje dostępności instytucji publicznych;
  - dane Zarządu Dróg Miasta Krakowa o remontach i utrudnieniach;
  - API Open-Meteo;
  - miejskie mapy toalet i wyposażenia parków.
- **Prompt i analiza zdjęć:** model językowy zamienia opis potrzeb na ustrukturyzowane ograniczenia, które użytkownik może poprawić. Model obrazu proponuje cechy widoczne na zdjęciu; wynik trafia do weryfikacji i nie zastępuje pomiaru ani potwierdzenia w terenie.
- **Konta i pliki:** logowanie dla właścicieli, moderatorów i chętnych użytkowników; wyszukiwanie bez konta. Pliki są przechowywane na dysku serwera.
- **Jakość i utrzymanie:** odbiór zgodności z WCAG 2.2 AA obejmuje także ręczne badanie klawiaturą i czytnikiem ekranu. Istotne są m.in. widoczność fokusu, obsługa bez przeciągania i wielkość celów dotykowych. Więcej informacji: [W3C: WCAG 2.2](https://www.w3.org/WAI/standards-guidelines/wcag/new-in-22/).
- **Powtarzalność wdrożenia:** cała aplikacja powinna działać w kontenerze Docker.
