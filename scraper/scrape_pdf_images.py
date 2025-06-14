import fitz
import os
import re
import csv

def extract_images_with_pattern(pdf_path, output_folder, pattern=r'\d+\.\d+\s*\|', min_size=200):
    """
    Extract images from PDF that have text matching the specified pattern underneath.
    
    Args:
        pdf_path: Path to the PDF file
        output_folder: Directory to save extracted images
        pattern: Regex pattern to match (default matches '16.1426 |' style patterns)
        min_size: Minimum width/height in pixels (default 200)
    """
    doc = fitz.open(pdf_path)
    os.makedirs(output_folder, exist_ok=True)
    
    total_extracted = 0
    extracted_data = []  # Store data for CSV
    
    for page_num, page in enumerate(doc):
        images = page.get_images(full=True)
        if not images:
            continue
        
        # Get all text blocks with their positions
        text_blocks = page.get_text("blocks")
        
        page_extracted = 0
        
        for img_index, img in enumerate(images):
            xref = img[0]
            
            # Get image rectangle on the page
            img_rects = page.get_image_rects(xref)
            if not img_rects:
                continue
                
            img_rect = img_rects[0]  # Use first occurrence of image
            
            # Look for text blocks below the image
            matching_text_found = False
            
            for block in text_blocks:
                # block format: (x0, y0, x1, y1, "text", block_no, block_type)
                if len(block) < 5:
                    continue
                    
                text_rect = fitz.Rect(block[0], block[1], block[2], block[3])
                text_content = block[4].strip()
                
                # Check if text block is below the image (y-coordinate is greater)
                # and horizontally overlaps or is close to the image
                if (text_rect.y0 > img_rect.y1 and  # Text is below image
                    abs(text_rect.x0 - img_rect.x0) < 100 and  # Horizontally aligned (within 100 units)
                    text_rect.y0 - img_rect.y1 < 50):  # Text is close to image (within 50 units)
                    
                    # Check if text matches the pattern
                    if re.search(pattern, text_content):
                        matching_text_found = True
                        print(f"✓ Found matching text: '{text_content.strip()}'")
                        break
            
            # Extract and save the image if pattern was found
            if matching_text_found:
                try:
                    pix = fitz.Pixmap(doc, xref)
                    
                    # Handle CMYK or unsupported colorspaces
                    if pix.colorspace.n not in [1, 3]:  # not grayscale or RGB
                        try:
                            pix = fitz.Pixmap(fitz.csRGB, pix)
                        except Exception as e:
                            print(f"⚠️ Skipping image {img_index + 1} on page {page_num + 1}: {e}")
                            continue
                    
                    # Check minimum size requirement
                    if pix.width < min_size or pix.height < min_size:
                        print(f"⚠️ Skipping small image {img_index + 1} on page {page_num + 1}: {pix.width}x{pix.height}px (min: {min_size}x{min_size}px)")
                        continue
                    
                    # Save with unique filename
                    output_path = os.path.join(output_folder, f"page_{page_num+1}_img_{img_index+1}.png")
                    pix.save(output_path)
                    print(f"✓ Saved image from page {page_num + 1}, image {img_index + 1} ({pix.width}x{pix.height}px)")
                    
                    # Parse the matching text to extract ID and name
                    matching_text = ""
                    for block in text_blocks:
                        if len(block) < 5:
                            continue
                        text_rect = fitz.Rect(block[0], block[1], block[2], block[3])
                        text_content = block[4].strip()
                        
                        if (text_rect.y0 > img_rect.y1 and 
                            abs(text_rect.x0 - img_rect.x0) < 100 and 
                            text_rect.y0 - img_rect.y1 < 50 and
                            re.search(pattern, text_content)):
                            matching_text = text_content
                            break
                    
                    # Split text into ID and Name
                    id_part = ""
                    name_part = ""
                    if '|' in matching_text:
                        parts = matching_text.split('|', 1)  # Split only on first |
                        id_part = parts[0].strip()
                        # remove leading
                        id_part = re.sub(r'^[\.\s]+', '', id_part).strip()
                        name_part = parts[1].strip() if len(parts) > 1 else ""
                    
                    # Add to CSV data
                    extracted_data.append({
                        'page': page_num + 1,
                        'image_index': img_index + 1,
                        'filename': f"page_{page_num+1}_img_{img_index+1}.png",
                        'width': pix.width,
                        'height': pix.height,
                        'full_text': matching_text,
                        'id': id_part,
                        'name': name_part
                    })
                    
                    page_extracted += 1
                    total_extracted += 1
                    
                except Exception as e:
                    print(f"⚠️ Error processing image {img_index + 1} on page {page_num + 1}: {e}")
        
        if page_extracted > 0:
            print(f"📄 Page {page_num + 1}: Extracted {page_extracted} images")
    
    print(f"\n🎯 Total images extracted: {total_extracted}")
    
    # Save CSV file
    if extracted_data:
        csv_path = os.path.join(output_folder, "extracted_images.csv")
        with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['page', 'image_index', 'filename', 'width', 'height', 'full_text', 'id', 'name']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(extracted_data)
        print(f"💾 CSV data saved to: {csv_path}")
    
    doc.close()

def extract_images_with_custom_pattern(pdf_path, output_folder, custom_pattern, min_size=200):
    """
    Wrapper function to use a custom regex pattern.
    
    Example patterns:
    - r'\d+\.\d+\s*\|' (matches '16.1426 |')
    - r'[A-Z0-9]+\.\d+\s*\|' (matches alphanumeric codes like 'ABC123.456 |')
    - r'[\w\d]+\.[\w\d]+\s*\|' (matches any word/digit combinations)
    """
    return extract_images_with_pattern(pdf_path, output_folder, custom_pattern, min_size)

# Example usage:
if __name__ == "__main__":
    # Default pattern matches '16.1426 |' style
    extract_images_with_pattern("catalogue_2024_subset.pdf", "extracted_images")
    
    # Or use custom pattern for different formats
    # extract_images_with_custom_pattern("your_pdf.pdf", "extracted_images", r'[A-Z0-9]+\.\d+\s*\|')