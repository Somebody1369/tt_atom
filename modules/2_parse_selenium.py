"""
Search a product on brain.com.ua with Selenium, open the first result, parse its page and save it to DB
"""
import os
import re
from pprint import pprint

from load_django import *
from parser_app.models import *
import certifi
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.selenium_manager import SeleniumManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException

# get_attribute('textContent') is used instead of .text: .text returns an empty string for hidden duplicates

SEARCH_QUERY = 'Apple iPhone 15 128GB Black'

# Chrome profile keeps cookies between runs
PROFILE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'chrome_profile')

# Debug screenshots are saved to the project's files folder
FILES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'files'))


def get_chrome_major_version():
    """Return the major version of the installed Google Chrome, or None if it is not found"""
    # Selenium Manager picks a chromedriver for the installed Chrome, the driver version is in its path
    driver_path = SeleniumManager().binary_paths(['--browser', 'chrome'])['driver_path']
    version = re.search(r'(\d+)\.\d+\.\d+\.\d+', driver_path)
    return int(version.group(1)) if version else None


# undetected_chromedriver downloads chromedriver with urllib; python.org builds of Python on macOS
# have no root certificates, so the certifi bundle is used
os.environ.setdefault('SSL_CERT_FILE', certifi.where())

# undetected_chromedriver calls quit() again in __del__ when Python shuts down and prints a traceback;
# quit() is already called in finally, so the destructor is disabled
uc.Chrome.__del__ = lambda self: None

options = uc.ChromeOptions()
options.add_argument(f'--user-data-dir={PROFILE_DIR}')

# undetected_chromedriver hides automation flags, so Cloudflare lets the browser in without manual actions
driver = uc.Chrome(options=options, version_main=get_chrome_major_version())
driver.maximize_window()

