#rst-data-head > table:nth-child(2) > tbody > tr:nth-child(3) > td > p > strong

import time
import random
from selenium import webdriver
from selenium.webdriver.common.by import By
import os
import logging
import logging.handlers
import platform
from db_handler import TabelogDB
import traceback

logger = None

def init_logger(app_name="tabelog", log_dir="./logs"):
    global logger
    if logger is not None:
        return logger

    logger = logging.getLogger(app_name)
    logger.setLevel(logging.INFO)

    formatter = logging.Formatter('%(asctime)s %(message)s')

    system = platform.system()
    if system in ("Linux", "Darwin"):
        syslog_path = '/dev/log' if system == "Linux" else '/var/run/syslog'
        handler = logging.handlers.SysLogHandler(address=syslog_path)
    else:
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

        log_file = os.path.join(log_dir, f"{app_name}.log")
        handler = logging.handlers.TimedRotatingFileHandler(
            log_file,
            when="midnight",       # 每天午夜轮换
            interval=1,            # 每1天
            backupCount=7,         # 保留7天的日志
            encoding='utf-8',
            utc=False              # 使用本地时间
        )

    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger

# ✅ 主 log 函数，替代 print()
def log(message):
    print(message)  # 输出到终端
    init_logger().info(message)  # 保存到日志

def parse_japanese_address(driver, css_selector: str = "p.rstinfo-table__address"):
    try:
        addr_elem = driver.find_element(By.CSS_SELECTOR, css_selector)
        a_tags = addr_elem.find_elements(By.TAG_NAME, "a")
        full_text = addr_elem.text.strip()

        prefecture = a_tags[0].text if len(a_tags) > 0 else ""
        city       = a_tags[1].text if len(a_tags) > 1 else ""
        town       = a_tags[2].text if len(a_tags) > 2 else ""

        # 剩下的就是番地（原始地址去掉已知部分）
        detail = full_text
        for tag in [prefecture, city, town]:
            detail = detail.replace(tag, "")
        detail = detail.strip()

        return {
            "prefecture": prefecture,
            "city": city,
            "town": town,
            "detail": detail,
            "full": full_text
        }
    except Exception as e:
        log(f"❌ 地址解析失败：{e}")
        return {
            "prefecture": "",
            "city": "",
            "town": "",
            "detail": "",
            "full": ""
        }

def scroll_into_view(driver, element):
    try:
        driver.execute_script("arguments[0].scrollIntoView(true);", element)
        time.sleep(0.3)  # 适当等待渲染
    except Exception as e:
        log(f"⚠️ 滚动失败：{e}")

def extract_shop_detail_table(driver):
    data = {
        "category": "",
        "budget": "",
        "payment": "",
        "seats": "",
        "open_date": "",
    }

    try:
        tables = driver.find_elements(By.CSS_SELECTOR, "#rst-data-head table.rstinfo-table__table")

        for table in tables:
            rows = table.find_elements(By.TAG_NAME, "tr")
            for row in rows:
                try:
                    th_elem = row.find_element(By.TAG_NAME, "th")
                    scroll_into_view(driver, th_elem)
                    th = row.find_element(By.TAG_NAME, "th").text.strip()
                    td = row.find_element(By.TAG_NAME, "td")

                    value = td.text.strip()
                    try:
                        notice = td.find_element(By.CSS_SELECTOR, "p.rstinfo-table__notice").text.strip()
                        value = f"{value}（{notice}）"
                    except:
                        pass

                    if "ジャンル" in th:
                        data["category"] = value
                    elif th == "予算（口コミ集計）":
                        ems = td.find_elements(By.TAG_NAME, "em")
                        values = [em.text.strip() for em in ems if em.text.strip()]
                        data["budget"] = " ".join(values)
                    elif "支払い方法" in th:
                        data["payment"] = value
                    elif "席数" in th:
                        data["seats"] = value
                    elif "オープン日" in th:
                        data["open_date"] = value

                except:
                    continue
    except Exception as e:
        log(f"❌ 店铺详细表格解析失败:{e}")

    return data

