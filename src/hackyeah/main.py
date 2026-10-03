from fastapi import APIRouter, FastAPI

app = FastAPI(title="Swoją Drogą API", version="0.1.0")

api_router = APIRouter(prefix="/api/v1")
app.include_router(api_router)
