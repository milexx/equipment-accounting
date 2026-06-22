import html
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from markupsafe import Markup

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
    "operator-admin-guide": {
        "title": "Инструкция оператора и администратора",
        "description": "Краткая инструкция по работе региона, центра и администратора.",
        "path": DOCS_ROOT / "12_operator_admin_guide.md",
    },
    "tech-stack": {
        "title": "Техстек системы",
        "description": "Backend, база данных, frontend, хранение фото, авторизация и проверки.",
        "path": DOCS_ROOT / "13_tech_stack.md",
    },
    "demo-deployment-scheme": {
        "title": "Схема разработки и развертывания",
        "description": "Как гибридная разработка, Git, демо VPS и будущий корпоративный контур связаны между собой.",
        "path": DOCS_ROOT / "55_demo_deployment_scheme.md",
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
            "content_html": render_markdown(path.read_text(encoding="utf-8")),
        },
    )


def render_markdown(markdown: str) -> Markup:
    html_parts: list[str] = []
    paragraph: list[str] = []
    list_type: str | None = None
    in_code = False
    code_lines: list[str] = []
    lines = markdown.splitlines()
    index = 0

    def flush_paragraph() -> None:
        if paragraph:
            html_parts.append(f"<p>{inline_format(' '.join(paragraph))}</p>")
            paragraph.clear()

    def close_list() -> None:
        nonlocal list_type
        if list_type:
            html_parts.append(f"</{list_type}>")
            list_type = None

    def open_list(tag: str) -> None:
        nonlocal list_type
        if list_type != tag:
            close_list()
            html_parts.append(f"<{tag}>")
            list_type = tag

    while index < len(lines):
        line = lines[index]
        stripped = line.strip()

        if stripped.startswith("```"):
            flush_paragraph()
            close_list()
            if in_code:
                html_parts.append(f"<pre><code>{html.escape(chr(10).join(code_lines))}</code></pre>")
                code_lines.clear()
                in_code = False
            else:
                in_code = True
            index += 1
            continue

        if in_code:
            code_lines.append(line)
            index += 1
            continue

        if not stripped:
            flush_paragraph()
            close_list()
            index += 1
            continue

        if is_table_start(lines, index):
            flush_paragraph()
            close_list()
            table_html, next_index = render_table(lines, index)
            html_parts.append(table_html)
            index = next_index
            continue

        image = re.match(r"^!\[([^\]]*)\]\(([^)]+)\)$", stripped)
        if image:
            flush_paragraph()
            close_list()
            html_parts.append(render_image(image.group(1), image.group(2)))
            index += 1
            continue

        heading = re.match(r"^(#{1,4})\s+(.+)$", stripped)
        if heading:
            flush_paragraph()
            close_list()
            level = len(heading.group(1))
            html_parts.append(f"<h{level}>{inline_format(heading.group(2))}</h{level}>")
            index += 1
            continue

        unordered = re.match(r"^[-*]\s+(.+)$", stripped)
        if unordered:
            flush_paragraph()
            open_list("ul")
            html_parts.append(f"<li>{inline_format(unordered.group(1))}</li>")
            index += 1
            continue

        ordered = re.match(r"^\d+\.\s+(.+)$", stripped)
        if ordered:
            flush_paragraph()
            open_list("ol")
            html_parts.append(f"<li>{inline_format(ordered.group(1))}</li>")
            index += 1
            continue

        close_list()
        paragraph.append(stripped)
        index += 1

    flush_paragraph()
    close_list()
    if in_code:
        html_parts.append(f"<pre><code>{html.escape(chr(10).join(code_lines))}</code></pre>")
    return Markup("\n".join(html_parts))


def inline_format(text: str) -> str:
    escaped = html.escape(text)
    escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
    return escaped


def render_image(alt: str, source: str) -> str:
    return (
        '<figure class="documentation-figure">'
        f'<img src="{html.escape(source, quote=True)}" alt="{html.escape(alt, quote=True)}">'
        f"<figcaption>{inline_format(alt)}</figcaption>"
        "</figure>"
    )


def is_table_start(lines: list[str], index: int) -> bool:
    if index + 1 >= len(lines):
        return False
    current = lines[index].strip()
    separator = lines[index + 1].strip()
    return current.startswith("|") and current.endswith("|") and bool(
        re.match(r"^\|[\s:|-]+\|$", separator)
    )


def render_table(lines: list[str], index: int) -> tuple[str, int]:
    headers = split_table_row(lines[index])
    index += 2
    rows: list[list[str]] = []
    while index < len(lines):
        stripped = lines[index].strip()
        if not (stripped.startswith("|") and stripped.endswith("|")):
            break
        rows.append(split_table_row(stripped))
        index += 1

    parts = ["<div class=\"markdown-table-wrap\"><table class=\"markdown-table\"><thead><tr>"]
    for header in headers:
        parts.append(f"<th>{inline_format(header)}</th>")
    parts.append("</tr></thead><tbody>")
    for row in rows:
        parts.append("<tr>")
        for cell in row:
            parts.append(f"<td>{inline_format(cell)}</td>")
        parts.append("</tr>")
    parts.append("</tbody></table></div>")
    return "".join(parts), index


def split_table_row(row: str) -> list[str]:
    return [cell.strip() for cell in row.strip().strip("|").split("|")]
