// Content script to show recommended GPU prices on eBay and Facebook Marketplace

// Function to extract GPU type from title
function extractGpuType(title) {
  if (!title) return null;
  const t = title.trim();
  const upper = t.toUpperCase();

  // Match NVIDIA RTX/GTX variants (e.g., "RTX 4070 Ti", "gtx1060", "RTX-3080 SUPER")
  const nvidiaMatch = upper.match(/\b(RTX|GTX)\s*-?\s*(\d{3,4})(?:\s*(TI|SUPER|SUPER))?\b/);
  if (nvidiaMatch) {
    const model = nvidiaMatch[2];
    const suffix = nvidiaMatch[3] ? nvidiaMatch[3].replace(/SUPER/i, 'Super').replace(/TI/i, 'Ti') : '';
    return `${model}${suffix ? ' ' + suffix : ''}`.trim();
  }

  // Match AMD RX variants (e.g., "RX 580", "RX 6800 XT")
  const amdMatch = upper.match(/\b(RX)\s*-?\s*(\d{3,4})(?:\s*(XT|XTX))?\b/);
  if (amdMatch) {
    const model = amdMatch[2];
    const suffix = amdMatch[3] ? amdMatch[3].toUpperCase() : '';
    return `RX ${model}${suffix ? ' ' + suffix : ''}`.trim();
  }

  return null;
}

// Function to extract current price
function extractPrice() {
  // Prioritize known selectors from eBay/Facebook structure
  const selectors = [
    '.s-card__price',  // Search results price
    '#prcIsum',        // eBay detail page price
    '[class*="notranslate"]',
    '[data-testid*="price"]',
    '[class*="price"]',
    '[class*="amount"]',
    '[class*="cost"]'
  ];
  for (const sel of selectors) {
    const el = document.querySelector(sel);
    if (el) {
      const text = el.textContent.trim();
      const match = text.match(/\$?(\d+(?:\.\d{2})?)/);
      if (match) return parseFloat(match[1]);
    }
  }
  // Fallback: search for price-like text in the page
  const bodyText = document.body.textContent;
  const priceMatch = bodyText.match(/\$(\d+(?:\.\d{2})?)/);
  if (priceMatch) return parseFloat(priceMatch[1]);
  return null;
}

// Function to show recommendation
function showRecommendation(averageData, current, gpuType = 'GPU') {
  // averageData is now an object with { used, parts } properties
  const usedPrice = averageData.used || averageData;  // Fallback for backward compatibility
  const partsPrice = averageData.parts;
  
  const recommended = usedPrice * 0.8;  // 20% below average used price
  const div = document.createElement('div');
  div.id = 'gpu-recommendation-overlay';
  div.style.cssText = `
    position: fixed;
    top: 50px;
    right: 50px;
    background: rgba(255, 255, 255, 0.95);
    border: 2px solid #007bff;
    padding: 50px;
    z-index: 10000;
    font-family: Arial, sans-serif;
    font-size: 14px;
    box-shadow: 0 0 10px rgba(0,0,0,0.5);
    max-width: 300px;
    border-radius: 5px;
    backdrop-filter: blur(4px);
  `;
  const diff = ((current - recommended) / recommended * 100).toFixed(1);
  const color = current > recommended ? 'red' : 'green';
  
  // Build the overlay content
  let content = `
    <div style="display: flex; justify-content: space-between; align-items: center;">
      <strong>${gpuType} Price Recommendation</strong>
      <button id="close-overlay" style="background: none; border: none; font-size: 16px; cursor: pointer;">&times;</button>
    </div>
    <br>
    <strong>Market Summary (Last 90 Days)</strong><br>
    Average Used Price: $${usedPrice}<br>`;
  
  if (partsPrice && partsPrice > 0) {
    content += `Average Parts Price: $${partsPrice}<br>`;
  }
  
  content += `<br>
    Recommended (20% below avg): $${recommended.toFixed(2)}<br>
    Current: $${current}<br>
    <span style="color: ${color};">${diff}% ${current > recommended ? 'above' : 'below'} recommended</span>
  `;
  
  div.innerHTML = content;
  document.body.appendChild(div);
  // Add close functionality
  document.getElementById('close-overlay').addEventListener('click', () => {
    div.remove();
  });
}

