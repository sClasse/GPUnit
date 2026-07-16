#TODO Update firefix extension to work with oems and models
#TODO Add motherboard and ram data to firefox extension

# Modular eBay Scraper for GPUs, Motherboards, and RAM
# Refactored to use reusable core functions with product-specific configurations

from bs4 import BeautifulSoup
import csv
from datetime import datetime
import time
import re
from dataclasses import dataclass, field
from typing import List, Dict, Any
from playwright.sync_api import sync_playwright, Page, BrowserContext
from playwright_stealth import Stealth
import random


@dataclass
class ProductConfig:
    """Configuration for a specific product type scraping"""
    name: str  # "GPU", "Motherboard", "RAM"
    search_keywords: List[str]
    keyword_filters: List[str]
    oem_models: Dict[str, List[str]] = field(default_factory=dict)
    output_folder: str = "C:/Users/yeahd/Documents/Python_Projects/GPUNIT/Pulls/"
    error_folder: str = "C:/Users/yeahd/Documents/Python_Projects/GPUNIT/gpu_scrape_errors/"


# ============================================================================
# PRODUCT CONFIGURATIONS
# ============================================================================

GPU_CONFIG = ProductConfig(
    name="GPU",
    search_keywords=[
        "4080", "1660", "1070", "1080", "2060", "2070", "2080",
        "3060", "3070", "3080", "3090", "4070", "4090", "4060",
        "5060", "5070", "5080", "5090"
    ],
    keyword_filters=[
        "fan replacement", "boxes only", "box only", "shield kit",
        "sheil kit", "powerlink", "back plate", "accessory kit",
        "extension", "90mm", "16pin to 3x8pin", "adapter", "cable",
        "stand", "laptop", "ssd", "hz"
    ],
    oem_models={
        "asus": ["tuf", "rog", "strix", "prime", "dual", "proart"],
        "evga": ["xc3", "ftw3", "ftw", "kingpin", "classified", "hybrid", "hydro copper", "xc ultra", "xc", "sc", "gaming", "black", "ko"],
        "gigabyte": ["aorus", "windforce", "eagle", "gaming", "aero", "vision", "master", "xtreme waterforce"],
        "msi": ["suprim", "vanguard", "expert", "gaming", "slim", "inspire", "ventus", "shadow", "mech", "lightning", "duke", "aero", "classic"],
        "palit": ["storm-x", "gamerock", "gamingpro", "dual", "infinity", "jetstream", "white", "oc"],
        "pny": ["oc", "argb", "verto"],
        "zotac": ["solid", "twin edge", "amp extreme", "amp", "solo", "trinity"]
    }
)

MOTHERBOARD_CONFIG = ProductConfig(
    name="Motherboard",
    search_keywords=[
        "B550", "B650", "B760", "B850", "X670", "X870", "Z790", "Z890"
    ],
    keyword_filters=[
        "box only", "heatsink only", "fan replacement"
    ],
    oem_models={
        "asus": ["rog maximus", "rog strix", "tuf", "prime", "proart"],
        "msi": ["meg", "mpg", "mag", "pro", "creator", "tomahawk", "gaming"],
        "gigabyte": ["aorus", "aero", "gaming", "eagle"],
        "asrock": ["aqua", "taichi", "creator", "steel legend", "livemixer", "extreme", "pro", "oc"],
        "nzxt": ["n5", "n7", "n9"],
        "zotac": []
    }
    
)

# Auto-generate RAM keywords for all DDR4 and DDR5 sizes (4GB to 128GB)
ddr4_sizes = [4, 8, 16, 32, 64, 128]
ddr5_sizes = [4, 8, 16, 32, 64, 128]
ram_keywords = (
    [f"DDR4 {size}GB" for size in ddr4_sizes] +
    [f"DDR5 {size}GB" for size in ddr5_sizes]
)

