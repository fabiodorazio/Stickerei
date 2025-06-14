import fitz
import os
import re
import csv

def extract_product_text_data(pdf_path, output_folder, pattern=r'[\d\w]+\.[\d\w]+[A-Z]?\s*\|'):
    """
    Extract product text data from PDF that matches the specified pattern.
    
    Args:
        pdf_path: Path to the PDF file
        output_folder: Directory to save CSV file
        pattern: Regex pattern to match product IDs (default matches '01.003T |' style patterns)
    """
    doc = fitz.open(pdf_path)
    os.makedirs(output_folder, exist_ok=True)
    
    extracted_products = []
    total_found = 0
    
    for page_num, page in enumerate(doc):
        # Get all text from the page
        text_content = page.get_text()
        
        # Find all matches of the pattern in the text
        matches = re.finditer(pattern, text_content, re.MULTILINE | re.DOTALL)
        
        page_products = 0
        
        for match in matches:
            try:
                # Get the position of the match
                match_start = match.start()
                match_end = match.end()
                
                # Extract a larger chunk of text around the match (next ~1000 characters)
                text_chunk = text_content[match_start:match_start + 1000]
                
                # Parse the product information
                product_data = parse_product_text(text_chunk, page_num + 1)
                
                if product_data:
                    extracted_products.append(product_data)
                    page_products += 1
                    total_found += 1
                    print(f"✓ Found product on page {page_num + 1}: {product_data['id']} | {product_data['name']}")
                
            except Exception as e:
                print(f"⚠️ Error parsing product on page {page_num + 1}: {e}")
        
        if page_products > 0:
            print(f"📄 Page {page_num + 1}: Found {page_products} products")
    
    print(f"\n🎯 Total products found: {total_found}")
    
    # Save CSV file
    if extracted_products:
        csv_path = os.path.join(output_folder, "product_data.csv")
        with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['page', 'id', 'name', 'description', 'sizes', 'price', 'full_text']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(extracted_products)
        print(f"💾 Product data saved to: {csv_path}")
    else:
        print("⚠️ No products found to save")
    
    doc.close()

def parse_product_text(text_chunk, page_num):
    """
    Parse product information from a text chunk.
    
    Expected format:
    ID | Name Description... Sizes Price
    """
    try:
        # Split by the first | to get ID and rest
        if '|' not in text_chunk:
            return None
        
        parts = text_chunk.split('|', 1)
        id_part = parts[0].strip()
        rest_text = parts[1].strip()
        
        # Extract ID (remove leading dots and spaces)
        product_id = re.sub(r'^[\.\s]+', '', id_part).strip()
        
        # Extract name - look for pattern like "B&C #E190 Schweres T-Shirt" (stops at first comma or specification)
        # Match brand and product name until first comma or number+g/m²
        name_match = re.match(r'^([^,]+?)(?:\s+\d+g/m²|,)', rest_text)
        if not name_match:
            # Fallback: get first part until comma
            name_match = re.match(r'^([^,]+)', rest_text)
        name = name_match.group(1).strip() if name_match else ""
        
        # Extract sizes pattern (XS – S – M – L – XL – XXL – 3XL – 4XL* – 5XL*)
        sizes_pattern = r'((?:XS|S|M|L|XL|XXL|\d+XL)(?:\s*[–-]\s*(?:XS|S|M|L|XL|XXL|\d+XL|\d+XL\*))*[^€]*?)(?=\d+\s*€|\d+\s+\d+\s*€)'
        sizes_match = re.search(sizes_pattern, rest_text)
        sizes = sizes_match.group(1).strip() if sizes_match else ""
        
        # Clean up sizes (remove extra text after the size list)
        if sizes:
            # Keep only the size part, remove descriptions after
            sizes = re.sub(r'\s*\*[^€]*', '*', sizes)  # Keep asterisks but remove their descriptions
            sizes = re.sub(r'\s{2,}', ' ', sizes)  # Replace multiple spaces with single space
        
        # Extract price (look for number after € symbol)
        price_pattern = r'€\s*(\d+(?:[,.-]\d+)*)'
        price_match = re.search(price_pattern, rest_text)
        price = price_match.group(1) if price_match else ""
        
        # Get description (everything between name and sizes)
        description = rest_text
        if sizes:
            description = rest_text.split(sizes)[0].strip()
        
        # Clean up description
        description = re.sub(r'\s+', ' ', description).strip()
        
        return {
            'page': page_num,
            'id': product_id,
            'name': name,
            'description': description,
            'sizes': sizes,
            'price': price,
            'full_text': text_chunk[:500]  # First 500 chars for reference
        }
        
    except Exception as e:
        print(f"⚠️ Error parsing product text: {e}")
        return None

def extract_product_text_custom_pattern(pdf_path, output_folder, custom_pattern):
    """
    Wrapper function to use a custom regex pattern.
    
    Example patterns:
    - r'[\d\w]+\.[\d\w]+[A-Z]?\s*\|' (matches '01.003T |')
    - r'\d+\.\d+\s*\|' (matches '16.1426 |')
    - r'[A-Z0-9]+\.\d+\s*\|' (matches alphanumeric codes)
    """
    return extract_product_text_data(pdf_path, output_folder, custom_pattern)



# Example usage:
if __name__ == "__main__":
    # Extract product data from PDF
    extract_product_text_data("catalogue_2024_subset.pdf", "extracted_images")
    
    # Or use custom pattern
    # extract_product_text_custom_pattern("your_pdf.pdf", "extracted_data", r'your_custom_pattern')