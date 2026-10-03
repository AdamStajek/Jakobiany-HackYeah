import { Link } from "react-router-dom";
import { PageHeading } from "../components/Common";

export function PublicData() {
  return (
    <div className="page narrow">
      <PageHeading title="Dane publiczne" description="Skąd pobieramy dane i co robimy, gdy źródło nie odpowiada." />
      <div className="panel prose">
        <h2>Otwarte źródła, jasne zasady</h2>
        <p>Korzystamy z publicznych danych i usług na warunkach ich dostawców, z zachowaniem autorstwa, licencji i limitów pobierania. Nie potrzebujemy dostępu do wewnętrznych systemów Urzędu Miasta Krakowa ani miejskich jednostek.</p>
        <h2>Miejsca i sieć piesza</h2>
        <p><a href="https://download.geofabrik.de/europe/poland/malopolskie.html">OpenStreetMap — wyciąg Małopolski</a> pobieramy jako plik PBF, a granicę Krakowa z publicznego API OSM. Dane wykorzystujemy zgodnie z <a href="https://www.openstreetmap.org/copyright">licencją ODbL</a>. Aktualizacja odbywa się przy uruchomieniu importu; obecnie nie ma automatycznego harmonogramu.</p>
        <h2>Konkretne dane miejskie</h2>
        <p><a href="https://msip.um.krakow.pl/arcgis/rest/services/Obserwatorium/">MSIP — publiczne API ArcGIS REST</a>: toalety (WT_WC_2023), kultura (K17_KULTURA, Miejskie_Instytucje_Kultury), noclegi (WT_OBIEKTY_HOTELOWE_KOH, WT_OBIEKTY_NOCLEGOWE_KON), zabytki (zabytki_do_pobrania) i aktywność (jestemAKTYWNY). Warstwy pobieramy partiami jako JSON. Dane filii Biblioteki Kraków odczytujemy z <a href="https://www.bip.krakow.pl/?dok_id=83400">publicznej strony BIP</a>. Oba źródła odświeżamy przy uruchomieniu importu, zgodnie z warunkami portali; nie zakładamy wspólnej otwartej licencji.</p>
        <p><a href="https://zdmk.krakow.pl/zestawienie-prac-w-miescie/">ZDMK — prace w mieście</a>: pobieramy publiczny plik KML mapy remontów przy uruchomieniu importu. Po 24 godzinach od pobrania dane wymagają odświeżenia. Brak jawnej licencji nie oznacza dowolności ponownego użycia.</p>
        <h2>Pozostałe informacje</h2>
        <p>Opisy uzupełniamy z publicznych stron miejsc i API Wikidata (CC0), a zdjęcia z API Wikimedia Commons z licencją i autorem konkretnego pliku. Strony miejsc przy kolejnym imporcie odświeżamy po 7 dniach; Wikidata i Commons przy uruchomieniu importu. Prognozę <a href="https://open-meteo.com/en/terms">Open-Meteo</a> pobieramy z API przy każdym planowaniu trasy, na warunkach dostawcy i z atrybucją.</p>
        <h2>Gdy źródło jest niedostępne</h2>
        <p>Zachowujemy wcześniejszą kopię danych bez zmiany daty pobrania. Nie obchodzimy blokad dostawcy. Jeśli pogoda nie odpowiada, pokazujemy ostrzeżenie i trasę bez prognozy. Starsze dane i brak informacji nie są potwierdzeniem dostępności.</p>
        <Link className="text-button" to="/data-quality">Jak czytać źródła i daty →</Link>
      </div>
    </div>
  );
}

export function Privacy() {
  return (
    <div className="page narrow">
      <PageHeading title="Prywatność i bezpieczeństwo" description="Dopasowujemy wyniki do Twoich preferencji, bez pytania o diagnozę." />
      <div className="panel prose">
        <h2>Ty wybierasz, co podajesz</h2>
        <p>Miejsca i trasy możesz przeglądać bez konta. Do dopasowania wystarczą preferencje: schody, szerokość przejścia, podjazdy czy miejsca odpoczynku. Nie wymagamy informacji o niepełnosprawności ani dokumentacji medycznej.</p>
        <h2>Co zapisujemy</h2>
        <p>Konto zawiera e-mail, nazwę użytkownika i zabezpieczone hasło. Zapisujemy też wybrane potrzeby, ulubione miejsca, zgłoszenia i postępy misji. Zgłoszenie może zawierać opis, miejsce i dodane przez Ciebie zdjęcia. Nie umieszczaj w nim danych wrażliwych ani danych innych osób.</p>
        <p>Lokalizację odczytujemy tylko za zgodą przeglądarki, aby pokazać pobliskie miejsca. Możesz odmówić lub cofnąć zgodę. Przy wyszukiwaniu i planowaniu trasy współrzędne są przekazywane do usługi; do prognozy trafia punkt początku trasy.</p>
        <h2>Ochrona kont i zgłoszeń</h2>
        <p>Hasła zapisujemy jako skróty z indywidualną solą. Sesja korzysta z ciasteczka HttpOnly, a operacje zapisu mają ochronę przed CSRF. Ograniczamy liczbę prób logowania. Dostęp do danych konta wymaga uwierzytelnienia; zdjęcia zgłoszeń widzą ich autor i moderatorzy.</p>
        <h2>Bezpieczne połączenia</h2>
        <p>Publiczne wdrożenie wymaga HTTPS i ciasteczek Secure. Publiczne źródła pobieramy przez HTTPS. Te zasady dotyczą także przesyłania danych konta i zgłoszeń.</p>
      </div>
    </div>
  );
}

export function DataQuality() {
  return (
    <div className="page narrow">
      <PageHeading title="Źródła i aktualność" description="Źródło i data pomagają ocenić informację przed wyjściem." />
      <div className="panel prose">
        <h2>Skąd pochodzi informacja?</h2>
        <p>W szczegółach miejsca sprawdzisz źródła danych: OpenStreetMap, miejskie zbiory, stronę miejsca lub zgłoszenie. Odnośnik pozwala zajrzeć do oryginału. Zdjęcia mają osobne informacje o autorze i licencji.</p>
        <h2>Pobranie a potwierdzenie</h2>
        <p>Data pobrania mówi, kiedy odczytaliśmy źródło. Data potwierdzenia mówi, kiedy informację zweryfikowano. Pobranie starego opisu nie oznacza nowego pomiaru. Jeśli daty lub pomiaru nie znamy, nie dopisujemy ich na podstawie zdjęć ani ogólnego opisu „dostępne”.</p>
        <h2>Braki i rozbieżności</h2>
        <p>Brak danych nie oznacza braku bariery. Informacje niepotwierdzone, sprzeczne lub nieaktualne wymagają ostrożności. Prognoza pogody nie potwierdza stanu chodnika, a punkt remontu nie określa całego zasięgu prac.</p>
        <h2>Pomóż uzupełnić dane</h2>
        <p>Jeśli na miejscu jest inaczej, zgłoś konkretną barierę lub udogodnienie. Podaj datę obserwacji i, jeśli możesz, pomiar lub zdjęcie. Zgłoszenie wymaga weryfikacji, zanim stanie się potwierdzoną informacją.</p>
        <Link className="button primary" to="/report">Zgłoś zmianę</Link>
      </div>
    </div>
  );
}
