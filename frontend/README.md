# Swoją Drogą — frontend demonstracyjny

React + TypeScript + Vite + React Router + Lucide. Samodzielna aplikacja SPA w języku polskim, inspirowana projektami w `docs/UI`. Nie uruchamia ani nie wywołuje backendu.

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

Testy jednostkowe sprawdzają rozróżnienie `null`, `false`, `0`, brak/konflikt/starość danych oraz wymagania. Testy przeglądarkowe obejmują desktop i telefon: profil, wyszukiwanie, zgłoszenia, trasy, misje, szerokość ekranów i brak wywołań API.

## Co działa

- Strona startowa, kategorie, wyszukiwanie, filtrowanie i sortowanie.
- Równoważna lista miejsc i mapa schematyczna ze znacznikami.
- Szczegóły i źródła faktów, z datą oraz wiarygodnością; brakujące, sprzeczne i stare dane.
- Zapisane miejsca, ręczna konfiguracja potrzeb, konto demonstracyjne.
- Stały scenariusz planowania trasy, tekstowe odcinki i ręcznie sterowany podgląd nawigacji; opcjonalny odczyt przez Web Speech API.
- Zgłoszenia i potwierdzenia, wybór lokalnego zdjęcia, misje ze statusem weryfikacji bez naliczania punktów.
- Responsywna nawigacja, etykiety, fokus, powiększony tekst, większy kontrast i respektowanie ograniczenia animacji.

## Dane i przyszła integracja

`src/data/types.ts` opisuje używany podzbiór kontraktu. `src/data/mock.ts` zawiera przykładowe fakty i ocenę **wyłącznie demonstracyjną**. API ma docelowo dostarczać `Assessment`, wiarygodność i trasę; lokalnego algorytmu nie należy przenosić do integracji. Pola `demo`, `alternatives` i lokalny `Report` są modelami widoku, nie DTO serwera. Nie ma fałszywego klienta HTTP ani przełącznika uruchamiającego niegotowe API.

Wszystkie zapisy są w pamięci karty i znikają po odświeżeniu. Nie zapisujemy danych logowania, opisu potrzeb ani zdjęć w localStorage. Pole pliku przechowuje lokalny `File`, a raport tylko jego nazwę. Nie realizujemy uploadu, analizy AI, moderacji ani geolokalizacji. Konto demo nie zbiera hasła i nie udaje prawdziwej sesji.

Mapa i trasa są schematem demonstracyjnym, bez kartografii OSM, kafli sieciowych i automatycznego routingu. MapLibre można dodać podczas integracji, zachowując tekstowe odpowiedniki. Własne ilustracje SVG znajdują się w `public/illustrations`; nie są zdjęciami rzeczywistych miejsc.

MVP nie obejmuje opinii, dodawania miejsc, nagród ani paneli właściciela/samorządu. Pełna zgodność WCAG 2.2 AA nie jest deklarowana: przed wdrożeniem konieczny jest audyt klawiaturą, czytnikiem ekranu i kontrastów.
