# GPU Arbitrage Bot

A system that detects underpriced GPUs across marketplaces and alerts the user in real time.

Primary use cases:

- Identify GPUs listed below market value
- Detect repairable GPUs for resale
- Track GPU market trends
- Alert the user to profitable listings quickly

Target platforms:

- eBay
- Facebook Marketplace

Core components:

1. Scraper layer (completed already; check "GPU_scrape_pre_co_pilot.py")
2. Listing database
3. Market pricing engine
4. Deal detection engine
5. Alert system
6. Firefox Browser Extension

Primary language: Python
Primary storage: SQLite