RAM_CONFIG = ProductConfig(
    name="RAM",
    search_keywords=ram_keywords,
    keyword_filters=[
        "box only", "boxes only", "adaptor"
    ],
    oem_models={
        "corsair": ["dominator", "vengeance rgb", "vengeance lpx", "vengeance" ],
        "g.skill": ["trident z5", "trident z royal", "trident", "ripjaw", "flare", "aegis", "sniper", "valor"],
        "kingston": ["renegade", "beast", "impact"],
        "crucial": ["pro", "standard"],
        "teamgroup": ["delta rgb", "delta tuf", "vulcan", "xtreem", "dark", "expert", "classic"],
        "adata": ["xpg lancer", "xpg spectrix", "xpg gammix", "premier"],
        "patriot": ["xtreme", "elite", "venom", "steel", "4", "elite", "signature"],
        "mushkin": ["pro", "lumina", "essentials", "proline", "redline"]
    }
)


# ============================================================================
# CORE SCRAPING FUNCTIONS
# ============================================================================

def setup_browser():
    """Initialize Playwright with Stealth and return browser, context, page, and the Playwright manager."""
    stealth = Stealth()
    p = stealth.use_sync(sync_playwright())
    context_manager = p.__enter__()

    try:
        browser = context_manager.chromium.launch(
            headless=False,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-features=IsolateOrigins,site-per-process",
                "--disable-web-security"
            ]
        )

        context = browser.new_context(
            user_agent="AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36 Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            viewport={"width": random.randint(1280, 1440), "height": random.randint(820, 980)},
            locale="en-US",
            timezone_id="America/New_York",
            screen={"width": 1920, "height": 1080},
            device_scale_factor=1
        )

        page = context.new_page()
        return p, browser, context, page
    except Exception:
        p.__exit__(None, None, None)
        raise


def search_ebay(page: Page, keyword: str) -> str:
    """Navigate eBay and search for keyword, return rendered HTML"""
    try:
        # Start from eBay homepage and type the query to avoid direct-search blocking
        page.goto("https://www.ebay.com/")

        # Wait for a known search input to appear
        try:
            page.wait_for_selector('input#gh-ac, input[name="_nkw"], input[aria-label*="Search"]', timeout=10000)
        except Exception:
            pass

        # Pick the first available search input selector
        if page.query_selector('input#gh-ac'):
            search_sel = 'input#gh-ac'
        elif page.query_selector('input[name="_nkw"]'):
            search_sel = 'input[name="_nkw"]'
        else:
            search_sel = 'input[aria-label*="Search"]'

        # Small human-like pause before typing
        time.sleep(random.uniform(1, 3))

        # Focus, type with per-character delay, then submit
        try:
            page.click(search_sel)
            page.type(search_sel, str(keyword), delay=random.randint(50, 150))
            page.keyboard.press("Enter")
        except Exception:
            pass

        # Wait for results to render
        try:
            page.wait_for_selector('ul.srp-results, div.srp-controls, div#srp-river-results', timeout=15000)
        except Exception:
            pass

        time.sleep(random.uniform(8, 12))

        # Explicitly enable Sold Items and 240 results per page if present
        try:
            sold_checkbox = page.query_selector('input[aria-label="Sold Items"]')
            print(f"[DEBUG] Searching for Sold Items checkbox for keyword={keyword}")
            if sold_checkbox:
                print(f"[DEBUG] Found Sold Items checkbox; visible={sold_checkbox.is_visible()}, enabled={sold_checkbox.is_enabled()}")
                page.evaluate('(el) => el.click()', sold_checkbox)
                page.wait_for_timeout(2000)
                print(f"[DEBUG] Clicked Sold Items checkbox for keyword={keyword}")
            else:
                print(f"[DEBUG] Sold Items checkbox not found for keyword={keyword}")
        except Exception as e:
            print(f"[DEBUG] Sold Items click exception for keyword={keyword}: {e}")

        try:
            ipp_button = page.query_selector('button[aria-controls="srp-ipp-menu-content"]')
            if ipp_button:
                ipp_button.click()
                page.wait_for_selector('#srp-ipp-menu-content', timeout=10000)
                page.click('#srp-ipp-menu-content >> text="240"')
                page.wait_for_selector('ul.srp-results', timeout=15000)
        except Exception:
            pass

    except Exception:
        # Fallback: direct navigation if homepage flow fails
        try:
            page.goto(f'https://www.ebay.com/sch/i.html?_nkw={keyword}&_sacat=0&_ipg=240&rt=nc&LH_Sold=1', timeout=30000)
            try:
                page.wait_for_selector('ul.srp-results', timeout=15000)
            except Exception:
                pass
        except Exception:
            print(f"Error Loading Search Results for {keyword}")
            pass

    return page.content()


