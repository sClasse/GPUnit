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
  // GPU detection should take priority over RAM/motherboard heuristics
  if (extractGpuType(title)) return 'GPU';
  if (/\bddr\d\b/.test(t) || /\bram\b/.test(t) || /\bmemory\b/.test(t)) return 'RAM';
  if (/motherboard|mobo|\bmb\b|chipset|\b(b|z|x)\d{3,4}\b/i.test(t)) return 'Motherboard';
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
    if (re.test(t)) { 
      oem = b; 
      console.log(`extractOEMModel: Found brand "${b}" in title (regex: /\\b${b}\\b/i)`);
      break; 
    }
  }

  const suffixPatterns = [
    'xc3','xc ultra','xc','ftw3','ftw','sc2','sc','hybrid','hydro copper','kingpin','ko',
    'gaming x trio','gaming x','gaming','rog','strix','tuf','ventus','suprim','dual',
    'prime','proart','aorus','vision','eagle','master','windforce','oc','ultra'
  ];
  const suffixRegex = new RegExp('\\b(?:' + suffixPatterns.join('|') + ')\\b', 'i');
  const suffixMatch = t.match(suffixRegex);
  let model = suffixMatch ? suffixMatch[0].trim() : null;
  if (suffixMatch) console.log(`extractOEMModel: Found suffix model "${suffixMatch[0]}" from patterns`);

  if (!model) {
    const modelMatch = t.match(/(ROG STRIX|TUF GAMING|VENTUS|SUPRIM|GAMING X TRIO|GAMING X|VENGEANCE LPX|VENGEANCE|TRIDENT Z|DOMINATOR|STRIX|B\d{3,4}[A-Z\-]*|Z\d{3,4}[A-Z\-]*|X\d{3,4}[A-Z\-]*|RTX\s*-?\s*\d{3,4}(?:\s*TI|\s*SUPER)?|GTX\s*-?\s*\d{3,4}|RX\s*-?\s*\d{3,4}(?:\s*XT|\s*XTX)?)/i);
    model = modelMatch ? modelMatch[0].trim() : null;
    if (modelMatch) console.log(`extractOEMModel: Found regex model "${modelMatch[0]}"`);
  }

  if ((!model || /RTX|GTX|RX/i.test(model)) && oem) {
    const re = new RegExp(oem + '\\s+([A-Z0-9][A-Za-z0-9\\- ]{1,40})', 'i');
    const m = t.match(re);
    if (m) {
      const candidate = m[1].trim().split(/\s{2,}|\s/).slice(0,4).join(' ');
      if (!model || !/RTX|GTX|RX/i.test(candidate)) {
        model = candidate;
        console.log(`extractOEMModel: Found OEM-specific model "${candidate}" after "${oem}"`);
      }
    }
  }

  console.log(`extractOEMModel result: oem="${oem}", model="${model}" from title: "${title.substring(0, 80)}..."`);
  return { oem: oem, model: model };
}

