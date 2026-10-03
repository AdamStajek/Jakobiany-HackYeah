# Swoją Drogą — frontend demonstracyjny

React + TypeScript + Vite + React Router + Lucide. Aplikacja SPA pobiera miejsca i ich fakty z API.

## Docker Compose

Z katalogu głównego: `docker compose up --build -d --wait`.
Frontend: http://localhost:5173; backend: http://localhost:8000/docs.
Kontener serwuje produkcyjną kompilację SPA i przekazuje `/api/` do backendu.
Trasy, zgłoszenia, logowanie i część ustawień nadal mają charakter demonstracyjny.

## Uruchomienie

Wymagane Node.js >=22.12 i npm.

```bash
cd frontend
npm ci
npm run dev
```

Adres: http://localhost:5173. Kompilacja: `npm run build`; podgląd kompilacji: `npm run preview`. Hostowanie produkcyjne wymaga przekierowania nieistniejących ścieżek na `index.html` (routing SPA).

## Sprawdzenie

```bash
npm test
npx playwright install chromium
npm run test:e2e
```

Testy jednostkowe sprawdzają rozróżnienie `null`, `false`, `0`, brak/konflikt/starość danych oraz wymagania. Testy przeglądarkowe obejmują desktop i telefon oraz przepływy demonstracyjne.

## Co działa

- Strona startowa, kategorie OSM oraz wyszukiwanie miejsc z API.
- Wyniki zawierają ocenę i fakty dostępności; szczegóły pokazują źródła, adres, kontakt i informacje pobrane z witryny miejsca.
- Mapa pozostaje schematycznym widokiem współrzędnych OSM.
- Zapisane miejsca, ręczna konfiguracja potrzeb, konto demonstracyjne.
- Stały scenariusz planowania trasy, tekstowe odcinki i ręcznie sterowany podgląd nawigacji; opcjonalny odczyt przez Web Speech API.
- Zgłoszenia i potwierdzenia, wybór lokalnego zdjęcia, misje ze statusem weryfikacji bez naliczania punktów.
- Responsywna nawigacja, etykiety, fokus, powiększony tekst, większy kontrast i respektowanie ograniczenia animacji.

## Dane i przyszła integracja

`src/data/api.ts` zawiera klienta API. `src/data/mock.ts` pozostaje używany przez trasy, zgłoszenia i misje. Wyszukiwanie i szczegóły miejsc nie korzystają już z tej kopii demonstracyjnej.

Wszystkie zapisy są w pamięci karty i znikają po odświeżeniu. Nie zapisujemy danych logowania, opisu potrzeb ani zdjęć w localStorage. Pole pliku przechowuje lokalny `File`, a raport tylko jego nazwę. Nie realizujemy uploadu, analizy AI, moderacji ani geolokalizacji. Konto demo nie zbiera hasła i nie udaje prawdziwej sesji.

Mapa i trasa są schematem demonstracyjnym, bez kartografii OSM, kafli sieciowych i automatycznego routingu. MapLibre można dodać podczas integracji, zachowując tekstowe odpowiedniki. Własne ilustracje SVG znajdują się w `public/illustrations`; nie są zdjęciami rzeczywistych miejsc.

MVP nie obejmuje opinii, dodawania miejsc, nagród ani paneli właściciela/samorządu. Pełna zgodność WCAG 2.2 AA nie jest deklarowana: przed wdrożeniem konieczny jest audyt klawiaturą, czytnikiem ekranu i kontrastów.
