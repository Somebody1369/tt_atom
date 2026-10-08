"""
Parse one brain.com.ua product page with Requests + BeautifulSoup and save it to DB
"""
from load_django import *
from parser_app.models import *
import sys
from pprint import pprint
import requests
from bs4 import BeautifulSoup

headers = {
    'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:126.0) Gecko/20100101 Firefox/126.0',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
    'Referer': 'https://www.google.com/',
    'Connection': 'keep-alive',
    'Cache-Control': 'no-cache',
    'Pragma': 'no-cache',
    'Upgrade-Insecure-Requests': '1',
    'DNT': '1',  # Do Not Track
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'same-origin',
    'Sec-Fetch-User': '?1',
    'TE': 'Trailers',  # Transfer Encoding
}

url = 'https://brain.com.ua/ukr/Mobilniy_telefon_Apple_iPhone_16_Pro_Max_256GB_Black_Titanium-p1145443.html'

try:
    response = requests.get(url, headers=headers, timeout=30)
except (requests.exceptions.ConnectionError, requests.exceptions.Timeout, requests.exceptions.TooManyRedirects) as error:
    print(f'Request error: {error}')
    sys.exit(1)

if response.status_code == 200:
    print('Success!')
    soup = BeautifulSoup(response.text, 'html.parser')

    data = {}

    try:
        data['full_name'] = soup.find('h1', attrs={'class': 'main-title'}).text.strip()
    except AttributeError:
        data['full_name'] = None

    try:
        data['product_code'] = soup.find('span', attrs={'class': 'br-pr-code-val'}).text.strip()
    except AttributeError:
        data['product_code'] = None

    try:
        # Only the current product's counter: the series counters are in series-comments-block
        reviews_block = soup.find('div', attrs={'id': 'fast-navigation-block-static'}).find('div', attrs={'class': 'main-comments-block'})
        data['reviews_count'] = int(reviews_block.find('a', attrs={'class': 'reviews-count'}).find('span').text.strip())
    except (AttributeError, ValueError):
        data['reviews_count'] = None

    # Main price block: br-pr-op = old (crossed out) price, only with a discount; br-pr-np = current price
    price_block = soup.find('div', attrs={'class': 'main-price-block'})

    try:
        old_price_text = price_block.find('div', attrs={'class': 'br-pr-op'}).find('span').text
        old_price = int(''.join(char for char in old_price_text if char.isdigit()))
    except (AttributeError, ValueError):
        old_price = None

    try:
        current_price_text = price_block.find('div', attrs={'class': 'br-pr-np'}).find('span').text
        current_price = int(''.join(char for char in current_price_text if char.isdigit()))
    except (AttributeError, ValueError):
        current_price = None

    if old_price:
        data['price'] = old_price
        data['sale_price'] = current_price
    else:
        data['price'] = current_price
        data['sale_price'] = None

    try:
        gallery = soup.find('div', attrs={'class': 'br-image-links'})
        data['photos'] = [img.get('src') for img in gallery.find_all('img', attrs={'class': 'br-main-img'})] or None
    except AttributeError:
        data['photos'] = None

    # Characteristics table: every row is <div><span>label</span><span>value</span></div>
    characteristics_block = soup.find('div', attrs={'class': 'br-pr-chr'})

    try:
        data['color'] = characteristics_block.find('span', string='Колір').find_next_sibling('span').get_text(strip=True)
    except AttributeError:
        data['color'] = None

    try:
        data['memory'] = characteristics_block.find('span', string="Вбудована пам'ять").find_next_sibling('span').get_text(strip=True)
    except AttributeError:
        data['memory'] = None

    try:
        data['manufacturer'] = characteristics_block.find('span', string='Виробник').find_next_sibling('span').get_text(strip=True)
    except AttributeError:
        data['manufacturer'] = None

    try:
        data['screen_diagonal'] = characteristics_block.find('span', string='Діагональ екрану').find_next_sibling('span').get_text(strip=True)
    except AttributeError:
        data['screen_diagonal'] = None

    try:
        data['display_resolution'] = characteristics_block.find('span', string='Роздільна здатність екрану').find_next_sibling('span').get_text(strip=True)
    except AttributeError:
        data['display_resolution'] = None

    try:
        characteristics = {}
        for group in characteristics_block.find_all('div', attrs={'class': 'br-pr-chr-item'}):
            for row in group.find('div').find_all('div', recursive=False):
                label = row.find('span')
                value = label.find_next_sibling('span') if label else None
                if label and value:
                    # split() + join() removes non-breaking spaces and extra whitespace inside the value
                    characteristics[label.get_text(strip=True)] = ' '.join(value.get_text().split())
        data['characteristics'] = characteristics or None
    except AttributeError:
        data['characteristics'] = None

    data['link'] = url
    data['source'] = 'bs4'

    pprint(data)

    # In a JSONField lookup characteristics=None means JSON null, not an empty field,
    # so get_or_create would not find the saved record and would create a duplicate
    if data['characteristics'] is None:
        del data['characteristics']
        data['characteristics__isnull'] = True

    product, created = Product.objects.get_or_create(**data)
    print(f'Saved to DB: id={product.id}, created={created}')
else:
    print(f'Error: {response.status_code}')
