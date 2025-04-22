import streamlit as st
import csv, json, re, time, urllib.parse as up, requests
from pathlib import Path
from bs4 import BeautifulSoup

# 設定ファイル読み込み
CFG     = json.loads(Path("google_api_key.json").read_text())
API_KEY = CFG["API_KEY"]
CSE_ID  = CFG["CSE_ID"]

# 会社名抽出用正規表現
ORG_REGEX = re.compile(
    r"(?:株式|有限|合同)会社[\s\u3000]*[\w\-\u3040-\u30FF\u4E00-\u9FFF]{1,40}"
    r"|[\w\-\u3040-\u30FF\u4E00-\u9FFF]{1,40}(?:Inc\.|Co\.,?\s?Ltd\.?)"
    r"|(?:\(株\)|\(有\)|\(合\))[\s\u3000]*[\w\-\u3040-\u30FF\u4E00-\u9FFF]{1,40}"
    r"|[\w\-\u3040-\u30FF\u4E00-\u9FFF]{1,40}(?:\(株\)|\(有\)|\(合\))"
)

def gsearch(q, start=1, num=10):
    url = "https://www.googleapis.com/customsearch/v1"
    params = {"key": API_KEY, "cx": CSE_ID, "q": q, "num": num, "start": start}
    return requests.get(url, params=params, timeout=30).json().get("items", [])

def collect(keyword, pref, max_hits):
    q = f"{keyword} site:blog OR inurl:blog"
    if pref:
        q += f" {pref}"
    results, start = [], 1
    while len(results) < max_hits:
        items = gsearch(q, start=start)
        if not items:
            break
        for it in items:
            url = it["link"]
            dom = up.urlparse(url).netloc
            if any(r["domain"] == dom for r in results):
                continue
            results.append({"domain": dom, "page_url": url})
            if len(results) >= max_hits:
                break
        start += 10
        time.sleep(1)
    return results

# --- Streamlit UI ---
st.title("ブログ収集SaaS")
st.write("キーワード・都道府県・取得件数を入力して「実行」を押すと、CSVが生成されます。")

keyword  = st.text_input("キーワード", value="システム開発")
pref     = st.text_input("都道府県", value="東京都")
max_hits = st.number_input("取得件数", min_value=1, max_value=100, value=3)

if st.button("実行"):
    with st.spinner("検索中…"):
        rows = collect(keyword, pref, max_hits)
    # CSV生成
    fname = f"blogs_{keyword}_{pref or 'all'}.csv"
    with open(fname, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["domain","page_url"])
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    st.success(f"{len(rows)} 件取得 → ファイルをダウンロードしてください")
    st.download_button("CSVをダウンロード", data=open(fname, "rb"), file_name=fname)