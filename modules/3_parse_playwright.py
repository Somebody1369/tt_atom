"""
Search a product on brain.com.ua with Playwright, open the first result, parse its page and save it to DB
"""
import os
from pprint import pprint

from load_django import *
from parser_app.models import *
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

SEARCH_QUERY = 'Apple iPhone 15 128GB Black'

# Chrome profile keeps cookies, so the Cloudflare check has to be passed manually only once
PROFILE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'playwright_profile')

# Timeout for optional fields: if an element is missing, the field gets None quickly instead of waiting 30 s
FIELD_TIMEOUT = 5000


def get_text(locator):
    """Return the text of the first matching element without extra whitespace"""
    return ' '.join(locator.first.text_content(timeout=FIELD_TIMEOUT).split())


def get_price(price_block, xpath):
    """Return a price from the price block as an integer"""
    price_text = price_block.locator(xpath).first.text_content(timeout=FIELD_TIMEOUT)
    return int(''.join(char for char in price_text if char.isdigit()))


data = {}

with sync_playwright() as p:
    # One browser for the whole script; real Chrome as in the employer's async_playwright_example.py
    browser = p.chromium.launch_persistent_context(
        PROFILE_DIR,
        channel='chrome',
        headless=False,
        viewport={'width': 1400, 'height': 900},
        args=['--disable-blink-features=AutomationControlled'],
    )
    page = browser.pages[0] if browser.pages else browser.new_page()

    page.goto('https://brain.com.ua/')
    print('Step 1: main page opened')

    # There are two search inputs with the same class: the hidden one is in header-top, the visible one in header-bottom
    search_input = page.locator("xpath=//div[contains(@class, 'header-bottom')]//input[@class='quick-search-input']")
    search_input.wait_for(state='visible', timeout=120000)
    search_input.click()
    search_input.press_sequentially(SEARCH_QUERY, delay=50)

    # Typing opens the quick search popup that covers the header button, so the popup's "Знайти" button is clicked
    search_button = page.locator("xpath=//input[@class='qsr-submit']")
    search_button.wait_for(state='visible', timeout=30000)
    search_button.click()
    print('Step 2: search query sent')

    print('If a Cloudflare check appears in the browser window, pass it manually (waiting up to 2 minutes)')
    first_result = page.locator("xpath=//div[contains(@class, 'br-pp-desc')]/a").first
    first_result.wait_for(state='visible', timeout=120000)
    first_result.scroll_into_view_if_needed()
    first_result.click()
    print('Step 3: first result clicked')

    page.locator("xpath=//h1[@class='main-title']").first.wait_for(state='attached', timeout=120000)
    print('Step 4: product page opened')

    try:
        data['full_name'] = get_text(page.locator("xpath=//h1[@class='main-title']"))
    except PlaywrightTimeoutError:
        data['full_name'] = None

    try:
        data['product_code'] = get_text(page.locator("xpath=//span[@class='br-pr-code-val']"))
    except PlaywrightTimeoutError:
        data['product_code'] = None

    try:
        data['reviews_count'] = int(get_text(page.locator("xpath=//a[contains(@class, 'reviews-count')]/span")))
    except (PlaywrightTimeoutError, ValueError):
        data['reviews_count'] = None

    # Main price block: br-pr-op = old (crossed out) price, only with a discount; br-pr-np = current price
    price_block = page.locator("xpath=//div[contains(@class, 'main-price-block')]").first

    try:
        old_price = get_price(price_block, "xpath=.//div[@class='br-pr-op']//span")
    except (PlaywrightTimeoutError, ValueError):
        old_price = None

    try:
        current_price = get_price(price_block, "xpath=.//div[@class='br-pr-np']//span")
    except (PlaywrightTimeoutError, ValueError):
        current_price = None

    if old_price:
        data['price'] = old_price
        data['sale_price'] = current_price
    else:
        data['price'] = current_price
        data['sale_price'] = None

    photos = page.locator("xpath=//div[contains(@class, 'br-image-links')]//img[@class='br-main-img']").all()
    # dict.fromkeys() removes duplicates if the slider clones slides
    data['photos'] = list(dict.fromkeys(img.get_attribute('src') for img in photos)) or None

    # Characteristics table: every row is <div><span>label</span><span>value</span></div>
    characteristics_block = page.locator("xpath=//div[@class='br-pr-chr']").first

    try:
        data['color'] = get_text(characteristics_block.locator("xpath=.//span[normalize-space(text())='Колір']/following-sibling::span"))
    except PlaywrightTimeoutError:
        data['color'] = None

    try:
        data['memory'] = get_text(characteristics_block.locator("xpath=.//span[normalize-space(text())=\"Вбудована пам'ять\"]/following-sibling::span"))
    except PlaywrightTimeoutError:
        data['memory'] = None

    try:
        data['manufacturer'] = get_text(characteristics_block.locator("xpath=.//span[normalize-space(text())='Виробник']/following-sibling::span"))
    except PlaywrightTimeoutError:
        data['manufacturer'] = None

    try:
        data['screen_diagonal'] = get_text(characteristics_block.locator("xpath=.//span[normalize-space(text())='Діагональ екрану']/following-sibling::span"))
    except PlaywrightTimeoutError:
        data['screen_diagonal'] = None

    try:
        data['display_resolution'] = get_text(characteristics_block.locator("xpath=.//span[normalize-space(text())='Роздільна здатність екрану']/following-sibling::span"))
    except PlaywrightTimeoutError:
        data['display_resolution'] = None

    characteristics = {}
    for row in characteristics_block.locator("xpath=.//div[@class='br-pr-chr-item']/div/div").all():
        try:
            label = get_text(row.locator('xpath=./span'))
            value = get_text(row.locator('xpath=./span/following-sibling::span'))
        except PlaywrightTimeoutError:
            continue
        characteristics[label] = value
    data['characteristics'] = characteristics or None

    data['link'] = page.url
    data['source'] = 'playwright'

    browser.close()

pprint(data)

# Django ORM is called after Playwright is closed: inside sync_playwright an event loop is running and Django refuses to work there
product, created = Product.objects.get_or_create(**data)
print(f'Saved to DB: id={product.id}, created={created}')