def get_detail_info(driver, url):
    """打开新标签页访问店铺详情页，提取地址和电话，返回后关闭标签页"""
    main_window = driver.current_window_handle

    try:
        # 打开新标签页
        driver.execute_script("window.open(arguments[0]);", url)
        time.sleep(2)

        # 切换到新标签页
        driver.switch_to.window(driver.window_handles[-1])
        time.sleep(3)  # 等页面加载

        try:
            # 地址
            addr = parse_japanese_address(driver)
            
            # 电话
            tel = ''
            elems = driver.find_elements(By.CSS_SELECTOR, "strong.rstinfo-table__tel-num")
            if elems:
                tel = elems[0].text.strip()

            #tel = driver.find_element(By.CSS_SELECTOR, "strong.rstinfo-table__tel-num").text.strip()
            
            data = extract_shop_detail_table(driver)
 
        except:
            log("⚠️ 没有找到『店舗情報（詳細）』标签，可能页面结构不同")
            addr = {}
            tel = ""

        # 关闭新标签页，返回主窗口
        driver.close()
        driver.switch_to.window(main_window)
        time.sleep(1)

        return {**addr, "tel": tel, **data}

    except Exception as e:
        log(f"❌ {url}获取详情失败：{e}")
        driver.switch_to.window(main_window)
        return {
            "prefecture": "",
            "city": "",
            "town": "",
            "detail": "",
            "full": "",
            "tel": "",
            "category": "",
            "budget": "",
            "payment": "",
            "seats": "",
            "open_date": ""
       }

def get_count(driver,url_info):

    try:
        # 访问页面（你已访问则跳过）

        driver.get(url_info["url"])
        time.sleep(1)  # 等待页面加载

        # 假设 driver 已启动并打开页面
        element = driver.find_element(By.CSS_SELECTOR, "#container > div.rstlist-contents.clearfix > div.flexible-rstlst > div > div.list-controll.clearfix")

        # 在 element 内查找 class 为 c-page-count 的元素
        count_elem = element.find_element(By.CLASS_NAME, "c-page-count")

        # 找到其中所有 strong 标签
        strongs = count_elem.find_elements(By.TAG_NAME, "strong")

        # 最后一个 strong 就是「全 件」的数字
        if strongs:
            total = int(strongs[-1].text.strip())
            log(f'{url_info["url"]} 全件数: {total}'	)
            db = TabelogDB()
            db.upsert_shop_list_summary(url_info["url"],url_info["parent_area_code"],url_info["area_code"],url_info["genre"],total)
            db.close
            return total
        else:
            log(f'{url_info["url"]} strong 标签不存在')
    except Exception as e:
        log(f'{url_info["url"]} cannot get')
        log(f'Exception: {type(e).__name__} - {e}')
        log(traceback.format_exc())

    return 0

def is_exit_shop(link,url):
    result = False
    db = TabelogDB()
    if db.is_exit_shop(link):
        db.countskip_to_shop_list_summary(url)
        result = True
    db.close()
    return result
    
def insert_or_update_shop(shop_data,url):
    db = TabelogDB()
    db.insert_or_update_shop(shop_data)
    db.count_to_shop_list_summary(url)
    db.close()
    log(f"✅ 已保存：{shop_data['name']}, link is {shop_data['url']}")
    
def insert_shop_catlog(link,area,genre):
    db = TabelogDB()
    result = db.insert_shop_catlog(link,area,genre)
    db.close()
    if result:
        log(f"✅ shop_catlog插入成功。 link: {link}, area: {area}, genre: {genre}")
    else:
        log(f"⚠️ shop_catlog数据已存在，未插入。 link: {link}, area: {area}, genre: {genre}")