def parse_listing(item, keyword: str, product_config: ProductConfig) -> tuple[Dict[str, Any], Dict[str, Any] | None]:
    """
    Parse a single eBay listing item.
    Returns (listing_dict, error_dict_or_None)
    """
    i = {}
    error = {}

    # Sale Date (handle old and new eBay HTML)
    try:
        sale_date_text = None
        # old structure
        caption = item.find('div', class_='s-card__caption')
        if caption:
            pos = caption.find('span', class_='positive')
            if pos and pos.get_text(strip=True):
                sale_date_text = pos.get_text(strip=True).replace('Sold', '').strip()

        # new structure: look for signal span or any span starting with 'Sold'
        if not sale_date_text:
            sig = item.select_one('span.signal, span.signal--recent, span.signal--recent')
            if sig and sig.get_text(strip=True).lower().startswith('sold'):
                sale_date_text = sig.get_text(strip=True).replace('Sold', '').strip()
            else:
                for sp in item.find_all('span'):
                    t = sp.get_text(strip=True)
                    if t and t.startswith('Sold'):
                        sale_date_text = t.replace('Sold', '').strip()
                        break

        if not sale_date_text:
            raise ValueError('sale date not found')

        i['Sale_Date'] = datetime.strptime(sale_date_text, "%b %d, %Y").strftime("%Y-%m-%d")
    except Exception:
        print(f"Error finding 'Sale Date' for {keyword} ({product_config.name})")
        error['Error Type'] = 'Sale Date'
        error['item Content'] = item
        return None, error

    # Item ID
    try:
        i['ID'] = item['id']
    except Exception:
        print(f"Error finding 'item_id' for {keyword} ({product_config.name})")
        error['Error Type'] = 'Item ID'
        error['item Content'] = item
        return None, error

    # Title (support multiple class patterns)
    try:
        def _first_text(selectors):
            for s in selectors:
                el = item.select_one(s)
                if el and el.get_text(strip=True):
                    return el.get_text(strip=True)
            return None

        title_selectors = [
            'div.s-card__title span',
            'a.su-link.su-item-card__title span',
            'div.su-card-container__header a span',
            'h3.s-item__title',
            'a.s-item__link h3'
        ]

        title_text = _first_text(title_selectors)
        if not title_text:
            raise ValueError('title not found')

        i['Title'] = title_text.encode('utf-8', 'ignore').decode('utf-8', 'ignore')
    except Exception:
        i['Title'] = "Unknown"

    # Determine OEM from title before any product-specific logic
    i['OEM'] = parse_oem(i['Title'], product_config)
    i['Model'] = parse_model(i['Title'], product_config, i['OEM'])

    # Check if title matches exclusion filters
    for filter_keyword in product_config.keyword_filters:
        if filter_keyword.lower() in i['Title'].lower():
            return None, None  # Skip this listing

    # Product-specific type parsing
    i['Type'] = parse_product_type(keyword, i['Title'], product_config)

    # Details (condition, seller feedback, etc.)
    try:
        details = item.find('div', class_='s-card__subtitle').text.split('·')
        if 'Brand' in details[0]:
            i['Details'] = 'Brand New'
        elif 'New' in details[0] or 'Open' in details[0]:
            i['Details'] = 'Open Box'
        elif 'Excellent' in details[0] or 'Very' in details[0] or 'Certified' in details[0]:
            i['Details'] = 'Refurbished'
        elif 'For' in details[0] or 'Parts' in details[0]:
            i['Details'] = 'Parts'
        else:
            i['Details'] = 'Used'

        try:
            i['Details-2'] = details[1].strip()
        except Exception:
            i['Details-2'] = 'Missing'

        try:
            i['Details-3'] = details[2].strip()
        except Exception:
            i['Details-3'] = 'Missing'

        try:
            i['Details-4'] = details[3].strip()
        except Exception:
            i['Details-4'] = 'Missing'
    except Exception:
        i['Details'] = None
        i['Details-2'] = 'Missing'
        i['Details-3'] = 'Missing'
        i['Details-4'] = 'Missing'

    # Price (robust extraction)
    try:
        price_selectors = ['span.s-card__price', 'span.su-item-card__price', 'span.s-item__price', 'div.su-card-container__footer span']
        price_text = None
        for sel in price_selectors:
            p_el = item.select_one(sel)
            if p_el and p_el.get_text(strip=True):
                price_text = p_el.get_text(strip=True)
                break

        # fallback: search for dollar amount anywhere in item
        if not price_text:
            m = re.search(r'\$[0-9\.,]+', item.get_text())
            price_text = m.group(0) if m else None

        if not price_text:
            raise ValueError('price not found')

        # normalize and parse
        price_num = re.search(r'\$?([0-9\,]+(?:\.[0-9]{1,2})?)', price_text)
        if price_num:
            i['Price'] = float(price_num.group(1).replace(',', ''))
        else:
            raise ValueError('price parse failed')
    except Exception:
        i['Price'] = 0.00
        print(f"Error finding 'Price' for {keyword} ({product_config.name})")
        error['Error Type'] = 'Price'
        error['item Content'] = item
        return i, error  # Return listing even with price error

    # Seller (try new attribute container, then fallbacks)
    try:
        seller = None
        # new-style container
        sec = item.select_one('.su-card-container__attributes__secondary')
        if sec and sec.get_text(strip=True):
            seller = sec.get_text(strip=True).split('\n')[0].split(' ')[0].strip()

        # common seller link
        if not seller:
            s_link = item.select_one('a[href*="/usr/"]') or item.select_one('a[href*="/seller/"]')
            if s_link and s_link.get_text(strip=True):
                seller = s_link.get_text(strip=True)

        # older-style
        if not seller:
            old = item.select_one('.s-item__seller-info-text')
            if old and old.get_text(strip=True):
                seller = old.get_text(strip=True).split(':')[-1].strip()

        if not seller:
            raise ValueError('seller not found')

        i['Seller'] = seller
    except Exception:
        i['Seller'] = "Missing"
        print(f"Error finding 'Seller' for {keyword} ({product_config.name})")
        error['Error Type'] = 'Seller'
        error['item Content'] = item
        return i, error

    # Shipping (robust extraction from attributes)
    try:
        shipping_string = None
        # new-style attributes primary container
        primary = item.select_one('.su-card-container__attributes__primary')
        if primary and primary.get_text(strip=True):
            shipping_string = primary.get_text(separator=' | ', strip=True)

        # fallback to old attribute rows
        if not shipping_string:
            rows = item.find_all('div', class_='s-card__attribute-row')
            if len(rows) >= 3:
                shipping_string = rows[2].get_text(strip=True)

        if not shipping_string:
            shipping_string = item.get_text()

        if 'Located in' in shipping_string or 'Free delivery' in shipping_string or 'Delivery not specified' in shipping_string:
            i['Shipping'] = 0.00
        else:
            regex_match = re.search(r'\$[0-9\,]+(?:\.[0-9]{1,2})?', shipping_string)
            if regex_match:
                i['Shipping'] = float(regex_match.group(0).replace('$', '').replace(',', ''))
            else:
                i['Shipping'] = 0.00
    except Exception:
        i['Shipping'] = 0.00
        print(f"Error finding 'Shipping' for {keyword} ({product_config.name})")
        error['Error Type'] = 'Shipping'
        error['item Content'] = item
        return i, error

    return i, None


