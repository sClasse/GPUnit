#TODO Update firefix extension to work with oems and models
#TODO Add motherboard and ram data to firefox extension

# Modular eBay Scraper for GPUs, Motherboards, and RAM
# Refactored to use reusable core functions with product-specific configurations

from bs4 import BeautifulSoup
import csv
from datetime import datetime
import os
import time
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Any
from urllib.parse import parse_qs, urlparse
from playwright.sync_api import sync_playwright, Page, BrowserContext
from playwright_stealth import Stealth
from dotenv import load_dotenv
import random

load_dotenv()

FIREFOX_PROFILE_DIR = Path(__file__).resolve().parent / "ebay_firefox_profile"


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
    """Launch headed Firefox with a persistent profile so cookies survive between runs."""
    stealth = Stealth()
    p = stealth.use_sync(sync_playwright())
    context_manager = p.__enter__()

    try:
        FIREFOX_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        print(f"Using persistent Firefox profile: {FIREFOX_PROFILE_DIR}")

        context = context_manager.firefox.launch_persistent_context(
            user_data_dir=str(FIREFOX_PROFILE_DIR),
            headless=False,
            viewport={"width": 1366, "height": 768},
            locale="en-US",
            timezone_id="America/New_York",
        )
        browser = context.browser
        page = context.pages[0] if context.pages else context.new_page()
        return p, browser, context, page
    except Exception:
        p.__exit__(None, None, None)
        raise


def _goto_ebay_homepage(page: Page) -> None:
    """Navigate to ebay.com without waiting for a full load, then pause 5–15 seconds."""
    try:
        page.goto("https://www.ebay.com/", wait_until="commit", timeout=10000)
    except Exception as e:
        print(f"[DEBUG] Homepage did not finish loading ({e}); continuing after wait")
    time.sleep(random.uniform(5, 15))


def _wait_for_stable_page(page: Page, timeout_ms: int = 15000) -> None:
    """Wait until the page finishes navigating so Playwright calls don't hit a dead context."""
    deadline = time.time() + timeout_ms / 1000
    last_url = None
    while time.time() < deadline:
        try:
            page.wait_for_load_state("domcontentloaded", timeout=3000)
            url = page.url
            if url == last_url:
                page.evaluate("1")
                return
            last_url = url
            time.sleep(0.4)
        except Exception:
            time.sleep(0.5)


def _current_search_keyword(page: Page) -> str | None:
    """Read the search keyword from the current eBay results URL, if any."""
    try:
        qs = parse_qs(urlparse(page.url).query)
        values = qs.get("_nkw") or qs.get("nkw") or []
        if values:
            return values[0]
    except Exception:
        return None
    return None


def _has_search_results(page: Page) -> bool:
    try:
        return page.locator("ul.srp-results li").count() > 0
    except Exception:
        return False


def _match_config_keyword(raw_keyword: str | None, search_keywords: List[str]) -> str | None:
    if not raw_keyword:
        return None
    raw_lower = raw_keyword.lower().strip()
    for kw in search_keywords:
        if kw.lower() == raw_lower:
            return kw
    for kw in search_keywords:
        if kw.lower() in raw_lower:
            return kw
    return None


def _ebay_is_logged_in(page: Page) -> bool:
    """Return True if the eBay header indicates a signed-in session."""
    for _ in range(4):
        try:
            if page.locator('a:has-text("Sign in")').first.is_visible(timeout=1500):
                return False
        except Exception:
            pass

        try:
            account_menu = page.query_selector(
                '#gh-ug.gh-control, button[aria-label*="Account" i], a[href*="myebay"], #gh-eb-My'
            )
            if account_menu:
                return True
        except Exception:
            time.sleep(0.5)
            continue

        try:
            header_text = page.locator("#gh").inner_text(timeout=2000)
            if re.search(r"\bHi\b", header_text) and "Sign in" not in header_text:
                return True
        except Exception:
            pass

        if _has_search_results(page):
            return True
        return False
    return _has_search_results(page)


