#!/usr/bin/env python3
"""Manual Youla catalog probe.

This script is intentionally small and unscheduled. It performs one public
catalog GraphQL request and prints normalized listing JSON.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


GRAPHQL_ENDPOINT = "https://api-gw.youla.ru/graphql"
APP_ID = "web/3"
ANON_UID = "6a384e7d63341"
MOSCOW_LOCATION = {"latitude": 55.750718, "longitude": 37.617661}

CATALOG_QUERY = """
query catalogProductsBoard($sort: Sort, $attributes: [AttributeItem!], $location: LocationInput, $cursor: Cursor!, $search: String, $datePublished: DateInput) {
  feed(input: {sort: $sort, attributes: $attributes, location: $location, search: $search, datePublished: $datePublished}, after: $cursor) {
    items {
      ... on BannerItem {
        type
        banner { title description buttonTitle imageURL }
      }
      ... on PromotedProductItem {
        product: productPromoted {
          id
          categoryId: category
          subcategoryId: subcategory
          price {
            origPrice { price }
            realPrice { price }
            realPriceText
            discount
          }
          url
          images { id num url }
          name
          location { cityName city addressText description latitude longitude }
          distanceText
          isPromoted
          favorite { enabled }
          deliveryAvailable
          paymentAvailable
          branding { imageUrl rating }
          salaryText
        }
        productAnalytics { promotionType }
      }
      ... on ProductItem {
        product {
          id
          categoryId: category
          subcategoryId: subcategory
          price {
            origPrice { price }
            realPrice { price }
            realPriceText
            discount
          }
          url
          images { id num url }
          name
          location { cityName city addressText description latitude longitude }
          distanceText
          isPromoted
          favorite { enabled }
          deliveryAvailable
          paymentAvailable
          branding { imageUrl rating }
          salaryText
        }
        productAnalytics { promotionType }
      }
    }
    pageInfo {
      cursor
      hasNextPage
      personalSearchId
      productsAnalytics { searchId }
    }
  }
}
""".strip()


def build_payload(search: str, cursor: str = "") -> dict[str, Any]:
    return {
        "operationName": "catalogProductsBoard",
        "variables": {
            "sort": "DEFAULT",
            "attributes": [{"slug": "categories", "value": [""], "from": None, "to": None}],
            "location": MOSCOW_LOCATION,
            "search": search,
            "cursor": cursor,
        },
        "query": CATALOG_QUERY,
    }


def fetch_catalog(search: str, timeout: float) -> dict[str, Any]:
    body = json.dumps(build_payload(search), ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        GRAPHQL_ENDPOINT,
        data=body,
        method="POST",
        headers={
            "Accept": "*/*",
            "Content-Type": "application/json",
            "Origin": "https://youla.ru",
            "Referer": f"https://youla.ru/all?q={urllib.parse.quote(search)}",
            "User-Agent": "Mozilla/5.0 equipment-accounting-youla-poc/0.1",
            "x-app-id": APP_ID,
            "appId": APP_ID,
            "x-uid": ANON_UID,
            "uid": ANON_UID,
            "x-offset-utc": "-25200",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response_body = response.read()
            return {
                "http_status": response.status,
                "payload": json.loads(response_body.decode("utf-8")),
            }
    except urllib.error.HTTPError as exc:
        return {
            "http_status": exc.code,
            "error": exc.read().decode("utf-8", errors="replace"),
        }
    except urllib.error.URLError as exc:
        return {
            "http_status": None,
            "error": str(exc),
        }


def normalize_product(item: dict[str, Any]) -> dict[str, Any] | None:
    product = item.get("product")
    if not isinstance(product, dict):
        return None

    price = product.get("price") or {}
    real_price = price.get("realPrice") or {}
    raw_price = real_price.get("price")
    normalized_price = raw_price / 100 if isinstance(raw_price, int | float) else None
    url = product.get("url")

    return {
        "source": "youla",
        "id": product.get("id"),
        "title": product.get("name"),
        "price_raw": raw_price,
        "price_rub": normalized_price,
        "price_text": price.get("realPriceText"),
        "url": f"https://youla.ru{url}" if isinstance(url, str) and url.startswith("/") else url,
        "city": (product.get("location") or {}).get("cityName"),
        "distance": product.get("distanceText"),
        "category_id": product.get("categoryId"),
        "subcategory_id": product.get("subcategoryId"),
    }


def normalize_response(search: str, result: dict[str, Any]) -> dict[str, Any]:
    payload = result.get("payload") or {}
    feed = ((payload.get("data") or {}).get("feed") or {})
    items = feed.get("items") or []
    products = [
        normalized
        for item in items
        if isinstance(item, dict)
        for normalized in [normalize_product(item)]
        if normalized is not None
    ]
    return {
        "source": "youla",
        "search": search,
        "http_status": result.get("http_status"),
        "status": "ok" if result.get("http_status") == 200 and products else "no_data",
        "count": len(products),
        "has_next_page": (feed.get("pageInfo") or {}).get("hasNextPage"),
        "cursor": (feed.get("pageInfo") or {}).get("cursor"),
        "items": products,
        "raw_errors": payload.get("errors"),
        "error": result.get("error"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one manual Youla catalog query.")
    parser.add_argument("search", help="Search phrase, for example: Lenovo ThinkPad T14")
    parser.add_argument("--timeout", type=float, default=15.0)
    args = parser.parse_args()

    result = fetch_catalog(args.search, args.timeout)
    normalized = normalize_response(args.search, result)
    json.dump(normalized, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0 if normalized["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
