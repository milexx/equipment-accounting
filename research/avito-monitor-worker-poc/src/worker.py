import argparse
import html
import json
import random
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup
from curl_cffi import requests


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def fetch_html(url: str, timeout: int) -> tuple[int, dict[str, str], str]:
    headers = {
        "user-agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            f"Chrome/{random.randint(142, 147)}.0.0.0 Safari/537.36"
        ),
    }
    impersonate = random.choice(["chrome", "edge", "firefox", "safari"])
    with requests.Session(impersonate=impersonate) as session:
        session.headers.update(headers)
        response = session.get(url, timeout=timeout, allow_redirects=True)
        return response.status_code, dict(response.headers), response.text


def is_blocked(status_code: int, text: str) -> tuple[bool, str | None]:
    lowered = text.lower()
    if status_code in {401, 403, 429}:
        return True, f"http_{status_code}"
    if "доступ ограничен" in lowered:
        return True, "access_restricted"
    if "проблема с ip" in lowered:
        return True, "access_restricted"
    if "подтвердите, что вы не робот" in lowered:
        return True, "captcha"
    return False, None


def extract_state_data(html_text: str) -> dict[str, Any]:
    soup = BeautifulSoup(html_text, "html.parser")
    for script in soup.select("script"):
        if script.get("type") != "mime/invalid":
            continue
        if script.get("data-mfe-state") != "true":
            continue
        if "sandbox" in script.get_text(""):
            continue
        try:
            payload = json.loads(html.unescape(script.get_text()))
        except json.JSONDecodeError:
            continue
        data = payload.get("state", {}).get("data", {})
        if data.get("catalog") or data.get("searchCore"):
            return data
    return {}


def extract_items(state_data: dict[str, Any]) -> list[dict[str, Any]]:
    catalog = state_data.get("catalog") or {}
    items = catalog.get("items") or []
    return [item for item in items if isinstance(item, dict) and item.get("id")]


def price_value(item: dict[str, Any]) -> int | None:
    price = item.get("priceDetailed") or {}
    value = price.get("value")
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def normalize_listing(item: dict[str, Any], job: dict[str, Any], fetched_at: str) -> dict[str, Any] | None:
    price = price_value(item)
    title = item.get("title")
    url_path = item.get("urlPath")
    if not title or price is None or not url_path:
        return None

    location = item.get("location") or {}
    timestamp = item.get("sortTimeStamp")
    published_at = None
    if isinstance(timestamp, int):
        published_at = datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc).isoformat().replace("+00:00", "Z")

    return {
        "source": "avito",
        "job_code": job["code"],
        "external_id": str(item.get("id")),
        "title": title,
        "description": item.get("description"),
        "price": price,
        "currency": "RUB",
        "url": "https://www.avito.ru/" + str(url_path).lstrip("/"),
        "location": location.get("name") if isinstance(location, dict) else None,
        "published_at": published_at,
        "fetched_at": fetched_at,
        "raw_payload": item,
    }


def classify_listing(listing: dict[str, Any], job: dict[str, Any]) -> tuple[str, list[str]]:
    title_text = (listing.get("title") or "").lower()
    description_text = (listing.get("description") or "").lower()
    text = f"{title_text} {description_text}"
    reject_reasons: list[str] = []
    unknown_reasons: list[str] = []

    defect_terms = [
        "донор",
        "на запчаст",
        "запчасти",
        "нерабоч",
        "не рабоч",
        "неисправ",
        "трещит",
        "требуется",
        "без внутреннего блока",
        "без блока",
        "не хватает",
        "отсутств",
        "замена печки",
        "термопленк",
    ]
    accessory_terms = [
        "картридж",
        "тонер",
        "печка",
        "плата",
        "шлейф",
        "ролик",
        "блок питания",
        "накладка",
        "масло",
        "блок проявки",
        "фотовал",
        "ракель",
        "прижимная планка",
        "developer unit",
        "drum unit",
    ]

    for term in job.get("required_terms", []):
        if term.lower() not in text:
            reject_reasons.append(f"missing_required:{term}")

    for term in job.get("negative_terms", []):
        if term.lower() in text:
            reject_reasons.append(f"negative_term:{term}")

    for term in accessory_terms:
        if term in title_text:
            reject_reasons.append(f"accessory_or_consumable:{term}")

    for term in defect_terms:
        if term in text:
            unknown_reasons.append(f"repair_or_incomplete:{term}")

    price = listing["price"]
    if price < job.get("price_min", 0):
        unknown_reasons.append("price_below_min")
    if price > job.get("price_max", 10**12):
        unknown_reasons.append("price_above_max")

    if reject_reasons:
        return "rejected", reject_reasons + unknown_reasons
    if unknown_reasons:
        return "unknown", unknown_reasons
    return "relevant", []


