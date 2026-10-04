import { PageHeading } from "../components/Common";

export function PublicData() {
  return (
    <div className="page narrow">
      <PageHeading
        title="Dane publiczne"
        description="Źródła miejsc, tras, transportu i pogody — co pobieramy i kiedy."
      />
      <div className="panel prose">
        <h2>Jak korzystamy z danych</h2>
        <p>
          Łączymy publiczne dane o Krakowie z obserwacjami użytkowników. Poniżej
          wymieniamy źródła obsługiwane przez aplikację i jej importer.
          Dostępność poszczególnych informacji zależy od zawartości źródła oraz
          pobranej kopii. Dane miejskie pobieramy z publicznych stron i API, bez
          dostępu do wewnętrznych systemów miasta.
        </p>
        <h2>OpenStreetMap — miejsca i drogi</h2>
        <p>
          <a href="https://download.geofabrik.de/europe/poland/malopolskie-latest.osm.pbf">
            Geofabrik: malopolskie-latest.osm.pbf
          </a>{" "}
          oraz{" "}
          <a href="https://www.openstreetmap.org/api/0.6/relation/449696/full.json">
            API OSM: granica Krakowa, relacja 449696
          </a>
          . Pobieramy plik PBF i JSON granicy. Odczytujemy nazwy, kategorie,
          adresy, współrzędne, kontakt, godziny otwarcia i oznaczenia
          dostępności miejsc, a także drogi, chodniki, przejścia, schody,
          nawierzchnie, nachylenia, szerokości, krawężniki i udogodnienia, jeśli
          są oznaczone w OSM. Z tych danych budujemy lokalną sieć pieszą.
          Aktualizacja następuje po uruchomieniu importu; nie ma automatycznego
          harmonogramu. Nieudane pobranie nie zastępuje poprzedniego pliku.
        </p>
        <p>
          Osobny importer sieci tras obsługuje też{" "}
          <a href="https://download.bbbike.org/osm/bbbike/Cracow/Cracow.osm.pbf">
            BBBike: Cracow.osm.pbf
          </a>
          , czyli wyciąg OSM Krakowa. Pobiera go po ręcznym uruchomieniu z opcją
          pobrania; zastępuje poprzedni plik dopiero po sprawdzeniu poprawności.
          Dane OSM są udostępniane na{" "}
          <a href="https://www.openstreetmap.org/copyright">licencji ODbL</a>.
        </p>
        <h2>MSIP Kraków — konkretne warstwy miejskie</h2>
        <p>
          W{" "}
          <a href="https://msip.um.krakow.pl/arcgis/rest/services/Obserwatorium/">
            publicznym API ArcGIS REST MSIP, katalog Obserwatorium
          </a>{" "}
          korzystamy z poniższych usług i warstw MapServer:
        </p>
        <ul>
          <li>
            <a href="https://msip.um.krakow.pl/arcgis/rest/services/Obserwatorium/WT_WC_2023/MapServer/0">
              WT_WC_2023 / 0
            </a>{" "}
            — toalety publiczne.
          </li>
          <li>
            <a href="https://msip.um.krakow.pl/arcgis/rest/services/Obserwatorium/K17_KULTURA/MapServer/0">
              K17_KULTURA / 0
            </a>{" "}
            — obiekty kultury.
          </li>
          <li>
            <a href="https://msip.um.krakow.pl/arcgis/rest/services/Obserwatorium/Miejskie_Instytucje_Kultury/MapServer">
              Miejskie_Instytucje_Kultury / 0–4
            </a>{" "}
            — miejskie instytucje kultury.
          </li>
          <li>
            <a href="https://msip.um.krakow.pl/arcgis/rest/services/Obserwatorium/WT_OBIEKTY_HOTELOWE_KOH/MapServer/0">
              WT_OBIEKTY_HOTELOWE_KOH / 0
            </a>{" "}
            — obiekty hotelowe.
          </li>
          <li>
            <a href="https://msip.um.krakow.pl/arcgis/rest/services/Obserwatorium/WT_OBIEKTY_NOCLEGOWE_KON/MapServer/0">
              WT_OBIEKTY_NOCLEGOWE_KON / 0
            </a>{" "}
            — obiekty noclegowe.
          </li>
          <li>
            <a href="https://msip.um.krakow.pl/arcgis/rest/services/Obserwatorium/zabytki_do_pobrania/MapServer">
              zabytki_do_pobrania / 0–1
            </a>{" "}
            — zabytki.
          </li>
          <li>
            <a href="https://msip.um.krakow.pl/arcgis/rest/services/Obserwatorium/jestemAKTYWNY/MapServer">
              jestemAKTYWNY / 0–13
            </a>{" "}
            — obiekty aktywności i rekreacji.
          </li>
        </ul>
        <p>
          Importer odpytuje endpointy /query: najpierw pobiera identyfikatory
          obiektów, potem ich atrybuty i geometrię partiami w JSON, ze
          współrzędnymi WGS84. Zachowuje atrybuty źródłowe; odczytuje nazwę,
          adres, położenie, stronę WWW, telefon, e-mail, godziny i opis, jeśli
          występują. Dla noclegów odczytuje też liczbę miejsc, pokoi i
          kategorię, a dla zabytków numer rejestru, datowanie i autora.
          Zachowuje dostępną datę aktualizacji źródła. Odświeżenie następuje
          przy uruchomieniu importu, bez automatycznego harmonogramu. Błędy są
          raportowane; pełna aktualizacja bazy nie publikuje nowej wersji, jeśli
          import źródła się nie powiedzie.
        </p>
        <h2>BIP — Biblioteka Kraków</h2>
        <p>
          <a href="https://www.bip.krakow.pl/?dok_id=83400">
            Wykaz filii Biblioteki Kraków, dok_id=83400
          </a>
          : z tabeli HTML pobieramy nazwę i numer filii, adres, telefon, e-mail
          oraz godziny otwarcia. Dopasowujemy je do miejsc po filii i adresie.
          Pobranie odbywa się przy uruchomieniu importu, bez harmonogramu. Brak
          tabeli lub błąd pobrania zgłaszamy jako błąd importu; poprzednia
          opublikowana baza pozostaje dostępna.
        </p>
        <h2>ZTP — komunikacja miejska</h2>
        <p>
          <a href="https://gtfs.ztp.krakow.pl/">Publiczny serwer GTFS ZTP</a>:
          pliki GTFS_KRK_A.zip, GTFS_KRK_M.zip i GTFS_KRK_T.zip pobieramy przez
          HTTP i odczytujemy zawarte w nich tabele CSV. Wykorzystujemy
          przystanki i ich współrzędne, linie, kursy, kierunki, godziny
          przyjazdów i odjazdów, kalendarze i wyjątki, przebiegi tras, zasady
          przesiadek oraz oznaczenia dostępności przystanków i kursów dla
          wózków.
        </p>
        <p>
          Rozkład odświeżamy przy zapotrzebowaniu, gdy kopia ma ponad 12 godzin,
          lub po ręcznym uruchomieniu importu. Po nieudanej próbie kolejne
          pobranie może nastąpić po 5 minutach. Nowa baza zastępuje starą
          dopiero po poprawnym imporcie wszystkich trzech plików. Przy błędzie
          korzystamy z poprzedniej kopii i pokazujemy ostrzeżenie; kopia starsza
          niż 24 godziny dostaje dodatkowe ostrzeżenie. Bez kopii funkcja
          zależna od rozkładu jest niedostępna.
        </p>
        <p>
          Z tego samego serwera pobieramy pliki TripUpdates_A.pb,
          TripUpdates_M.pb, TripUpdates_T.pb oraz VehiclePositions_A.pb,
          VehiclePositions_M.pb, VehiclePositions_T.pb. To GTFS Realtime w
          formacie Protocol Buffers: aktualizacje kursów, opóźnienia i pozycje
          pojazdów z czasem pomiaru. Pobieramy je na żądanie, z pamięcią
          podręczną na 30 sekund. Odrzucamy dane starsze niż 3 minuty. Bez
          świeżych aktualizacji kursów używamy rozkładu i ostrzegamy;
          niedostępnych pozycji pojazdów nie pokazujemy.
        </p>
        <h2>ZDMK — parkingi OZN</h2>
        <p>
          <a href="https://services-eu1.arcgis.com/svTzSt3AvH7sK6q9/arcgis/rest/services/Miejsca_postojowe_OZN/FeatureServer/0">
            ArcGIS REST: Miejsca_postojowe_OZN, FeatureServer / 0
          </a>
          : z endpointu /query pobieramy JSON partiami do 1000 rekordów, ze
          współrzędnymi WGS84. Wykorzystujemy identyfikator, punkt adresowy i
          położenie miejsc postojowych dla osób z niepełnosprawnościami. Zbiór
          nie dostarcza aplikacji informacji o bieżącym zajęciu parkingu.
        </p>
        <p>
          Odświeżanie działa na żądanie po 12 godzinach lub ręcznie; ponowna
          próba po błędzie jest możliwa po 5 minutach. Zachowujemy poprzednią
          poprawną kopię i pokazujemy ostrzeżenie, także gdy ma ponad 24
          godziny. Bez kopii nie można wyznaczyć wariantu wymagającego parkingu
          OZN.
        </p>
        <h2>ZDMK — prace drogowe</h2>
        <p>
          <a href="https://zdmk.krakow.pl/zestawienie-prac-w-miescie/">
            Zestawienie prac w mieście
          </a>
          : pobieramy{" "}
          <a href="https://www.google.com/maps/d/kml?mid=1_iHhcnIv8THHQSyeLFPArE6k2zhIrtA&amp;forcekml=1">
            publiczny plik KML mapy ZDMK w Google My Maps
          </a>
          . Odczytujemy nazwę, rodzaj prac, lokalizację opisową i punkt na
          mapie, daty „od” i „do” oraz zmiany organizacji ruchu. Zachowujemy też
          pola źródłowe. Import jest uruchamiany ręcznie; dane mają termin
          ważności 24 godziny od pobrania, co nie oznacza automatycznego
          odświeżenia. Błąd pobrania lub pusty plik nie zastępuje poprawnej
          kopii. Punkt remontu nie określa całego obszaru robót ani zamknięcia
          chodnika.
        </p>
        <h2>Strony miejsc, Wikidata i Wikimedia Commons</h2>
        <p>
          Publiczne strony WWW wskazane przy miejscach pobieramy jako HTML. Z
          tekstu i danych strukturalnych odczytujemy opisy, kontakt, godziny
          otwarcia oraz jawne informacje o dostępności. Importer sprawdza je
          ponownie po 7 dniach, przy kolejnym uruchomieniu; nie ma stałego
          harmonogramu. Błędy zapisuje w raporcie i pozostawia wcześniejsze dane
          w bazie.
        </p>
        <p>
          <a href="https://www.wikidata.org/w/api.php">API Wikidata</a>, metoda
          wbgetentities: po identyfikatorach przypisanych w OSM pobieramy
          polskie lub angielskie nazwy i opisy, stronę WWW, telefon, e-mail,
          adres, nazwę pliku zdjęcia, status i numer rejestru zabytku, daty
          powstania i otwarcia, architekta oraz odnośniki do Wikipedii. Dane CC0
          odświeżamy przy uruchomieniu importu; błąd blokuje publikację pełnej
          aktualizacji bazy.
        </p>
        <p>
          <a href="https://commons.wikimedia.org/w/api.php">
            API Wikimedia Commons
          </a>
          , query / imageinfo: dla plików wskazanych przez OSM lub Wikidata
          pobieramy adres obrazu i miniatury, typ pliku, opis, autora, podpis i
          licencję wraz z jej adresem. Metadane odświeżamy przy uruchomieniu
          importu. Nie zastępujemy wcześniejszych danych nieudanym pobraniem.
          Same obrazy przeglądarka ładuje z adresów dostawcy; ich niedostępność
          może oznaczać brak zdjęcia. Licencję i autorstwo podajemy dla
          konkretnego pliku.
        </p>
        <h2>Open-Meteo — pogoda</h2>
        <p>
          <a href="https://api.open-meteo.com/v1/forecast">
            API prognozy Open-Meteo
          </a>
          : dla współrzędnych początku trasy pobieramy JSON z godzinową
          temperaturą, temperaturą odczuwalną, opadem, opadem śniegu, pokrywą
          śnieżną i kodem pogody. Wyliczamy z nich ostrzeżenia o upale, śniegu i
          ryzyku oblodzenia. Pobieramy świeżą prognozę przy planowaniu, bez
          zapisu w bazie i bez kopii na dysku. Przy błędzie pokazujemy
          ostrzeżenie i wynik bez prognozy. Prognoza nie potwierdza stanu
          chodnika.
        </p>
        <h2>Usługi wyświetlania i wyznaczania tras</h2>
        <p>
          <a href="https://tile.openstreetmap.org/">
            Kafelki mapy OpenStreetMap
          </a>
          : przeglądarka pobiera obrazy PNG dla oglądanego obszaru i
          powiększenia podczas korzystania z mapy. Nie prowadzimy osobnego
          harmonogramu aktualizacji; przy błędzie pokazujemy komunikat o
          problemie z mapą.
        </p>
        <p>
          <a href="https://router.project-osrm.org/">OSRM</a>,
          /route/v1/driving: przy planowaniu dojazdu samochodem wysyłamy
          współrzędne początku i końca odcinka. Otrzymujemy geometrię,
          odległość, czas i kroki trasy w JSON. Serwer można zmienić w
          konfiguracji. Nie przechowujemy lokalnej kopii sieci samochodowej ani
          danych o korkach. Gdy usługa nie zwróci trasy, aplikacja może pokazać
          brak wariantu dojazdu.
        </p>
        <p>
          <a href="https://maps.googleapis.com/maps/api/js">
            Google Maps JavaScript API — Places
          </a>
          : jeśli skonfigurowano klucz, przeglądarka pobiera kartę miejsca na
          podstawie jego współrzędnych. Karta może zawierać nazwę, adres,
          godziny, kontakt, zdjęcia, oceny i opinie udostępnione przez Google.
          Jest ładowana przy otwarciu szczegółów miejsca; nie importujemy jej do
          naszej bazy. Bez klucza lub przy błędzie pokazujemy informację o
          niedostępności karty.
        </p>
        <h2>Obserwacje społeczności i aktualność</h2>
        <p>
          Użytkownicy dodają miejsca, opisy barier i udogodnień, pomiary, daty
          obserwacji oraz zdjęcia. Zgłoszenia podlegają weryfikacji; samo
          wysłanie nie czyni informacji potwierdzoną. To dane społeczności, a
          nie miejski zbiór publiczny. Analiza AI pomaga interpretować opisy i
          zdjęcia, lecz nie jest osobnym źródłem faktów o mieście.
        </p>
        <p>
          W szczegółach miejsc pokazujemy źródła i dostępne daty. Data pobrania
          mówi, kiedy odczytano źródło, a nie kiedy ktoś sprawdził miejsce. Brak
          danych, stary opis lub ogólne oznaczenie dostępności nie potwierdzają
          braku barier. Zachowujemy odnośniki i informacje o pochodzeniu; nie
          przypisujemy wszystkim miejskim zbiorom jednej wspólnej licencji.
        </p>
      </div>
    </div>
  );
}

