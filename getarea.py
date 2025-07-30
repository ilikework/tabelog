import os
import time
import sqlite3
from urllib.parse import urlparse
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options


DB_PATH = "tabelog.db"


def extract_area_code(href: str):
    """
    提取 href 中的最底层地区 code 及其上一级 code。

    示例:
    /matome/hokkaido/A0105/A010501/list/ → ("A010501", "A0105")
    /matome/hokkaido/A0105/list/ → ("A0105", "hokkaido")
    /matome/hokkaido/list/ → ("hokkaido", None)
    """
    parts = href.strip("/").split("/")

    if parts and parts[0] == "matome":
        parts = parts[1:]

    codes = [p for p in parts if p.lower() != "list"]

    if not codes:
        return None, None
    elif len(codes) == 1:
        return codes[0], None
    else:
        return codes[-1], codes[-2]
    

def get_areas(driver):
    url = "https://tabelog.com/matome/area_lst/"
    driver.get(url)
    driver.implicitly_wait(3)

    area_list = []
    seen_hrefs = set()  # ✅ 用于去重 href

    sections = driver.find_elements(By.CSS_SELECTOR, "section.area-cat-navi")
    for sec in sections:
        try:
            level1_name = sec.find_element(By.CSS_SELECTOR, "h2.area-cat-navi__title").text.strip()
            if "" not in seen_hrefs:
                area_list.append((level1_name, level1_name, 1, None, ""))
                seen_hrefs.add("")

            level2_items = sec.find_elements(By.CSS_SELECTOR, "ul.area-cat-navi__list > li")
            for level2_item in level2_items:
                a2 = level2_item.find_element(By.CSS_SELECTOR, "a.area-cat-navi__list-target")
                name2 = a2.text.strip()
                href2 = a2.get_attribute("href").strip()
                if href2 in seen_hrefs:
                    continue
                code2, parent_code = extract_area_code(href2)
                area_list.append((name2, code2, 2, parent_code, href2))
                seen_hrefs.add(href2)

                # 子地区（Level 3）
                try:
                    subareas = level2_item.find_elements(By.CSS_SELECTOR, "ul.area-cat-list li")
                    for sub_item in subareas:
                        a3 = sub_item.find_element(By.CSS_SELECTOR, "a")
                        name3 = a3.text.strip()
                        href3 = a3.get_attribute("href").strip()
                        if href3 in seen_hrefs:
                            continue
                        code3, parent_code = extract_area_code(href3)
                        area_list.append((name3, code3, 3, parent_code, href3))
                        seen_hrefs.add(href3)

                        # 子子地区（Level 4）
                        try:
                            sub_sub_items = sub_item.find_elements(By.CSS_SELECTOR, "ul.sub-area-navi__list li a")
                            for a4 in sub_sub_items:
                                name4 = a4.text.strip()
                                href4 = a4.get_attribute("href").strip()
                                if href4 in seen_hrefs:
                                    continue
                                code4, parent_code = extract_area_code(href4)
                                area_list.append((name4, code4, 4, parent_code, href4))
                                seen_hrefs.add(href4)
                        except:
                            pass
                except:
                    pass
        except:
            continue

    return area_list



def save_areas_to_db(areas):
    now = time.strftime('%Y-%m-%d %H:%M:%S')
    first_create = not os.path.exists(DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # 表结构
    cur.execute("""
    CREATE TABLE IF NOT EXISTS area (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        code TEXT UNIQUE,
        level INTEGER,
        parent_code TEXT,
        href TEXT,
        priority INTEGER DEFAULT 100, 
        create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        update_user TEXT DEFAULT 'system',
        is_deleted INTEGER DEFAULT 0
    );""")

    for name, code, level, parent_code, href in areas:
        cur.execute("SELECT id FROM area WHERE code = ?", (code,))
        row = cur.fetchone()
        if row:
            cur.execute("""
                UPDATE area
                SET name = ?, level = ?, parent_code = ?, href = ?, update_time = ?, is_deleted = 0
                WHERE code = ?
            """, (name, level, parent_code, href, now, code))
        else:
            cur.execute("""
                INSERT INTO area (name, code, level, parent_code, href, create_time, update_time, update_user, is_deleted)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'system', 0)
            """, (name, code, level, parent_code, href, now, now))

    conn.commit()
    conn.close()
    print(f"✅ 共保存 {len(areas)} 个地区（首次创建数据库: {first_create}）")


def main():
    options = webdriver.ChromeOptions()
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("start-maximized")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36")

    driver = webdriver.Chrome(options=options)

    try:
        print("🌐 正在提取地区信息 ...")
        areas = get_areas(driver)
        for item in areas:
            print(f"名称: {item[0]} | Code: {item[1]} | Level: {item[2]} | Parent: {item[3]} | Href: {item[4]}")
        save_areas_to_db(areas)
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
