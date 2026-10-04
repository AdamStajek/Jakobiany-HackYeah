# Swoją Drogą — frontend

React + TypeScript + Vite + React Router + Lucide. Aplikacja SPA pobiera miejsca i ich fakty z API.

## Docker Compose

Z katalogu głównego: `docker compose up --build -d --wait`.
Frontend: http://localhost:5173; backend: http://localhost:8000/docs.
Kontener serwuje produkcyjną kompilację SPA i przekazuje `/api/` do backendu.
Planowanie tras korzysta z API i sieci pieszej całego Krakowa z OSM. Przygotowanie grafu opisuje [planowanie miejskie](../docs/city-routing.md). Konta, profile, zapisane miejsca, zgłoszenia, zdjęcia i misje korzystają z API oraz trwałego zapisu SQLite.

## Uruchomienie

Wymagane Node.js >=22.12 i npm.

```bash
cd frontend
npm ci
npm run dev
```

Adres: http://localhost:5173. Serwer Vite przekazuje `/api/` do backendu na http://127.0.0.1:8000 — uruchom go równolegle. Kompilacja: `npm run build`; podgląd kompilacji: `npm run preview`. Hostowanie produkcyjne wymaga przekierowania nieistniejących ścieżek na `index.html` (routing SPA).

## Sprawdzenie

```bash
npm test
npx playwright install chromium
npm run test:e2e
npm run test:account
npm run test:a11y
npm run test:ux
```

Testy jednostkowe sprawdzają rozróżnienie `null`, `false`, `0`, brak/konflikt/starość danych oraz wymagania. `test:account` uruchamia frontend i API z tymczasową bazą oraz testowym modelem interpretacji. Sprawdza na komputerze i telefonie rejestrację, logowanie, zapis profilu, upload zdjęcia, zgłoszenie i przyznanie punktów po weryfikacji; nie korzysta z produkcyjnej bazy ani płatnego API.

`test:a11y` sprawdza reguły WCAG A/AA przez axe oraz klawiaturę, fokus, formularze, mapę i reflow w Playwright na szerokościach 1440, 768, 390 i 320 px. Zakres poprawek i ograniczenia automatycznej oceny opisuje [raport dostępności](../docs/wcag-2.2-aa.md).

`test:ux` sprawdza układy na szerokościach 320, 390, 768, 940, 1024 i 1440 px, równe kafelki kategorii, menu, filtry, ocenę dostępności, znaczniki mapy i wyszukiwanie AI. Przechodzi również rejestrację z powrotem do dodawania miejsca i wybór współrzędnych na mapie. Zrzuty ekranów trafiają do `ux-results/`. Testy używają tymczasowej bazy API; kafle OSM są celowo blokowane, aby sprawdzić też komunikat awarii mapy.

## Co działa

- Strona startowa, kategorie OSM oraz wyszukiwanie miejsc z API.
- Wyniki zawierają ocenę i fakty dostępności; szczegóły pokazują źródła, adres, kontakt i informacje pobrane z witryny miejsca.
- Interaktywna mapa Leaflet z kaflami OpenStreetMap, znacznikami i geometrią tras z API.
- Rejestracja, logowanie, wylogowanie i odtwarzanie sesji z cookie HttpOnly.
- Trwały zapis potrzeb i miejsc na koncie. Gość może ustawić wymagania w bieżącej karcie.
- Interpretacja opisu potrzeb przez API, z możliwością poprawienia i zatwierdzenia propozycji oraz ręcznego ustawienia wymagań przy awarii usługi.
- Planowanie przez `POST /api/v1/routes/plan`: wybór punktów i ograniczeń, geometria, długość, czas, fakty i ostrzeżenia z backendu. Szczegóły i ręczny podgląd nawigacji korzystają z tej samej obliczonej trasy; opcjonalny odczyt przez Web Speech API.
- Wysyłanie zgłoszeń, potwierdzeń i prywatnych zdjęć; odczyt historii oraz decyzji moderatora.
- Misje oparte na rzeczywistych miejscach: trwały postęp, odpowiedzi, odrzucenie i ponowne zgłoszenie oraz punkty naliczane jednokrotnie po akceptacji przez niezależnego moderatora.
- Panel moderatora `/review`, dostępny z profilu konta z rolą `moderator`. Nadawanie roli opisuje [README backendu](../README.md).
- Responsywna nawigacja, etykiety, fokus, powiększony tekst, większy kontrast i respektowanie ograniczenia animacji.

## Dane i zapis

`src/data/api.ts` zawiera klienta API. Miejsca, zgłoszenia i misje pobierają rzeczywiste rekordy z backendu. Z `src/data/mock.ts` interfejs wykorzystuje wspólne etykiety i formatowanie faktów.

Obliczona trasa jest przechowywana w sessionStorage bieżącej karty. Dane konta pozostają w SQLite po odświeżeniu, wylogowaniu i restarcie backendu. Hasła i CSRF nie są zapisywane w localStorage. Zdjęcia są przesyłane jako multipart, dekodowane i pozbawiane metadanych; podgląd wymaga sesji autora lub moderatora. Opis potrzeb jest interpretowany przez API, a profil zapisuje się dopiero po zatwierdzeniu. Podgląd nawigacji nie śledzi pozycji.

Mapa pobiera kafle OpenStreetMap. Planer oblicza trasy dla całego Krakowa, minimalizując niedogodności z zatwierdzonego profilu. Początek i cel można wyszukać po nazwie/adresie lub wskazać na mapie. Znane naruszenia i braki danych są jawne; niepołączone punkty zwracają pusty wynik. Szczegóły i ograniczenia opisuje [planowanie miejskie](../docs/city-routing.md). Własne ilustracje SVG znajdują się w `public/illustrations`; nie są zdjęciami rzeczywistych miejsc.

Interfejs nie udostępnia opinii, wymiany punktów na zniżki ani paneli właściciela/samorządu. Dodawanie miejsc i ich moderacja są objęte testami dostępności. Pełna zgodność WCAG 2.2 AA wymaga osobnego badania.