export function Privacy() {
  return (
    <div className="page narrow">
      <PageHeading
        title="Prywatność i bezpieczeństwo"
        description="Jakie dane podajesz, komu są przekazywane i jak chronimy konto oraz zdjęcia."
      />
      <div className="panel prose">
        <h2>Korzystanie bez konta i profil potrzeb</h2>
        <p>
          Miejsca i trasy możesz przeglądać bez logowania. Samodzielnie
          wybierasz wymagania, takie jak brak schodów, szerokość przejścia,
          nachylenie, dostępna toaleta czy odległość między miejscami
          odpoczynku. Nie wymagamy diagnozy ani dokumentacji medycznej. Po
          zalogowaniu możesz zapisywać profile potrzeb i ulubione miejsca oraz
          wysyłać zgłoszenia i wykonywać misje.
        </p>
        <h2>Dane zapisane w aplikacji</h2>
        <p>
          Zapisujemy e-mail, imię lub nazwę użytkownika, zabezpieczony skrót
          hasła, sesje logowania, profile potrzeb, ulubione miejsca, zgłoszenia,
          dodane miejsca, powiązane zdjęcia oraz postęp misji, punkty i
          reputację. Zgłoszenie może zawierać opis, lokalizację, pomiar i datę
          obserwacji. Zweryfikowane informacje o miejscu mogą trafić do jego
          publicznego opisu.
        </p>
        <p>
          W pamięci przeglądarki zapisujemy wybrany język. W pamięci bieżącej
          sesji przechowujemy wynik planowania trasy i informacje o pokazanych
          powiadomieniach misji. Wynik trasy może zawierać wybrane punkty i
          preferencje. Ciasteczko sesji służy do utrzymania logowania.
        </p>
        <h2>Lokalizacja i usługi zewnętrzne</h2>
        <p>
          Lokalizację urządzenia odczytujemy po zgodzie udzielonej w
          przeglądarce, aby znaleźć pobliskie miejsca lub ustawić punkt trasy.
          Możesz odmówić, cofnąć zgodę w przeglądarce albo wskazać punkt
          ręcznie. Planer nie prowadzi ciągłego śledzenia pozycji. Współrzędne
          użyte do wyszukiwania i planowania są przekazywane do naszego serwera.
        </p>
        <p>
          Do Open-Meteo trafiają współrzędne początku trasy, a do
          skonfigurowanego serwera OSRM — punkty odcinka samochodowego. Przy
          włączonej karcie Google Maps współrzędne oglądanego miejsca trafiają
          do Google. Przeglądarka łączy się też bezpośrednio z dostawcą kafelków
          OSM i obrazów miejsc; dostawca otrzymuje żądanie sieciowe, w tym adres
          IP oraz wskazanie pobieranego kafelka lub pliku.
        </p>
        <h2>Analiza opisów przez AI</h2>
        <p>
          Gdy uruchamiasz analizę tekstowego opisu potrzeb, przekazujemy ten
          opis do API OpenAI. Przy interpretacji wyszukiwania miejsca lub trasy
          przekazujemy opis i aktualne wymagania formularza. Odpowiedź proponuje
          ustawienia, które możesz sprawdzić i zmienić. Nie wpisuj do opisu
          danych osobowych ani dokumentacji medycznej. Jeśli analiza jest
          niedostępna, wymagania możesz ustawić ręcznie.
        </p>
        <h2>Zdjęcia: przetwarzanie i dostęp</h2>
        <p>
          Przyjmujemy JPEG, PNG i WebP do 10 MB oraz 20 milionów pikseli.
          Sprawdzamy poprawność pliku, usuwamy metadane, w tym EXIF, i
          zapisujemy obraz jako PNG. Lokalny model wykrywa ludzi, twarze,
          tablice rejestracyjne, tekst, dokumenty i ekrany; wykryte obszary
          zastępujemy jednolitym kolorem. Opis i analiza zdjęcia również
          powstają lokalnie na serwerze.
        </p>
        <p>
          Przy przetwarzaniu w tle obraz bez metadanych jest tymczasowo
          przechowywany w prywatnym pliku przed anonimizacją. Może zostać użyty
          do lokalnej weryfikacji misji. Nie jest udostępniany jako podgląd;
          plik tymczasowy usuwamy po zakończeniu przetwarzania. Jeśli
          anonimizacja się nie powiedzie, zdjęcie jest odrzucane. Błąd tworzenia
          opisu pozostawia zdjęcie do ręcznej weryfikacji.
        </p>
        <p>
          Zdjęcia zgłoszeń może odczytać ich autor i moderator po zalogowaniu.
          Autor może usunąć zdjęcie, o ile nie jest powiązane ze zgłoszeniem.
          Automatyczne wykrywanie może pominąć szczegóły — przed wysłaniem
          unikaj fotografowania danych osobowych i wrażliwych.
        </p>
        <h2>Ochrona konta i operacji zapisu</h2>
        <p>
          Hasła przechowujemy jako skróty PBKDF2-SHA256 z indywidualną losową
          solą i 600 000 iteracji. Sesja wygasa po 24 godzinach; wylogowanie
          unieważnia ją na serwerze. Ciasteczko ma ustawienia HttpOnly i
          SameSite=Lax, a Secure jest domyślnie włączone i zależy od
          konfiguracji wdrożenia.
        </p>
        <p>
          Operacje zapisu wymagające logowania sprawdzają token CSRF, a
          logowanie i rejestracja kontrolują pochodzenie żądania. Ograniczamy
          próby logowania i rejestracji do 10 na minutę na adres IP w obrębie
          procesu serwera. Dostęp do prywatnych zasobów sprawdzamy po
          użytkowniku, a funkcje moderacji wymagają odpowiedniej roli. Pliki
          zdjęć zapisujemy z uprawnieniami ograniczonymi do konta systemowego
          aplikacji.
        </p>
      </div>
    </div>
  );
}
