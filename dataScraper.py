from flask import Flask, jsonify
from flask_cors import CORS
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime
import os

app = Flask(__name__)
CORS(app)

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

@app.route('/scrape', methods=['GET'])
def scrape():
    try:
        print("Starting scrape process...")
        products = scrape_product_info()
        
        if products and len(products) > 0:
            print(f"Found {len(products)} products")
            return jsonify({
                "status": "success",
                "products": products
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

if __name__ == '__main__':
    print("Starting application...")
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
