# Database Schema

## listings

Stores raw scraped listings.

| column | type |
|------|------|
id | text |
platform | text |
title | text |
gpu_model | text |
price | float |
condition | text |
seller_id | text |
seller_feedback | integer |
location | text |
url | text |
created_at | timestamp |

---

## market_stats

Computed statistics per GPU model.

| column | type |
|------|------|
gpu_model | text |
median_price_30d | float |
median_price_7d | float |
sales_volume | integer |
price_trend | float |

---

## deals

Flagged deals detected by the scoring engine.

| column | type |
|------|------|
listing_id | text |
gpu_model | text |
price | float |
market_price | float |
discount | float |
deal_score | float |
detected_at | timestamp |