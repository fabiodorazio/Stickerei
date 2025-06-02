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
        self.max_scroll_attempts = 50  # Reduced for more focused approach
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
    
    def analyze_page_type(self):
        """Determine what type of pagination/loading this page uses"""
        logger.info("=== ANALYZING PAGE TYPE ===")
        
        # Check for pagination elements
        pagination_selectors = [
            ".pagination",
            ".pager",
            ".page-numbers",
            "[class*='page']",
            "a[href*='p=']",
            "a[href*='page=']",
            ".next",
            ".pages"
        ]
        
        pagination_found = False
        for selector in pagination_selectors:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    logger.info(f"Found pagination: {selector} ({len(elements)} elements)")
                    pagination_found = True
                    # Get sample links
                    for elem in elements[:3]:
                        href = elem.get_attribute("href")
                        text = elem.text.strip()
                        if href and text:
                            logger.info(f"  Pagination link: '{text}' -> {href}")
            except:
                continue
        
        # Check for AJAX load indicators
        ajax_indicators = [
            "button[class*='load']",
            "button[class*='more']",
            ".load-more",
            "[data-role*='load']",
            ".ajax-loader",
            ".loading"
        ]
        
        ajax_found = False
        for selector in ajax_indicators:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    logger.info(f"Found AJAX indicator: {selector} ({len(elements)} elements)")
                    ajax_found = True
            except:
                continue
        
        # Check URL structure for clues
        current_url = self.driver.current_url
        logger.info(f"Current URL: {current_url}")
        
        if "page=" in current_url or "p=" in current_url:
            logger.info("✓ URL-based pagination detected")
            return "url_pagination"
        elif ajax_found:
            logger.info("✓ AJAX loading detected")
            return "ajax_loading"
        elif pagination_found:
            logger.info("✓ Traditional pagination detected")
            return "pagination"
        else:
            logger.info("? Unknown pagination type - will try multiple approaches")
            return "unknown"
    
    def handle_url_pagination(self):
        """Handle URL-based pagination"""
        logger.info("=== HANDLING URL PAGINATION ===")
        
        all_products = []
        base_url = self.driver.current_url
        page = 1
        max_pages = 50  # Safety limit
        
        while page <= max_pages:
            logger.info(f"\n--- Processing Page {page} ---")
            
            # Construct page URL
            if "?" in base_url:
                page_url = f"{base_url}&p={page}"
            else:
                page_url = f"{base_url}?p={page}"
            
            logger.info(f"Loading: {page_url}")
            
            try:
                self.driver.get(page_url)
                time.sleep(3)
                
                # Count products on this page
                products_on_page = self.count_products_on_current_page()
                logger.info(f"Products found on page {page}: {products_on_page}")
                
                if products_on_page == 0:
                    logger.info("No products found - reached end")
                    break
                
                # Extract products from current page
                page_products = self.extract_products_from_current_page()
                all_products.extend(page_products)
                
                logger.info(f"Total products collected: {len(all_products)}")
                
                # Check if we've reached our target
                if len(all_products) >= self.target_count:
                    logger.info(f"Target reached! Collected {len(all_products)} products")
                    break
                
                # Check if we should continue
                if not self.should_continue_pagination():
                    logger.info("No more pages available")
                    break
                
                page += 1
                
            except Exception as e:
                logger.error(f"Error on page {page}: {e}")
                break
        
        return all_products
    
    
    def handle_traditional_pagination(self):
        """Handle traditional pagination with next buttons - TextileWorld.eu specific"""
        logger.info("=== HANDLING TRADITIONAL PAGINATION (TextileWorld.eu) ===")
        
        all_products = []
        page = 1
        visited_urls = set()
        base_url_pattern = None
        
        while page <= 50:  # Safety limit
            logger.info(f"\n--- Processing Page {page} ---")
            
            # Track current URL to detect loops and extract pattern
            current_url = self.driver.current_url
            logger.info(f"Current URL: {current_url}")
            
            if current_url in visited_urls:
                logger.warning(f"Already visited {current_url} - stopping to prevent loop")
                break
            visited_urls.add(current_url)
            
            # Extract base URL pattern on first page
            if page == 1:
                base_url_pattern = self.extract_base_url_pattern(current_url)
                logger.info(f"Detected base URL pattern: {base_url_pattern}")
            
            # Extract products from current page
            page_products = self.extract_products_from_current_page()
            all_products.extend(page_products)
            
            logger.info(f"Products on page {page}: {len(page_products)}")
            logger.info(f"Total products: {len(all_products)}")
            
            # If no products found on this page, we might be done
            if len(page_products) == 0:
                logger.info("No products found on this page - pagination might be complete")
                break
            
            # Try to navigate to next page
            if not self.navigate_to_next_page(base_url_pattern, page + 1):
                logger.info("Could not navigate to next page - pagination complete")
                break
            
            time.sleep(3)
            page += 1
            
            if len(all_products) >= self.target_count:
                logger.info(f"Target reached! Collected {len(all_products)} products")
                break
        
        return all_products

    def extract_base_url_pattern(self, url):
        """Extract the base URL pattern for TextileWorld.eu pagination"""
        import re
        
        # Pattern: https://www.textileworld.eu/catalogsearch/result/index/cc_geschlecht/3945/dir/desc/order/relevance/p/1/
        # We want: https://www.textileworld.eu/catalogsearch/result/index/cc_geschlecht/3945/dir/desc/order/relevance/p/{page}/
        
        # Replace the page number with a placeholder
        pattern = re.sub(r'/p/\d+/', '/p/{page}/', url)
        
        # If no /p/number/ pattern found, try to construct it
        if '{page}' not in pattern:
            if url.endswith('/'):
                pattern = url + 'p/{page}/'
            else:
                pattern = url + '/p/{page}/'
        
        return pattern

    def navigate_to_next_page(self, base_url_pattern, next_page):
        """Navigate to next page using URL manipulation or button clicks"""
        
        # Method 1: Try direct URL navigation (most reliable for TextileWorld.eu)
        if base_url_pattern and '{page}' in base_url_pattern:
            try:
                next_url = base_url_pattern.format(page=next_page)
                logger.info(f"Attempting direct navigation to: {next_url}")
                
                self.driver.get(next_url)
                time.sleep(2)
                
                # Verify we got a valid page
                if self.verify_valid_page():
                    logger.info(f"Successfully navigated to page {next_page}")
                    return True
                else:
                    logger.warning(f"Page {next_page} appears to be invalid or empty")
                    return False
                    
            except Exception as e:
                logger.error(f"Direct navigation failed: {e}")
        
        # Method 2: Try to find and click pagination buttons
        return self.click_next_page_textileworld()

    def click_next_page_textileworld(self):
        """Find and click next page button specific to TextileWorld.eu"""
        
        # First, look for the pagination container
        self.analyze_textileworld_pagination()
        
        # TextileWorld.eu specific selectors
        next_selectors = [
            # Standard pagination
            ".pages .next",
            ".pages a.next",
            ".pagination .next",
            ".pagination a.next",
            
            # Magento-style pagination (TextileWorld.eu likely uses Magento)
            ".pages .pages-items .next",
            ".pages .pages-items a[title*='Next']",
            ".pages .pages-items a[title*='Weiter']", # German for "Next"
            ".pages .pages-items a[title*='nächste']", # German for "next"
            
            # Generic next buttons
            "a[title*='Next' i]",
            "a[title*='Weiter' i]",
            "a[rel='next']",
            
            # Look for numeric pagination (current page + 1)
            ".pages .pages-items a",
            ".pagination a",
            
            # Text-based selectors
            "a:contains('Next')",
            "a:contains('Weiter')",
            "a:contains('>')",
            "a:contains('»')"
        ]
        
        logger.info("Searching for TextileWorld.eu pagination buttons...")
        
        # Get current page number for numeric pagination
        current_page = self.get_current_page_number()
        target_page = current_page + 1 if current_page else 2
        
        for selector in next_selectors:
            try:
                if ":contains(" in selector:
                    # Handle jQuery-style selectors
                    text = selector.split("'")[1] if "'" in selector else selector.split('"')[1]
                    elements = self.driver.find_elements(By.XPATH, f"//a[contains(text(), '{text}')]")
                else:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                
                for element in elements:
                    if self.is_valid_textileworld_next_button(element, target_page):
                        try:
                            logger.info(f"Found valid next button: {element.text} -> {element.get_attribute('href')}")
                            
                            # Scroll to element
                            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
                            time.sleep(1)
                            
                            # Click the button
                            self.driver.execute_script("arguments[0].click();", element)
                            time.sleep(2)
                            
                            if self.verify_valid_page():
                                return True
                                
                        except Exception as e:
                            logger.debug(f"Error clicking button: {e}")
                            continue
                            
            except Exception as e:
                logger.debug(f"Error with selector {selector}: {e}")
                continue
        
        return False

    def is_valid_textileworld_next_button(self, element, target_page):
        """Check if element is a valid next button for TextileWorld.eu"""
        try:
            if not (element.is_displayed() and element.is_enabled()):
                return False
            
            text = element.text.strip()
            href = element.get_attribute("href")
            title = (element.get_attribute("title") or "").lower()
            classes = (element.get_attribute("class") or "").lower()
            
            # Skip disabled buttons
            if "disabled" in classes or element.get_attribute("disabled"):
                return False
            
            # Skip javascript void links
            if href and ("javascript:" in href or href == "#"):
                return False
            
            # Check for "next" indicators (English/German)
            next_indicators = [
                "next" in text.lower(),
                "weiter" in text.lower(),
                "nächste" in text.lower(),
                "next" in title,
                "weiter" in title,
                text in [">", "»", "→"]
            ]
            
            # Check for numeric pagination
            if text.isdigit() and int(text) == target_page:
                next_indicators.append(True)
            
            # Check URL contains next page number
            if href and f"/p/{target_page}/" in href:
                next_indicators.append(True)
            
            # Avoid previous buttons
            prev_indicators = [
                "previous" in text.lower(),
                "zurück" in text.lower(),
                "vorherige" in text.lower(),
                text in ["<", "«", "←"]
            ]
            
            return any(next_indicators) and not any(prev_indicators)
            
        except Exception as e:
            logger.debug(f"Error validating TextileWorld button: {e}")
            return False

    def analyze_textileworld_pagination(self):
        """Analyze TextileWorld.eu pagination structure"""
        logger.info("\n=== TEXTILEWORLD.EU PAGINATION ANALYSIS ===")
        
        # Look for Magento-style pagination
        pagination_selectors = [
            ".pages",
            ".pagination",
            ".toolbar-bottom .pages",
            ".page-numbers"
        ]
        
        for selector in pagination_selectors:
            try:
                containers = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for container in containers:
                    if container.is_displayed():
                        logger.info(f"Found pagination container: {selector}")
                        html = container.get_attribute('outerHTML')
                        logger.info(f"  HTML: {html[:300]}...")
                        
                        # Look for all links
                        links = container.find_elements(By.TAG_NAME, "a")
                        logger.info(f"  Found {len(links)} pagination links:")
                        for link in links:
                            text = link.text.strip()
                            href = link.get_attribute("href")
                            title = link.get_attribute("title")
                            logger.info(f"    Text: '{text}', Title: '{title}', Href: {href}")
                        
                        return
                        
            except Exception as e:
                continue
        
        logger.warning("No pagination container found")

    def verify_valid_page(self):
        """Verify we're on a valid product page"""
        try:
            # Wait for page to load
            time.sleep(2)
            
            # Check for common indicators of a valid product page
            indicators = [
                # Product containers
                ".products-grid",
                ".product-items",
                ".category-products",
                ".search-results",
                
                # At least one product
                ".product-item",
                ".item",
                "[data-product-id]"
            ]
            
            for indicator in indicators:
                elements = self.driver.find_elements(By.CSS_SELECTOR, indicator)
                if elements and any(el.is_displayed() for el in elements):
                    logger.info(f"Valid page confirmed - found {indicator}")
                    return True
            
            # Check if we got an error page
            error_indicators = [
                "no products",
                "keine produkte",
                "404",
                "page not found",
                "seite nicht gefunden"
            ]
            
            page_text = self.driver.find_element(By.TAG_NAME, "body").text.lower()
            for error in error_indicators:
                if error in page_text:
                    logger.warning(f"Error page detected: {error}")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error verifying page: {e}")
            return False

    def get_current_page_number(self):
        """Get current page number from TextileWorld.eu"""
        try:
            # Method 1: From URL
            url = self.driver.current_url
            import re
            page_match = re.search(r'/p/(\d+)/', url)
            if page_match:
                return int(page_match.group(1))
            
            # Method 2: From pagination element
            current_selectors = [
                ".pages .current",
                ".pages .active",
                ".pagination .current",
                ".pagination .active"
            ]
            
            for selector in current_selectors:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for element in elements:
                    text = element.text.strip()
                    if text.isdigit():
                        return int(text)
            
            return 1  # Default to page 1
            
        except Exception as e:
            logger.debug(f"Error getting current page: {e}")
            return 1
    
    def should_continue_pagination(self):
        """Check if there are more pages to process"""
        # Look for indicators that there are more pages
        indicators = [
            ".next",
            ".next-page",
            "a[href*='p=']",
            ".pagination a"
        ]
        
        for selector in indicators:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for elem in elements:
                    if elem.is_displayed() and elem.is_enabled():
                        return True
            except:
                continue
        
        return False
    
    def count_products_on_current_page(self):
        """Count products on the current page using multiple methods"""
        counts = []
        
        # Method 1: Product links
        product_link_selectors = [
            "a[href*='html']",
            "a[title]",
            ".product-item a",
            ".product a",
            "a[href*='product']"
        ]
        
        for selector in product_link_selectors:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                # Filter for actual product links
                product_count = 0
                for elem in elements:
                    href = elem.get_attribute("href") or ""
                    title = elem.get_attribute("title") or ""
                    text = elem.text or ""
                    
                    # Check if this looks like a product
                    combined_text = (href + " " + title + " " + text).lower()
                    if any(brand in combined_text for brand in ['jack', 'jones', 'morning', 'soya', 'selected']):
                        product_count += 1
                
                if product_count > 0:
                    counts.append(product_count)
                    
            except:
                continue
        
        # Method 2: Text-based counting
        try:
            page_text = self.driver.page_source.lower()
            brand_mentions = 0
            brands = ['jack & jones', 'jack&jones', 'new morning', 'soyaconcept', 'selected homme']
            for brand in brands:
                brand_mentions += page_text.count(brand)
            
            if brand_mentions > 0:
                counts.append(brand_mentions // 2)  # Divide by 2 to account for duplicates
        except:
            pass
        
        final_count = max(counts) if counts else 0
        logger.info(f"Product count methods: {counts} -> Final: {final_count}")
        return final_count
    
    def extract_products_from_current_page(self):
        """Extract all products from the current page"""
        logger.info("Extracting products from current page...")
        
        products = []
        soup = BeautifulSoup(self.driver.page_source, 'html.parser')
        
        # Strategy 1: Find all links and filter for products
        all_links = soup.find_all('a', href=True)
        
        for link in all_links:
            href = link.get('href', '')
            title = link.get('title', '')
            text = link.get_text(strip=True)
            
            # Check if this is a product link
            combined_text = (href + " " + title + " " + text).lower()
            
            # Brand detection
            has_brand = any(brand in combined_text for brand in [
                'jack', 'jones', 'morning', 'soya', 'selected'
            ])
            
            if has_brand and len(text) > 3:
                # Find product-info element
                product_info_elem = link.find_parent(class_='product-info') or link.find(class_='product-info')
                product_info_text = product_info_elem.get_text(strip=True) if product_info_elem else ''
                
                # Find collateral-box element
                collateral_elem = link.find_parent(id='collateral-box') or soup.find(id='collateral-box')
                collateral_text = collateral_elem.get_text(strip=True) if collateral_elem else ''
                
                # Extract product data
                product_data = {
                    'name': title or text,
                    'url': href,
                    'price': self.find_price_near_element_bs4(link, soup),
                    'product': product_info_text,  # New element: class='product-info'
                    'id': collateral_text,         # New element: id='collateral-box'
                    'source_page': self.driver.current_url,
                    'raw_text': text[:100]
                }
                print(product_data)
                
                # Validate and clean
                if self.is_valid_product(product_data):
                    products.append(product_data)
        
        # Strategy 2: Look for structured product data
        product_containers = soup.select('.product-item, .item, [data-product-id]')
        for container in product_containers:
            product_data = self.extract_from_container_bs4(container)
            if product_data and self.is_valid_product(product_data):
                # Add the new elements to container-extracted products as well
                product_info_elem = container.find(class_='product-info')
                product_info_text = product_info_elem.get_text(strip=True) if product_info_elem else ''
                
                collateral_elem = soup.find(id='collateral-box')
                collateral_text = collateral_elem.get_text(strip=True) if collateral_elem else ''
                
                product_data['product'] = product_info_text
                product_data['id'] = collateral_text
                
                products.append(product_data)
        
        # Remove duplicates
        unique_products = self.deduplicate_products(products)
        
        logger.info(f"Extracted {len(unique_products)} unique products from current page")
        return unique_products
    
    def find_price_near_element_bs4(self, element, soup):
        """Find price near an element using BeautifulSoup"""
        # Look in the element and its parents
        search_elements = [element]
        
        parent = element.parent
        for _ in range(3):
            if parent:
                search_elements.append(parent)
                parent = parent.parent
            else:
                break
        
        price_patterns = [
            r'(\d+[.,]\d{2})\s*€',
            r'€\s*(\d+[.,]\d{2})',
            r'\b(\d+[.,]\d{2})\b',
            r'(\d{1,4}[.,]\d{2})',
        ]
        
        for search_elem in search_elements:
            text = search_elem.get_text() if hasattr(search_elem, 'get_text') else str(search_elem)
            for pattern in price_patterns:
                match = re.search(pattern, text)
                if match:
                    price = match.group(1).replace(',', '.')
                    try:
                        price_float = float(price)
                        if 1 <= price_float <= 1000:
                            return price
                    except:
                        continue
        
        return ""
    
    def extract_from_container_bs4(self, container):
        """Extract product data from a container element"""
        try:
            # Find product name
            name_selectors = ['h2', 'h3', '.product-name', '.title', 'a[title]']
            name = ""
            
            for selector in name_selectors:
                elem = container.select_one(selector)
                if elem:
                    name = elem.get('title') or elem.get_text(strip=True)
                    if name:
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
                'extraction_method': 'container'
            }
        except:
            return None
    
    def is_valid_product(self, product_data):
        """Validate if product data is valid"""
        name = product_data.get('name', '').strip()
        
        if len(name) < 3:
            return False
        
        # Check for brand indicators
        name_lower = name.lower()
        has_brand = any(brand in name_lower for brand in [
            'jack', 'jones', 'morning', 'soya', 'selected'
        ])
        
        return has_brand
    
    def deduplicate_products(self, products):
        """Remove duplicate products"""
        seen = set()
        unique_products = []
        
        for product in products:
            name = product.get('name', '').strip()
            # Create normalized key
            key = re.sub(r'[^\w\s]', '', name.lower()).replace(' ', '')
            
            if len(key) > 3 and key not in seen:
                seen.add(key)
                unique_products.append(product)
        
        return unique_products
    
    def smart_scraping_approach(self):
        """Intelligent scraping based on page analysis"""
        logger.info("=== STARTING SMART SCRAPING ===")
        
        # First, analyze what type of page we're dealing with
        page_type = self.analyze_page_type()
        
        all_products = []
        
        if page_type == "url_pagination":
            all_products = self.handle_url_pagination()
        elif page_type == "pagination":
            all_products = self.handle_traditional_pagination()
        elif page_type == "ajax_loading":
            # Fall back to scroll-based approach for AJAX
            logger.info("Detected AJAX - trying scroll approach...")
            self.enhanced_infinite_scroll()
            all_products = self.extract_products_from_current_page()
        else:
            # Try multiple approaches
            logger.info("Unknown page type - trying multiple approaches...")
            
            # Try pagination first
            try:
                all_products = self.handle_traditional_pagination()
                if len(all_products) < 10:  # If we didn't get many results
                    logger.info("Pagination yielded few results, trying URL approach...")
                    url_products = self.handle_url_pagination()
                    if len(url_products) > len(all_products):
                        all_products = url_products
            except Exception as e:
                logger.error(f"Pagination failed: {e}")
                # Fall back to current page extraction
                all_products = self.extract_products_from_current_page()
        
        return all_products
    
    def enhanced_infinite_scroll(self):
        """Simplified infinite scroll for AJAX loading"""
        logger.info("=== SIMPLIFIED INFINITE SCROLL ===")
        
        last_count = 0
        stable_count = 0
        
        for attempt in range(20):
            # Scroll down
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            
            # Count products
            current_count = self.count_products_on_current_page()
            
            if current_count > last_count:
                logger.info(f"Scroll {attempt + 1}: Found {current_count} products (+{current_count - last_count})")
                stable_count = 0
                last_count = current_count
            else:
                stable_count += 1
                logger.info(f"Scroll {attempt + 1}: No new products ({stable_count}/5)")
                
                if stable_count >= 5:
                    logger.info("No more content loading")
                    break
            
            # Try clicking load more buttons
            if attempt % 3 == 0:
                self.trigger_load_more_buttons()
        
        return last_count
    
    def trigger_load_more_buttons(self):
        """Find and click load more buttons"""
        selectors = [
            "button:contains('Load More')",
            "button:contains('Show More')",
            ".load-more",
            ".show-more",
            "button[class*='load']"
        ]
        
        for selector in selectors:
            try:
                if 'contains(' in selector:
                    text = selector.split("'")[1]
                    elements = self.driver.find_elements(By.XPATH, f"//button[contains(text(), '{text}')]")
                else:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                
                for element in elements:
                    if element.is_displayed() and element.is_enabled():
                        logger.info(f"Clicking load more button: {element.text}")
                        self.driver.execute_script("arguments[0].click();", element)
                        time.sleep(3)
                        return True
            except:
                continue
        
        return False
    
    def save_results(self, products, filename='textile_products_improved.csv'):
        """Save results to CSV and JSON"""
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
                # Ensure all required fields exist
                row = {field: product.get(field, '') for field in fieldnames}
                writer.writerow(row)
        
        # Save JSON
        json_filename = filename.replace('.csv', '.json')
        with open(json_filename, 'w', encoding='utf-8') as jsonfile:
            json.dump(products, jsonfile, indent=2, ensure_ascii=False)
        
        logger.info(f"✓ Results saved to: {filename} and {json_filename}")
        return filename
    
    def run(self, url):
        """Main execution method"""
        logger.info("=== IMPROVED TEXTILE WORLD SCRAPER ===")
        logger.info(f"Target: {self.target_count} products")
        logger.info(f"URL: {url}")
        
        if not self.setup_chrome_driver():
            return False
        
        try:
            # Load initial page
            logger.info("Loading initial page...")
            self.driver.get(url)
            time.sleep(5)
            
            # Use smart scraping approach
            products = self.smart_scraping_approach()
            
            if products:
                # Save results
                filename = self.save_results(products)
                
                # Show preview
                logger.info(f"\n=== RESULTS PREVIEW ===")
                logger.info(f"Total products found: {len(products)}")
                
                for i, product in enumerate(products[:10], 1):
                    name = product.get('name', 'N/A')[:50]
                    price = product.get('price', 'N/A')
                    logger.info(f"{i:2d}. {name:<50} - {price}")
                
                if len(products) > 10:
                    logger.info(f"... and {len(products) - 10} more products")
                
                logger.info(f"\n✓ Success Rate: {(len(products)/self.target_count)*100:.1f}%")
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
    
    # Create scraper instance
    scraper = ImprovedTextileWorldScraper(
        headless=False,  # Keep False for debugging
        target_count=3000
    )
    
    # Run scraper
    success = scraper.run(url)
    
    if success:
        print("\n🎉 SCRAPING COMPLETED SUCCESSFULLY! 🎉")
    else:
        print("\n❌ SCRAPING FAILED - Check logs for details")
    
    input("\nPress Enter to exit...")

if __name__ == "__main__":
    main()
    