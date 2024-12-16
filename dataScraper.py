from flask import Flask, jsonify, request
from flask_cors import CORS
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import sqlite3
from datetime import datetime
import json

app = Flask(__name__)
CORS(app)

# SQLite database setup
DATABASE = 'pc_parts.db'

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS products (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        product_name TEXT,
                        price TEXT,
                        category TEXT,
                        scraped_at TEXT
                    )''')
    conn.commit()
    conn.close()

# Remove the CATEGORY_URLS dictionary and replace with category URLs
CATEGORY_URLS = {
    "CPU": "https://www.racuntech.com/c/cpu",
    "Motherboard": "https://www.racuntech.com/c/motherboard",
    "RAM": "https://www.racuntech.com/c/ram",
    "GPU": "https://www.racuntech.com/c/gpu",
    "PSU": "https://www.racuntech.com/c/psu",
    "Case": "https://www.racuntech.com/c/casing",
    "CPU Cooler": ["https://www.racuntech.com/c/aio", "https://www.racuntech.com/c/cpu-cooler"],
    "ROM": "https://www.racuntech.com/c/storage-26299",
    "Case Fan": "https://www.racuntech.com/c/casing-fan"
}

def scrape_product_info():
    print("Starting web scraping...")
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    product_data = []
    
    for category, urls in CATEGORY_URLS.items():
        if isinstance(urls, list):
            # Handle multiple URLs for same category (like CPU Cooler)
            for url in urls:
                scrape_category(driver, url, category, product_data)
        else:
            scrape_category(driver, urls, category, product_data)

    driver.quit()
    print(f"Scraping completed. Found {len(product_data)} products")
    return product_data

def scrape_category(driver, base_url, category, product_data):
    page_num = 1
    
    while True:
        url = f'{base_url}?ppg=96&page={page_num}'
        print(f"Scraping {category} - page {page_num}...")
        driver.get(url)

        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '.ict-catalog-item-wrap'))
            )
        except Exception as e:
            print(f"Error waiting for page load: {e}")
            break

        product_items = driver.find_elements(By.CSS_SELECTOR, '.ict-catalog-item-wrap')
        if not product_items:
            break

        for item in product_items:
            try:
                product_name_element = item.find_element(By.CSS_SELECTOR, '.open-ict-product.product_name')
                product_name = product_name_element.text.strip() if product_name_element else "Unknown Product"
                price_element = item.find_element(By.CSS_SELECTOR, '.oe_currency_value')
                price = price_element.text.strip() if price_element else "Price not available"
                
                product_data.append({
                    'product_name': product_name,
                    'price': price,
                    'category': category,
                    'scraped_at': datetime.now().isoformat()
                })
            except Exception as e:
                print(f"Error extracting data for item: {e}")

        page_num += 1

@app.route('/')
def index():
    return "Welcome to the Product Info Scraper API!"

@app.route('/products', methods=['GET'])
def get_products():
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT product_name, price, category FROM products")
        products = cursor.fetchall()
        conn.close()
        return jsonify([dict(row) for row in products])
    except Exception as e:
        print(f"Error in get_products: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/scrape-status', methods=['GET'])
def get_scrape_status():
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM products")
        count = cursor.fetchone()[0]
        conn.close()
        return jsonify({
            'has_data': count > 0,
            'total_products': count
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/scrape', methods=['GET'])
def scrape():
    try:
        print("Starting scrape process...")
        products = scrape_product_info()
        
        if products and len(products) > 0:
            print(f"Found {len(products)} products")
            # Delete existing products and insert new ones into SQLite
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM products")
            cursor.executemany(
                "INSERT INTO products (product_name, price, category, scraped_at) VALUES (?, ?, ?, ?)",
                [(product['product_name'], product['price'], product['category'], product['scraped_at']) for product in products]
            )
            conn.commit()
            conn.close()
            
            return jsonify({
                "status": "success",
                "message": f"Successfully scraped {len(products)} products",
                "count": len(products)
            })
        else:
            print("No products found")
            return jsonify({
                "status": "error",
                "message": "No products found during scraping"
            }), 404
    except Exception as e:
        print(f"Error during scrape: {str(e)}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route('/check-db', methods=['GET'])
def check_db():
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM products")
        count = cursor.fetchone()[0]
        cursor.execute("SELECT product_name, price, category FROM products LIMIT 5")
        sample = cursor.fetchall()
        conn.close()
        return jsonify({
            'total_documents': count,
            'sample_data': [dict(row) for row in sample]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/products/search', methods=['GET'])
def search_products():
    query = request.args.get('q', '')
    category = request.args.get('category', '')
    
    try:
        filter_query = []
        params = []
        if category:
            filter_query.append("category = ?")
            params.append(category)
        if query:
            filter_query.append("product_name LIKE ?")
            params.append(f"%{query}%")
        
        where_clause = " AND ".join(filter_query) if filter_query else "1=1"
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(f"SELECT product_name, price, category FROM products WHERE {where_clause}", params)
        products = cursor.fetchall()
        conn.close()
        return jsonify([dict(row) for row in products])
    except Exception as e:
        print(f"Error in search_products: {e}")
        return jsonify({"error": str(e)}), 500

# Add CORS headers to allow the request
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

if __name__ == '__main__':
    print("Starting application...")
    
    # Initialize the SQLite database
    init_db()
    
    # Check if database already has data
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM products")
        count = cursor.fetchone()[0]
        conn.close()
        
        if count == 0:
            print("No data found in database. Running initial scrape...")
            products = scrape_product_info()
            if products:
                conn = get_db()
                cursor = conn.cursor()
                cursor.executemany(
                    "INSERT INTO products (product_name, price, category, scraped_at) VALUES (?, ?, ?, ?)",
                    [(product['product_name'], product['price'], product['category'], product['scraped_at']) for product in products]
                )
                conn.commit()
                conn.close()
                print(f"Initial scrape completed. Saved {len(products)} products to database")
        else:
            print(f"Database already contains {count} products. Skipping initial scrape.")
    except Exception as e:
        print(f"Error during database check: {e}")
    
    app.run(debug=True, host="0.0.0.0", port=5000)
