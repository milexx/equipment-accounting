# Youla Source POC

Manual discovery prototype for using Youla as an experimental pricing source.

Status on 2026-06-21:

- Youla home/search HTML returns `HTTP 200` from the current server.
- Public listing data is available through `https://api-gw.youla.ru/graphql`.
- The first controlled query for `Lenovo ThinkPad T14` returned product cards and prices.

This is not integrated into the application and must not be scheduled.

Run manually:

```bash
python3 fetch_youla_catalog.py "Lenovo ThinkPad T14"
```

The script emits normalized JSON to stdout. Prices from Youla are returned in kopecks and normalized to rubles.
