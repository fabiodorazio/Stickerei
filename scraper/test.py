import csv
import time
import re
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from bs4 import BeautifulSoup
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ImprovedTextileWorldScraper:
    def __init__(self, headless=False, target_count=3000):
        self.target_count = target_count
        self.found_products = set()
        self.driver = None
        self.headless = headless
        self.max_scroll_attempts = 30  # Per page scroll attempts
        self.products_data = []
        
    def setup_chrome_driver(self):
        """Enhanced Chrome driver setup"""
        logger.info("=== SETTING UP CHROME DRIVER ===")
        
        chrome_options = Options()
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        if self.headless:
            chrome_options.add_argument("--headless=new")
        
        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            self.driver.implicitly_wait(10)
            logger.info("✓ Chrome driver initialized successfully")
            return True
        except Exception as e:
            logger.error(f"✗ Driver setup failed: {e}")
            return False
    
    def infinite_scroll_current_page(self):
        """Perform infinite scrolling on the current page to load all products"""
        logger.info("--- Starting infinite scroll on current page ---")
        
        # Get initial product count
        initial_count = self.count_products_on_current_page()
        logger.info(f"Initial products visible: {initial_count}")
        
        last_height = self.driver.execute_script("return document.body.scrollHeight")
        last_product_count = initial_count
        stable_iterations = 0
        max_stable_iterations = 5
        
        for scroll_attempt in range(self.max_scroll_attempts):
            # Scroll to bottom
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            
            # Wait for potential content to load
            time.sleep(2)
            
            # Try to trigger any "Load More" buttons
            if scroll_attempt % 3 == 0:  # Every 3rd scroll attempt
                self.trigger_load_more_buttons()
                time.sleep(1)
            
            # Check for new content
            new_height = self.driver.execute_script("return document.body.scrollHeight")
            current_product_count = self.count_products_on_current_page()
            
            if current_product_count > last_product_count:
                logger.info(f"Scroll {scroll_attempt + 1}: Found {current_product_count} products (+{current_product_count - last_product_count})")
                last_product_count = current_product_count
                stable_iterations = 0
            elif new_height > last_height:
                logger.info(f"Scroll {scroll_attempt + 1}: Page height increased, checking for products...")
                stable_iterations = 0
            else:
                stable_iterations += 1
                logger.info(f"Scroll {scroll_attempt + 1}: No changes detected ({stable_iterations}/{max_stable_iterations})")
            
            last_height = new_height
            
            # If no changes for several iterations, we've likely loaded everything
            if stable_iterations >= max_stable_iterations:
                logger.info("No more content loading - page fully scrolled")
                break
            
            # Additional scroll techniques for stubborn pages
            if scroll_attempt % 5 == 0:
                # Try scrolling in smaller increments
                for i in range(3):
                    self.driver.execute_script(f"window.scrollBy(0, {200 + i * 100});")
                    time.sleep(0.5)
        
        final_count = self.count_products_on_current_page()
        logger.info(f"Infinite scroll complete: {initial_count} → {final_count} products (+{final_count - initial_count})")
        
        # Scroll back to top for next page navigation
        self.driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(1)
        
        return final_count
    
    def handle_traditional_pagination_with_scroll(self):
        """Handle traditional pagination with infinite scroll on each page"""
        logger.info("=== HANDLING PAGINATION WITH PER-PAGE INFINITE SCROLL ===")
        
        all_products = []
        page = 1
        max_pages = 50  # Safety limit
        
        while page <= max_pages:
            logger.info(f"\n=== Processing Page {page} ===")
            
            # First, perform infinite scroll on current page
            products_after_scroll = self.infinite_scroll_current_page()
            
            # Extract all products from the fully loaded page
            page_products = self.extract_products_from_current_page()
            all_products.extend(page_products)
            
            logger.info(f"Products extracted from page {page}: {len(page_products)}")
            logger.info(f"Total products collected: {len(all_products)}")
            
            # Check if we've reached our target
            if len(all_products) >= self.target_count:
                logger.info(f"🎯 Target reached! Collected {len(all_products)} products")
                break
            
            # Try to navigate to next page
            if not self.click_next_page():
                logger.info("No more pages available - pagination complete")
                break
            
            # Wait for next page to load
            time.sleep(3)
            
            # Verify we're on a new page
            if not self.verify_page_change():
                logger.warning("Page didn't change - stopping pagination")
                break
            
            page += 1
        
        logger.info(f"Pagination complete: {len(all_products)} total products from {page-1} pages")
        return all_products
    
    def verify_page_change(self):
        """Verify that the page has actually changed"""
        try:
            # Wait for page to stabilize
            time.sleep(2)
            
            # Check for common page change indicators
            indicators = [
                "document.readyState === 'complete'",
                "!document.querySelector('.loading')",
                "!document.querySelector('.spinner')"
            ]
            
            for indicator in indicators:
                try:
                    if not self.driver.execute_script(f"return {indicator}"):
                        time.sleep(1)
                except:
                    continue
            
            return True
        except:
            return True
    
    def trigger_load_more_buttons(self):
        """Find and click various types of load more buttons"""
        load_more_selectors = [
            # Common button texts
            "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'load more')]",
            "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'show more')]",
            "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'more products')]",
            "//a[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'load more')]",
            
            # Common CSS classes and IDs
            ".load-more",
            ".show-more", 
            ".load-more-products",
            ".btn-load-more",
            "#load-more",
            "#show-more",
            "[data-role='load-more']",
            "[data-action='load-more']",
            
            # Generic button patterns
            "button[class*='load']",
            "button[class*='more']",
            "a[class*='load']",
            "a[class*='more']"
        ]
        
        buttons_clicked = 0
        
        for selector in load_more_selectors:
            try:
                if selector.startswith("//"):
                    # XPath selector
                    elements = self.driver.find_elements(By.XPATH, selector)
                else:
                    # CSS selector
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                
                for element in elements:
                    try:
                        if element.is_displayed() and element.is_enabled():
                            # Check if button is in viewport
                            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
                            time.sleep(0.5)
                            
                            button_text = element.text.strip().lower()
                            logger.info(f"Clicking button: '{button_text}'")
                            
                            # Try clicking with JavaScript to avoid interception
                            self.driver.execute_script("arguments[0].click();", element)
                            buttons_clicked += 1
                            time.sleep(2)
                            
                            # Only click first matching button per selector
                            break
                            
                    except Exception as e:
                        continue
                        
            except Exception as e:
                continue
        
        if buttons_clicked > 0:
            logger.info(f"Clicked {buttons_clicked} load more buttons")
            time.sleep(3)  # Wait for content to load
        
        return buttons_clicked > 0
    
    def click_next_page(self):
        """Find and click the next page button with enhanced detection"""
        logger.info("Looking for next page button...")
        
        next_selectors = [
            # XPath selectors for text-based matching
            "//a[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'next')]",
            "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'next')]",
            "//a[contains(text(), '>')]",
            "//a[contains(text(), '→')]",
            "//a[contains(text(), '»')]",
            
            # Attribute-based selectors
            "a[title*='Next' i]",
            "a[aria-label*='Next' i]",
            "button[title*='Next' i]",
            "button[aria-label*='Next' i]",
            
            # Class-based selectors
            ".next",
            ".next-page", 
            ".pagination-next",
            ".pager-next a",
            ".page-next",
            
            # Generic pagination patterns
            ".pagination a[href*='p=']",
            ".pagination a[href*='page=']",
            ".pager a[href*='p=']",
            
            # ID-based selectors
            "#next-page",
            "#pagination-next"
        ]
        
        for selector in next_selectors:
            try:
                if selector.startswith("//"):
                    elements = self.driver.find_elements(By.XPATH, selector)
                else:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                
                for element in elements:
                    try:
                        if element.is_displayed() and element.is_enabled():
                            href = element.get_attribute("href")
                            text = element.text.strip()
                            
                            # Skip javascript: links and empty links
                            if href and "javascript:" not in href:
                                logger.info(f"Found next page button: '{text}' -> {href}")
                                
                                # Scroll to element and click
                                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
                                time.sleep(1)
                                self.driver.execute_script("arguments[0].click();", element)
                                
                                # Wait for navigation
                                time.sleep(3)
                                return True
                                
                    except Exception as e:
                        continue
                        
            except Exception as e:
                continue
        
        logger.info("No next page button found")
        return False
    
    def count_products_on_current_page(self):
        """Enhanced product counting with multiple strategies"""
        counts = []
        
        # Strategy 1: Count product links
        try:
            product_link_patterns = [
                "a[href*='.html']",
                "a[title]",
                ".product-item a",
                ".product a", 
                "a[href*='product']",
                ".item a"
            ]
            
            for pattern in product_link_patterns:
                elements = self.driver.find_elements(By.CSS_SELECTOR, pattern)
                product_count = 0
                
                for elem in elements:
                    href = elem.get_attribute("href") or ""
                    title = elem.get_attribute("title") or ""
                    text = elem.text or ""
                    
                    combined_text = (href + " " + title + " " + text).lower()
                    if any(brand in combined_text for brand in ['jack', 'jones', 'morning', 'soya', 'selected']):
                        product_count += 1
                
                if product_count > 0:
                    counts.append(product_count)
                    
        except Exception as e:
            logger.debug(f"Product link counting failed: {e}")
        
        # Strategy 2: Count brand mentions in page source
        try:
            page_text = self.driver.page_source.lower()
            brand_patterns = [
                r'jack\s*&\s*jones',
                r'jack\s*jones',
                r'new\s*morning',
                r'soyaconcept',
                r'selected\s*homme'
            ]
            
            total_mentions = 0
            for pattern in brand_patterns:
                matches = re.findall(pattern, page_text)
                total_mentions += len(matches)
            
            if total_mentions > 0:
                # Estimate products (each product might be mentioned 2-3 times)
                estimated_products = total_mentions // 2
                counts.append(estimated_products)
                
        except Exception as e:
            logger.debug(f"Brand mention counting failed: {e}")
        
        # Strategy 3: Count structured product containers
        try:
            container_selectors = [
                '.product-item',
                '.product',
                '.item',
                '[data-product-id]',
                '.catalog-product'
            ]
            
            for selector in container_selectors:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if len(elements) > 0:
                    counts.append(len(elements))
                    
        except Exception as e:
            logger.debug(f"Container counting failed: {e}")
        
        final_count = max(counts) if counts else 0
        if counts:
            logger.debug(f"Product count methods: {counts} -> Final: {final_count}")
        
        return final_count
    
    def extract_products_from_current_page(self):
        """Enhanced product extraction from current page"""
        logger.info("Extracting products from fully loaded page...")
        
        products = []
        soup = BeautifulSoup(self.driver.page_source, 'html.parser')
        
        # Strategy 1: Extract from all links
        all_links = soup.find_all('a', href=True)
        
        for link in all_links:
            href = link.get('href', '')
            title = link.get('title', '')
            text = link.get_text(strip=True)
            
            combined_text = (href + " " + title + " " + text).lower()
            
            # Enhanced brand detection
            brand_keywords = [
                'jack', 'jones', 'morning', 'soya', 'selected',
                'jackjones', 'jack&jones'
            ]
            
            has_brand = any(brand in combined_text for brand in brand_keywords)
            
            if has_brand and len(text) > 3 and href:
                product_data = {
                    'name': title or text,
                    'url': href,
                    'price': self.find_price_near_element_bs4(link, soup),
                    'source_page': self.driver.current_url,
                    'raw_text': text[:100],
                    'extraction_method': 'link_analysis'
                }
                
                if self.is_valid_product(product_data):
                    products.append(product_data)
        
        # Strategy 2: Extract from structured containers
        container_selectors = [
            '.product-item', '.product', '.item', 
            '[data-product-id]', '.catalog-product'
        ]
        
        for selector in container_selectors:
            containers = soup.select(selector)
            for container in containers:
                product_data = self.extract_from_container_bs4(container)
                if product_data and self.is_valid_product(product_data):
                    products.append(product_data)
        
        # Remove duplicates
        unique_products = self.deduplicate_products(products)
        
        logger.info(f"Extracted {len(unique_products)} unique products from current page")
        return unique_products
    
    def find_price_near_element_bs4(self, element, soup):
        """Enhanced price detection"""
        search_elements = [element]
        
        # Add parent elements for context
        parent = element.parent
        for _ in range(4):  # Check more parent levels
            if parent:
                search_elements.append(parent)
                parent = parent.parent
            else:
                break
        
        # Enhanced price patterns
        price_patterns = [
            r'(\d+[.,]\d{2})\s*€',
            r'€\s*(\d+[.,]\d{2})',
            r'\$\s*(\d+[.,]\d{2})',
            r'(\d+[.,]\d{2})\s*\$',
            r'(\d{1,4}[.,]\d{2})',
            r'(\d{1,4})\s*€',
            r'€\s*(\d{1,4})',
        ]
        
        for search_elem in search_elements:
            text = search_elem.get_text() if hasattr(search_elem, 'get_text') else str(search_elem)
            
            for pattern in price_patterns:
                matches = re.findall(pattern, text)
                for match in matches:
                    try:
                        price = match.replace(',', '.')
                        price_float = float(price)
                        if 1 <= price_float <= 2000:  # Reasonable price range
                            return f"{price_float:.2f}"
                    except:
                        continue
        
        return ""
    
    def extract_from_container_bs4(self, container):
        """Enhanced container-based extraction"""
        try:
            # Find product name with multiple strategies
            name_selectors = [
                'h1', 'h2', 'h3', 'h4',
                '.product-name', '.title', '.name',
                'a[title]', '.product-title'
            ]
            
            name = ""
            for selector in name_selectors:
                elem = container.select_one(selector)
                if elem:
                    name = elem.get('title') or elem.get_text(strip=True)
                    if name and len(name) > 3:
                        break
            
            if not name:
                return None
            
            # Find URL
            url = ""
            link = container.select_one('a[href]')
            if link:
                url = link.get('href', '')
            
            # Find price
            price = self.find_price_near_element_bs4(container, None)
            
            return {
                'name': name,
                'url': url,
                'price': price,
                'source_page': self.driver.current_url,
                'extraction_method': 'container_structured'
            }
        except Exception as e:
            logger.debug(f"Container extraction failed: {e}")
            return None
    
    def is_valid_product(self, product_data):
        """Enhanced product validation"""
        name = product_data.get('name', '').strip()
        
        if len(name) < 3:
            return False
        
        # Check for brand indicators (case insensitive)
        name_lower = name.lower()
        brand_keywords = [
            'jack', 'jones', 'morning', 'soya', 'selected',
            'jackjones', 'jack&jones', 'soyaconcept'
        ]
        
        has_brand = any(brand in name_lower for brand in brand_keywords)
        
        # Additional validation: avoid navigation/menu items
        invalid_indicators = [
            'search', 'menu', 'navigation', 'footer', 'header',
            'login', 'register', 'cart', 'checkout', 'contact'
        ]
        
        has_invalid = any(invalid in name_lower for invalid in invalid_indicators)
        
        return has_brand and not has_invalid
    
    def deduplicate_products(self, products):
        """Enhanced deduplication"""
        seen = set()
        unique_products = []
        
        for product in products:
            name = product.get('name', '').strip()
            url = product.get('url', '').strip()
            
            # Create normalized key from name and URL
            name_key = re.sub(r'[^\w\s]', '', name.lower()).replace(' ', '')
            url_key = url.split('?')[0] if url else ''  # Remove query parameters
            
            combined_key = f"{name_key}|{url_key}"
            
            if len(name_key) > 3 and combined_key not in seen:
                seen.add(combined_key)
                unique_products.append(product)
        
        return unique_products
    
    def smart_scraping_approach(self):
        """Enhanced smart scraping with per-page infinite scroll"""
        logger.info("=== STARTING ENHANCED SMART SCRAPING ===")
        
        # Use pagination with infinite scroll on each page
        all_products = self.handle_traditional_pagination_with_scroll()
        
        return all_products
    
    def save_results(self, products, filename='textile_products_enhanced.csv'):
        """Enhanced results saving"""
        logger.info(f"=== SAVING {len(products)} PRODUCTS ===")
        
        if not products:
            logger.warning("No products to save!")
            return None
        
        # Save CSV
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['name', 'price', 'url', 'source_page', 'extraction_method', 'raw_text']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for product in products:
                row = {field: product.get(field, '') for field in fieldnames}
                writer.writerow(row)
        
        # Save JSON with additional metadata
        json_data = {
            'scraping_info': {
                'total_products': len(products),
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                'target_count': self.target_count
            },
            'products': products
        }
        
        json_filename = filename.replace('.csv', '.json')
        with open(json_filename, 'w', encoding='utf-8') as jsonfile:
            json.dump(json_data, jsonfile, indent=2, ensure_ascii=False)
        
        logger.info(f"✓ Results saved to: {filename} and {json_filename}")
        return filename
    
    def run(self, url):
        """Main execution method"""
        logger.info("=== ENHANCED TEXTILE WORLD SCRAPER WITH PER-PAGE INFINITE SCROLL ===")
        logger.info(f"Target: {self.target_count} products")
        logger.info(f"URL: {url}")
        
        if not self.setup_chrome_driver():
            return False
        
        try:
            # Load initial page
            logger.info("Loading initial page...")
            self.driver.get(url)
            time.sleep(5)
            
            # Use enhanced smart scraping
            products = self.smart_scraping_approach()
            
            if products:
                # Save results
                filename = self.save_results(products)
                
                # Show enhanced preview
                logger.info(f"\n=== RESULTS SUMMARY ===")
                logger.info(f"Total products found: {len(products)}")
                logger.info(f"Target achievement: {(len(products)/self.target_count)*100:.1f}%")
                
                # Show breakdown by extraction method
                method_counts = {}
                for product in products:
                    method = product.get('extraction_method', 'unknown')
                    method_counts[method] = method_counts.get(method, 0) + 1
                
                logger.info(f"Extraction methods: {method_counts}")
                
                # Show sample products
                logger.info(f"\n=== SAMPLE PRODUCTS ===")
                for i, product in enumerate(products[:15], 1):
                    name = product.get('name', 'N/A')[:60]
                    price = product.get('price', 'N/A')
                    method = product.get('extraction_method', 'N/A')
                    logger.info(f"{i:2d}. {name:<60} - €{price:<8} [{method}]")
                
                if len(products) > 15:
                    logger.info(f"... and {len(products) - 15} more products")
                
                return True
            else:
                logger.error("No products found!")
                return False
                
        except Exception as e:
            logger.error(f"Scraping failed: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            if self.driver:
                self.driver.quit()

def main():
    """Main function"""
    url = "https://www.textileworld.eu/catalogsearch/result/index/adjclear/true/"
    
    # Create enhanced scraper instance
    scraper = ImprovedTextileWorldScraper(
        headless=False,  # Keep False for debugging
        target_count=3000
    )
    
    # Run enhanced scraper
    success = scraper.run(url)
    
    if success:
        print("\n🎉 ENHANCED SCRAPING COMPLETED SUCCESSFULLY! 🎉")
        print("📊 Check the generated CSV and JSON files for detailed results")
    else:
        print("\n❌ SCRAPING FAILED - Check logs for details")
    
    input("\nPress Enter to exit...")

if __name__ == "__main__":
    main()