import requests
from bs4 import BeautifulSoup

url = "https://www.textileworld.eu"

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

try:
    # Fetch the page
    response = requests.get(url, headers=headers)
    response.raise_for_status()  # Check for HTTP errors
    
    soup = BeautifulSoup(response.text, 'html.parser')

    # Extract catalogue number (updated selectors)
    catalogue_number = soup.find('div', {'class': 'product-info'})
    print(catalogue_number)
    if catalogue_number:
        print('yes')
        article_number = soup.find('div', class_='product-info').text.strip()
    else:
        catalogue_number = "Not found"
    
    # Extract price (updated selectors)
    price = soup.find('span', {'class': 'price'})
    if price:
        price = price.text.strip()
    else:
        price = "Not found"
    article_name = soup.find('div', class_='collateral-box').text.strip()
    
    print(f"Catalogue Number: {article_number}")
    print(f"Price: {price}")
    print(f"Name {article_name}")
    
except Exception as e:
    print(f"Error occurred: {e}")