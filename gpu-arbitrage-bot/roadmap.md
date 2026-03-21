# Development Roadmap

## Phase 1 — MVP

Goals:

- Scrape eBay GPU listings (completed already; check "GPU_scrape_pre_co_pilot.py")
- Ensure "GPU_scrape_pre_co_pilot.py" includes all required fields
- Modify scraper to fetch active listings (currently fetches sold/completed)
- Store listings in SQLite
- Compute median prices
- Detect listings 20% below market
- Print deal alerts in terminal

Deliverables:

- market_price_calculator.py
- deal_detector.py

---

## Phase 2 — Alerts

Add real-time notifications.

Features:

- Discord bot alerts
- configurable deal thresholds
- alert deduplication

Deliverables:

- discord_bot.py
- alert_manager.py

---

## Phase 3 — Browser Extension

Firefox extension that enhances eBay and facebook marketplace search pages.

Features:

- overlay showing market price
- deal score indicator
- price comparison