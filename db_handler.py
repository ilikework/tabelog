import sqlite3
import os
import threading
from datetime import datetime

class TabelogDB:
    def __init__(self, db_path="tabelog.db"):
        self.db_path = db_path
        self.lock = threading.Lock()
        self.conn = None
        self.cursor = None

        is_new_db = not os.path.exists(self.db_path)

        self._connect()

        if is_new_db:
            print("📁 数据库文件不存在，首次创建:", self.db_path)
        #else:
            #print("✅ 已加载数据库文件:", self.db_path)

        if not self._table_exists("shops"):
            print("📦 表不存在，正在创建 shops 表...")
            self._create_shops_table()

        if not self._table_exists("shop_list_summary"):
            print("📦 表不存在，正在创建 shop_list_summary 表...")
            self._create_shop_list_summary_table()
            
        if not self._table_exists("shop_catlog"):
            print("📦 表不存在，正在创建 shop_catlog 表...")
            self._create_shop_catlog_table()

    def _create_shop_list_summary_table(self):
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS shop_list_summary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE,
                parent_area_code TEXT,
                area TEXT,
                genre TEXT,
                get_count INTEGER DEFAULT 0,
                skip_count INTEGER DEFAULT 0,
                total_count INTEGER,
                is_deleted INTEGER DEFAULT 0,
                create_time TEXT DEFAULT CURRENT_TIMESTAMP,
                update_time TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        self.conn.commit()

    def _create_shop_catlog_table(self):
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS shop_catlog (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                link TEXT NOT NULL,
                area TEXT NOT NULL,
                genre TEXT NOT NULL,
                is_deleted INTEGER DEFAULT 0,
                create_time TEXT DEFAULT CURRENT_TIMESTAMP,
                update_time TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(link, area, genre)
            );
        """)

        self.conn.commit()
        
    def insert_shop_catlog(self,link, area, genre):

        sql = """
        INSERT INTO shop_catlog (link, area, genre)
        VALUES (?, ?, ?)
        ON CONFLICT(link, area, genre) DO NOTHING;
        """
        self.cursor.execute(sql, (link, area, genre))
        self.conn.commit()
        changes = self.conn.total_changes

        if changes:
            return True
        else:
            return False        
        
    def _connect(self):
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()

    def _table_exists(self, table_name: str) -> bool:
        self.cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name=?;
        """, (table_name,))
        return self.cursor.fetchone() is not None

    def _create_shops_table(self):
        create_sql = """
        CREATE TABLE shops (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            url TEXT UNIQUE,
            score TEXT,
            reviews TEXT,
            prefecture TEXT,
            city TEXT,
            town TEXT,
            detail TEXT,
            full_address TEXT,
            phone TEXT,
            category TEXT,
            budget TEXT,
            payment TEXT,
            seats TEXT,
            open_date TEXT,     
            area TEXT,
            genre TEXT,
            is_deleted INTEGER DEFAULT 0,
            create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
        self.cursor.execute(create_sql)
        self.conn.commit()

    def select_areas(self,priority):
        cur = self.conn.cursor()

        cur.execute("""
            SELECT name, code, level, parent_code, href
            FROM area
            WHERE is_deleted = 0
            AND   level >=3
            AND   priority >= ?
            ORDER BY priority DESC,id ASC
        """,(priority,))
        rows = cur.fetchall()

        # 可选：转换为 list[dict]
        areas = []
        for row in rows:
            areas.append({
                "name": row[0],
                "code": row[1],
                "level": row[2],
                "parent_code": row[3],
                "href": row[4]
            })

        return areas

    def select_genres(self):
        cur = self.conn.cursor()

        cur.execute("""
                    SELECT name, code, level, parent_code
                    FROM genre AS g
                    WHERE NOT EXISTS (
                    SELECT 1
                    FROM genre AS child
                    WHERE child.parent_code = g.code
                    )
                    AND is_deleted = 0
                    ORDER BY code ASC
                """)
        rows = cur.fetchall()

        genres = []
        for row in rows:
            genres.append({
                "name": row[0],
                "code": row[1],
                "level": row[2],
                "parent_code": row[3]
            })

        return genres    

    def is_need_get_shop(self, url):
        self.cursor.execute("SELECT get_count,skip_count,total_count FROM shop_list_summary WHERE url = ? AND is_deleted = 0", (url,))
        result = self.cursor.fetchone()
        if result:
             if result[0]+result[1] >= result[2]:
                return False,result[0],result[1],result[2]
             else:
                 return True,result[0],result[1],result[2]
        return True,0,0,0

    def count_to_shop_list_summary(self,url):
        sql = '''
            UPDATE shop_list_summary
            SET get_count = get_count + 1,
                update_time = DATETIME('now', 'localtime')
            WHERE url = ? AND is_deleted = 0
        '''
        self.cursor.execute(sql, (url,))
        self.conn.commit()
        
    def countskip_to_shop_list_summary(self,url):
        sql = '''
            UPDATE shop_list_summary
            SET skip_count = skip_count + 1,
                update_time = DATETIME('now', 'localtime')
            WHERE url = ? AND is_deleted = 0
        '''
        self.cursor.execute(sql, (url,))
        self.conn.commit()

    def upsert_shop_list_summary(self, url, parent_area_code, area, genre, total_count):
        # 先检查是否已存在该 URL
        self.cursor.execute("SELECT id FROM shop_list_summary WHERE url = ? AND is_deleted = 0", (url,))
        result = self.cursor.fetchone()

        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        if result:
            # 存在：执行 UPDATE
            sql = '''
                UPDATE shop_list_summary
                SET total_count = ?, update_time = ?
                WHERE url = ? AND is_deleted = 0
            '''
            self.cursor.execute(sql, (total_count, now, url))
        else:
            # 不存在：执行 INSERT
            sql = '''
                INSERT INTO shop_list_summary
                (url, parent_area_code, area, genre, total_count, create_time, update_time)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            '''
            self.cursor.execute(sql, (url, parent_area_code, area, genre, total_count, now, now))

        self.conn.commit()

    def is_exit_shop(self, shop_url):
        result = False
        self.cursor.execute("SELECT id FROM shops WHERE url = ?", (shop_url,))
        row = self.cursor.fetchone()
        if row:
            result = True
        
        return result

    def insert_or_update_shop(self, shop_data: dict):
        with self.lock:
            self.cursor.execute("SELECT id FROM shops WHERE url = ?", (shop_data.get("url", ""),))
            row = self.cursor.fetchone()

            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            if row:
                # 已存在，更新
                self.cursor.execute("""
                    UPDATE shops
                    SET name=?, score=?, reviews=?, prefecture=?, city=?, town=?, detail=?,full_address=?, phone=?,
                        category=?, budget=?,payment=?, seats=?, open_date=?, area=?, genre=?,
                        is_deleted=0, update_time=?
                    WHERE url=?
                """, (
                    shop_data.get("name", ""),
                    shop_data.get("score", ""),
                    shop_data.get("reviews", ""),
                    shop_data.get("prefecture", ""),
                    shop_data.get("city", ""),
                    shop_data.get("town", ""),
                    shop_data.get("detail", ""),
                    shop_data.get("full", ""),
                    shop_data.get("phone", ""),
                    shop_data.get("category", ""),
                    shop_data.get("budget", ""),
                    shop_data.get("payment", ""),
                    shop_data.get("seats", ""),
                    shop_data.get("open_date", ""),
                    shop_data.get("area", ""),
                    shop_data.get("genre", ""),
                    now,
                    shop_data.get("url", "")
                ))
                print(f"🔄 更新店铺: {shop_data.get('name')}")
            else:
                # 不存在，插入
                self.cursor.execute("""
                    INSERT INTO shops (
                        name, url, score, reviews, prefecture, city, town,
                        detail, full_address, phone,
                        category, budget, payment, seats, open_date,area,genre,
                        is_deleted, create_time, update_time
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
                """, (
                    shop_data.get("name", ""),
                    shop_data.get("url", ""),
                    shop_data.get("score", ""),
                    shop_data.get("reviews", ""),
                    shop_data.get("prefecture", ""),
                    shop_data.get("city", ""),
                    shop_data.get("town", ""),
                    shop_data.get("detail", ""),
                    shop_data.get("full", ""),
                    shop_data.get("phone", ""),
                    shop_data.get("category", ""),
                    shop_data.get("budget", ""),
                    shop_data.get("payment", ""),
                    shop_data.get("seats", ""),
                    shop_data.get("open_date", ""),                    
                    shop_data.get("area", ""),
                    shop_data.get("genre", ""),
                    now, now
                ))
                print(f"➕ 插入店铺: {shop_data.get('name')}")
                

            self.conn.commit()

    def close(self):
        if self.conn:
            self.conn.close()
            #print("✅ 已关闭数据库")