def parse_product_type(keyword: str, title: str, product_config: ProductConfig) -> str:
    """Parse product-specific type information from keyword and title"""
    if product_config.name == "GPU":
        return parse_gpu_type(keyword, title)
    elif product_config.name == "Motherboard":
        return parse_motherboard_type(keyword, title)
    elif product_config.name == "RAM":
        return parse_ram_type(keyword, title)
    else:
        return keyword


def parse_gpu_type(keyword: str, title: str) -> str:
    """Extract GPU variant info (Ti, Super, etc.) from title"""
    if 'ti' in title.lower():
        return f"{keyword} Ti"
    elif 'super' in title.lower():
        return f"{keyword} Super"
    else:
        return keyword


def parse_motherboard_type(keyword: str, title: str) -> str:
    """Extract motherboard variant info from title"""
    if 'mini' in title.lower() or 'itx' in title.lower():
        return f"{keyword} ITX"
    elif 'micro' in title.lower() or 'mtx' in title.lower():
        return f"{keyword} MATX"
    elif 'eatx' in title.lower() or 'e-atx' in title.lower() or 'extended atx' in title.lower():
        return f"{keyword} EATX"
    else:
        return f"{keyword} ATX"


def parse_ram_type(keyword: str, title: str) -> str:
    """Extract RAM variant info from title"""
    # For RAM, the keyword already contains DDR version and size
    # Can be enhanced to detect specific speed/brand if needed
    return keyword


