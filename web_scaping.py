import os
import re
import csv
import time
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

def setup_driver():
    """Tarayıcı ayarlarını yapar ve başlatır."""
    chrome_options = Options()
    # chrome_options.add_argument("--headless")  # Arka planda çalışması için bu satırı açabilirsin
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    return driver

def scrape_migros_category(category_url, folder_name, item_limit=50):
    """Belirtilen kategoriden ürün görsellerini indirir."""
    driver = setup_driver()
    try:
        driver.get(category_url)
        WebDriverWait(driver, 15).until(lambda d: d.execute_script('return document.readyState') == 'complete')
        time.sleep(2)

        if not os.path.exists(folder_name):
            os.makedirs(folder_name)

        downloaded_count = 0
        seen_urls = set()
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0 Safari/537.36',
            'Accept': 'image/webp,image/apng,image/*,*/*',
            'Accept-Language': 'tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7'
        }
        session = requests.Session()
        session.headers.update(headers)
        metadata = []

        try:
            for c in driver.get_cookies():
                session.cookies.set(c['name'], c.get('value', ''), domain=c.get('domain'))
        except Exception:
            pass
        session.headers['Referer'] = category_url

        max_scrolls = 20
        no_progress_rounds = 0

        while downloaded_count < item_limit and max_scrolls > 0:
            products = driver.find_elements(By.CSS_SELECTOR, "sm-product-card, fe-product-card, mat-card, .product-card, div.product-item")

            if not products:
                driver.execute_script("window.scrollBy(0, 1200);")
                time.sleep(2)
                max_scrolls -= 1
                no_progress_rounds += 1
                if no_progress_rounds >= 3:
                    print("Ürün kartı bulunamadı; seçiciler sayfayla eşleşmiyor olabilir.")
                    break
                continue

            progress_this_round = 0

            for product in products:
                if downloaded_count >= item_limit:
                    break

                try:
                    img_element = None
                    try:
                        img_element = product.find_element(By.TAG_NAME, "img")
                    except Exception:
                        pass

                    product_name = None
                    for sel in (".product-name", ".productTitle", ".title", "h3", ".product-title"):
                        try:
                            el = product.find_element(By.CSS_SELECTOR, sel)
                            text = el.text.strip()
                            if text:
                                product_name = text
                                break
                        except Exception:
                            continue

                    if not product_name and img_element:
                        alt = img_element.get_attribute('alt')
                        if alt and alt.strip():
                            product_name = alt.strip()

                    if not product_name:
                        product_name = product.get_attribute("aria-label") or f"product_{downloaded_count + 1}"

                    safe_name = re.sub(r'[\\/*?:"<>|]', '_', product_name).strip()

                    img_url = None
                    if img_element:
                        img_url = (
                            img_element.get_attribute("src")
                            or img_element.get_attribute("data-src")
                            or img_element.get_attribute("data-lazy")
                            or img_element.get_attribute("srcset")
                        )

                    if not img_url:
                        continue

                    if "," in img_url:
                        parts = [p.strip() for p in img_url.split(',')]
                        img_url = parts[0].split()[0]

                    if not img_url.startswith('http'):
                        continue

                    high_res_url = img_url.replace("300x300", "1200x1200") if "300x300" in img_url else img_url
                    if high_res_url in seen_urls:
                        continue

                    resp = session.get(high_res_url, timeout=20)
                    content_len = int(resp.headers.get('Content-Length') or 0)
                    if resp.status_code != 200 or (content_len and content_len < 500) or (not content_len and len(resp.content) < 500):
                        resp = session.get(img_url, timeout=20)
                        content_len = int(resp.headers.get('Content-Length') or 0)

                    if resp.status_code == 200 and (content_len > 500 or len(resp.content) > 500):
                        file_path = os.path.join(folder_name, f"{safe_name}.jpg")
                        with open(file_path, 'wb') as f:
                            f.write(resp.content)

                        price_text = None
                        for psel in (".price", ".product-price", ".price-amount", ".productCard__price", ".price-box", ".amount", ".priceValue", ".product-price__value", ".prdct-price", ".price__value"):
                            try:
                                p_el = product.find_element(By.CSS_SELECTOR, psel)
                                txt = p_el.text.strip()
                                if txt:
                                    price_text = txt
                                    break
                            except Exception:
                                continue

                        price_clean = None
                        if price_text:
                            m = re.search(r"[0-9]+[\.,]?[0-9]*", price_text.replace('\u2009', ''))
                            if m:
                                price_clean = m.group(0).replace(',', '.')

                        product_link = None
                        try:
                            a = product.find_element(By.CSS_SELECTOR, "a")
                            product_link = a.get_attribute('href')
                        except Exception:
                            pass

                        metadata.append({
                            'name': product_name,
                            'safe_name': safe_name,
                            'price': price_clean,
                            'link': product_link,
                            'image': high_res_url,
                            'file': file_path
                        })

                        seen_urls.add(high_res_url)
                        downloaded_count += 1
                        progress_this_round += 1
                        print(f"{downloaded_count}: {safe_name} indirildi. ({file_path})")
                    else:
                        size = len(resp.content) if resp is not None else 0
                        print(f"Atlandı (indirilemedi): {safe_name} - {high_res_url} (status={resp.status_code if resp is not None else 'N/A'} size={size})")

                except requests.RequestException as rexc:
                    print(f"HTTP hatası: {rexc}")
                except Exception as e:
                    print(f"İşlenemeyen ürün: {e}")

            if progress_this_round == 0:
                no_progress_rounds += 1
            else:
                no_progress_rounds = 0

            if no_progress_rounds >= 3:
                print("İlerleme yok; muhtemelen ürün seçicileri güncel değil.")
                break

            driver.execute_script("window.scrollBy(0, 1200);")
            time.sleep(2)
            max_scrolls -= 1

        if metadata:
            csv_path = os.path.join(folder_name, 'metadata.csv')
            try:
                with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
                    fieldnames = ['name', 'safe_name', 'price', 'link', 'image', 'file']
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    writer.writeheader()
                    for row in metadata:
                        writer.writerow(row)
                print(f"Metadata kaydedildi: {csv_path}")
            except Exception as e:
                print(f"Metadata yazma hatası: {e}")

        print("İşlem tamamlandı.")
    finally:
        driver.quit()

# --- KULLANIM ---
target_url = "https://www.migros.com.tr/atistirmalik-c-113fb?srsltid=AfmBOorb3UjP-LY0Z6T9V0HQMXq8vozDdm-3m_VVSr1zlhXOb76C2V7G" # Örnek: Atıştırmalık kategorisi
scrape_migros_category(target_url, "migros_dataset", item_limit=30)