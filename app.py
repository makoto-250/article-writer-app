from flask import Flask, request, jsonify
import os
import requests

app = Flask(__name__)

@app.route("/")
def hello():
    return "Flask + Docker セットアップ成功！"

@app.route('/zenserp-urls', methods=['POST'])
def zenserp_urls():
    try:
        data = request.get_json()
        keyword = data.get('keyword', '').strip()
        if not keyword:
            return jsonify({'error': 'Keyword is required'}), 400

        api_key = os.getenv("ZENSERP_API_KEY")
        params = {
            "q": keyword,
            "num": "10",
            "gl": "jp",
            "hl": "ja",
            "apikey": api_key,
            "search_type": "web"
        }

        resp = requests.get("https://app.zenserp.com/api/v2/search", params=params)
        result = resp.json()

        urls = []
        for item in result.get("organic", []):
            url = item.get("url")
            if url and "google." not in url:
                urls.append(url)

        return jsonify({"zenurl": urls})

    except Exception as e:
        return jsonify({"error": "Zenserp error", "detail": str(e)}), 500
    
    from bs4 import BeautifulSoup

@app.route('/scrape-html', methods=['POST'])
def scrape_html():
    try:
        data = request.get_json()
        urls = data.get('zenurl', [])
        if not urls or not isinstance(urls, list):
            return jsonify({'error': 'zenurl list is required'}), 400

        html_texts = []
        for url in urls:
            try:
                resp = requests.get(url, timeout=5)
                soup = BeautifulSoup(resp.text, 'html.parser')
                # 一般的に本文とみなされるタグを優先して抽出
                for tag in ['article', 'main', 'body']:
                    content = soup.find(tag)
                    if content:
                        break
                else:
                    content = soup

                text = content.get_text(separator=' ', strip=True)
                html_texts.append(text[:5000])  # 長すぎると扱いにくいので切る
            except Exception as e:
                html_texts.append("")

        return jsonify({"scraphtml_list": html_texts})

    except Exception as e:
        return jsonify({"error": "Scrape error", "detail": str(e)}), 500
    
import MeCab
from collections import Counter
import re

@app.route("/extract-kyoukigo", methods=["POST"])
def extract_kyoukigo():
    try:
        data = request.get_json()
        if not data or "scraphtml_list" not in data:
            return jsonify({"error": "scraphtml_list is required"}), 400

        scraphtml_list = data["scraphtml_list"]
        if not isinstance(scraphtml_list, list):
            return jsonify({"error": "scraphtml_list must be a list"}), 400

        # MeCab準備（NEologdパスを適宜修正してください）
        mecab = MeCab.Tagger("-d /usr/lib/mecab/dic/mecab-ipadic-neologd")

        word_counter = Counter()
        for html in scraphtml_list:
            text = re.sub(r'<[^>]*?>', '', html)  # HTMLタグ除去
            node = mecab.parseToNode(text)
            while node:
                features = node.feature.split(",")
                if features[0] in ["名詞"] and features[1] not in ["数", "非自立", "接尾", "代名詞"]:
                    word = node.surface
                    if word and len(word) > 1:
                        word_counter[word] += 1
                node = node.next

        # 出現回数順で共起語リストと上位5語
        kyoukigo_list = [w for w, c in word_counter.most_common(40)]
        kyoukigo_top5 = kyoukigo_list[:5]

        return jsonify({
            "kyoukigo_list": kyoukigo_list,
            "kyoukigo_top5": kyoukigo_top5
        })

    except Exception as e:
        return jsonify({"error": "Internal Server Error", "detail": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
