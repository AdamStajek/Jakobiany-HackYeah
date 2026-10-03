# Dostępność — WCAG 2.2 AA

Zakres: interfejs React w `frontend`, strony publiczne, konto, potrzeby,
zgłoszenia, misje, moderacja, wyszukiwanie AI, planowanie i podgląd tras.
Wymagania: [WCAG 2.2, W3C](https://www.w3.org/TR/WCAG22/).

## Uruchomienie weryfikacji

```sh
cd frontend
npm ci
npx playwright install chromium
npm run test:a11y
npm test
npm run build
```

`playwright.accessibility.config.ts` uruchamia API z tymczasową bazą przez
`tests/account_server.py` oraz Vite na porcie 5337. Testy nie modyfikują
produkcyjnej bazy. Istniejące serwery testowe można ponownie wykorzystać lokalnie;
CI uruchamia własne procesy. Wyniki, zrzuty i ślady błędów trafiają do
`frontend/a11y-results`, oddzielnie od pozostałych testów Playwright.
Scenariusze AI, mobilności i planowania używają kontrolowanych odpowiedzi API.

Zestaw ma dziewięć scenariuszy na czterech szerokościach: 1440, 768, 390 i 320 px.
Skan axe obejmuje reguły WCAG A/AA 2.0, 2.1, 2.2 oraz dobre praktyki.
Dodatkowe testy sprawdzają rzeczywistą obsługę klawiaturą i układ strony.

## Zrealizowane poprawki

| Obszar | Kryteria | Zmiana i sposób sprawdzenia |
| --- | --- | --- |
| Obrazy i linki | 1.1.1, 2.4.4, 2.5.3, 4.1.2 | Linki do miejsc mają nazwy również bez zdjęcia. Zdjęcia korzystają z opisu źródłowego, a dowody z opisu zgłoszenia; przy uploadzie zdjęcia zgłoszenie wymaga opisu. |
| Formularze | 1.3.1, 1.3.5, 3.3.1–3.3.3 | Etykiety są oddzielone od wskazówek przez `aria-labelledby` i `aria-describedby`. Dodano instrukcję minimalnej długości odpowiedzi, identyfikację błędnych pól i fokus na polu wymagającym poprawy. Imię ma `autocomplete="given-name"`. |
| Kontrast | 1.4.1, 1.4.3, 1.4.11 | Przyciemniono tekst ostrzeżeń, punktów, opisów i nawigacji mobilnej. Naprawiono kontrast instrukcji nawigacji. Linki w treści są podkreślone; obramowania pól i przycisków mają kontrast ponad 3:1. |
| Powiększenie i układ | 1.4.4, 1.4.10, 1.4.12 | Usunięto wymuszone przewijanie zakładek i przepełnianie kolumn. Nagłówek i kontrolki mogą się zawijać; sekcja startowa rośnie z tekstem. Testy obejmują 320 px, tekst 200% oraz odstępy 1.5/0.12em/0.16em/2em. |
| Klawiatura i fokus | 2.1.1, 2.1.2, 2.4.1, 2.4.3, 2.4.7, 2.4.11 | Zakładki obsługują strzałki, Home i End z pojedynczym aktywnym tabulatorem. Menu zamyka Escape. Mapa obsługuje Enter i spację na znacznikach, wybór środka klawiszem Enter oraz anulowanie przez Escape. Zamknięcie szczegółów znacznika przywraca fokus. Testy przechodzą przez elementy Tab i sprawdzają, czy nie są całkowicie zasłonięte. |
| Nawigacja SPA i kroki | 2.4.2, 2.4.3, 4.1.3 | Tytuł dokumentu odpowiada nagłówkowi strony; przy przejściu na nową stronę fokus trafia do jej nagłówka. Zmiana kroku profilu kieruje fokus na treść nowego kroku, a krok ma `aria-current`. Instrukcje nawigacji i stany misji są ogłaszane. |
| Mapa i ruch | 2.5.1, 2.5.7, 2.5.8 | Dodano przyciski przesuwania mapy jako alternatywę dla przeciągania. Punkty można wybrać również przez wyszukiwanie lub środek mapy. Przystanki, pojazdy i parkingi mają listę tekstową. Znaczniki przystanków mają co najmniej 24 × 24 px, a przyciski mapy 44 × 44 px. |
| Komunikaty i aktualizacje | 2.2.1, 2.2.2, 4.1.3 | Komunikaty pozostają do zamknięcia i nie zasłaniają treści jako stała nakładka. Użytkownik może zatrzymać aktualizację pojazdów bez utraty aktualnie wyświetlanych danych. Test używa zegara Playwright. |
| Język | 3.1.1, 3.1.2 | Przełącznik zmienia język dokumentu. Teksty przetłumaczone mają język angielski, a nieprzetłumaczone polskie fragmenty zachowują `lang="pl"`. Nazwy miejsc nie są automatycznie tłumaczone. |
| Uwierzytelnianie | 3.3.8 | Pozostawiono natywne pola i autouzupełnianie e-maila oraz hasła, bez blokowania wklejania i menedżerów haseł. Nie wprowadzono testów pamięci ani CAPTCHA. |
| Preferencje | 1.4.3, 1.4.4 | Sprawdzono większy tekst i zwiększony kontrast oraz respektowanie `prefers-reduced-motion`. |

Przykładowe kontrasty po poprawkach: ostrzeżenia `#805000` na `#fff1dc` — 6.16:1;
przygaszony tekst `#526565` na `#f1f0e7` — 5.39:1;
obramowanie pól `#456b62` na `#fbfcf9` — 5.77:1.

## Granice potwierdzenia

Brak błędów axe i poprawny przebieg Playwright potwierdzają objęte nimi reguły
oraz scenariusze. Nie stanowią deklaracji pełnej zgodności WCAG dla wszystkich
możliwych danych, stanów i technologii asystujących.

Do oceny ręcznej pozostają: użyteczność z NVDA/Firefox i VoiceOver/Safari,
jakość opisów rzeczywistych zdjęć i treści użytkowników, komunikaty walidacji
w różnych przeglądarkach oraz powiększenie przeglądarki i skala systemowa.
Istniejące zdjęcia bez opisu wymagają uzupełnienia przez autora; nazwę pliku
traktujemy jako fallback, a nie dowód jakości tekstu alternatywnego.

Aplikacja nie zawiera nagrań wideo ani automatycznie odtwarzanego audio; opcjonalny
odczyt instrukcji jest uruchamiany przez użytkownika. Kryteria dotyczące takich
nagrań są nieadekwatne do sprawdzonych widoków. Wnioski o pozostałych kryteriach,
których nie rozstrzyga automatyzacja, wymagają oceny pełnych procesów użytkownika.
