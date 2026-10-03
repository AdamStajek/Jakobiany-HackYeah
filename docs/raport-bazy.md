# Raport bazy miejsc — Kraków

Stan bazy: 7 314 miejsc. Dane pochodzą z OpenStreetMap; wyciąg źródłowy z 2 października 2026, import do bazy z 3 października 2026. Miejscem nazywam tu obiekt zapisany w tabeli `places`, niekoniecznie odrębną placówkę.

## Miejsca według typu

| Typ | Liczba miejsc |
| --- | ---: |
| Zabytki | 1 947 |
| Sklepy spożywcze | 1 303 |
| Hotele | 266 |
| Urzędy | 138 |
| Banki | 136 |
| Poczty | 130 |
| Domy kultury | 94 |
| Muzea | 90 |
| Biblioteki | 87 |
| Punkty widokowe | 63 |
| Teatry | 33 |
| Kina | 12 |
| Kluby seniora | 2 |

Typy mogą się nakładać, dlatego ich liczby nie sumują się do liczby unikalnych miejsc. Nazwę ma 3 122 miejsc.

## Dane dostępności z modelu

W bazie nie ma kompletu pięciu podstawowych informacji (schody, próg, winda, szerokość wejścia, dostępna toaleta) dla żadnego miejsca. Poniżej podaję, ile miejsc ma znaną wartość poszczególnego atrybutu z `Attribute` w modelu. Wartości w bazie nadal mają status niepotwierdzony.

| Atrybut | Miejsca ze znaną wartością | Znane wartości |
| --- | ---: | --- |
| `steps_count` | 1 | 1: 1 miejsce |
| `steps_present` | 0 | brak |
| `threshold_height_cm` | 0 | brak |
| `kerb_height_cm` | 0 | brak |
| `raised_kerb` | 0 | brak |
| `lighting_available` | 0 | brak |
| `smoothness` | 0 | brak |
| `entrance_width_cm` | 2 | 153 cm: 1; 300 cm: 1 |
| `slope_percent` | 0 | brak |
| `ramp_available` | 0 | brak |
| `elevator_available` | 3 | dostępna: 3 |
| `accessible_toilet` | 30 | tak: 16; nie: 14; dodatkowo 1 wartość w konflikcie źródeł |
| `rest_area_available` | 91 | dostępne: 91 |
| `surface` | 13 | fine_gravel: 5; grass: 4; asphalt, concrete, paved, paving_stones: po 1 |
| `distance_without_rest_m` | 0 | brak |
| `heat_risk` | 0 | brak |
| `icing_risk` | 0 | brak |
| `snow_risk` | 0 | brak |
| `construction_present` | 0 | brak |

Dla `steps_count`, `threshold_height_cm`, `entrance_width_cm`, `ramp_available`, `elevator_available`, `accessible_toilet`, `rest_area_available`, `surface` i `slope_percent` baza ma rekord faktu dla każdego z 7 314 miejsc; brak znanej wartości jest zapisany jako brak danych. Pozostałe atrybuty modelu nie mają obecnie rekordów w tabeli faktów tej bazy. Liczba potwierdzonych terenowo wartości: 0.

## Inne dane miejsc

| Informacja | Miejsca |
| --- | ---: |
| Nazwa | 3 122 |
| Ulica i numer | 1 160 |
| Strona internetowa | 1 066 |
| Telefon | 335 |
| Godziny otwarcia | 1 288 |
| Jawny `access=private` lub `access=no` | 88 |

Pokrycie pól dostępności z modelu: 126 miejsc ma co najmniej jeden znany atrybut (liczniki pól nakładają się). Dane OSM i powiązane obiekty są wskazówkami, nie potwierdzeniem dostępności na miejscu.