def calculate_snapshot(
    job: dict[str, Any],
    raw_count: int,
    normalized: list[dict[str, Any]],
    relevant: list[dict[str, Any]],
    fetched_at: str,
) -> dict[str, Any]:
    prices = [item["price"] for item in relevant]
    status = "success" if prices else "no_data"
    return {
        "job_code": job["code"],
        "position_name": job["position_name"],
        "snapshot_date": fetched_at[:10],
        "source": "avito",
        "status": status,
        "raw_count": raw_count,
        "normalized_count": len(normalized),
        "relevant_count": len(relevant),
        "rejected_count": len([item for item in normalized if item.get("relevance_status") == "rejected"]),
        "unknown_count": len([item for item in normalized if item.get("relevance_status") == "unknown"]),
        "min_price": min(prices) if prices else None,
        "max_price": max(prices) if prices else None,
        "median_price": statistics.median(prices) if prices else None,
        "currency": "RUB",
        "fetched_at": fetched_at,
    }


def run_job(job: dict[str, Any], timeout: int, run_dir: Path) -> dict[str, Any]:
    fetched_at = iso(utc_now())
    job_dir = run_dir / job["code"]
    raw_dir = job_dir / "raw_pages"
    try:
        status_code, headers, html_text = fetch_html(job["search_url"], timeout)
    except Exception as exc:
        report = {
            "job_code": job["code"],
            "status": "parser_error",
            "error": f"{type(exc).__name__}: {exc}",
            "items_found": 0,
            "items_relevant": 0,
            "fetched_at": fetched_at,
        }
        write_json(job_dir / "job_report.json", report)
        return report

    (raw_dir / "page_1.html").parent.mkdir(parents=True, exist_ok=True)
    (raw_dir / "page_1.html").write_text(html_text, encoding="utf-8")
    write_json(job_dir / "response_meta.json", {"status_code": status_code, "headers": headers})

    status_blocked, reason = is_blocked(status_code, html_text)
    if status_blocked:
        report = {
            "job_code": job["code"],
            "status": "blocked" if reason != "captcha" else "captcha",
            "block_reason": reason,
            "http_status": status_code,
            "items_found": 0,
            "items_relevant": 0,
            "fetched_at": fetched_at,
        }
        write_json(job_dir / "job_report.json", report)
        return report

    state_data = extract_state_data(html_text)
    raw_items = extract_items(state_data)
    write_json(job_dir / "raw_listings.json", raw_items)

    normalized = [
        normalized_item
        for item in raw_items
        if (normalized_item := normalize_listing(item, job, fetched_at)) is not None
    ]

    relevant: list[dict[str, Any]] = []
    unknown: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for item in normalized:
        relevance_status, reject_reasons = classify_listing(item, job)
        item_with_relevance = {
            **item,
            "relevance_status": relevance_status,
            "reject_reasons": reject_reasons,
        }
        if relevance_status == "relevant":
            relevant.append(item_with_relevance)
        elif relevance_status == "unknown":
            unknown.append(item_with_relevance)
        else:
            rejected.append(item_with_relevance)

    classified = relevant + unknown + rejected
    snapshot = calculate_snapshot(job, len(raw_items), classified, relevant, fetched_at)

    write_json(job_dir / "normalized_listings.json", classified)
    write_json(job_dir / "relevant_listings.json", relevant)
    write_json(job_dir / "unknown_listings.json", unknown)
    write_json(job_dir / "rejected_listings.json", rejected)
    write_json(job_dir / "daily_snapshot.json", snapshot)

    report = {
        "job_code": job["code"],
        "status": snapshot["status"],
        "http_status": status_code,
        "items_found": len(raw_items),
        "items_normalized": len(normalized),
        "items_relevant": len(relevant),
        "items_unknown": len(unknown),
        "items_rejected": len(rejected),
        "fetched_at": fetched_at,
    }
    write_json(job_dir / "job_report.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/search_jobs.json")
    parser.add_argument("--runs-dir", default="runs")
    args = parser.parse_args()

    started_at = utc_now()
    run_id = started_at.strftime("%Y%m%dT%H%M%SZ")
    run_dir = Path(args.runs_dir) / run_id
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))

    job_reports = []
    jobs = config.get("jobs", [])
    request_delay = config.get("request_delay_seconds", 0)
    for index, job in enumerate(jobs):
        if index > 0 and request_delay > 0:
            time.sleep(request_delay)
        job_reports.append(run_job(job, config.get("timeout_seconds", 20), run_dir))

    finished_at = utc_now()
    run_report = {
        "run_id": run_id,
        "started_at": iso(started_at),
        "finished_at": iso(finished_at),
        "status": "success" if all(r["status"] in {"success", "no_data"} for r in job_reports) else "partial_success",
        "jobs_total": len(job_reports),
        "jobs_success": sum(1 for r in job_reports if r["status"] == "success"),
        "jobs_blocked": sum(1 for r in job_reports if r["status"] in {"blocked", "captcha"}),
        "jobs_failed": sum(1 for r in job_reports if r["status"] not in {"success", "no_data", "blocked", "captcha"}),
        "job_reports": job_reports,
    }
    write_json(run_dir / "run_report.json", run_report)
    print(json.dumps(run_report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
