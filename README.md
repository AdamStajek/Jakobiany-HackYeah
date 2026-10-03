# Swoją Drogą — API

Minimalny szablon FastAPI na Pythonie 3.13. Bez endpointów biznesowych.
Pusty router w `src/hackyeah/main.py` przygotowuje prefiks `/api/v1`.
Nowe routery należy zarejestrować przed `app.include_router(api_router)`.
Kontrakt API: [docs/kontrakt-frontend-backend.md](docs/kontrakt-frontend-backend.md).

## Uruchomienie lokalne

```bash
uv sync
uv run uvicorn hackyeah.main:app --app-dir src --reload
```

## Docker

```bash
docker build -t hackyeah-api .
docker run --rm -p 8000:8000 hackyeah-api
```

Dokumentacja Swagger: http://localhost:8000/docs.
ReDoc: http://localhost:8000/redoc. Schemat: http://localhost:8000/openapi.json.
Ścieżka `/` zwraca `404`, ponieważ szablon nie definiuje endpointów.
Kontener uruchamia aplikację jako użytkownik bez uprawnień roota.