def ebay_login(page: Page, context: BrowserContext) -> None:
    """
    Confirm an authenticated eBay session from the persistent Firefox profile.
    Opens the homepage only and continues without waiting for keyboard input.
    """
    _goto_ebay_homepage(page)

    if _has_search_results(page):
        kw = _current_search_keyword(page) or "current search"
        print(f"Search results already open ({kw}); continuing from this page")
        return

    if _ebay_is_logged_in(page):
        print("Already signed in to eBay (persistent profile)")
        return

    print("Warning: not signed in. Continuing with the persistent profile anyway.")


def _enable_sold_items_filter(page: Page, keyword: str) -> None:
    """Enable eBay 'Sold Items' filter on search results (supports old and new UI)."""
    print(f"[DEBUG] Enabling Sold Items filter for keyword={keyword}")

    try:
        page.wait_for_selector(
            'a.su-selection-group__link, input[aria-label="Sold Items"]',
            timeout=10000,
        )
    except Exception:
        print(f"[DEBUG] Sold Items controls not found for keyword={keyword}")
        return

    # New UI: link-style toggle in "Show only" selection group
    sold_link = page.locator(
        'a.su-selection-group__link:has(.su-selection-group__label--container:text-is("Sold Items"))'
    )

    if sold_link.count() > 0:
        sold_toggle = sold_link.first
        checkbox = sold_toggle.locator('input.checkbox__control[type="checkbox"]')
        try:
            if checkbox.count() > 0 and checkbox.is_checked():
                print(f"[DEBUG] Sold Items already enabled for keyword={keyword}")
                return
        except Exception:
            pass

        print(f"[DEBUG] Clicking Sold Items link for keyword={keyword}")
        sold_toggle.click(delay=random.randint(50, 150))
        time.sleep(random.uniform(4, 8))
        try:
            page.wait_for_selector('ul.srp-results, div.srp-controls, div#srp-river-results', timeout=15000)
        except Exception:
            pass
        print(f"[DEBUG] Sold Items link clicked for keyword={keyword}")
        return

    # Legacy UI: visible checkbox input
    sold_checkbox = page.query_selector('input[aria-label="Sold Items"]')
    if sold_checkbox:
        print(f"[DEBUG] Found legacy Sold Items checkbox for keyword={keyword}")
        sold_checkbox.click()
        time.sleep(random.uniform(4, 8))
        print(f"[DEBUG] Clicked legacy Sold Items checkbox for keyword={keyword}")
        return

    print(f"[DEBUG] Sold Items toggle not found for keyword={keyword}")


def _pick_search_selector(page: Page) -> str:
    if page.query_selector('input#gh-ac'):
        return 'input#gh-ac'
    if page.query_selector('input[name="_nkw"]'):
        return 'input[name="_nkw"]'
    return 'input[aria-label*="Search"]'


def _results_url_has_param(page: Page, name: str, value: str) -> bool:
    try:
        qs = parse_qs(urlparse(page.url).query)
        return value in qs.get(name, [])
    except Exception:
        return False


def _submit_search_term(page: Page, keyword: str) -> None:
    """Type a new keyword into the header search box on the current page and submit."""
    search_sel = _pick_search_selector(page)
    time.sleep(random.uniform(1, 3))
    page.click(search_sel, timeout=10000)
    page.fill(search_sel, "")
    page.type(search_sel, str(keyword), delay=random.randint(50, 150))
    page.keyboard.press("Enter")
    try:
        page.wait_for_selector(
            'ul.srp-results, div.srp-controls, div#srp-river-results',
            timeout=20000,
        )
    except Exception:
        pass
    time.sleep(random.uniform(8, 12))


