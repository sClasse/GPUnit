# GPU Deal Scoring Algorithm

Goal: score listings based on probability of profitable resale.

## Inputs

listing_price
market_price
title
seller_feedback
condition

## Discount calculation

discount =

(market_price - listing_price) / market_price

## Price score

price_score = discount * 100

## Title score

Signals poorly written listings.

Rules:

- title < 4 words → +5
- missing GPU model → +10
- generic terms → +5

## Repair signal

Keyword detection:

artifact
no display
for parts
not tested
broken

repair_score = 15 if keyword match

## Seller score

seller_feedback < 20 → +5

## Final score

deal_score =
(price_score * 0.6) +
(title_score * 0.15) +
(repair_score * 0.15) +
(seller_score * 0.1)

## Deal thresholds

score < 15 → ignore
15–30 → good deal
30–45 → strong deal
45+ → urgent alert