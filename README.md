# GPUnit - GPU Arbitrage Bot

A Python-based bot that scrapes eBay GPU listings, computes market prices from historical sales data, detects arbitrage opportunities, and alerts users via Discord, CLI, or browser extension.

## Features

- **Web Scraping**: Automated scraping of eBay GPU listings using Playwright and BeautifulSoup.
- **Market Pricing**: Calculates reliable market prices using median pricing and weighted medians from historical sales.
- **Deal Detection**: Identifies deals below market value with a customizable scoring algorithm.
- **Alerts**: Real-time notifications via Discord bot, terminal output, or Firefox extension.
- **Data Storage**: SQLite database for listings, market stats, and detected deals.
- **Browser Extension**: Firefox extension with price overlays and deal indicators.

## Project Structure

```
GPUnit/
├── gpu-arbitrage-bot/          # Core bot documentation and specs
│   ├── alerts/                 # Discord bot specifications
│   ├── data/                   # Database schema
│   ├── deal_detection/         # Scoring algorithm
│   ├── pricing/                # Pricing model
│   └── System Architecture.md  # System overview and diagrams
├── firefox_extension/          # Firefox extension files
├── Archive/                    # Archived files
├── Pulls/                      # Historical sales data CSVs
├── gpu_scrape_errors/          # Error logs from scraping
├── condense.py                 # Data processing script
├── GPU_scrape_pre_co_pilot.py  # Scraper for historical sales
├── requirements.txt            # Python dependencies
└── README.md                   # This file
```

## Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/sClasse/GPUnit.git
   cd GPUnit
   ```

2. **Set up Python environment**:
   ```bash
   python -m venv venv
   # On Windows: venv\Scripts\activate
   # On macOS/Linux: source venv/bin/activate
   pip install -r requirements.txt
   playwright install  # Install browser binaries
   ```

3. **Initialize the database**:
   ```bash
   python -c "
   import sqlite3
   conn = sqlite3.connect('gpu_arbitrage.db')
   # Run schema creation scripts here
   conn.close()
   "
   ```

## Usage

### Running the Scraper
```bash
python GPU_scrape_pre_co_pilot.py  # Scrapes historical sales (for pricing data)
```

### Processing Data
```bash
python condense.py  # Combines CSVs and computes averages
```

### Firefox Extension
1. Open Firefox and go to `about:debugging`.
2. Click "This Firefox" > "Load Temporary Add-on".
3. Select `firefox_extension/manifest.json`.
4. The extension will overlay prices on eBay/Facebook Marketplace.

## Development Roadmap

### Phase 0: Prerequisites and Setup ✅
- Environment setup, documentation review, database initialization.

### Phase 1: MVP (Core Functionality) 🔄
- Integrate scraper with database.
- Implement pricing engine and deal detection.
- Basic CLI alerts.

### Phase 2: Alerts System
- Discord bot integration.
- Alert deduplication and rate limiting.

### Phase 3: Browser Extension
- Price overlays and deal indicators.

## Contributing

1. Fork the repository.
2. Create a feature branch: `git checkout -b feature-name`.
3. Commit changes: `git commit -m 'Add feature'`.
4. Push to branch: `git push origin feature-name`.
5. Open a Pull Request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Disclaimer

This bot is for educational purposes. Respect website terms of service and rate limits when scraping. Use responsibly.
