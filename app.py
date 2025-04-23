import streamlit as st
import csv, json, re, time, urllib.parse as up, requests
from pathlib import Path
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

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

def is_corporate_site(url):
    """コーポレートサイトかどうかをチェック"""
    try:
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 会社名の検出
        text = soup.get_text()
        if ORG_REGEX.search(text):
            return True
            
        # コーポレートサイトによくある要素のチェック
        corporate_elements = [
            '会社概要', '企業情報', 'about', 'company', 'corporate',
            '採用情報', 'recruit', 'career', 'お問い合わせ', 'contact'
        ]
        for element in corporate_elements:
            if element in text.lower():
                return True
                
        return False
    except:
        return False

def has_recent_updates(url):
    """直近1-2ヶ月以内に更新があるかチェック"""
    try:
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # ブログ記事やニュースの日付を探す
        date_patterns = [
            r'\d{4}[-/年]\d{1,2}[-/月]\d{1,2}日?',
            r'\d{1,2}[-/月]\d{1,2}日?',
            r'\d{1,2}[-/月]\d{1,2}日?'
        ]
        
        # 日付を含む可能性のある要素を探す
        for element in soup.find_all(['time', 'span', 'div', 'p']):
            text = element.get_text()
            for pattern in date_patterns:
                if re.search(pattern, text):
                    # 日付を解析
                    try:
                        date_str = re.search(pattern, text).group()
                        # 日付の正規化（例: 2023年12月31日 → 2023-12-31）
                        date_str = re.sub(r'[年月]', '-', date_str)
                        date_str = re.sub(r'日', '', date_str)
                        date = datetime.strptime(date_str, '%Y-%m-%d')
                        
                        # 1-2ヶ月以内かチェック
                        if date > datetime.now() - timedelta(days=60):
                            return True
                    except:
                        continue
        return False
    except:
        return False

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
                
            # コーポレートサイトかつ最近の更新がある場合のみ追加
            if is_corporate_site(url) and has_recent_updates(url):
                results.append({"domain": dom, "page_url": url})
                if len(results) >= max_hits:
                    break
                    
        start += 10
        time.sleep(1)
    return results

# --- Streamlit UI ---
st.title("ブログ収集SaaS")
st.write("キーワード・都道府県・取得件数を入力して「実行」を押すと、CSVが生成されます。")
st.write("※コーポレートサイトで、直近1-2ヶ月以内に更新のあるブログのみを取得します。")

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