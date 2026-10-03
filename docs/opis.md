# Swoją Drogą / By the Way

## Idea aplikacji

**Swoją Drogą / By the Way** to aplikacja, która pozwala seniorom z trudnościami w poruszaniu się sprawdzić dostępność miejsc oraz wyznaczyć trasę z punktu A do punktu B wraz z oceną, czy użytkownik może ją pokonać.

Użytkownik może utworzyć profil, opisując swoje potrzeby w prompcie. Może też od razu wyszukać miejsce lub trasę, wpisując, co chce zrobić i jakie ma trudności.

Dla wybranego profilu aplikacja wskazuje miejsca i trasy spełniające wymagania użytkownika, np. bez schodów i stromych podejść albo z najwyżej dwoma stopniami. Dane o dostępności pobiera automatycznie z publicznych baz. Właściciele miejsc mogą utworzyć profil obiektu i dodać aktualne informacje lub zaakceptować dane przygotowane automatycznie. Zweryfikowane informacje mają pierwszeństwo.

## Udział użytkowników

Użytkownicy mogą pomagać w uzupełnianiu brakujących danych. Aplikacja będzie przydzielać im misje, np. wykonanie zdjęcia miejsca. Model AI przeanalizuje zdjęcie i zaproponuje parametry dostępności do dalszej weryfikacji. Za wykonane misje użytkownicy otrzymają punkty, które będzie można wymienić na zniżki w usługach miasta Krakowa lub u partnerów.

Użytkownik będzie mógł również zgłosić niepewną informację. Osoby znajdujące się w okolicy otrzymają powiadomienie i za punkty będą mogły sprawdzić zgłoszenie na miejscu oraz dodać zdjęcie. System przeanalizuje fotografię, aby dodatkowo zweryfikować zgłoszone dane. Potwierdzanie i zgłaszanie informacji będzie możliwe także bez misji, ale za mniejszą liczbę punktów.

## Bariery stałe i czasowe

Aplikacja powinna informować zarówno o stałych barierach dostępności, jak i o utrudnieniach czasowych, takich jak oblodzenie, upał na trasie bez zadaszenia czy brak klimatyzacji w obiekcie. Może w tym celu korzystać z danych pogodowych, informacji o remontach, braku oświetlenia i niedziałającej infrastrukturze.

## Indywidualny profil potrzeb

Użytkownicy mogą tworzyć profile opisujące ich szczególne potrzeby. Inteligentny czat pozwoli im podać bardziej szczegółowe informacje, na przykład:

> Poruszam się o kulach. Mogę przejść kilka schodów, ale potrzebuję miejsca do siedzenia mniej więcej co 300 metrów.

Bariery trudno opisać za pomocą kilku etykiet. Na podstawie opisu aplikacja przygotuje profil ograniczeń, który użytkownik będzie mógł poprawić. Posłuży on do proponowania dopasowanych miejsc i tras.

## Panel dla samorządu

Z aplikacji mogą korzystać także samorządy, np. miasto Kraków. Osobny panel może pokazywać, które bariery należy usunąć w pierwszej kolejności oraz jaki będzie efekt danej naprawy — na przykład do ilu miejsc poprawi się dostęp po uruchomieniu jednej windy.

## Zakres prototypu

Prototyp skupimy na seniorach z trudnościami w poruszaniu się po Krakowie. Po wyszukaniu miejsca lub trasy użytkownik zobaczy konkretne informacje o:

- schodach i progach,
- podjazdach i windach,
- szerokości wejść,
- nawierzchni,
- toaletach,
- miejscach odpoczynku.

Przy każdej informacji pokażemy jej źródło, datę i procentową wiarygodność. Brak danych oraz dane sprzeczne lub nieaktualne oznaczymy jako **niepotwierdzone**. Nigdy nie będą one traktowane jako potwierdzenie dostępności.

## Wiarygodność danych

Wiarygodność będziemy obliczać na podstawie:

1. Zgłoszeń właścicieli miejsc — najwyższa waga.
2. Zgłoszeń i weryfikacji użytkowników.
3. Weryfikacji zgłoszeń użytkowników przez AI.
4. Danych pogodowych w przypadku informacji zależnych od pogody — średnia waga.
5. Automatycznej analizy OpenStreetMap i innych źródeł — najniższa waga.

Waga zgłoszenia użytkownika będzie malała wraz z upływem czasu od jego dodania.

