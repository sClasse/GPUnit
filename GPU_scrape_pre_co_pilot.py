#TODO Use keyword filter list to skip unwanted listings
#TODO The exception statment for page.goto() is saying there is error but it still works fine....

#Sometime after August 15th 2025, eBay changed the HTML structure of their search results page.
#       s-item__caption changed to s-card__caption. 
#Current State ------ Need to add try except blocks for title section
# Post Aug 15th ebay added more list elements causing some unecessarcy loops and failures.


from bs4 import BeautifulSoup
import csv
from datetime import datetime
import time
import re
from playwright.sync_api import sync_playwright #Used to render URL and get past challenge page
from playwright_stealth import Stealth #Used to try to mitigate ebay's heavy fingerprinting detection
import random

errors = []
search_keys = [#Keywords I use in ebay previously
    "4070", "1660", "1070", "1080", "2060", "2070", "2080", 
    "3060", "3070", "3080", "3090", "4080", "4090", "4060",
    "5060", "5070", "5080", "5090"]
keyword_filter = [# Helps filter out unwanted listings, add here as needed
    "fan replacement", "boxes only", "box only", "shield kit", 
    "sheil kit", "powerlink", "back plate", "accessory kit",
    "extension", "90mm", "16pin to 3x8pin", "adapter", "cable", 
    "stand", "laptop", "ssd", "hz"]
gpus = [] # Placeholder to store gpu listing data before writing to CSV
with Stealth().use_sync(sync_playwright()) as p: #Leverage stealth to help mitigate fingerprinting
    browser = p.chromium.launch(headless=True)#Launch chromium (chromium recommend in DOCs) but in the background
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    ) #Create a new browser context using Firefox
    page = context.new_page() #Open a new browser page within the current context/instance
    for key in search_keys:
        try:
            page.goto(
                'https://www.ebay.com/sch/i.html?_from=R40&_nkw=' + 
                key + '&_sacat=0&rt=nc&LH_Sold=1&LH_Complete=1&_ipg=240'#,
               # wait_until='domcontentloaded' ##Removing temporarily
            ) #Navigate to the desired URL and wait for browser idle
        #Interestingly enough both OpenAI and Copilot suggest using "wait_until" or "wait_for_selector" methods.
        #   both of which are actively NOT recommended in Playwright docs. Instead docs recommend using the page.locator method
        #   to handle waiting for elements.

            page.locator("srp-results").wait_for() #Wait for the listings to load
        except Exception:
            print("Error Loading Search Results for " + key)
            pass
        html = page.content() #Get the final rendered HTML content after any JS has run
        #r = requests.get('https://www.ebay.com/sch/i.html?_from=R40&_nkw=' + key + '&_sacat=0&rt=nc&LH_Sold=1&LH_Complete=1&_ipg=240')
        soup = BeautifulSoup(html, 'html.parser')
        list = soup.find('ul', class_='srp-results')
        for item in list.find_all("li", recursive=False):
            if item.find('li', class_='srp-river-answer'): #This ignores the carouusel of "suggested items" included that we don't need.
                continue
            i = {}
            error = {}
            # sale_date = item.find('div', class_='s-card__caption--row') #This works pre August 15th 2025
            sale_date = item.find('div', class_='s-card__caption') #Look for sale date div first;sometimes it doesn't exist.
            try:
                #i['Sale_Date'] = sale_date.find('span', class_='POSITIVE').text.replace("Sold  ", "") #Pre Aug 15,2025
                i['Sale_Date'] = sale_date.find('span', class_='positive').text.replace("Sold  ", "")
                #Convert date to ensure matching date formats for all csv files
                i['Sale_Date'] = datetime.strptime(i['Sale_Date'], "%b %d, %Y").strftime("%Y-%m-%d")
            except:
                print("Error finding 'Sale Date' for " + key)
                error['Error Type'] = 'Sale Date'
                error['item Content'] = item
                errors.append(error)
                continue
            try:
                i['ID'] = item['id']
            except:
                print("Error finding 'item_id' for " + key)
                error['Error Type'] = 'Item ID'
                error['item Content'] = item
                errors.append(error)
                continue
            # i['Title'] = item.find('div', class_='s-card__title').text # Pre Aug 15,2025
            i['Title'] = item.find('div', class_='s-card__title').find('span').text
            # Need to pull this from within the title div, <span class="su-styled-text
            i['Title'] = i['Title'].encode('utf-8', 'ignore').decode('utf-8', 'ignore')
            for keyword in keyword_filter:
                if i['Title'].lower() == keyword:
                    continue                
            if 'ti' in i['Title'].lower():
                i['Type'] = key + ' Ti'
            elif 'super' in i['Title'].lower():
                i['Type'] = key + ' Super'
            else:
                i['Type'] = key