def parse_oem(title: str, product_config: ProductConfig) -> str:
    """Extract OEM information from a listing title."""
    normalized_title = title.strip()
    if not normalized_title:
        return "Unknown"

    lower_title = normalized_title.lower()
    oem = "Unknown"

    # Prefer configured OEMs when they exist
    if getattr(product_config, 'oem_models', None):
        # Sort longest OEM names first so multi-word names are matched before shorter substrings
        for candidate in sorted(product_config.oem_models.keys(), key=len, reverse=True):
            if candidate.lower() in lower_title:
                if candidate.isalpha() and len(candidate) <= 4:
                    return candidate.upper()
                return candidate.title()
    
    # Fallback to hardcoded OEM lists when oem_models is not present
    if product_config.name == "GPU":
        known_oems = [
            "NVIDIA", "AMD", "ASUS", "MSI", "GIGABYTE", "EVGA", "ZOTAC",
            "PALIT", "PNY", "SAPPHIRE", "GALAX", "INNO3D", "PowerColor"
        ]
    elif product_config.name == "Motherboard":
        known_oems = ["ASUS", "GIGABYTE", "MSI", "ASRock", "Biostar", "EVGA", "AORUS"]
    elif product_config.name == "RAM":
        known_oems = [
            "Corsair", "G.Skill", "Kingston", "Crucial", "Patriot",
            "Team", "ADATA", "Ballistix", "HyperX", "GeIL", "Mushkin"
        ]
    else:
        known_oems = []

    for candidate in known_oems:
        if candidate.lower() in lower_title:
            oem = candidate
            break

    return oem


def parse_model(title: str, product_config: ProductConfig, oem: str | None = None) -> str:
    """Extract OEM-specific model information from a listing title."""
    normalized_title = title.lower()
    model_candidates: List[str] = []

    if getattr(product_config, 'oem_models', None):
        oem_key = oem.lower() if oem else None
        if oem_key and oem_key in product_config.oem_models:
            model_candidates = product_config.oem_models[oem_key]
        else:
            for models in product_config.oem_models.values():
                model_candidates.extend(models)

    if not model_candidates:
        return "Unknown"

    # Match longest model names first to avoid partial collisions
    for model in sorted(set(model_candidates), key=len, reverse=True):
        if model and re.search(rf"\b{re.escape(model)}\b", normalized_title):
            return model

    return "Unknown"


