# GPU Price Recommender Firefox Extension

This extension shows recommended purchase prices for GPUs on eBay and Facebook Marketplace listings, based on your recent sales data averages.

## Files

- `manifest.json`: Extension configuration with content scripts for eBay and Facebook Marketplace (Manifest V3).
- `data.js`: Contains average prices per GPU type from your data.
- `content.js`: Script that runs on listing pages, extracts GPU type and price, and displays recommendation with improved detection and error handling.

## How to Install

1. Open Firefox and go to `about:debugging`.
2. Click "Load Temporary Add-on".
3. Select `manifest.json` from this directory.
4. Visit a GPU listing on eBay or Facebook Marketplace to see the recommendation overlay.

## What it does

- Automatically detects GPU listings by parsing the page title with expanded patterns (e.g., "GeForce RTX 4070").
- Matches the GPU model to your average sale prices.
- Displays a fixed overlay in the top-right corner showing the average sale price, recommended price (20% below average), current listing price, and percentage difference.
- Includes a close button to dismiss the overlay.
- Adds console logging for debugging if detection fails.
- Waits 2 seconds after page load for dynamic content.

## Notes

- The data is based on your "GPU Cleaned.csv" averages from the last 3 months.
- Improved price extraction with more selectors and fallback text search.
- For production, consider more robust parsing or API integration.