import requests
import pandas as pd

url = "https://free-proxy-list.net/"
dfs = pd.read_html(requests.get(url).text)
proxy_table = dfs[0]  # 取第一个表格（代理表）

# 筛选高匿名 + HTTPS 支持的 US 代理
filtered = proxy_table[
    (proxy_table["Anonymity"] == "elite proxy") &
    (proxy_table["Https"] == "yes") 
]

# 拼接为 IP:Port
proxies = filtered.apply(lambda row: f"{row['IP Address']}:{row['Port']}", axis=1).tolist()
valid = []
for proxy in proxies:
    try:
        r = requests.get("https://httpbin.org/ip",
                         proxies={"http": f"http://{proxy}", "https": f"http://{proxy}"},
                         timeout=5)
        if r.status_code == 200:
            valid.append(proxy)
    except:
        pass

print("可用代理：", valid)
