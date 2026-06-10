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

// Detect category from title: GPU, RAM, Motherboard
function detectCategory(title) {
  if (!title) return 'GPU';
  const t = title.toLowerCase();
  if (/\bddr\d\b/.test(t) || /\bram\b/.test(t) || /\bmemory\b/.test(t)) return 'RAM';
  if (/motherboard|mobo|\bmb\b|chipset|\b(b|z|x)\d{3,4}\b/i.test(t)) return 'Motherboard';
  if (extractGpuType(title)) return 'GPU';
  return 'GPU';
}

// Try to extract OEM (brand) and Model from title using heuristics
function extractOEMModel(title) {
  if (!title) return { oem: null, model: null };
  const t = title.trim();
  const brands = ['ASUS','MSI','GIGABYTE','EVGA','ZOTAC','PNY','SAPPHIRE','XFX','PALIT','GALAX','CORSAIR','G.SKILL','KINGSTON','CRUCIAL','TEAM','PATRIOT','ASRock','BIOSTAR','INTEL','AMD'];
  let oem = null;
  for (const b of brands) {
    const re = new RegExp('\\b' + b + '\\b', 'i');
    if (re.test(t)) { oem = b; break; }
  }
  const modelMatch = t.match(/(ROG STRIX|TUF GAMING|VENTUS|SUPRIM|GAMING X TRIO|GAMING X|VENGEANCE LPX|VENGEANCE|TRIDENT Z|DOMINATOR|STRIX|B\d{3,4}[A-Z\-]*|Z\d{3,4}[A-Z\-]*|X\d{3,4}[A-Z\-]*|RTX\s*-?\s*\d{3,4}(?:\s*TI|\s*SUPER)?|GTX\s*-?\s*\d{3,4}|RX\s*-?\s*\d{3,4}(?:\s*XT|\s*XTX)?)/i);
  let model = modelMatch ? modelMatch[0].trim() : null;
  if (!model && oem) {
    const re = new RegExp(oem + '\\s+([A-Z0-9][A-Za-z0-9\\- ]{1,40})', 'i');
    const m = t.match(re);
    if (m) model = m[1].trim().split(/\s{2,}|\s/).slice(0,4).join(' ');
  }
  return { oem: oem, model: model };
}

// Find the best matching key in category data using candidate strings
function findBestMatch(categoryData, candidates) {
  if (!categoryData) return null;
  for (const c of candidates) {
    if (!c) continue;
    if (categoryData[c]) return categoryData[c];
  }
  const keys = Object.keys(categoryData);
  for (const c of candidates) {
    if (!c) continue;
    const lc = c.toLowerCase();
    const k = keys.find(k => k.toLowerCase() === lc);
    if (k) return categoryData[k];
  }
  for (const c of candidates) {
    if (!c) continue;
    const lc = c.toLowerCase();
    const k = keys.find(k => k.toLowerCase().includes(lc) || lc.includes(k.toLowerCase()));
    if (k) return categoryData[k];
  }
  return null;
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
  const currentPrice = extractPrice();
  const category = detectCategory(title);
  const { oem, model } = extractOEMModel(title);
  const dataByCategory = window.dataByCategory || { GPU: window.gpuAverages || {}, RAM: window.ramAverages || {}, Motherboard: window.motherboardAverages || {} };
  const categoryData = dataByCategory[category] || {};

  // Candidate keys to try: model, OEM+model, gpuType (for GPUs), title fragments
  const gpuType = extractGpuType(title);
  const candidates = [];
  if (model) candidates.push(model);
  if (oem && model) candidates.push(`${oem} ${model}`);
  if (gpuType) candidates.push(gpuType);
  candidates.push(title.trim());

  const average = findBestMatch(categoryData, candidates) || null;

  console.log('Title used for extraction:', title);
  console.log('Detected category:', category);
  console.log('OEM/model detected:', oem, model);
  console.log('Current Price detected:', currentPrice);
  console.log('Average matched:', average);

  if (!average) {
    showMessage(`No average price available for this listing.`, category);
    return false;
  }
  if (!currentPrice) {
    showMessage('Could not detect the current listing price.', category);
    return false;
  }

  const displayLabel = model || gpuType || title;
  showRecommendation(average, currentPrice, displayLabel);
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
  const usedPriceVal = Number(gpuData.usedPrice) || 0;
  const partsPriceVal = Number(gpuData.partsPrice) || 0;
  const usedDiff = usedPriceVal ? ((currentPrice - usedPriceVal) / usedPriceVal * 100).toFixed(0) : 'N/A';
  const partsDiff = partsPriceVal ? ((currentPrice - partsPriceVal) / partsPriceVal * 100).toFixed(0) : null;
  
  // Determine color for percentages (green for negative/cheap, red for positive/expensive)
  const usedColor = usedDiff < 0 ? '#00aa00' : '#cc0000';
  const partsColor = partsDiff < 0 ? '#00aa00' : '#cc0000';
  
  // Build badge content with item label and colored prices
  const label = gpuData.type || gpuData.label || gpuData.model || gpuData.oem || 'Item';
  let badgeHTML = `${label}<br>`;
  badgeHTML += `Used: $${usedPriceVal} <span style="color: ${usedColor}">(${usedDiff !== 'N/A' ? (usedDiff > 0 ? '+' : '') + usedDiff + '%' : 'N/A'})</span> [${gpuData.usedVol || 0}]<br>`;
  if (partsPriceVal > 0) {
    badgeHTML += `Parts: $${partsPriceVal} <span style="color: ${partsColor}">(${partsDiff > 0 ? '+' : ''}${partsDiff}%)</span> [${gpuData.partsVol || 0}]`;
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
    const category = detectCategory(title);
    const { oem, model } = extractOEMModel(title);
    const dataByCategory = window.dataByCategory || { GPU: window.gpuAverages || {}, RAM: window.ramAverages || {}, Motherboard: window.motherboardAverages || {} };
    const categoryData = dataByCategory[category] || {};
    const gpuType = extractGpuType(title);
    const candidates = [];
    if (model) candidates.push(model);
    if (oem && model) candidates.push(`${oem} ${model}`);
    if (gpuType) candidates.push(gpuType);
    candidates.push(title.trim());
    const average = findBestMatch(categoryData, candidates);
    if (!average) return;

    const baseline = average.used || average;
    const recommended = baseline * 0.8;

    const itemData = {
      label: model || gpuType || title,
      usedPrice: average.used,
      partsPrice: average.parts || 0,
      usedVol: average.usedVol || 0,
      partsVol: average.partsVol || 0
    };

    let statusIndicator, textColor;
    if (price <= recommended) {
      statusIndicator = '✓';
      textColor = '#00aa00';
    } else if (price <= baseline) {
      statusIndicator = '⚠️';
      textColor = '#ff9900';
    } else {
      statusIndicator = '✕';
      textColor = '#cc0000';
    }

    addBadgeToItem(item, statusIndicator, textColor, itemData, price);
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