# Market Pricing Model

Goal: compute a reliable market reference price for each GPU.

Average price is not reliable due to outliers.

Use median pricing instead.

## Baseline formula

market_price = median(last_30_days_sales)

## Weighted median

More recent listings have higher weight.

Example:

0–3 days old → weight 3
4–10 days → weight 2
10–30 days → weight 1

## Trend calculation

price_trend =

median_price_7d - median_price_30d

Positive trend → rising demand
Negative trend → declining prices