import os
import time
import sqlite3
from urllib.parse import urlparse

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options


DB_PATH = "tabelog.db"

# 提取 code 和 level
def extract_code_and_level(href: str):
    path = urlparse(href).path  # e.g., /rstLst/ramen/
    parts = path.strip("/").split("/")
    if len(parts) >= 2 and parts[0] == "rstLst":
        code = parts[1]
        if code.startswith("MC") or code.startswith("RC"):
            level = 2
        else:
            level = 1
        return code, level
    return "", 0

# 提取ジャンル信息
def get_genres(driver):
    url = "https://tabelog.com/cat_lst/"
    driver.get(url)
    time.sleep(2)

    genre_list = []

    # 每个大类 block
    frames = driver.find_elements(By.CSS_SELECTOR, "div.rst-janrelst__frame")
    for frame in frames:
        try:
            # 大类（Level 1）
            h3 = frame.find_element(By.CSS_SELECTOR, "h3.rst-janrelst__title > a")
            name1 = h3.text.strip()
            href1 = h3.get_attribute("href").strip()
            code1, _ = extract_code_and_level(href1)
            genre_list.append((name1, code1, 1, None))  # parent_code = None

            # 中类（Level 2）
            items = frame.find_elements(By.CSS_SELECTOR, "div.rst-janrelst__item")
            for item in items:
                try:
                    h4 = item.find_element(By.CSS_SELECTOR, "h4.rst-janrelst__item2 > a")
                    name2 = h4.text.strip()
                    href2 = h4.get_attribute("href").strip()
                    code2, _ = extract_code_and_level(href2)
                    genre_list.append((name2, code2, 2, code1))  # parent = 大类

                    # 小类（Level 3）
                    try:
                        li_links = item.find_elements(By.CSS_SELECTOR, "ul.rst-janrelst__item3 li > a")
                        for a in li_links:
                            name3 = a.text.strip()
                            href3 = a.get_attribute("href").strip()
                            code3, _ = extract_code_and_level(href3)
                            genre_list.append((name3, code3, 3, code2))  # parent = 中类
                    except:
                        pass
                except:
                    continue
        except:
            continue

    return genre_list


# 保存到数据库
def save_genres_to_db(genres):
    first_create = not os.path.exists(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS genre (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            code TEXT UNIQUE,
            level INTEGER,
            parent_code TEXT,
            create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            update_user TEXT DEFAULT 'system',
            is_deleted INTEGER DEFAULT 0
        );
    """)

    now = time.strftime('%Y-%m-%d %H:%M:%S')

    for name, code, level, parent_code in genres:
        cursor.execute("SELECT id, is_deleted FROM genre WHERE code = ?", (code,))
        result = cursor.fetchone()

        if result:
            genre_id, is_deleted = result
            cursor.execute("""
                UPDATE genre
                SET name = ?, level = ?, parent_code = ?, update_time = ?, update_user = ?, is_deleted = 0
                WHERE id = ?
            """, (name, level, parent_code, now, "system", genre_id))
        else:
            cursor.execute("""
                INSERT INTO genre (name, code, level, parent_code, create_time, update_time, update_user, is_deleted)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0)
            """, (name, code, level, parent_code, now, now, "system"))

    conn.commit()
    conn.close()
    print(f"✅ 共保存 {len(genres)} 个ジャンル（首次创建数据库: {first_create}）")

# 主程序
def run():
    options = webdriver.ChromeOptions()
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("start-maximized")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36")

    driver = webdriver.Chrome(options=options)

    try:
        genres = get_genres(driver)
        save_genres_to_db(genres)
    finally:
        driver.quit()

if __name__ == "__main__":
    run()
