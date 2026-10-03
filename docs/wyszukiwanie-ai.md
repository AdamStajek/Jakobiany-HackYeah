# Wyszukiwanie AI w planerach

Planer miejsc i planer tras udostępniają pole opisu oraz przyciski „Przygotuj wyszukiwanie” i „Zastosuj wyszukiwanie”. Po zastosowaniu można poprawić filtry. W planerze tras należy wybrać konkretne punkty z wyników katalogu albo na mapie, a następnie nacisnąć „Pokaż trasę”.

Backend korzysta z dwóch agentów PydanticAI w `src/hackyeah/search_ai.py`. Klucz `OPENAI_API_KEY` jest ładowany z głównego `.env` wyłącznie na serwerze. Model wybiera `OPENAI_MODEL`, zgodnie z konfiguracją istniejącego agenta potrzeb. Nowe zależności nie są wymagane.

Endpointy:

- `POST /api/v1/places/interpret`: zwraca `query`, `constraints`, `summary`, `questions`.
- `POST /api/v1/routes/interpret`: zwraca `origin_query`, `destination_query`, `constraints`, `summary`, `questions`.

Oba przyjmują `{ "description": "opis do 4000 znaków", "constraints": { ... } }`. Wymagania mają istniejący schemat `Constraints`. Niepodany punkt trasy ma wartość `null` i zachowuje aktualny wybór w formularzu. Wyszukiwanie bez nazwy lub kategorii używa `*`.

AI przygotowuje parametry wyszukiwania, a wyniki miejsc i trasy pochodzą z dotychczasowych endpointów oraz danych katalogu. Propozycja nie potwierdza dostępności miejsca. Odpowiedzi mają `Cache-Control: no-store`; brak klucza lub błąd dostawcy zwraca `503 DEPENDENCY_UNAVAILABLE` bez ujawniania danych wejściowych.

Testy: `PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -p 'test_search_ai.py'`.
