import argparse
import html
import json
import os
import re
import socket
import subprocess
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse

from bs4 import BeautifulSoup
from curl_cffi import requests


DEFAULT_PRIMARY_IMPERSONATE = "safari"
PRIMARY_USER_AGENTS = {
    "chrome": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/143.0.0.0 Safari/537.36"
    ),
    "edge": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/143.0.0.0 Safari/537.36 Edg/143.0.0.0"
    ),
    "firefox": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:141.0) "
        "Gecko/20100101 Firefox/141.0"
    ),
    "safari": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/17.5 Safari/605.1.15"
    ),
}

INFRASTRUCTURE_ERROR_MARKERS = [
    "could not resolve host",
    "failed to connect",
    "connection timed out",
    "network is unreachable",
    "temporary failure in name resolution",
]
MIN_RELEVANT_FOR_SUCCESS = 5
MULTI_UNIT_PATTERNS = [
    re.compile(r"\b\d+\s*шт\.?\b"),
    re.compile(r"\bиз\s+\d+\s*шт\.?\b"),
    re.compile(r"\bлот\s+из\s+\d+\b"),
    re.compile(r"\bкомплект\s+из\s+\d+\b"),
]
MULTI_UNIT_SINGLE_PRICE_EXCEPTIONS = [
    re.compile(r"в\s+наличии\s+1\s*шт[!. ]"),
    re.compile(r"\b1\s*шт\.?\b"),
    re.compile(r"цена\s+за\s+1\s*шт\.?\b"),
    re.compile(r"цена\s+указана\s+за\s+1\s*шт\.?\b"),
    re.compile(r"цена\s+указана\s+за\s+1\s*штук[ауи]?\b"),
    re.compile(r"цена\s+за\s+одн[ау]\s*шт\.?\b"),
    re.compile(r"цена\s+указана\s+за\s+один\s+телефон\b"),
    re.compile(r"стоимость\s+за\s+1\s*шт\.?\b"),
    re.compile(r"\b\d+\s*руб\s*/\s*шт\.?\b"),
]
MULTI_UNIT_HINTS = [
    "в наличии",
    "несколько штук",
    "несколько единиц",
    "партия",
    "оптом",
]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json_file(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def relative_path(path: Path, start: Path) -> str:
    try:
        return str(path.relative_to(start))
    except ValueError:
        return str(path)


def copy_text_artifact(source_path: Path, target_path: Path) -> bool:
    if not source_path.exists():
        return False
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(source_path.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
    return True


def copy_json_artifact(source_path: Path, target_path: Path) -> bool:
    if not source_path.exists():
        return False
    write_json(target_path, read_json_file(source_path))
    return True


def primary_request_profile() -> tuple[str, str]:
    impersonate = os.getenv("AVITO_PRIMARY_IMPERSONATE", DEFAULT_PRIMARY_IMPERSONATE).strip().lower()
    if impersonate not in PRIMARY_USER_AGENTS:
        impersonate = DEFAULT_PRIMARY_IMPERSONATE
    user_agent = os.getenv("AVITO_PRIMARY_USER_AGENT") or PRIMARY_USER_AGENTS[impersonate]
    return impersonate, user_agent


def fetch_html(url: str, timeout: int) -> tuple[int, dict[str, str], str, dict[str, Any]]:
    impersonate, user_agent = primary_request_profile()
    headers = {"user-agent": user_agent}
    with requests.Session(impersonate=impersonate) as session:
        session.headers.update(headers)
        response = session.get(url, timeout=timeout, allow_redirects=True)
        request_meta = {
            "impersonate": impersonate,
            "headers": headers,
        }
        return response.status_code, dict(response.headers), response.text, request_meta


def is_infrastructure_error_text(error_text: str | None) -> bool:
    normalized = (error_text or "").lower()
    return any(marker in normalized for marker in INFRASTRUCTURE_ERROR_MARKERS)


def is_infrastructure_job_report(job_report: dict[str, Any]) -> bool:
    return (
        job_report.get("status") == "parser_error"
        and job_report.get("http_status") is None
        and is_infrastructure_error_text(str(job_report.get("error") or ""))
    )


def is_infrastructure_run_report(run_report: dict[str, Any]) -> bool:
    job_reports = run_report.get("job_reports")
    return isinstance(job_reports, list) and bool(job_reports) and all(
        is_infrastructure_job_report(job_report)
        for job_report in job_reports
        if isinstance(job_report, dict)
    )


def probe_search_hosts(config: dict[str, Any]) -> dict[str, Any]:
    hosts = sorted(
        {
            parsed.netloc
            for job in config.get("jobs", [])
            if isinstance(job, dict)
            and isinstance(job.get("search_url"), str)
            and job.get("search_url")
            and (parsed := urlparse(job["search_url"])).netloc
        }
    )
    failures = []
    for host in hosts:
        try:
            socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        except OSError as exc:
            failures.append({"host": host, "error": f"{type(exc).__name__}: {exc}"})

    return {
        "status": "ready" if not failures else "dns_unready",
        "checked_hosts": hosts,
        "failures": failures,
    }


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
        candidates = [
            payload.get("state", {}).get("data", {}),
            payload.get("loaderData", {}).get("data", {}),
            payload.get("data", {}),
            payload,
        ]
        for data in candidates:
            if isinstance(data, dict) and (data.get("catalog") or data.get("searchCore")):
                return data
    return {}


def extract_items(state_data: dict[str, Any]) -> list[dict[str, Any]]:
    catalog = state_data.get("catalog") or {}
    items = catalog.get("items") or []
    return [item for item in items if isinstance(item, dict) and item.get("id")]


def nested_payload_value(item: dict[str, Any], step_name: str, payload_key: str) -> Any:
    containers = [item]
    iva = item.get("iva")
    if isinstance(iva, dict):
        containers.append(iva)
    for container in containers:
        steps = container.get(step_name)
        if not isinstance(steps, list):
            continue
        for step in steps:
            if not isinstance(step, dict):
                continue
            payload = step.get("payload")
            if not isinstance(payload, dict):
                continue
            value = payload.get(payload_key)
            if value is not None:
                return value
    return None


def detect_page_problem(html_text: str, state_data: dict[str, Any]) -> tuple[bool, str | None]:
    normalized_text = html_text.replace("\xa0", " ")
    if "Такой страницы не существует" in normalized_text:
        return True, "page_not_found"
    status = state_data.get("status") or {}
    if isinstance(status, dict) and status.get("code") == 404:
        return True, "page_not_found"
    return False, None


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
    description = item.get("description")
    if description is None:
        description = nested_payload_value(item, "DescriptionStep", "description")
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
        "description": description,
        "price": price,
        "currency": "RUB",
        "url": "https://www.avito.ru/" + str(url_path).lstrip("/"),
        "location": location.get("name") if isinstance(location, dict) else None,
        "published_at": published_at,
        "fetched_at": fetched_at,
        "raw_payload": item,
    }


def is_multi_unit_offer(text: str) -> bool:
    normalized = text.lower()
    if any(pattern.search(normalized) for pattern in MULTI_UNIT_SINGLE_PRICE_EXCEPTIONS):
        return False
    if any(pattern.search(normalized) for pattern in MULTI_UNIT_PATTERNS):
        return True
    if any(hint in normalized for hint in MULTI_UNIT_HINTS) and "шт" in normalized:
        return True
    return False


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

    if is_multi_unit_offer(text):
        unknown_reasons.append("multi_unit_offer")

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


def upper_median(values: list[int | float]) -> int | float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[len(ordered) // 2]


def calculate_snapshot(
    job: dict[str, Any],
    raw_count: int,
    normalized: list[dict[str, Any]],
    relevant: list[dict[str, Any]],
    fetched_at: str,
    source: str = "avito",
) -> dict[str, Any]:
    prices = [item["price"] for item in relevant]
    if not prices:
        status = "no_data"
    elif len(relevant) < MIN_RELEVANT_FOR_SUCCESS:
        status = "low_sample"
    else:
        status = "success"
    return {
        "job_code": job["code"],
        "position_name": job["position_name"],
        "snapshot_date": fetched_at[:10],
        "source": source,
        "status": status,
        "raw_count": raw_count,
        "normalized_count": len(normalized),
        "relevant_count": len(relevant),
        "rejected_count": len([item for item in normalized if item.get("relevance_status") == "rejected"]),
        "unknown_count": len([item for item in normalized if item.get("relevance_status") == "unknown"]),
        "min_price": min(prices) if prices else None,
        "max_price": max(prices) if prices else None,
        "median_price": upper_median(prices),
        "currency": "RUB",
        "fetched_at": fetched_at,
    }


def write_evidence_bundle(
    job: dict[str, Any],
    fetched_at: str,
    job_dir: Path,
    source: str,
    snapshot: dict[str, Any],
    relevant: list[dict[str, Any]],
) -> None:
    run_dir = job_dir.parent
    evidence_dir = run_dir / "evidence" / job["code"]
    evidence_dir.mkdir(parents=True, exist_ok=True)

    artifacts: list[dict[str, Any]] = []
    artifact_specs = [
        {
            "kind": "search_html",
            "source_path": job_dir / "raw_pages" / "page_1.html",
            "target_path": evidence_dir / "search_result.html",
            "copy": copy_text_artifact,
        },
        {
            "kind": "search_json",
            "source_path": job_dir / "state_data.json",
            "target_path": evidence_dir / "search_result.json",
            "copy": copy_json_artifact,
        },
    ]
    if source == "avito_duff89":
        artifact_specs.append(
            {
                "kind": "search_json",
                "source_path": job_dir / "duff89_normalized_listings.json",
                "target_path": evidence_dir / "search_result.json",
                "copy": copy_json_artifact,
            }
        )
    if source == "youla":
        artifact_specs.append(
            {
                "kind": "search_json",
                "source_path": job_dir / "youla_raw_response.json",
                "target_path": evidence_dir / "search_result.json",
                "copy": copy_json_artifact,
            }
        )

    seen_targets: set[Path] = set()
    for spec in artifact_specs:
        target_path = spec["target_path"]
        if target_path in seen_targets:
            continue
        copied = spec["copy"](spec["source_path"], target_path)
        if not copied:
            continue
        seen_targets.add(target_path)
        artifacts.append(
            {
                "kind": spec["kind"],
                "format": target_path.suffix.lstrip("."),
                "path": relative_path(target_path, run_dir),
                "source_path": relative_path(spec["source_path"], run_dir),
            }
        )

    manifest = {
        "run_id": run_dir.name,
        "job_code": job["code"],
        "position_name": job.get("position_name"),
        "source": source,
        "search_url": job.get("search_url"),
        "snapshot_date": snapshot.get("snapshot_date"),
        "fetched_at": fetched_at,
        "status": snapshot.get("status"),
        "relevant_count": len(relevant),
        "artifacts": artifacts,
    }
    write_json(evidence_dir / "manifest.json", manifest)


def persist_classified_snapshot(
    job: dict[str, Any],
    fetched_at: str,
    job_dir: Path,
    source: str,
    raw_count: int,
    normalized: list[dict[str, Any]],
    extra_report_fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    relevant: list[dict[str, Any]] = []
    unknown: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for item in normalized:
        item = {**item, "source": source, "job_code": job["code"], "fetched_at": fetched_at}
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
    snapshot = calculate_snapshot(job, raw_count, classified, relevant, fetched_at, source=source)

    write_json(job_dir / f"raw_listings_{source}.json", normalized)
    write_json(job_dir / "normalized_listings.json", classified)
    write_json(job_dir / "relevant_listings.json", relevant)
    write_json(job_dir / "unknown_listings.json", unknown)
    write_json(job_dir / "rejected_listings.json", rejected)
    write_json(job_dir / "daily_snapshot.json", snapshot)
    write_evidence_bundle(job, fetched_at, job_dir, source, snapshot, relevant)

    report = {
        "job_code": job["code"],
        "source": source,
        "status": snapshot["status"],
        "items_found": raw_count,
        "items_normalized": len(normalized),
        "items_relevant": len(relevant),
        "items_unknown": len(unknown),
        "items_rejected": len(rejected),
        "fetched_at": fetched_at,
    }
    if extra_report_fields:
        report.update(extra_report_fields)
    write_json(job_dir / "job_report.json", report)
    return report


def format_diagnostic_command(command: list[str], job: dict[str, Any], job_dir: Path) -> list[str]:
    values = {
        "job_code": job["code"],
        "search_url": job["search_url"],
        "job_dir": str(job_dir),
    }
    return [part.format(**values) for part in command]


def run_block_diagnostic(
    job: dict[str, Any],
    job_dir: Path,
    block_diagnostic: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not block_diagnostic or not block_diagnostic.get("enabled"):
        return None

    command = block_diagnostic.get("command")
    if not isinstance(command, list) or not all(isinstance(part, str) for part in command):
        return {
            "status": "not_configured",
            "error": "block_diagnostic.command must be a list of strings",
        }

    timeout = int(block_diagnostic.get("timeout_seconds") or 60)
    rendered_command = format_diagnostic_command(command, job, job_dir)
    started_at = iso(utc_now())
    env = {
        **os.environ,
        "AVITO_DIAGNOSTIC_JOB_CODE": job["code"],
        "AVITO_DIAGNOSTIC_SEARCH_URL": job["search_url"],
        "AVITO_DIAGNOSTIC_JOB_DIR": str(job_dir),
    }
    try:
        completed = subprocess.run(
            rendered_command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
        result = {
            "status": "success" if completed.returncode == 0 else "failed",
            "started_at": started_at,
            "finished_at": iso(utc_now()),
            "command": rendered_command,
            "returncode": completed.returncode,
            "stdout_tail": completed.stdout[-4000:],
            "stderr_tail": completed.stderr[-4000:],
        }
    except FileNotFoundError as exc:
        result = {
            "status": "missing",
            "started_at": started_at,
            "finished_at": iso(utc_now()),
            "command": rendered_command,
            "error": str(exc),
        }
    except subprocess.TimeoutExpired as exc:
        result = {
            "status": "timeout",
            "started_at": started_at,
            "finished_at": iso(utc_now()),
            "command": rendered_command,
            "timeout_seconds": timeout,
            "stdout_tail": (exc.stdout or "")[-4000:] if isinstance(exc.stdout, str) else "",
            "stderr_tail": (exc.stderr or "")[-4000:] if isinstance(exc.stderr, str) else "",
        }

    write_json(job_dir / "block_diagnostic.json", result)
    return result


YOULA_CATALOG_QUERY = """
query catalogProductsBoard($sort: Sort, $attributes: [AttributeItem!], $location: LocationInput, $cursor: Cursor!, $search: String, $datePublished: DateInput) {
  feed(input: {sort: $sort, attributes: $attributes, location: $location, search: $search, datePublished: $datePublished}, after: $cursor) {
    items {
      ... on PromotedProductItem {
        product: productPromoted {
          id
          categoryId: category
          subcategoryId: subcategory
          price { realPrice { price } realPriceText discount }
          url
          name
          location { cityName }
          distanceText
        }
      }
      ... on ProductItem {
        product {
          id
          categoryId: category
          subcategoryId: subcategory
          price { realPrice { price } realPriceText discount }
          url
          name
          location { cityName }
          distanceText
        }
      }
    }
    pageInfo { cursor hasNextPage productsAnalytics { searchId } }
  }
}
""".strip()


def normalize_youla_item(item: dict[str, Any]) -> dict[str, Any] | None:
    product = item.get("product")
    if not isinstance(product, dict):
        return None
    price = product.get("price") or {}
    real_price = price.get("realPrice") or {}
    raw_price = real_price.get("price")
    title = product.get("name")
    url = product.get("url")
    if not title or not isinstance(raw_price, int | float) or not url:
        return None
    return {
        "source": "youla",
        "external_id": product.get("id"),
        "title": str(title),
        "description": "",
        "price": int(raw_price / 100),
        "currency": "RUB",
        "url": f"https://youla.ru{url}" if isinstance(url, str) and url.startswith("/") else str(url),
        "location": (product.get("location") or {}).get("cityName"),
        "published_at": None,
        "raw_payload": product,
    }


def fetch_youla_listings(job: dict[str, Any], timeout: int) -> tuple[int | None, list[dict[str, Any]], dict[str, Any]]:
    search = job.get("youla_search") or job.get("position_name") or job["code"]
    payload = {
        "operationName": "catalogProductsBoard",
        "variables": {
            "sort": "DEFAULT",
            "attributes": [{"slug": "categories", "value": [""], "from": None, "to": None}],
            "location": {"latitude": 55.750718, "longitude": 37.617661},
            "search": search,
            "cursor": "",
        },
        "query": YOULA_CATALOG_QUERY,
    }
    headers = {
        "accept": "*/*",
        "content-type": "application/json",
        "origin": "https://youla.ru",
        "referer": f"https://youla.ru/all?q={quote(str(search))}",
        "user-agent": "Mozilla/5.0 equipment-accounting-youla-poc/0.1",
        "x-app-id": "web/3",
        "appId": "web/3",
        "x-uid": "6a384e7d63341",
        "uid": "6a384e7d63341",
        "x-offset-utc": "-25200",
    }
    response = requests.post("https://api-gw.youla.ru/graphql", json=payload, headers=headers, timeout=timeout)
    data = response.json()
    feed = ((data.get("data") or {}).get("feed") or {})
    raw_items = feed.get("items") or []
    listings = [
        normalized
        for item in raw_items
        if isinstance(item, dict)
        for normalized in [normalize_youla_item(item)]
        if normalized is not None
    ]
    return response.status_code, listings, data


def try_duff89_fallback(
    job: dict[str, Any],
    fetched_at: str,
    job_dir: Path,
    block_diagnostic: dict[str, Any] | None,
    primary_report: dict[str, Any],
) -> dict[str, Any] | None:
    diagnostic = primary_report.get("block_diagnostic") or run_block_diagnostic(job, job_dir, block_diagnostic)
    if not isinstance(diagnostic, dict) or diagnostic.get("status") != "success":
        return None
    payload = load_json(job_dir / "duff89_normalized_listings.json", {})
    items = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(items, list) or not items:
        return None
    return persist_classified_snapshot(
        job,
        fetched_at,
        job_dir,
        "avito_duff89",
        len(items),
        [item for item in items if isinstance(item, dict)],
        {
            "fallback_from": "avito",
            "primary_status": primary_report.get("status"),
            "primary_http_status": primary_report.get("http_status"),
            "block_diagnostic": diagnostic,
        },
    )


def try_youla_fallback(
    job: dict[str, Any],
    fetched_at: str,
    job_dir: Path,
    youla_fallback: dict[str, Any] | None,
    primary_report: dict[str, Any],
) -> dict[str, Any] | None:
    if not youla_fallback or not youla_fallback.get("enabled"):
        return None
    timeout = int(youla_fallback.get("timeout_seconds") or 20)
    try:
        http_status, listings, raw_payload = fetch_youla_listings(job, timeout)
    except Exception as exc:
        write_json(
            job_dir / "youla_fallback_report.json",
            {"status": "failed", "error": f"{type(exc).__name__}: {exc}"},
        )
        return None
    write_json(job_dir / "youla_raw_response.json", raw_payload)
    fallback_report = {"status": "success" if http_status == 200 and listings else "no_data", "http_status": http_status, "count": len(listings)}
    write_json(job_dir / "youla_fallback_report.json", fallback_report)
    if fallback_report["status"] != "success":
        return None
    return persist_classified_snapshot(
        job,
        fetched_at,
        job_dir,
        "youla",
        len(listings),
        listings,
        {
            "fallback_from": "avito",
            "primary_status": primary_report.get("status"),
            "primary_http_status": primary_report.get("http_status"),
            "youla_http_status": http_status,
        },
    )


def apply_fallback_chain(
    job: dict[str, Any],
    fetched_at: str,
    job_dir: Path,
    primary_report: dict[str, Any],
    block_diagnostic: dict[str, Any] | None,
    youla_fallback: dict[str, Any] | None,
) -> dict[str, Any]:
    if primary_report.get("status") == "success":
        return primary_report
    # Keep a low-sample Avito result as the primary truth instead of replacing it
    # with a weaker marketplace fallback.
    if primary_report.get("status") == "low_sample":
        return primary_report
    duff89_report = try_duff89_fallback(job, fetched_at, job_dir, block_diagnostic, primary_report)
    if duff89_report and duff89_report.get("status") == "success":
        return duff89_report
    youla_report = try_youla_fallback(job, fetched_at, job_dir, youla_fallback, primary_report)
    if youla_report and youla_report.get("status") == "success":
        return youla_report
    return primary_report


def process_html(
    job: dict[str, Any],
    fetched_at: str,
    job_dir: Path,
    status_code: int,
    headers: dict[str, str],
    html_text: str,
    block_diagnostic: dict[str, Any] | None = None,
    request_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    raw_dir = job_dir / "raw_pages"
    (raw_dir / "page_1.html").parent.mkdir(parents=True, exist_ok=True)
    (raw_dir / "page_1.html").write_text(html_text, encoding="utf-8")
    response_meta = {"status_code": status_code, "headers": headers}
    if request_meta:
        response_meta["request"] = request_meta
    write_json(job_dir / "response_meta.json", response_meta)

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
        diagnostic = run_block_diagnostic(job, job_dir, block_diagnostic)
        if diagnostic:
            report["block_diagnostic"] = diagnostic
        write_json(job_dir / "job_report.json", report)
        return report

    state_data = extract_state_data(html_text)
    write_json(job_dir / "state_data.json", state_data)
    has_page_problem, page_problem = detect_page_problem(html_text, state_data)
    if has_page_problem:
        report = {
            "job_code": job["code"],
            "status": "parser_error",
            "error": page_problem,
            "http_status": status_code,
            "items_found": 0,
            "items_relevant": 0,
            "fetched_at": fetched_at,
        }
        write_json(job_dir / "job_report.json", report)
        return report

    raw_items = extract_items(state_data)
    write_json(job_dir / "raw_listings.json", raw_items)

    normalized = [
        normalized_item
        for item in raw_items
        if (normalized_item := normalize_listing(item, job, fetched_at)) is not None
    ]

    report = persist_classified_snapshot(job, fetched_at, job_dir, "avito", len(raw_items), normalized)
    report.update({
        "http_status": status_code,
    })
    write_json(job_dir / "job_report.json", report)
    return report


def run_job(
    job: dict[str, Any],
    timeout: int,
    run_dir: Path,
    block_diagnostic: dict[str, Any] | None = None,
    youla_fallback: dict[str, Any] | None = None,
) -> dict[str, Any]:
    fetched_at = iso(utc_now())
    job_dir = run_dir / job["code"]
    try:
        status_code, headers, html_text, request_meta = fetch_html(job["search_url"], timeout)
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
        return apply_fallback_chain(job, fetched_at, job_dir, report, block_diagnostic, youla_fallback)

    report = process_html(job, fetched_at, job_dir, status_code, headers, html_text, block_diagnostic, request_meta)
    return apply_fallback_chain(job, fetched_at, job_dir, report, block_diagnostic, youla_fallback)


def live_run_exists_for_date(runs_dir: Path, run_date: str) -> tuple[bool, dict[str, Any] | None]:
    if not runs_dir.exists():
        return False, None
    for run_report_path in sorted(runs_dir.glob("*/run_report.json"), reverse=True):
        run_id = run_report_path.parent.name
        if run_id.endswith("_offline"):
            continue
        run_report = load_json(run_report_path, {})
        if is_infrastructure_run_report(run_report):
            continue
        started_at = run_report.get("started_at")
        if isinstance(started_at, str) and started_at[:10] == run_date:
            return True, {
                "run_id": run_report.get("run_id", run_id),
                "started_at": started_at,
                "status": run_report.get("status"),
                "path": str(run_report_path.parent),
            }
    return False, None


def print_same_day_live_guard(existing_run: dict[str, Any], run_date: str) -> int:
    payload = {
        "status": "blocked_by_same_day_guard",
        "run_date": run_date,
        "message": "Live Avito run already exists for this UTC date",
        "existing_run": existing_run,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 3


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/search_jobs.json")
    parser.add_argument("--runs-dir", default="runs")
    parser.add_argument("--allow-same-day-live", action="store_true")
    args = parser.parse_args()

    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    runtime_probe = probe_search_hosts(config)
    if runtime_probe["status"] != "ready":
        payload = {
            "status": "infrastructure_unready",
            "reason": "dns_resolution_failed",
            "message": "Search host DNS resolution failed before live run start",
            "runtime": runtime_probe,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 4

    started_at = utc_now()
    run_id = started_at.strftime("%Y%m%dT%H%M%SZ")
    run_dir = Path(args.runs_dir) / run_id
    if not args.allow_same_day_live:
        run_exists, existing_run = live_run_exists_for_date(Path(args.runs_dir), started_at.date().isoformat())
        if run_exists and existing_run is not None:
            return print_same_day_live_guard(existing_run, started_at.date().isoformat())

    job_reports = []
    jobs = config.get("jobs", [])
    request_delay = config.get("request_delay_seconds", 0)
    for index, job in enumerate(jobs):
        if index > 0 and request_delay > 0:
            time.sleep(request_delay)
        job_reports.append(
            run_job(
                job,
                config.get("timeout_seconds", 20),
                run_dir,
                config.get("block_diagnostic"),
                config.get("youla_fallback"),
            )
        )

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


def read_config(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_config(config: dict[str, Any]) -> tuple[bool, list[str], dict[str, Any]]:
    errors: list[str] = []
    jobs = config.get("jobs")
    if not isinstance(jobs, list) or not jobs:
        errors.append("jobs must be a non-empty list")
        jobs = []

    seen_codes: set[str] = set()
    for index, job in enumerate(jobs):
        prefix = f"jobs[{index}]"
        if not isinstance(job, dict):
            errors.append(f"{prefix} must be an object")
            continue
        code = job.get("code")
        if not isinstance(code, str) or not code:
            errors.append(f"{prefix}.code is required")
        elif code in seen_codes:
            errors.append(f"{prefix}.code is duplicated: {code}")
        else:
            seen_codes.add(code)

        for field in ["position_name", "source", "search_url"]:
            if not isinstance(job.get(field), str) or not job.get(field):
                errors.append(f"{prefix}.{field} is required")

        url = job.get("search_url")
        if isinstance(url, str) and url:
            parsed = urlparse(url)
            if parsed.scheme != "https":
                errors.append(f"{prefix}.search_url must use https")
            if parsed.netloc != "www.avito.ru":
                errors.append(f"{prefix}.search_url must point to www.avito.ru")
            if not parsed.query:
                errors.append(f"{prefix}.search_url must include a query string")

        for field in ["required_terms", "negative_terms"]:
            value = job.get(field)
            if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
                errors.append(f"{prefix}.{field} must be a list of strings")

        for field in ["price_min", "price_max"]:
            if not isinstance(job.get(field), int):
                errors.append(f"{prefix}.{field} must be an integer")
        if isinstance(job.get("price_min"), int) and isinstance(job.get("price_max"), int):
            if job["price_min"] >= job["price_max"]:
                errors.append(f"{prefix}.price_min must be lower than price_max")

    summary = {
        "jobs_total": len(jobs),
        "job_codes": [job.get("code") for job in jobs if isinstance(job, dict)],
        "request_delay_seconds": config.get("request_delay_seconds"),
        "timeout_seconds": config.get("timeout_seconds"),
        "block_diagnostic_enabled": bool(
            isinstance(config.get("block_diagnostic"), dict)
            and config["block_diagnostic"].get("enabled")
        ),
        "youla_fallback_enabled": bool(
            isinstance(config.get("youla_fallback"), dict)
            and config["youla_fallback"].get("enabled")
        ),
    }

    block_diagnostic = config.get("block_diagnostic")
    if block_diagnostic is not None:
        if not isinstance(block_diagnostic, dict):
            errors.append("block_diagnostic must be an object")
        else:
            command = block_diagnostic.get("command")
            if block_diagnostic.get("enabled") and (
                not isinstance(command, list)
                or not command
                or not all(isinstance(part, str) for part in command)
            ):
                errors.append("block_diagnostic.command must be a non-empty list of strings")

    youla_fallback = config.get("youla_fallback")
    if youla_fallback is not None and not isinstance(youla_fallback, dict):
        errors.append("youla_fallback must be an object")

    return not errors, errors, summary


def print_config_validation(config_path: Path) -> int:
    config = read_config(config_path)
    is_valid, errors, summary = validate_config(config)
    payload = {
        "status": "ok" if is_valid else "invalid",
        "errors": errors,
        "summary": summary,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if is_valid else 2


def build_preflight(config_path: Path, runs_dir: Path) -> tuple[int, dict[str, Any]]:
    config = read_config(config_path)
    config_is_valid, config_errors, config_summary = validate_config(config)
    runtime_probe = probe_search_hosts(config) if config_is_valid else {
        "status": "skipped",
        "checked_hosts": [],
        "failures": [],
    }
    today = utc_now().date().isoformat()
    live_exists, existing_run = live_run_exists_for_date(runs_dir, today)
    status = "ready"
    exit_code = 0
    if not config_is_valid:
        status = "invalid_config"
        exit_code = 2
    elif runtime_probe["status"] != "ready":
        status = "infrastructure_unready"
        exit_code = 4
    elif live_exists:
        status = "blocked_by_same_day_guard"
        exit_code = 3
    return exit_code, {
        "status": status,
        "utc_date": today,
        "config": {
            "path": str(config_path),
            "valid": config_is_valid,
            "errors": config_errors,
            "summary": config_summary,
        },
        "runtime": runtime_probe,
        "same_day_guard": {
            "live_run_exists": live_exists,
            "existing_run": existing_run,
        },
        "next_live_command": ".venv/bin/python src/worker.py --config config/search_jobs.json --runs-dir runs",
    }


def print_preflight(config_path: Path, runs_dir: Path) -> int:
    exit_code, payload = build_preflight(config_path, runs_dir)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return exit_code


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def reason_counts(items: list[dict[str, Any]]) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for item in items:
        for reason in item.get("reject_reasons", []):
            counter[reason] += 1
    return dict(counter.most_common())


def diagnose_raw_html(job_dir: Path) -> list[str]:
    html_path = job_dir / "raw_pages" / "page_1.html"
    if not html_path.exists():
        return []
    html_text = html_path.read_text(encoding="utf-8", errors="replace")
    findings = []
    normalized_text = html_text.replace("\xa0", " ")
    if "Доступ ограничен: проблема с IP" in normalized_text:
        findings.append("access_restricted_ip")
    if "Такой страницы не существует" in normalized_text:
        findings.append("page_not_found")
    state_data = extract_state_data(html_text)
    status = state_data.get("status") or {}
    if isinstance(status, dict) and status.get("code") == 404 and "page_not_found" not in findings:
        findings.append("page_not_found")
    if "подтвердите, что вы не робот" in html_text.lower():
        findings.append("captcha")
    return findings


def analyze_run(run_dir: Path) -> dict[str, Any]:
    run_report = load_json(run_dir / "run_report.json", {})
    jobs = []
    for job_dir in sorted(
        path for path in run_dir.iterdir() if path.is_dir() and (path / "job_report.json").exists()
    ):
        job_report = load_json(job_dir / "job_report.json", {})
        snapshot = load_json(job_dir / "daily_snapshot.json", {})
        rejected = load_json(job_dir / "rejected_listings.json", [])
        unknown = load_json(job_dir / "unknown_listings.json", [])
        jobs.append(
            {
                "job_code": job_dir.name,
                "source": snapshot.get("source") or job_report.get("source") or "avito",
                "status": job_report.get("status"),
                "http_status": job_report.get("http_status"),
                "block_reason": job_report.get("block_reason"),
                "error": job_report.get("error"),
                "raw_count": snapshot.get("raw_count", job_report.get("items_found", 0)),
                "normalized_count": snapshot.get(
                    "normalized_count", job_report.get("items_normalized", 0)
                ),
                "relevant_count": snapshot.get(
                    "relevant_count", job_report.get("items_relevant", 0)
                ),
                "unknown_count": snapshot.get("unknown_count", job_report.get("items_unknown", 0)),
                "rejected_count": snapshot.get(
                    "rejected_count", job_report.get("items_rejected", 0)
                ),
                "min_price": snapshot.get("min_price"),
                "max_price": snapshot.get("max_price"),
                "median_price": snapshot.get("median_price"),
                "html_findings": diagnose_raw_html(job_dir),
                "block_diagnostic": job_report.get("block_diagnostic")
                or load_json(job_dir / "block_diagnostic.json", None),
                "rejected_reason_counts": reason_counts(rejected),
                "unknown_reason_counts": reason_counts(unknown),
            }
        )
    return {
        "run_id": run_report.get("run_id", run_dir.name),
        "status": run_report.get("status"),
        "started_at": run_report.get("started_at"),
        "finished_at": run_report.get("finished_at"),
        "jobs_total": run_report.get("jobs_total", len(jobs)),
        "jobs": jobs,
    }


def print_run_analysis(run_dir: Path) -> int:
    print(json.dumps(analyze_run(run_dir), ensure_ascii=False, indent=2))
    return 0


def find_job(config: dict[str, Any], job_code: str) -> dict[str, Any]:
    for job in config.get("jobs", []):
        if job.get("code") == job_code:
            return job
    raise ValueError(f"Unknown job code: {job_code}")


def process_from_html(config_path: Path, job_code: str, html_path: Path, runs_dir: Path) -> int:
    config = read_config(config_path)
    job = find_job(config, job_code)
    started_at = utc_now()
    run_id = f"{started_at.strftime('%Y%m%dT%H%M%SZ')}_offline"
    run_dir = runs_dir / run_id
    html_text = html_path.read_text(encoding="utf-8", errors="replace")
    report = process_html(
        job,
        iso(started_at),
        run_dir / job["code"],
        200,
        {"offline_source": str(html_path)},
        html_text,
    )
    finished_at = utc_now()
    run_report = {
        "run_id": run_id,
        "started_at": iso(started_at),
        "finished_at": iso(finished_at),
        "status": "success" if report["status"] in {"success", "no_data"} else "partial_success",
        "jobs_total": 1,
        "jobs_success": 1 if report["status"] == "success" else 0,
        "jobs_blocked": 1 if report["status"] in {"blocked", "captcha"} else 0,
        "jobs_failed": 1 if report["status"] not in {"success", "no_data", "blocked", "captcha"} else 0,
        "job_reports": [report],
    }
    write_json(run_dir / "run_report.json", run_report)
    print(json.dumps(run_report, ensure_ascii=False, indent=2))
    return 0


def value_or_dash(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def render_markdown_report(analysis: dict[str, Any]) -> str:
    lines = [
        f"# Price Monitoring Run Report: {analysis['run_id']}",
        "",
        f"Status: `{analysis.get('status')}`.",
        "",
        "```text",
        f"started_at: {analysis.get('started_at')}",
        f"finished_at: {analysis.get('finished_at')}",
        f"jobs_total: {analysis.get('jobs_total')}",
        "```",
        "",
        "| Позиция | Source | HTTP | Статус | Raw | Normalized | Relevant | Unknown | Rejected | Min | Max | Median | Findings | Diagnostic |",
        "|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for job in analysis["jobs"]:
        findings = ", ".join(job["html_findings"]) if job["html_findings"] else "-"
        diagnostic = job.get("block_diagnostic") or {}
        diagnostic_status = diagnostic.get("status") if isinstance(diagnostic, dict) else None
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{job['job_code']}`",
                    f"`{job.get('source')}`",
                    value_or_dash(job.get("http_status")),
                    f"`{job.get('status')}`",
                    value_or_dash(job.get("raw_count")),
                    value_or_dash(job.get("normalized_count")),
                    value_or_dash(job.get("relevant_count")),
                    value_or_dash(job.get("unknown_count")),
                    value_or_dash(job.get("rejected_count")),
                    value_or_dash(job.get("min_price")),
                    value_or_dash(job.get("max_price")),
                    value_or_dash(job.get("median_price")),
                    findings,
                    f"`{diagnostic_status}`" if diagnostic_status else "-",
                ]
            )
            + " |"
        )

    lines.extend(["", "## Reject Reasons", ""])
    for job in analysis["jobs"]:
        lines.append(f"### `{job['job_code']}`")
        if not job["rejected_reason_counts"] and not job["unknown_reason_counts"]:
            lines.append("")
            lines.append("No reject or unknown reasons.")
            lines.append("")
            continue
        for title, key in [
            ("Rejected", "rejected_reason_counts"),
            ("Unknown", "unknown_reason_counts"),
        ]:
            if not job[key]:
                continue
            lines.append("")
            lines.append(title + ":")
            lines.append("")
            for reason, count in job[key].items():
                lines.append(f"- `{reason}`: {count}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def write_markdown_report(run_dir: Path, output_path: Path) -> int:
    report = render_markdown_report(analyze_run(run_dir))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")
    print(str(output_path))
    return 0


def guess_recommended_decision(analysis: dict[str, Any]) -> str:
    jobs = analysis["jobs"]
    success_count = sum(1 for job in jobs if job.get("status") == "success")
    blocked_count = sum(1 for job in jobs if job.get("status") in {"blocked", "captcha"})
    parser_error_count = sum(1 for job in jobs if job.get("status") == "parser_error")
    if success_count >= 2 and blocked_count == 0:
        return "continue_endurance_day_3"
    if blocked_count + parser_error_count >= 2:
        return "hold_http_unstable_candidate"
    return "continue_endurance_with_caution"


def render_endurance_doc(
    analysis: dict[str, Any],
    day: str,
    date: str,
    decision: str | None = None,
    next_action: str | None = None,
) -> str:
    effective_decision = decision or guess_recommended_decision(analysis)
    effective_next_action = next_action or "Продолжить по gate checklist."
    lines = [
        f"# Endurance Test Оценщика: День {day}",
        "",
        f"Дата: {date}.",
        "",
        f"Статус: `{analysis.get('status')}`.",
        "",
        "## Live Run",
        "",
        "```text",
        f"run_id: {analysis.get('run_id')}",
        f"started_at: {analysis.get('started_at')}",
        f"finished_at: {analysis.get('finished_at')}",
        f"status: {analysis.get('status')}",
        f"jobs_total: {analysis.get('jobs_total')}",
        "```",
        "",
        "## Результаты По Позициям",
        "",
        "| Позиция | Source | HTTP | Статус | Raw | Normalized | Relevant | Unknown | Rejected | Min | Max | Median | Findings | Diagnostic |",
        "|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for job in analysis["jobs"]:
        findings = ", ".join(job["html_findings"]) if job["html_findings"] else "-"
        diagnostic = job.get("block_diagnostic") or {}
        diagnostic_status = diagnostic.get("status") if isinstance(diagnostic, dict) else None
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{job['job_code']}`",
                    f"`{job.get('source')}`",
                    value_or_dash(job.get("http_status")),
                    f"`{job.get('status')}`",
                    value_or_dash(job.get("raw_count")),
                    value_or_dash(job.get("normalized_count")),
                    value_or_dash(job.get("relevant_count")),
                    value_or_dash(job.get("unknown_count")),
                    value_or_dash(job.get("rejected_count")),
                    value_or_dash(job.get("min_price")),
                    value_or_dash(job.get("max_price")),
                    value_or_dash(job.get("median_price")),
                    findings,
                    f"`{diagnostic_status}`" if diagnostic_status else "-",
                ]
            )
            + " |"
        )

    lines.extend(["", "## Наблюдения", ""])
    for job in analysis["jobs"]:
        details = []
        if job.get("block_reason"):
            details.append(f"block_reason: `{job['block_reason']}`")
        if job.get("error"):
            details.append(f"error: `{job['error']}`")
        if job["html_findings"]:
            details.append("findings: " + ", ".join(f"`{item}`" for item in job["html_findings"]))
        diagnostic = job.get("block_diagnostic") or {}
        if isinstance(diagnostic, dict) and diagnostic.get("status"):
            details.append(f"block diagnostic: `{diagnostic['status']}`")
        if job["rejected_reason_counts"]:
            top_reason, top_count = next(iter(job["rejected_reason_counts"].items()))
            details.append(f"top rejected reason: `{top_reason}` ({top_count})")
        detail_text = "; ".join(details) if details else "без дополнительных замечаний"
        lines.append(f"- `{job['job_code']}`: `{job.get('status')}`, {detail_text}.")

    lines.extend(
        [
            "",
            "## Решение После Запуска",
            "",
            "```text",
            effective_decision,
            "```",
            "",
            "## Следующий Шаг",
            "",
            effective_next_action,
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def write_endurance_doc(
    run_dir: Path,
    output_path: Path,
    day: str,
    date: str,
    decision: str | None,
    next_action: str | None,
) -> int:
    report = render_endurance_doc(analyze_run(run_dir), day, date, decision, next_action)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")
    print(str(output_path))
    return 0


def list_live_run_dirs(runs_dir: Path) -> list[Path]:
    if not runs_dir.exists():
        return []
    return [
        path
        for path in sorted(runs_dir.iterdir())
        if path.is_dir() and not path.name.endswith("_offline") and (path / "run_report.json").exists()
    ]


def is_infrastructure_attempt(analysis: dict[str, Any]) -> bool:
    jobs = analysis.get("jobs") or []
    if not jobs:
        return False
    for job in jobs:
        if job.get("status") != "parser_error":
            return False
        if job.get("http_status") is not None:
            return False
        error = str(job.get("error") or "").lower()
        if not is_infrastructure_error_text(error):
            return False
    return True


def summarize_gate(runs_dir: Path) -> dict[str, Any]:
    all_analyses = [analyze_run(run_dir) for run_dir in list_live_run_dirs(runs_dir)]
    excluded_runs = [
        {
            "run_id": analysis["run_id"],
            "started_at": analysis.get("started_at"),
            "status": analysis.get("status"),
            "reason": "infrastructure_attempt",
        }
        for analysis in all_analyses
        if is_infrastructure_attempt(analysis)
    ]
    analyses = [analysis for analysis in all_analyses if not is_infrastructure_attempt(analysis)]
    job_totals: dict[str, Counter[str]] = {}
    for analysis in analyses:
        for job in analysis["jobs"]:
            job_totals.setdefault(job["job_code"], Counter())[job.get("status") or "unknown"] += 1

    days_total = len(analyses)
    runs_with_two_successes = sum(
        1 for analysis in analyses if sum(1 for job in analysis["jobs"] if job.get("status") == "success") >= 2
    )
    runs_with_majority_blocked_or_failed = sum(
        1
        for analysis in analyses
        if sum(
            1
            for job in analysis["jobs"]
            if job.get("status") in {"blocked", "captcha", "parser_error"}
        )
        >= 2
    )

    if days_total >= 3 and runs_with_two_successes >= 2 and runs_with_majority_blocked_or_failed == 0:
        recommendation = "go_worker_prototype_candidate"
    elif days_total >= 2 and runs_with_majority_blocked_or_failed >= 2:
        recommendation = "hold_http_unstable_candidate"
    else:
        recommendation = "continue_endurance"

    return {
        "runs_seen_total": len(all_analyses),
        "runs_total": days_total,
        "runs_excluded": len(excluded_runs),
        "runs_with_two_successes": runs_with_two_successes,
        "runs_with_majority_blocked_or_failed": runs_with_majority_blocked_or_failed,
        "recommendation": recommendation,
        "runs": analyses,
        "excluded_runs": excluded_runs,
        "job_totals": {
            job_code: dict(counter.most_common()) for job_code, counter in sorted(job_totals.items())
        },
    }


def render_gate_summary(summary: dict[str, Any]) -> str:
    lines = [
        "# Gate Summary: Price Monitoring Endurance",
        "",
        f"Recommendation: `{summary['recommendation']}`.",
        "",
        "```text",
        f"runs_seen_total: {summary.get('runs_seen_total', summary['runs_total'])}",
        f"runs_total: {summary['runs_total']}",
        f"runs_excluded: {summary.get('runs_excluded', 0)}",
        f"runs_with_two_successes: {summary['runs_with_two_successes']}",
        f"runs_with_majority_blocked_or_failed: {summary['runs_with_majority_blocked_or_failed']}",
        "```",
        "",
        "## Runs",
        "",
        "| Run | Started | Status | Success | Blocked/Captcha | Parser Errors |",
        "|---|---|---|---:|---:|---:|",
    ]
    for analysis in summary["runs"]:
        success_count = sum(1 for job in analysis["jobs"] if job.get("status") == "success")
        blocked_count = sum(1 for job in analysis["jobs"] if job.get("status") in {"blocked", "captcha"})
        parser_error_count = sum(1 for job in analysis["jobs"] if job.get("status") == "parser_error")
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{analysis['run_id']}`",
                    value_or_dash(analysis.get("started_at")),
                    f"`{analysis.get('status')}`",
                    str(success_count),
                    str(blocked_count),
                    str(parser_error_count),
                ]
            )
            + " |"
        )

    excluded_runs = summary.get("excluded_runs") or []
    if excluded_runs:
        lines.extend(["", "## Excluded Runs", ""])
        lines.extend(["| Run | Started | Status | Reason |", "|---|---|---|---|"])
        for run in excluded_runs:
            lines.append(
                "| "
                + " | ".join(
                    [
                        f"`{run['run_id']}`",
                        value_or_dash(run.get("started_at")),
                        f"`{run.get('status')}`",
                        f"`{run.get('reason')}`",
                    ]
                )
                + " |"
            )

    lines.extend(["", "## Job Totals", ""])
    if not summary["job_totals"]:
        lines.append("No live runs found.")
    for job_code, status_counts in summary["job_totals"].items():
        status_text = ", ".join(f"`{status}`: {count}" for status, count in status_counts.items())
        lines.append(f"- `{job_code}`: {status_text}")

    lines.extend(["", "## Gate Rules", ""])
    lines.extend(
        [
            "- `go_worker_prototype_candidate`: at least 3 runs, at least 2 runs with 2+ successful jobs, and no run where blocked/parser errors dominate.",
            "- `hold_http_unstable_candidate`: at least 2 runs where blocked/parser errors dominate.",
            "- `continue_endurance`: not enough evidence yet.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def write_gate_summary(runs_dir: Path, output_path: Path) -> int:
    report = render_gate_summary(summarize_gate(runs_dir))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")
    print(str(output_path))
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/search_jobs.json")
    parser.add_argument("--runs-dir", default="runs")
    parser.add_argument("--analyze-run")
    parser.add_argument("--write-markdown-report")
    parser.add_argument("--write-endurance-doc")
    parser.add_argument("--write-gate-summary", action="store_true")
    parser.add_argument("--output")
    parser.add_argument("--day")
    parser.add_argument("--date")
    parser.add_argument("--decision")
    parser.add_argument("--next-action")
    parser.add_argument("--dry-run-config", action="store_true")
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--from-html")
    parser.add_argument("--job-code")
    args, remaining = parser.parse_known_args()
    config_path = Path(args.config)

    if args.dry_run_config:
        raise SystemExit(print_config_validation(config_path))
    if args.preflight:
        raise SystemExit(print_preflight(config_path, Path(args.runs_dir)))
    if args.analyze_run:
        raise SystemExit(print_run_analysis(Path(args.analyze_run)))
    if args.write_markdown_report:
        if not args.output:
            raise SystemExit("--output is required with --write-markdown-report")
        raise SystemExit(write_markdown_report(Path(args.write_markdown_report), Path(args.output)))
    if args.write_endurance_doc:
        missing = [
            name
            for name, value in [
                ("--output", args.output),
                ("--day", args.day),
                ("--date", args.date),
            ]
            if not value
        ]
        if missing:
            raise SystemExit(", ".join(missing) + " required with --write-endurance-doc")
        raise SystemExit(
            write_endurance_doc(
                Path(args.write_endurance_doc),
                Path(args.output),
                args.day,
                args.date,
                args.decision,
                args.next_action,
            )
        )
    if args.write_gate_summary:
        if not args.output:
            raise SystemExit("--output is required with --write-gate-summary")
        raise SystemExit(write_gate_summary(Path(args.runs_dir), Path(args.output)))
    if args.from_html:
        if not args.job_code:
            raise SystemExit("--job-code is required with --from-html")
        raise SystemExit(
            process_from_html(config_path, args.job_code, Path(args.from_html), Path(args.runs_dir))
        )

    import sys

    sys.argv = [sys.argv[0], "--config", str(config_path), "--runs-dir", args.runs_dir, *remaining]
    raise SystemExit(main())
