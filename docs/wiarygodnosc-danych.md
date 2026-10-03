# Wiarygodność informacji

Każda konkretna wartość faktu w bazie, np. `steps_count = 2`, ma wynik punktowy
i jeden z trzech poziomów wiarygodności. Punkty są sumą aktualnych dowodów,
które potwierdzają tę samą wartość.

## Liczenie punktów

Dla dowodu w wieku `w` pełnych tygodni stosujemy mnożnik czasu:

```text
time_factor = 0.9 ^ w
```

Wiek liczymy od `observed_at`, a gdy go nie podano — od `created_at` lub czasu
pobrania danych mapowych. Każdy dowód starzeje się osobno.

| Dowód | Punkty przed uwzględnieniem czasu |
| --- | ---: |
| Zgłoszenie właściciela | `15` |
| Zgłoszenie użytkownika | `5 * x * y` |
| Dane z map | `5` |

`x` to wiarygodność autora wyliczona z historii jego rozpatrzonych zgłoszeń,
w zakresie od `0` do `1`: liczba przyjętych zgłoszeń podzielona przez liczbę
wszystkich rozpatrzonych zgłoszeń. Użytkownik bez historii otrzymuje `x = 0.5`.
`y = 1`, gdy zgłoszenie zawiera zdjęcie, a analiza AI potwierdziła zgłaszaną
wartość; w każdym innym przypadku `y = 0.25`.

Łączny wkład wszystkich zgłoszeń użytkowników jest ograniczony do 15 punktów:

```text
user_points = min(15, sum(5 * x_i * y_i * 0.9 ^ w_i))

score =
    sum(15 * 0.9 ^ w_i for owner reports)
    + user_points
    + sum(5 * 0.9 ^ w_i for map evidence)
```

Do wyniku wliczamy wyłącznie przyjęte zgłoszenia i aktualnie używane dane
mapowe. Odrzucone i oczekujące zgłoszenia nie dodają punktów. Dowody dotyczące
innej wartości tego samego atrybutu są liczone dla tej innej wartości, zamiast
podwyższać wynik informacji sprzecznej.

## Poziomy

| Wynik | Wartość w bazie | Etykieta |
| ---: | --- | --- |
| `> 10` | `certain` | pewne |
| `> 5` i `<= 10` | `probable` | prawdopodobne |
| `<= 5` | `uncertain` | niepewne |

Wynik przechowujemy bez zaokrąglania; zaokrąglenie służy wyłącznie do
prezentacji. Dzięki temu wartości graniczne 5 i 10 zawsze trafiają do właściwej
kategorii.

## Zapis i odświeżanie

Tabela faktów przechowuje co najmniej:

- `confidence_score` — bieżący wynik punktowy,
- `confidence_level` — `certain | probable | uncertain`,
- `confidence_calculated_at` — czas ostatniego przeliczenia.

Dowód przechowuje typ źródła, czas obserwacji, identyfikator autora dla
zgłoszeń użytkowników oraz informację, czy zdjęcie potwierdziła analiza AI.
W czasie przeliczenia zapisujemy też użyte `x` i `y`, aby wynik był możliwy do
sprawdzenia.

Wynik jest przeliczany:

1. natychmiast po przyjęciu, zmianie lub odrzuceniu zgłoszenia oraz po zmianie
   wyniku analizy zdjęcia;
2. po imporcie lub zmianie danych mapowych;
3. raz dziennie dla wszystkich faktów przez idempotentny skrypt uruchamiany
   z harmonogramu.

Polecenie przeznaczone do dziennego harmonogramu:

```bash
PYTHONPATH=src python -m scripts.update_confidence --database data/krakow.sqlite3
```

Przeliczenie wyniku i zapis poziomu odbywają się w tej samej transakcji.