function normalizeKey(key) {
  if (!key) return '';
  return String(key)
    .trim()
    .toLowerCase()
    .replace(/\s+/g, ' ')
    .replace(/['"\u2019\u2018]/g, '')
    .replace(/-+/g, ' ')
    .trim();
}

function findMatchInObject(dataObj, candidates) {
  if (!dataObj || typeof dataObj !== 'object') return null;
  const keys = Object.keys(dataObj);
  const normalizedKeys = keys.map(k => ({ raw: k, norm: normalizeKey(k) }));

  for (const candidate of candidates) {
    if (!candidate) continue;
    const target = normalizeKey(candidate);
    if (!target) continue;
    const exact = normalizedKeys.find(k => k.norm === target);
    if (exact) return dataObj[exact.raw];
  }

  for (const candidate of candidates) {
    if (!candidate) continue;
    const target = normalizeKey(candidate);
    if (!target) continue;
    const partial = normalizedKeys.find(k => k.norm.includes(target) || target.includes(k.norm));
    if (partial) return dataObj[partial.raw];
  }

  return null;
}

function getAverageBreakdown(categoryData, oem, model, gpuType) {
  const breakdown = { model: null, oem: null, type: null };
  const normalizedOEM = normalizeKey(oem);
  const normalizedModel = normalizeKey(model);
  const normalizedGpuType = normalizeKey(gpuType);

  console.log(`getAverageBreakdown: Looking for model="${model}" (normalized: "${normalizedModel}"), oem="${oem}" (normalized: "${normalizedOEM}"), gpuType="${gpuType}" (normalized: "${normalizedGpuType}")`);

  // Models are now nested by Type, then OEM, then Model
  if (normalizedModel && categoryData.models && normalizedGpuType) {
    const typeKey = Object.keys(categoryData.models).find(k => normalizeKey(k) === normalizedGpuType);
    console.log(`getAverageBreakdown: Looking for GPU type key matching "${normalizedGpuType}" in models. Found: ${typeKey}`);
    
    if (typeKey) {
      const modelsByOEM = categoryData.models[typeKey];
      if (normalizedOEM) {
        const oemKey = Object.keys(modelsByOEM).find(k => normalizeKey(k) === normalizedOEM);
        console.log(`getAverageBreakdown: Looking for OEM key matching "${normalizedOEM}" in models[${typeKey}]. Found: ${oemKey}`);
        if (oemKey) {
          breakdown.model = findMatchInObject(modelsByOEM[oemKey], [normalizedModel, `${normalizedOEM} ${normalizedModel}`]);
          if (breakdown.model) console.log(`getAverageBreakdown: Found type-specific model in ${typeKey}/${oemKey}: $${breakdown.model.used} [${breakdown.model.usedVol}]`);
        }
      }
      
      // If not found in specific OEM, search generically within this GPU type
      if (!breakdown.model) {
        console.log(`getAverageBreakdown: No type+OEM specific model found, searching generically across all OEMs in ${typeKey}`);
        for (const oemKey of Object.keys(modelsByOEM)) {
          const modelMatch = findMatchInObject(modelsByOEM[oemKey], [normalizedModel]);
          if (modelMatch) {
            breakdown.model = modelMatch;
            console.log(`getAverageBreakdown: Found type-generic model match in ${typeKey}/${oemKey}: $${modelMatch.used} [${modelMatch.usedVol}]`);
            break;
          }
        }
      }
    }
  }

  if (!breakdown.model && normalizedModel && categoryData.modelOnly) {
    breakdown.model = findMatchInObject(categoryData.modelOnly, [normalizedModel]);
    if (breakdown.model) console.log(`getAverageBreakdown: Found model in modelOnly: $${breakdown.model.used} [${breakdown.model.usedVol}]`);
  }

  if (normalizedOEM && categoryData.oems) {
    breakdown.oem = findMatchInObject(categoryData.oems, [normalizedOEM]);
    if (breakdown.oem) console.log(`getAverageBreakdown: Found OEM "${normalizedOEM}": $${breakdown.oem.used} [${breakdown.oem.usedVol}]`);
  }

  if (normalizedGpuType && categoryData.types) {
    breakdown.type = findMatchInObject(categoryData.types, [normalizedGpuType]);
    if (breakdown.type) console.log(`getAverageBreakdown: Found GPU type "${normalizedGpuType}": $${breakdown.type.used} [${breakdown.type.usedVol}]`);
  }

  console.log(`getAverageBreakdown result:`, breakdown);
  return breakdown;
}

// Find the best matching key in category data using candidate strings
function findBestMatch(categoryData, candidates, context = {}) {
  if (!categoryData) return null;
  const oem = normalizeKey(context.oem);
  const model = normalizeKey(context.model);
  const normCandidates = candidates.map(normalizeKey).filter(Boolean);

  // If the data set is a flat mapping like old style { '3080': { used: ... }}
  const direct = findMatchInObject(categoryData, normCandidates);
  if (direct) return direct;

  // Models by OEM have the highest specificity.
  if (oem && model && categoryData.models) {
    const oemKey = Object.keys(categoryData.models).find(k => normalizeKey(k) === oem);
    if (oemKey) {
      const modelMatch = findMatchInObject(categoryData.models[oemKey], [model, `${oem} ${model}`]);
      if (modelMatch) return modelMatch;
    }
  }

  // Generic model matches across any OEM.
  if (model && categoryData.models) {
    for (const oemKey of Object.keys(categoryData.models)) {
      const modelMatch = findMatchInObject(categoryData.models[oemKey], [model]);
      if (modelMatch) return modelMatch;
    }
  }

  // OEM-level averages.
  if (oem && categoryData.oems) {
    const oemMatch = findMatchInObject(categoryData.oems, [oem]);
    if (oemMatch) return oemMatch;
  }

  // Type-level averages.
  if (categoryData.types) {
    const typeMatch = findMatchInObject(categoryData.types, normCandidates);
    if (typeMatch) return typeMatch;
  }

  // Fallback to bare model-only averages.
  if (categoryData.modelOnly) {
    const modelOnlyMatch = findMatchInObject(categoryData.modelOnly, normCandidates);
    if (modelOnlyMatch) return modelOnlyMatch;
  }

  return null;
}

function getCategoryData() {
  const byCategory = (typeof dataByCategory !== 'undefined') ? dataByCategory : {};
  return {
    GPU: byCategory.GPU || (typeof gpuAverages !== 'undefined' ? gpuAverages : {}),
    RAM: byCategory.RAM || (typeof ramAverages !== 'undefined' ? ramAverages : {}),
    Motherboard: byCategory.Motherboard || (typeof motherboardAverages !== 'undefined' ? motherboardAverages : {})
  };
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
  const dataByCategory = getCategoryData();
  console.log('GPU extension (detail): dataByCategory types', typeof dataByCategory, 'gpuAverages', typeof gpuAverages, 'ramAverages', typeof ramAverages, 'motherboardAverages', typeof motherboardAverages);
  const categoryData = dataByCategory[category] || {};

  // Candidate keys to try: model, OEM+model, gpuType (for GPUs), title fragments
  const gpuType = extractGpuType(title);
  const candidates = [];
  if (model) candidates.push(model);
  if (oem && model) candidates.push(`${oem} ${model}`);
  if (gpuType) candidates.push(gpuType);
  candidates.push(title.trim());

  const average = findBestMatch(categoryData, candidates, { oem, model }) || null;

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
    bottom: 8px;
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
  
  function getColorForDiff(diff) {
    return diff < 0 ? '#00aa00' : '#cc0000';
  }

  function formatPriceLine(price, vol, diff) {
    const diffPercent = diff !== null && diff !== 'N/A' ? `${diff > 0 ? '+' : ''}${diff}%` : 'N/A';
    const color = getColorForDiff(parseFloat(diff));
    return `$${price} [${vol}] <span style="color: ${color};">(${diffPercent})</span>`;
  }

  // Build badge content with item label and colored prices
  const typeLabel = gpuData.type ? `${gpuData.type} ` : '';
  const label = gpuData.label || (gpuData.oem && gpuData.model ? `${typeLabel}${gpuData.oem} ${gpuData.model}` : gpuData.model || gpuData.type || gpuData.oem || 'Item');
  let badgeHTML = `${label}<br>`;

  if (gpuData.modelAvg) {
    const modelUsedPrice = Number(gpuData.modelAvg.used) || 0;
    const modelPartsPrice = Number(gpuData.modelAvg.parts) || 0;
    const modelUsedDiff = modelUsedPrice ? ((currentPrice - modelUsedPrice) / modelUsedPrice * 100).toFixed(0) : 'N/A';
    const modelPartsDiff = modelPartsPrice ? ((currentPrice - modelPartsPrice) / modelPartsPrice * 100).toFixed(0) : 'N/A';
    const modelLabel = gpuData.model
      ? `${gpuData.type ? `${gpuData.type} ` : ''}${gpuData.oem ? `${gpuData.oem} ` : ''}${gpuData.model}`
      : (gpuData.type && gpuData.oem ? `${gpuData.type} ${gpuData.oem} Model` : 'Model');
    badgeHTML += `${modelLabel}: ${formatPriceLine(modelUsedPrice, gpuData.modelAvg.usedVol || 0, modelUsedDiff)} | ${formatPriceLine(modelPartsPrice, gpuData.modelAvg.partsVol || 0, modelPartsDiff)}<br>`;
  }

  if (gpuData.oemAvg) {
    const oemUsedPrice = Number(gpuData.oemAvg.used) || 0;
    const oemPartsPrice = Number(gpuData.oemAvg.parts) || 0;
    const oemUsedDiff = oemUsedPrice ? ((currentPrice - oemUsedPrice) / oemUsedPrice * 100).toFixed(0) : 'N/A';
    const oemPartsDiff = oemPartsPrice ? ((currentPrice - oemPartsPrice) / oemPartsPrice * 100).toFixed(0) : 'N/A';
    const oemLabel = gpuData.type ? `${gpuData.type} ${gpuData.oem || 'OEM'}` : (gpuData.oem || 'OEM');
    badgeHTML += `${oemLabel}: ${formatPriceLine(oemUsedPrice, gpuData.oemAvg.usedVol || 0, oemUsedDiff)} | ${formatPriceLine(oemPartsPrice, gpuData.oemAvg.partsVol || 0, oemPartsDiff)}<br>`;
  }

  if (gpuData.typeAvg) {
    const typeUsedPrice = Number(gpuData.typeAvg.used) || 0;
    const typePartsPrice = Number(gpuData.typeAvg.parts) || 0;
    const typeUsedDiff = typeUsedPrice ? ((currentPrice - typeUsedPrice) / typeUsedPrice * 100).toFixed(0) : 'N/A';
    const typePartsDiff = typePartsPrice ? ((currentPrice - typePartsPrice) / typePartsPrice * 100).toFixed(0) : 'N/A';
    const typeLabel = gpuData.type || 'Type';
    badgeHTML += `${typeLabel} avg: ${formatPriceLine(typeUsedPrice, gpuData.typeAvg.usedVol || 0, typeUsedDiff)} | ${formatPriceLine(typePartsPrice, gpuData.typeAvg.partsVol || 0, typePartsDiff)}`;
  }
  
  badge.innerHTML = badgeHTML;
  
  item.style.position = item.style.position || 'relative';
  item.appendChild(badge);
}

function processSearchResults() {
  const allItems = document.querySelectorAll(
    '.su-card-container, .srp-results .s-item, .ui-search-result, [data-testid="search-result-item"], .s-item, li.s-item, [role="listitem"], .ebayui-dne-item-featured-card, .gallery-item'
  );
  console.log('GPU extension: processSearchResults started, items found:', allItems.length);
  if (!allItems.length) {
    console.log('GPU extension: no search items found yet');
    return;
  }

  const uncheckedItems = Array.from(allItems).filter(item => !item.dataset.gpuPriceChecked);
  if (!uncheckedItems.length) {
    console.log('GPU extension: all items already processed, skipping repeated run');
    return;
  }

  let debugCount = 0;
  let matchedCount = 0;
  let skippedCount = 0;
  uncheckedItems.forEach(item => {
    item.dataset.gpuPriceChecked = 'true';

    const titleEl = item.querySelector(
      '.s-card__title, .s-item__title, .ui-search-item__title, h2, h3, [data-testid="item-title"], .ux-textspans, .title, .listing-title'
    );
    const priceEl = item.querySelector(
      '.s-card__price, .s-item__price, .ui-search-price__part, .s-item__detail span, .price, [data-testid="item-price"], [data-price], .s-item__price span'
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
    if (!priceMatch) {
      skippedCount += 1;
      return;
    }

    const price = parseFloat(priceMatch[1]);
    const category = detectCategory(title);
    const { oem, model } = extractOEMModel(title);
    const dataByCategory = getCategoryData();
    console.log('GPU extension: dataByCategory types', typeof dataByCategory, 'gpuAverages', typeof gpuAverages, 'ramAverages', typeof ramAverages, 'motherboardAverages', typeof motherboardAverages);
    const categoryData = dataByCategory[category] || {};
    console.log('GPU extension: candidate category', category, 'categoryData keys', Object.keys(categoryData).slice(0,10), 'total', Object.keys(categoryData).length);
    const gpuType = extractGpuType(title);
    const candidates = [];
    if (model) candidates.push(model);
    if (oem && model) candidates.push(`${oem} ${model}`);
    if (gpuType) candidates.push(gpuType);
    candidates.push(title.trim());
    const average = findBestMatch(categoryData, candidates, { oem, model });
    if (!average) {
      console.log('GPU extension: no average match', { title, category, oem, model, candidates, keysSample: Object.keys(categoryData).slice(0,10) });
      skippedCount += 1;
      return;
    }

    const averages = getAverageBreakdown(categoryData, oem, model, gpuType);
    matchedCount += 1;
    const baseline = average.used || average;
    const recommended = baseline * 0.8;

    const label = [oem, model].filter(Boolean).join(' ') || gpuType || title;
    const itemData = {
      label,
      type: gpuType,
      oem,
      model,
      usedPrice: average.used,
      partsPrice: average.parts || 0,
      usedVol: average.usedVol || 0,
      partsVol: average.partsVol || 0,
      modelAvg: averages.model,
      oemAvg: averages.oem,
      typeAvg: averages.type
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
  console.log('GPU extension: processSearchResults finished, matched items:', matchedCount, 'skipped items:', skippedCount);
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