// Overlay helper (shared by recommendation and status messages)
function clearOverlay() {
  const existing = document.getElementById('gpu-recommendation-overlay');
  if (existing) existing.remove();
}

function showMessage(message, gpuType = 'GPU') {
  clearOverlay();
  const div = document.createElement('div');
  div.id = 'gpu-recommendation-overlay';
  div.style.cssText = `
    position: fixed;
    top: 10px;
    right: 10px;
    background: rgba(255, 255, 255, 0.95);
    border: 2px solid #007bff;
    padding: 10px;
    z-index: 10000;
    font-family: Arial, sans-serif;
    font-size: 14px;
    box-shadow: 0 0 10px rgba(0,0,0,0.5);
    max-width: 300px;
    border-radius: 5px;
    backdrop-filter: blur(4px);
  `;
  div.innerHTML = `
    <div style="display: flex; justify-content: space-between; align-items: center;">
      <strong>${gpuType} Price Recommendation</strong>
      <button id="close-overlay" style="background: none; border: none; font-size: 16px; cursor: pointer;">&times;</button>
    </div>
    <br>
    ${message}
  `;
  document.body.appendChild(div);
  document.getElementById('close-overlay').addEventListener('click', () => {
    div.remove();
  });
}

function attemptShowRecommendation() {
  // Prioritize known title selectors for eBay/Facebook detail pages
  const titleSelectors = [
    '#itemTitle',  // eBay detail page title
    'h1.it-ttl',   // eBay alternative
    'h1',          // General h1
    '[data-testid*="title"]',
    'title'        // Fallback to document title
  ];
  let titleEl = null;
  for (const sel of titleSelectors) {
    titleEl = document.querySelector(sel);
    if (titleEl) break;
  }
  const title = titleEl ? titleEl.textContent : document.title;
  const gpuType = extractGpuType(title);
  const currentPrice = extractPrice();
  const average = gpuType ? gpuAverages[gpuType] : null;

  console.log('Title used for GPU extraction:', title);
  console.log('GPU Type detected:', gpuType);
  console.log('Current Price detected:', currentPrice);
  console.log('Average for type:', average);

  if (!gpuType) {
    showMessage(`Could not detect a GPU model from the title: "${title}"`);
    return false;
  }
  if (!average || !average.used) {
    showMessage(`No average price available for "${gpuType}".`, gpuType);
    return false;
  }
  if (!currentPrice) {
    showMessage('Could not detect the current listing price.', gpuType);
    return false;
  }

  showRecommendation(average, currentPrice, gpuType);
  return true;
}

// Helpers for search-results enhancements
function addBadgeToItem(item, statusIndicator, textColor, gpuData, currentPrice) {
  if (item.querySelector('.gpu-recommendation-badge')) return;
  const badge = document.createElement('div');
  badge.className = 'gpu-recommendation-badge';
  badge.style.cssText = `
    position: absolute;
    top: 8px;
    right: 8px;
    background: white;
    padding: 8px 10px;
    border-radius: 4px;
    font-size: 13px;
    font-weight: bold;
    z-index: 1000;
    cursor: pointer;
    border: 1px solid #ccc;
    line-height: 1.4;
  `;
  
  // Calculate percentage differences
  const usedDiff = ((currentPrice - gpuData.usedPrice) / gpuData.usedPrice * 100).toFixed(0);
  const partsDiff = gpuData.partsPrice > 0 ? ((currentPrice - gpuData.partsPrice) / gpuData.partsPrice * 100).toFixed(0) : null;
  
  // Determine color for percentages (green for negative/cheap, red for positive/expensive)
  const usedColor = usedDiff < 0 ? '#00aa00' : '#cc0000';
  const partsColor = partsDiff < 0 ? '#00aa00' : '#cc0000';
  
  // Build badge content with GPU type and colored prices
  let badgeHTML = `${gpuData.type}<br>`;
  badgeHTML += `Used: $${gpuData.usedPrice} <span style="color: ${usedColor}">(${usedDiff > 0 ? '+' : ''}${usedDiff}%)</span> [${gpuData.usedVol}]<br>`;
  if (gpuData.partsPrice > 0) {
    badgeHTML += `Parts: $${gpuData.partsPrice} <span style="color: ${partsColor}">(${partsDiff > 0 ? '+' : ''}${partsDiff}%)</span> [${gpuData.partsVol}]`;
  } else {
    badgeHTML += `Parts: N/A`;
  }
  
  badge.innerHTML = badgeHTML;
  
  item.style.position = item.style.position || 'relative';
  item.appendChild(badge);
}