#Removing Link field as it's causing duplicate checks to fail because the link is unique but the item_ID is the same in the CSV.
#            try:
#                a = item.find('a', class_='s-card__link') #Changed s-item to s-card post Aug 15,2025
#                i['Link'] = a['href']
#            except:
#                print("Error finding 'Link' for " + key)
#                error['Error Type'] = 'Link'
#                error['item Content'] = item
#                errors.append(error)
#                continue
            try: #Changed s-item to s-card post Aug 15,2025
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
                except:
                    i['Details-2'] = 'Missing'
                try: 
                    i['Details-3'] = details[2].strip()
                except:
                    i['Details-3'] = 'Missing'
                try:
                    i['Details-4'] = details[3].strip()
                except:
                    i['Details-4'] = 'Missing'
            except:
                i['Details'] = None
            try:
                i['Price'] = item.find('span', class_='s-card__price').text.strip("$") #Changed s-item to s-card post Aug 15,2025
                i['Price'] = float(i['Price'].replace(",", ""))
            except:
                i['Price'] = 0.00
                print("Error finding 'Price' for " + key)
                error['Error Type'] = 'Price'
                error['item Content'] = item
                errors.append(error)
            try:
                i['Seller'] = item.find('div', class_ = 'su-card-container__attributes__secondary').text.split(' ')[0].strip()
            except:
                i['Seller'] = "Missing"
                print("Error finding 'Seller' for " + key)
                error['Error Type'] = 'Seller'
                error['item Content'] = item
                errors.append(error)
            try:
                shipping_string = item.find_all('div', class_='s-card__attribute-row')[2].text
                if ('Located in' in shipping_string):
                    i['Shipping'] = 0
                elif shipping_string == 'Free delivery':
                    i['Shipping'] = 0
                elif shipping_string == 'Delivery not specified':
                    i['Shipping'] = 0
                else:
                    i['Shipping'] = re.search(r'\$(?:(?:[1-9][0-9]{0,2})(?:,[0-9]{3})+|[1-9][0-9]*|0)(?:[.,][0-9][0-9]?)?(?![0-9]+)', shipping_string).group(0)
                    i['Shipping'] = float(i['Shipping'].strip("+$ shipping"))
            except:
                i['Shipping'] = 0.00
                print("Error finding 'Shipping' for " + key)
                error['Error Type'] = 'Shipping'
                error['item Content'] = item
                errors.append(error)
            gpus.append(i)
        time.sleep(random.uniform(4,8)) #Sleep between 4-8 seconds to help mitigate bot detection
    context.close()
    browser.close()
csv_file = "C:/Users/yeahd/Documents/Python_Projects/GPUNIT/Pulls/" + datetime.today().strftime("%m-%d-%y") + " -- GPU Sale Price.csv"
with open(csv_file, mode="w", encoding="utf-8", newline="") as csvfile:
    fieldnames = ["ID", "Type", "Sale Date", "Details", "Price", "Seller", "Shipping"]
    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
    writer.writeheader()
    for gpu in gpus:
        writer.writerow({
            "ID": gpu["ID"],
            "Type": gpu["Type"],
            "Sale Date": gpu["Sale_Date"],
            "Details": gpu["Details"],
            "Price": gpu["Price"] + gpu["Shipping"],
            "Seller": gpu["Seller"],
            "Shipping": gpu["Shipping"]#,
#            "Link": gpu["Link"]
        })
error_file = "C:/Users/yeahd/Documents/Python_Projects/GPUNIT/gpu_scrape_errors/" + datetime.today().strftime("%m-%d-%y") + " -- GPU Errors.csv"
with open(error_file, mode="w", encoding="utf-8", newline="") as errorfile:
    fieldnames = ["Error Type", "item Content"]
    writer = csv.DictWriter(errorfile, fieldnames=fieldnames)
    writer.writeheader()
    for error in errors:
        writer.writerow({
            "Error Type": error["Error Type"],
            "item Content": error["item Content"]
        })