def get_list(driver,url,total,area,genre):

    # 翻页采集逻辑
    page = 1
    exurl = url
    count = 0
    #link =''
    while True:
        try:

            # 初始化浏览器
            driver.get(exurl)
            log(f"🔍 正在处理第 {page} 页...")
            time.sleep(3)  # 等待页面加载
            #scroll_to_bottom(driver, pause=1.5, max_scrolls=10)
            
            shops = driver.find_elements(By.CSS_SELECTOR, "div.list-rst.js-rst-cassette-wrap")
            log(f"本页共找到 {len(shops)} 个店铺")

            for rst in shops:
                try:
                    driver.execute_script("arguments[0].scrollIntoView();", rst)
                    time.sleep(0.3)

                    name_elem = rst.find_element(By.CSS_SELECTOR, "a.list-rst__rst-name-target")
                    name = name_elem.text.strip()
                    link = name_elem.get_attribute("href")
                    log(f"{link}")
                    if not link:
                        continue # skip .
                    insert_shop_catlog(link,area,genre)
                    if is_exit_shop(link,url):
                        log(f"⚠️ 跳过已收集：{link}")
                        continue # skip to reget.

                    #score = rst.find_element(By.CSS_SELECTOR, "span.c-rating__val").text.strip()
                    #reviews = rst.find_element(By.CSS_SELECTOR, "em.list-rst__rvw-count-num").text.strip()
                    score = '0'
                    elems = rst.find_elements(By.CSS_SELECTOR, "span.c-rating__val")
                    if elems:
                        score = elems[0].text.strip()
                    
                    reviews = '0'
                    elems = rst.find_elements(By.CSS_SELECTOR, "em.list-rst__rvw-count-num")
                    if elems:
                        reviews = elems[0].text.strip()

                    detail = get_detail_info(driver,link + "#title-rstdata")
                    shop_data = {
                                "name": name,
                                "url": link,
                                "score": score,
                                "reviews": reviews,
                                "prefecture": detail["prefecture"],
                                "city": detail["city"],
                                "town": detail["town"],
                                "detail": detail["detail"],
                                "full": detail["full"],
                                "phone": detail["tel"],
                                "category": detail["category"],
                                "budget": detail["budget"],
                                "payment": detail["payment"],
                                "seats": detail["seats"],
                                "open_date": detail["open_date"],
                                "area": area,
                                "genre": genre,
                                }
                    insert_or_update_shop(shop_data,url)
                    count += 1
                    time.sleep(random.uniform(1,2))
                except Exception as e:
                    log(f"❌ {link} 跳过异常：{e}")

            total -=len(shops)
            if total<=0 or page>=60:
                break
            page += 1
            exurl = f"{url}/{page}"

            time.sleep(random.uniform(2,3))
        except:
            log("▶️ 无下一页，结束采集")
            break

    log(f"🎉 完成，共采集 {count} 家店铺，保存到 tabelog.db")

def convert_matome_url_to_rstLst(url: str) -> str:
    """
    将 URL 从 matome 格式转换为 rstLst 格式
    例：
    https://tabelog.com/matome/fukushima/A0701/list/ →
    https://tabelog.com/fukushima/A0701/rstLst/
    """
    if "/matome/" in url:
        url = url.replace("/matome/", "/")
    if url.endswith("/list/"):
        url = url[:-6] + "/rstLst/"
    elif url.endswith("/list"):
        url = url[:-5] + "/rstLst/"
    return url

def get_urls():
    db = TabelogDB()
    areas = db.select_areas(101)
    genres = db.select_genres()
    db.close()

    urls = []
    for area in areas:
        for genre in genres:
            url = convert_matome_url_to_rstLst(area["href"])
            url += genre["code"]
            url_info = {
                "url": url,
                "parent_area_code": area["parent_code"],
                "area_code": area["code"],
                "genre": genre["code"],
            }
            urls.append(url_info)
    
    return urls

if __name__ == "__main__":
    urls = get_urls()
    i = 1
    options = webdriver.ChromeOptions()
    #options.add_argument("--disable-blink-features=AutomationControlled")
    #options.add_argument("start-maximized")
    #options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36")

    options.add_argument("--enable-unsafe-swiftshader")  # 显式开启 software fallback
    options.add_argument('--disable-gpu')  # Windows 系统建议加上
    options.add_argument('--headless=new')  # 关键：开启无头模式
    options.add_argument('--window-size=1920,1080')  # 建议加窗口尺寸，避免布局问题
    options.add_argument('--no-sandbox')  # 有时防崩溃用（特别是在Linux）
    options.add_argument("--log-level=3")  # 只输出致命错误
    options.add_experimental_option("excludeSwitches", ["enable-logging"])    

    driver = webdriver.Chrome(options=options)

    for url_info in urls:
        total = get_count(driver,url_info)
        db = TabelogDB()
        need,result0,result1,result2 = db.is_need_get_shop(url_info["url"])
        db.close()
        
        if need and total>0:
            log(f'⬇️ 开始收集：{url_info["url"]}， 需要收集：{result2}件，已收集{result0+result1}件')
            get_list(driver,url_info["url"],total,url_info["area_code"],url_info["genre"])
        else:
            log(f'⚠️ 跳过收集：{url_info["url"]}， 需要收集：{result2}件，已收集{result0+result1}件')

    driver.quit()