def search_ebay(page: Page, keyword: str, context: BrowserContext | None = None) -> str:
    """Search for keyword from the current eBay page and return rendered HTML."""
    try:
        current_kw = _current_search_keyword(page)
        if (
            current_kw
            and current_kw.lower() == str(keyword).lower()
            and _has_search_results(page)
        ):
            print(f"[DEBUG] Reusing already-open sold results for keyword={keyword}")
            return page.content()

        on_results = _has_search_results(page) or "/sch/" in page.url
        if on_results:
            print(f"[DEBUG] Searching for {keyword} from current results page (no homepage)")
            _submit_search_term(page, keyword)
        else:
            print(f"[DEBUG] Not on results yet; opening homepage once for {keyword}")
            _goto_ebay_homepage(page)
            _submit_search_term(page, keyword)

        if not _results_url_has_param(page, "LH_Sold", "1"):
            try:
                _enable_sold_items_filter(page, keyword)
            except Exception as e:
                print(f"[DEBUG] Sold Items click exception for keyword={keyword}: {e}")
            time.sleep(random.uniform(4, 8))
        else:
            print(f"[DEBUG] Sold Items already in URL for keyword={keyword}")

        if not _results_url_has_param(page, "_ipg", "240"):
            try:
                ipp_button = page.query_selector('button[aria-controls="srp-ipp-menu-content"]')
                if ipp_button:
                    ipp_button.click(delay=random.randint(50, 150))
                    page.wait_for_selector('#srp-ipp-menu-content', timeout=10000)
                    time.sleep(random.uniform(0.8, 1.8))
                    page.click('#srp-ipp-menu-content >> text="240"', delay=random.randint(50, 150))
                    try:
                        page.wait_for_selector('ul.srp-results', timeout=15000)
                    except Exception:
                        pass
            except Exception as e:
                print(f"[DEBUG] 240 IPP click exception for keyword={keyword}: {e}")
        else:
            print(f"[DEBUG] 240 per page already in URL for keyword={keyword}")

    except Exception as e:
        print(f"Error Loading Search Results for {keyword}: {e}")

    try:
        return page.content()
    except Exception as e:
        print(f"Could not read page HTML for {keyword}: {e}")
        time.sleep(2)
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

def _collect_listings_from_html(
    html: str,
    keyword: str,
    product_config: ProductConfig,
    results: List[Dict[str, Any]],
    errors: List[Dict[str, Any]],
) -> None:
    if (
        "Access Denied" in html
        or "errors.edgesuite.net" in html
        or "Something went wrong on our end" in html
    ):
        print(f"Access Denied / error page still present for {keyword}; skipping")
        return

    soup = BeautifulSoup(html, 'html.parser')
    listing_list = soup.find('ul', class_='srp-results')

    if not listing_list:
        print(f"No listings found for {keyword}")
        return

    before = len(results)
    for item in listing_list.find_all("li", recursive=False):
        if item.find('li', class_='srp-river-answer'):
            continue

        listing, error = parse_listing(item, keyword, product_config)

        if error and listing is None:
            errors.append(error)
        elif listing:
            results.append(listing)
            if error:
                errors.append(error)

    print(f"Parsed {len(results) - before} listings for {keyword}")


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
        ebay_login(page, context)
        _wait_for_stable_page(page)

        remaining_keywords = list(product_config.search_keywords)
        current_kw = _match_config_keyword(
            _current_search_keyword(page),
            remaining_keywords,
        )
        if current_kw and _has_search_results(page):
            print(f"\nTaking over from open results for: {current_kw}")
            try:
                html = page.content()
            except Exception:
                _wait_for_stable_page(page)
                html = page.content()
            _collect_listings_from_html(html, current_kw, product_config, results, errors)
            remaining_keywords = [kw for kw in remaining_keywords if kw != current_kw]
            time.sleep(random.uniform(8, 20))

        for keyword in remaining_keywords:
            print(f"\nSearching for: {keyword}")
            html = search_ebay(page, keyword, context)
            _collect_listings_from_html(html, keyword, product_config, results, errors)
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