function processSearchResults() {
  const allItems = document.querySelectorAll(
    '.su-card-container, .srp-results .s-item, .ui-search-result, [data-testid="search-result-item"], .s-item'
  );
  if (!allItems.length) {
    console.log('GPU extension: no search items found yet');
  }

  let debugCount = 0;
  allItems.forEach(item => {
    if (item.dataset.gpuPriceChecked) return;
    item.dataset.gpuPriceChecked = 'true';

    const titleEl = item.querySelector(
      '.s-card__title, .s-item__title, .ui-search-item__title, h2, h3, [data-testid="item-title"]'
    );
    const priceEl = item.querySelector(
      '.s-card__price, .s-item__price, .ui-search-price__part, .s-item__detail span, .price, [data-testid="item-price"]'
    );

    if (!titleEl || !priceEl) {
      if (debugCount < 3) {
        console.log('GPU extension: missing title or price for item', item);
        debugCount += 1;
      }
      return;
    }

    const title = titleEl.textContent.trim();
    const priceText = priceEl.textContent.trim();
    const priceMatch = priceText.match(/\$?(\d+(?:\.\d{2})?)/);
    if (!priceMatch) return;

    const price = parseFloat(priceMatch[1]);
    const gpuType = extractGpuType(title);
    const average = gpuType ? gpuAverages[gpuType] : null;
    if (!gpuType || !average) return;

    // Use the used price as the baseline for comparison
    const baseline = average.used || average;
    const recommended = baseline * 0.8;
    
    // Build GPU data object
    const gpuData = {
      type: gpuType,
      usedPrice: average.used,
      partsPrice: average.parts || 0,
      usedVol: average.usedVol || 0,
      partsVol: average.partsVol || 0
    };
    
    // Determine status indicator and color based on price comparison
    let statusIndicator, textColor;
    if (price <= recommended) {
      statusIndicator = '✓';
      textColor = '#00aa00';  // Green - great deal
    } else if (price <= baseline) {
      statusIndicator = '⚠️';
      textColor = '#ff9900';  // Yellow/Orange - fair price
    } else {
      statusIndicator = '✕';
      textColor = '#cc0000';  // Red - overpriced
    }
    
    addBadgeToItem(item, statusIndicator, textColor, gpuData, price);
  });
}

function isSearchResultsPage() {
  const url = window.location.href;
  return url.includes('/sch/') || url.includes('/search/') || url.includes('/marketplace/');
}

// Main logic
if (window.location.hostname.includes('ebay.com') || window.location.hostname.includes('facebook.com')) {
  console.log('GPU extension loaded on:', window.location.href);
  
  function runAfterLoad() {
    console.log('GPU extension: page loaded, checking if search page');
    // Scan search results pages (listings grid)
    if (isSearchResultsPage()) {
      console.log('GPU extension: detected search page, processing results');
      processSearchResults();
      const observer = new MutationObserver(() => processSearchResults());
      observer.observe(document.body, { childList: true, subtree: true });
      return; // Skip the detail-page overlay logic on search pages
    }

    // On detail pages, show the popup overlay
    console.log('GPU extension: detected detail page, attempting overlay');
    let attempts = 0;
    const maxAttempts = 10;
    const interval = setInterval(() => {
      attempts += 1;
      const done = attemptShowRecommendation();
      if (done || attempts >= maxAttempts) {
        clearInterval(interval);
      }
    }, 1500);
  }
  
  if (document.readyState === 'complete') {
    runAfterLoad();
  } else {
    window.addEventListener('load', runAfterLoad);
  }
}