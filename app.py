from flask import Flask, request, jsonify
from bs4 import BeautifulSoup
from collections import Counter
from dotenv import load_dotenv
import requests
import os
import MeCab
import re

load_dotenv()

app = Flask(__name__)

# 動作確認用
@app.route("/")
def hello():
    return "Flask + Docker セットアップ成功！"

# 1. Zenserpで検索上位URL取得
@app.route('/get-zenserp-urls', methods=['POST'])
def get_zenserp_urls():
    try:
        data = request.get_json()
        keyword = data.get("keyword", "").strip()
        if not keyword:
            return jsonify({"error": "keyword is required"}), 400

        api_key = os.getenv("ZENSERP_API_KEY")
        params = {
            "q": keyword,
            "num": "10",
            "gl": "jp",
            "hl": "ja",
            "apikey": api_key,
            "search_type": "web"
        }

        response = requests.get("https://app.zenserp.com/api/v2/search", params=params)
        result = response.json()

        urls = [item.get("url") for item in result.get("organic", []) if item.get("url") and "google." not in item.get("url")]
        return jsonify({"zenurl": urls})
    except Exception as e:
        return jsonify({"error": "Zenserp error", "detail": str(e)}), 500

# 2. スクレイピングで本文取得
@app.route('/scrape-html', methods=['POST'])
def scrape_html():
    try:
        data = request.get_json()
        urls = data.get("zenurl", [])
        if not urls or not isinstance(urls, list):
            return jsonify({'error': 'zenurl list is required'}), 400

        html_texts = []
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

        for url in urls:
            try:
                res = requests.get(url, headers=headers, timeout=10)
                res.raise_for_status()
                soup = BeautifulSoup(res.text, "html.parser")
                text = soup.get_text(separator="\n", strip=True)
                html_texts.append(text[:5000])
            except Exception as e:
                html_texts.append("")

        return jsonify({"scraphtml_list": html_texts})
    except Exception as e:
        return jsonify({"error": "Scrape error", "detail": str(e)}), 500

# 3. MeCabで共起語抽出（フィルタあり）
@app.route("/extract-cooccurrence", methods=["POST"])
def extract_cooccur_terms():
    try:
        data = request.get_json()
        html_list = data.get("scraphtml_list", [])
        if not html_list or not isinstance(html_list, list):
            return jsonify({"error": "scraphtml_list must be a list of text"}), 400

        tagger = MeCab.Tagger("-r /etc/mecabrc -d /usr/lib/x86_64-linux-gnu/mecab/dic/mecab-ipadic-neologd")
        tagger.parse('')

        valid_pos = {"名詞", "動詞", "形容詞", "副詞"}
        word_counter = Counter()

        for html in html_list:
            parsed = tagger.parse(html)
            for line in parsed.splitlines():
                if line == "EOS" or not line.strip():
                    continue
                try:
                    surface, features = line.split("\t")
                    pos = features.split(",")[0]
                    if pos in valid_pos and len(surface) > 1:
                        word_counter[surface] += 1
                except ValueError:
                    continue

        kyoukigo_list = [w for w, _ in word_counter.most_common(30)]
        kyoukigo_top5 = kyoukigo_list[:5]

        return jsonify({
            "kyoukigo_list": kyoukigo_list,
            "kyoukigo_top5": kyoukigo_top5
        })
    except Exception as e:
        return jsonify({"error": "Internal Server Error", "detail": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