step = 'open main page'
try:
    driver.get('https://brain.com.ua/')
    print('Step 1: main page opened')

    # There are two search inputs with the same class: the hidden one is in header-top, the visible one in header-bottom
    step = 'wait for the search input'
    search_input = WebDriverWait(driver, 120).until(
        EC.element_to_be_clickable((By.XPATH, "//div[contains(@class, 'header-bottom')]//input[@class='quick-search-input']"))
    )
    search_input.send_keys(SEARCH_QUERY)

    # Typing opens the quick search popup that covers the header button, so the popup's "Знайти" button is clicked
    step = 'wait for the search button'
    search_button = WebDriverWait(driver, 30).until(
        EC.element_to_be_clickable((By.XPATH, "//input[@class='qsr-submit']"))
    )
    search_button.click()
    print('Step 2: search query sent')

    print('If a Cloudflare check appears in the browser window, pass it manually (waiting up to 2 minutes)')
    step = 'wait for the search results'
    first_result = WebDriverWait(driver, 120).until(
        EC.element_to_be_clickable((By.XPATH, "//div[contains(@class, 'br-pp-desc')]/a"))
    )
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", first_result)
    first_result.click()
    print('Step 3: first result clicked')

    step = 'wait for the product page'
    WebDriverWait(driver, 120).until(EC.presence_of_element_located((By.XPATH, "//h1[@class='main-title']")))
    print('Step 4: product page opened')

    data = {}

    try:
        data['full_name'] = driver.find_element(By.XPATH, "//h1[@class='main-title']").get_attribute('textContent').strip()
    except NoSuchElementException:
        data['full_name'] = None

    try:
        data['product_code'] = driver.find_element(By.XPATH, "//span[@class='br-pr-code-val']").get_attribute('textContent').strip()
    except NoSuchElementException:
        data['product_code'] = None

    try:
        # Only the current product's counter: the series counters are in series-comments-block
        data['reviews_count'] = int(driver.find_element(By.XPATH, "//div[@id='fast-navigation-block-static']//div[contains(@class, 'main-comments-block')]//a[contains(@class, 'reviews-count')]/span").get_attribute('textContent').strip())
    except (NoSuchElementException, ValueError):
        data['reviews_count'] = None

    # Main price block: br-pr-op = old (crossed out) price, only with a discount; br-pr-np = current price
    try:
        price_block = driver.find_element(By.XPATH, "//div[contains(@class, 'main-price-block')]")
    except NoSuchElementException:
        price_block = None

    try:
        old_price_text = price_block.find_element(By.XPATH, ".//div[@class='br-pr-op']//span").get_attribute('textContent')
        old_price = int(''.join(char for char in old_price_text if char.isdigit()))
    except (NoSuchElementException, AttributeError, ValueError):
        old_price = None

    try:
        current_price_text = price_block.find_element(By.XPATH, ".//div[@class='br-pr-np']//span").get_attribute('textContent')
        current_price = int(''.join(char for char in current_price_text if char.isdigit()))
    except (NoSuchElementException, AttributeError, ValueError):
        current_price = None

    if old_price:
        data['price'] = old_price
        data['sale_price'] = current_price
    else:
        data['price'] = current_price
        data['sale_price'] = None

    # find_elements() does not raise NoSuchElementException, it returns an empty list
    photos = driver.find_elements(By.XPATH, "//div[contains(@class, 'br-image-links')]//img[@class='br-main-img']")
    # dict.fromkeys() removes duplicates if the slider clones slides
    data['photos'] = list(dict.fromkeys(img.get_attribute('src') for img in photos)) or None

    # Characteristics table: every row is <div><span>label</span><span>value</span></div>
    try:
        characteristics_block = driver.find_element(By.XPATH, "//div[@class='br-pr-chr']")
    except NoSuchElementException:
        characteristics_block = None

    try:
        data['color'] = characteristics_block.find_element(By.XPATH, ".//span[normalize-space(text())='Колір']/following-sibling::span").get_attribute('textContent').strip()
    except (NoSuchElementException, AttributeError):
        data['color'] = None

    try:
        data['memory'] = characteristics_block.find_element(By.XPATH, ".//span[normalize-space(text())=\"Вбудована пам'ять\"]/following-sibling::span").get_attribute('textContent').strip()
    except (NoSuchElementException, AttributeError):
        data['memory'] = None

    try:
        data['manufacturer'] = characteristics_block.find_element(By.XPATH, ".//span[normalize-space(text())='Виробник']/following-sibling::span").get_attribute('textContent').strip()
    except (NoSuchElementException, AttributeError):
        data['manufacturer'] = None

    try:
        data['screen_diagonal'] = characteristics_block.find_element(By.XPATH, ".//span[normalize-space(text())='Діагональ екрану']/following-sibling::span").get_attribute('textContent').strip()
    except (NoSuchElementException, AttributeError):
        data['screen_diagonal'] = None

    try:
        data['display_resolution'] = characteristics_block.find_element(By.XPATH, ".//span[normalize-space(text())='Роздільна здатність екрану']/following-sibling::span").get_attribute('textContent').strip()
    except (NoSuchElementException, AttributeError):
        data['display_resolution'] = None

    try:
        characteristics = {}
        for row in characteristics_block.find_elements(By.XPATH, ".//div[@class='br-pr-chr-item']/div/div"):
            try:
                label = row.find_element(By.XPATH, './span')
                value = label.find_element(By.XPATH, './following-sibling::span')
            except NoSuchElementException:
                continue
            # split() + join() removes non-breaking spaces and extra whitespace inside the value
            characteristics[label.get_attribute('textContent').strip()] = ' '.join(value.get_attribute('textContent').split())
        data['characteristics'] = characteristics or None
    except AttributeError:
        data['characteristics'] = None

    data['link'] = driver.current_url
    data['source'] = 'selenium'

    pprint(data)

    product, created = Product.objects.get_or_create(**data)
    print(f'Saved to DB: id={product.id}, created={created}')
except TimeoutException:
    os.makedirs(FILES_DIR, exist_ok=True)
    screenshot_path = os.path.join(FILES_DIR, 'selenium_debug.png')
    driver.save_screenshot(screenshot_path)
    print(f'Timeout on step: {step}')
    print(f'Page title: {driver.title}')
    print(f'Page url: {driver.current_url}')
    print(f'Screenshot saved: {screenshot_path}')
finally:
    driver.quit()