## Dane i ich aktualizacja

Prototyp wykorzysta OpenStreetMap (OSM), deklaracje właścicieli miejsc i zgłoszenia użytkowników. Dane OSM będziemy aktualizować codziennie, oznaczając źródło i licencję ODbL. Zgłoszenia będzie można poprawiać, a analiza zdjęć pomoże je weryfikować.

Oddzielne moduły pobierania, weryfikacji i prezentacji danych pozwolą później dodać informacje o pogodzie i remontach oraz rozszerzyć aplikację na kolejne miasta, bez dostępu do wewnętrznych systemów miejskich. Przed podłączeniem nowego zbioru danych określimy jego licencję, sposób i częstotliwość pobierania oraz działanie aplikacji podczas awarii źródła.

## Dostępność, prywatność i utrzymanie

Korzystanie z wyszukiwarki nie będzie wymagało konta ani podawania informacji o niepełnosprawności — wystarczy opis istotnych barier. Konta i zgłoszenia zostaną zabezpieczone, zdjęcia będą chronione przed ujawnieniem danych osób, a połączenia szyfrowane.

Aplikacja musi spełniać standard **WCAG 2.2 na poziomie AA**. W prototypie sprawdzimy obsługę klawiaturą i czytnikiem ekranu, kontrast oraz tekstową wersję informacji z mapy. Udokumentujemy pozostałe ograniczenia.

Zespół będzie odpowiadał za hosting, aktualizacje, bezpieczeństwo i obsługę zgłoszeń poza infrastrukturą miasta. Bezpłatny dostęp dla użytkowników może finansować oferta abonamentowa dla obiektów, hoteli i organizatorów wydarzeń, uzupełniona systemem partnerskim.

## Proponowana architektura

- **Aplikacja webowa:** React z TypeScript i Next.js. Do wyświetlania mapy posłuży [MapLibre GL JS](https://maplibre.org/maplibre-gl-js/docs/). Mapa zawsze będzie miała równoważną tekstową listę miejsc, barier i kroków trasy. Dostępność całego interfejsu wymaga osobnej weryfikacji.
- **API i przetwarzanie danych:** Python i FastAPI. API udostępni wspólne formaty danych dla wyszukiwarki, tras, zgłoszeń i paneli.
- **Baza danych i wyznaczanie tras:** PostgreSQL z [PostGIS](https://postgis.net/docs/using_postgis_query.html) do przechowywania danych przestrzennych oraz [pgRouting](https://docs.pgrouting.org/latest/en/) do obliczania tras. Koszt odcinka uwzględni wymagania profilu, np. schody, nawierzchnię i odległość do miejsca odpoczynku. Brak informacji o odcinku zwiększy niepewność trasy; nie będzie oznaczał potwierdzenia jej dostępności.
- **Źródła danych:** wyciąg OSM dla Krakowa i codzienne pliki zmian, deklaracje obiektów oraz zgłoszenia użytkowników. Każdy fakt będzie miał przypisane źródło, datę, status weryfikacji i historię zmian. Po sprawdzeniu przydatności i warunków wykorzystania można także użyć:
  - krakowskiego MSIP;
  - deklaracji dostępności instytucji publicznych;
  - danych Zarządu Dróg Miasta Krakowa o remontach i utrudnieniach;
  - API Open-Meteo;
  - miejskich map toalet i wyposażenia parków.
- **Opis potrzeb i analiza zdjęć:** model językowy zamieni opis użytkownika na ustrukturyzowane ograniczenia, które będzie można poprawić. Model obrazu zaproponuje cechy widoczne na zdjęciu. Wynik trafi do weryfikacji i nie zastąpi pomiaru ani potwierdzenia w terenie.
- **Konta i pliki:** logowanie będzie dostępne dla właścicieli, moderatorów i chętnych użytkowników; wyszukiwanie pozostanie dostępne bez konta. Pliki będą przechowywane na dysku serwera.
- **Jakość i utrzymanie:** odbiór zgodności z WCAG 2.2 AA obejmie również ręczne badanie klawiaturą i czytnikiem ekranu. Sprawdzimy m.in. [widoczność fokusu, obsługę bez przeciągania i wielkość celów dotykowych](https://www.w3.org/WAI/standards-guidelines/wcag/new-in-22/).
- **Powtarzalność wdrożenia:** cała aplikacja powinna działać w kontenerze Docker.
