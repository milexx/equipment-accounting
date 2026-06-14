from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.api.auth import router as auth_router
from app.api.documentation import router as documentation_router
from app.api.equipment import router as equipment_router
from app.api.health import router as health_router
from app.api.region import router as region_router
from app.auth.provider import get_auth_provider
from app.config import settings
from app.database import SessionLocal

app = FastAPI(title="Equipment Accounting", version="0.1.0")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
Path(settings.photo_root).mkdir(parents=True, exist_ok=True)
app.mount("/media/photos", StaticFiles(directory=settings.photo_root), name="photos")

templates = Jinja2Templates(directory="app/templates")

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(documentation_router)
app.include_router(equipment_router)
app.include_router(region_router)


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    with SessionLocal() as db:
        current_user = get_auth_provider().get_current_user(request, db)
    return templates.TemplateResponse(request, "index.html", {"current_user": current_user})
