import fitz  # PyMuPDF
import re
import csv

def extract_product_data(pdf_path):
    doc = fitz.open(pdf_path)
    product_data = []
    
    for page_num, page in enumerate(doc, start=1):
        text = page.get_text()
        
        # Extract all product IDs and names
        id_name_matches = list(re.finditer(
            r'(?P<id>[A-Za-z0-9]+(?:\.[A-Za-z0-9]+)+)\s*\|\s*(?P<name>[^\n€]+)',
            text
        ))
        
        # Extract all prices
        price_matches = list(re.finditer(
            r'€\s*(?P<price>\d+[\.,]\d{1,2})',
            text
        ))
        
        # Match products to prices by their order on the page
        for i, id_match in enumerate(id_name_matches):
            product_id = id_match.group('id')
            product_name = id_match.group('name').strip()
            
            # Get corresponding price (same index)
            price = "Not found"
            if i < len(price_matches):
                price = price_matches[i].group('price').replace(',', '.')
            
            product_data.append({
                'Page': page_num,
                'ID': product_id,
                'Name': product_name,
                'Price': f"€{price}" if price != "Not found" else price
            })
    
    return product_data

def clean_product_name(name):
    """Clean up product names by removing extra spaces and newlines"""
    name = re.sub(r'\s+', ' ', name)  # Replace multiple spaces
    name = re.sub(r'\s*\n\s*', ' ', name)  # Replace newlines with space
    return name.strip()

# Usage
pdf_path = "catalogue_2024_subset.pdf"
products = extract_product_data(pdf_path)

# Clean up names and filter valid entries
cleaned_products = []
for product in products:
    # Skip entries where name is just whitespace or too short
    if len(product['Name'].strip()) > 3:
        product['Name'] = clean_product_name(product['Name'])
        cleaned_products.append(product)

# Print results
print("EXTRACTED PRODUCTS:\n")
for product in cleaned_products[:50]:  # Print first 50 results
    print(f"Page {product['Page']:>2} | {product['ID']:>10} | {product['Name'][:50]:<50} | {product['Price']}")

# Save to CSV
with open('product_prices_accurate.csv', 'w', newline='', encoding='utf-8') as csvfile:
    fieldnames = ['Page', 'ID', 'Name', 'Price']
    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(cleaned_products)

print(f"\nTotal valid products found: {len(cleaned_products)}")
print("Results saved to product_prices_accurate.csv")