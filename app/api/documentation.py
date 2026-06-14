from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter(prefix="/documentation", tags=["documentation"])
templates = Jinja2Templates(directory="app/templates")

DOCS_ROOT = Path("docs").resolve()
DOCUMENTS = {
    "business-processes": {
        "title": "Бизнес-процесс системы",
        "description": "Как оборудование проходит путь от ввода регионом до решения центра.",
        "path": DOCS_ROOT / "11_business_processes.md",
    },
    "mvp-plan": {
        "title": "План реализации MVP",
        "description": "Границы MVP, Definition of Done, текущие статусы и очередь работ.",
        "path": DOCS_ROOT / "05_mvp_plan.md",
    },
}


@router.get("", response_class=HTMLResponse)
def documentation_index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "documentation/index.html",
        {"documents": DOCUMENTS},
    )


@router.get("/{document_slug}", response_class=HTMLResponse)
def documentation_page(document_slug: str, request: Request) -> HTMLResponse:
    document = DOCUMENTS.get(document_slug)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    path = document["path"]
    if not path.exists():
        raise HTTPException(status_code=404, detail="Document file not found")

    return templates.TemplateResponse(
        request,
        "documentation/page.html",
        {
            "document": document,
            "content": path.read_text(encoding="utf-8"),
        },
    )
