import requests
from bs4 import BeautifulSoup
import csv
import time
import re
from urllib.parse import urljoin
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TextileWorldScraper:
    def __init__(self, base_url="https://www.textileworld.eu/catalogsearch/result/index/adjclear/true/p/"):
        self.base_url = base_url
        self.session = requests.Session()
        # Add headers to mimic a real browser
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        self.products = []
    
    def get_page(self, page_num):
        """Fetch a single page and return BeautifulSoup object"""
        url = f"{self.base_url}{page_num}/"
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return BeautifulSoup(response.content, 'html.parser')
        except requests.RequestException as e:
            logger.error(f"Error fetching page {page_num}: {e}")
            return None
    
    def extract_product_info(self, product_element):
        """Extract product information from a product element"""
        product_data = {}
        
        # Extract logo/image
        logo_container = product_element.find('div', class_='logo-container')
        if logo_container:
            img = logo_container.find('img')
            product_data['image_url'] = img.get('src', '') if img else ''
        else:
            product_data['image_url'] = ''
        
        # Extract price
        price_box = product_element.find('div', class_='price-box')
        if price_box:
            price_span = price_box.find('span', class_='price')
            if price_span:
                # Extract the innermost price span
                inner_price = price_span.find('span', class_='price')
                product_data['price'] = inner_price.text.strip() if inner_price else price_span.text.strip()
            else:
                product_data['price'] = ''
            
            # Extract price postfix (tax info)
            postfix = price_box.find('span', class_='price-postfix')
            product_data['price_postfix'] = postfix.text.strip() if postfix else ''
        else:
            product_data['price'] = ''
            product_data['price_postfix'] = ''
        
        # Extract product info
        product_info = product_element.find('div', class_='product-info')
        if product_info:
            # SKU
            sku_p = product_info.find('p', class_='sku')
            product_data['sku'] = sku_p.text.strip() if sku_p else ''
            
            # Product title and link
            title_h5 = product_info.find('h5')
            if title_h5:
                title_link = title_h5.find('a')
                if title_link:
                    product_data['title'] = title_link.text.strip()
                    product_data['product_url'] = urljoin("https://www.textileworld.eu", title_link.get('href', ''))
                else:
                    product_data['title'] = title_h5.text.strip()
                    product_data['product_url'] = ''
            else:
                product_data['title'] = ''
                product_data['product_url'] = ''
        else:
            product_data['sku'] = ''
            product_data['title'] = ''
            product_data['product_url'] = ''
        
        # Extract collateral box info
        collateral_box = product_element.find('div', class_='collateral-box')
        if collateral_box:
            # Product subtitle
            subtitle_div = collateral_box.find('div', class_='product-subtitle')
            product_data['subtitle'] = subtitle_div.text.strip() if subtitle_div else ''
            
            # Product specs
            specs_div = collateral_box.find('div', class_='product-specs')
            product_data['specs'] = specs_div.text.strip() if specs_div else ''
        else:
            product_data['subtitle'] = ''
            product_data['specs'] = ''
        
        # Check if new product
        new_product = product_element.find('p', class_='new-product')
        product_data['is_new'] = 'Yes' if new_product and new_product.text.strip() else 'No'
        print(product_data)
        
        return product_data
    
    def scrape_page(self, page_num):
        """Scrape products from a single page"""
        logger.info(f"Scraping page {page_num}")
        soup = self.get_page(page_num)
        
        if not soup:
            return False
        
        # Find all product containers - you might need to adjust this selector
        # based on the actual HTML structure
        products = soup.find_all('div', class_='item')  # Adjust class name as needed
        
        if not products:
            # Try alternative selectors
            products = soup.find_all('li', class_='item')
            
        if not products:
            logger.info(f"No products found on page {page_num}")
            return False
        
        page_products = []
        for product in products:
            try:
                product_data = self.extract_product_info(product)
                if product_data.get('title'):  # Only add if we have a title
                    product_data['page_number'] = page_num
                    page_products.append(product_data)
            except Exception as e:
                logger.error(f"Error extracting product data: {e}")
                continue
        
        self.products.extend(page_products)
        logger.info(f"Found {len(page_products)} products on page {page_num}")
        return len(page_products) > 0
    
    def scrape_all_pages(self, start_page=1, max_pages=None, delay=1):
        """Scrape all pages until no more products are found"""
        page_num = start_page
        consecutive_empty_pages = 0
        max_consecutive_empty = 3  # Stop after 3 consecutive empty pages
        
        while True:
            if max_pages and page_num > max_pages:
                break
                
            has_products = self.scrape_page(page_num)
            
            if not has_products:
                consecutive_empty_pages += 1
                if consecutive_empty_pages >= max_consecutive_empty:
                    logger.info(f"Stopping after {consecutive_empty_pages} consecutive empty pages")
                    break
            else:
                consecutive_empty_pages = 0
            
            page_num += 1
            
            # Add delay to be respectful to the server
            time.sleep(delay)
        
        logger.info(f"Scraping completed. Total products found: {len(self.products)}")
    
    def save_to_csv(self, filename='textileworld_products.csv'):
        """Save scraped products to CSV file"""
        if not self.products:
            logger.warning("No products to save")
            return
        
        fieldnames = [
            'page_number', 'sku', 'title', 'price', 'price_postfix', 
            'subtitle', 'specs', 'is_new', 'image_url', 'product_url'
        ]
        
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(self.products)
        
        logger.info(f"Data saved to {filename}")

def main():
    """Main function to run the scraper"""
    scraper = TextileWorldScraper()
    
    # Test with first few pages
    print("Starting scrape...")
    scraper.scrape_all_pages(start_page=1, max_pages=5, delay=2)  # Start with 5 pages for testing
    
    # Save to CSV
    scraper.save_to_csv('textileworld_products.csv')
    
    print(f"Scraping completed! Found {len(scraper.products)} products")

if __name__ == "__main__":
    main()