# Youla Source Discovery

Date: 2026-06-21

## Goal

Check whether Youla can be used as an additional experimental market source for the pricing module after Avito started returning `HTTP 403` for all monitored jobs on Day 4.

## Summary

Youla is technically reachable from the current server and can return public listing data through its GraphQL catalog endpoint.

This does not make Youla a production-stable source yet. It is a better candidate for a second manual experimental source than repeating blocked Avito runs, because the first controlled request returned `HTTP 200` and listing payloads with prices.

## What Was Checked

Direct HTTP checks:

- `https://youla.ru/` returned `HTTP 200`.
- `https://www.youla.ru/` redirected to `https://youla.ru/`.
- `https://m.youla.ru/` redirected to `https://youla.io/`.
- `https://youla.ru/moskva?q=Lenovo%20ThinkPad%20T14` returned `HTTP 200`.
- `https://youla.ru/all?q=Lenovo%20ThinkPad%20T14` returned `HTTP 200`.

The HTML contains `window.__YOULA_STATE__` with:

- `apiUri: https://api.youla.ru`
- `apiFederationUri: https://api-gw.youla.ru/graphql`
- `apiProxyUri: /web-api`
- `apiClientId: web/3`
- public anonymous `uid`
- Moscow geolocation data

The SSR state did not contain product listings. Listing data is loaded by the frontend through Apollo GraphQL.

## GraphQL Endpoint

Relevant frontend query found in Youla JS bundles:

```graphql
query catalogProductsBoard(
  $sort: Sort,
  $attributes: [AttributeItem!],
  $location: LocationInput,
  $cursor: Cursor!,
  $search: String,
  $datePublished: DateInput
) {
  feed(
    input: {
      sort: $sort,
      attributes: $attributes,
      location: $location,
      search: $search,
      datePublished: $datePublished
    },
    after: $cursor
  ) {
    items {
      ... on BannerItem {
        type
        banner {
          title
          description
          buttonTitle
          imageURL
        }
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
          location {
            cityName
            city
            addressText
            description
            latitude
            longitude
          }
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
          location {
            cityName
            city
            addressText
            description
            latitude
            longitude
          }
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
```

Control request:

- endpoint: `https://api-gw.youla.ru/graphql`
- operation: `catalogProductsBoard`
- search: `Lenovo ThinkPad T14`
- location: Moscow coordinates from SSR state
- result: `HTTP 200`
- payload: product items with `id`, `name`, `price.origPrice.price`, `price.realPrice.price`, `price.realPriceText`, `url`, `location.cityName`, `distanceText`
- pageInfo returned cursor and `hasNextPage: true`

Manual POC script verification:

- command: `python3 research/youla-source-poc/fetch_youla_catalog.py 'Lenovo ThinkPad T14'`
- result: `HTTP 200`
- normalized status: `ok`
- normalized count: `30`
- first normalized price example: `4500000 -> 45000.0`

## Important Data Shape

Observed price units are integer kopecks, not rubles:

- `4500000` corresponds to `45 000 ₽`.
- `13500000` corresponds to `135 000 ₽`.
- `799000` corresponds to `7 990 ₽`.

For normalization:

- store raw source price as returned;
- store normalized rubles as `price / 100`;
- keep `realPriceText` for audit/debug display.

## Source Quality Notes

Pros:

- public endpoint returned `HTTP 200` from the same server where Avito returned `HTTP 403`;
- no login was needed for the tested catalog query;
- payload already has structured prices, title, URL, city and distance;
- pagination exists through `pageInfo.cursor`.

Risks:

- this is an internal web GraphQL API, not a stable public partner API;
- request headers and query schema can change without notice;
- current first request was only a discovery check, not endurance testing;
- search relevance is broad: a `Lenovo ThinkPad T14` query returned some unrelated Lenovo models, so existing relevance filtering is still required;
- Youla coverage for some enterprise equipment may be weaker than Avito.

## Decision

Recommended next state: `youla_manual_source_poc`.

Use Youla as a manual experimental source behind the same source-status boundary as Avito:

- no scheduler;
- no background repeated crawling;
- one controlled run per test window;
- store every run as a snapshot with source status;
- do not treat a successful Youla response as proof of production reliability.

## Next Steps

1. Add a small manual Youla POC script that runs one query and emits normalized JSON.
2. Run it against the current monitored items once, with conservative pacing.
3. Compare Youla relevance and median prices with the last successful Avito snapshots.
4. If useful, add `source = youla` snapshots to the pricing history model without changing the UI contract.
5. Keep Avito as `manual_experimental` / `blocked_recently`; do not repeat blocked Avito same-day.
