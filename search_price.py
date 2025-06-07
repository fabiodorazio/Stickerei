import csv

CSV_FILE = "products_simple.csv"

def load_products(csv_file=CSV_FILE):
    products = []
    with open(csv_file, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            products.append(row)
    return products

def find_price(products, query):
    query_lower = query.lower()
    matches = [p for p in products if query_lower in p['name'].lower()]
    return matches

def main():
    products = load_products()
    query = input("Enter product name: ").strip()
    if not query:
        print("No product name entered")
        return
    matches = find_price(products, query)
    if matches:
        for product in matches:
            name = product.get('name', 'Unknown')
            price = product.get('price', 'N/A')
            prod_id = product.get('id', '')
            if prod_id:
                print(f"{name} (ID: {prod_id}) -> Price: {price}")
            else:
                print(f"{name} -> Price: {price}")
    else:
        print("Product not found")

if __name__ == "__main__":
    main()