def write_results(results: List[Dict[str, Any]], errors: List[Dict[str, Any]], product_config: ProductConfig) -> None:
    """Write results and errors to CSV files"""
    csv_file = f"{product_config.output_folder}{datetime.today().strftime('%m-%d-%y')} -- {product_config.name} Sale Price.csv"
    error_file = f"{product_config.error_folder}{datetime.today().strftime('%m-%d-%y')} -- {product_config.name} Errors.csv"

    # Write results CSV
    with open(csv_file, mode="w", encoding="utf-8", newline="") as csvfile:
        fieldnames = ["ID", "OEM", "Model", "Type", "Sale Date", "Details", "Price", "Seller", "Shipping"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for result in results:
            writer.writerow({
                "ID": result.get("ID", ""),
                "OEM": result.get("OEM", "Unknown"),
                "Model": result.get("Model", "Unknown"),
                "Type": result.get("Type", ""),
                "Sale Date": result.get("Sale_Date", ""),
                "Details": result.get("Details", ""),
                "Price": result.get("Price", 0) + result.get("Shipping", 0),
                "Seller": result.get("Seller", ""),
                "Shipping": result.get("Shipping", 0)
            })

    print(f"✓ {product_config.name} results written to: {csv_file}")

    # Write errors CSV
    if errors:
        with open(error_file, mode="w", encoding="utf-8", newline="") as errorfile:
            fieldnames = ["Error Type", "item Content"]
            writer = csv.DictWriter(errorfile, fieldnames=fieldnames)
            writer.writeheader()
            for error in errors:
                writer.writerow({
                    "Error Type": error.get("Error Type", ""),
                    "item Content": error.get("item Content", "")
                })
        print(f"✓ {product_config.name} errors written to: {error_file}")


# ============================================================================
# MAIN SCRAPING ENGINE
# ============================================================================

def scrape_ebay(product_config: ProductConfig) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Universal scraper function that works with any product configuration.
    Returns (results, errors)
    """
    print(f"\n{'='*60}")
    print(f"Starting {product_config.name} scrape...")
    print(f"{'='*60}")

    results = []
    errors = []

    p, browser, context, page = setup_browser()

    try:
        for keyword in product_config.search_keywords:
            print(f"\nSearching for: {keyword}")
            html = search_ebay(page, keyword)

            # Detect Access Denied / challenge pages
            if "Access Denied" in html or "errors.edgesuite.net" in html:
                print(f"Access Denied encountered for {keyword}")
                continue

            soup = BeautifulSoup(html, 'html.parser')
            listing_list = soup.find('ul', class_='srp-results')

            if not listing_list:
                print(f"No listings found for {keyword}")
                continue

            for item in listing_list.find_all("li", recursive=False):
                if item.find('li', class_='srp-river-answer'):
                    continue

                listing, error = parse_listing(item, keyword, product_config)
                
                if error and listing is None:
                    # Only error, no listing data
                    errors.append(error)
                elif listing:
                    # Listing parsed successfully (may have partial error)
                    results.append(listing)
                    if error:
                        errors.append(error)

            time.sleep(random.uniform(8, 20))

    finally:
        try:
            context.close()
        except Exception:
            pass
        try:
            browser.close()
        except Exception:
            pass
        try:
            p.__exit__(None, None, None)
        except Exception:
            pass

    print(f"\n✓ Scraped {len(results)} {product_config.name} listings")
    print(f"✓ Encountered {len(errors)} errors")

    write_results(results, errors, product_config)
    return results, errors


# ============================================================================
# WRAPPER FUNCTIONS FOR SPECIFIC PRODUCTS
# ============================================================================

def scrape_gpus() -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Scrape GPU listings"""
    return scrape_ebay(GPU_CONFIG)


def scrape_motherboards() -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Scrape motherboard listings"""
    return scrape_ebay(MOTHERBOARD_CONFIG)


def scrape_ram() -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Scrape RAM listings"""
    return scrape_ebay(RAM_CONFIG)


def scrape_all() -> Dict[str, tuple[List[Dict[str, Any]], List[Dict[str, Any]]]]:
    """Scrape all product types sequentially"""
    print("\n" + "="*60)
    print("SCRAPING ALL PRODUCTS")
    print("="*60)

    results = {}
    results['GPU'] = scrape_gpus()
    results['Motherboard'] = scrape_motherboards()
    results['RAM'] = scrape_ram()

    print("\n" + "="*60)
    print("ALL SCRAPING COMPLETE")
    print("="*60)
    return results


# ============================================================================
# MAIN EXECUTION
# ============================================================================

if __name__ == "__main__":
    # Choose which scraper to run:
    # scrape_gpus()
    #scrape_motherboards()
    # scrape_ram()
     scrape_all()
