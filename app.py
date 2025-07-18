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

@app.route("/analyze-intent-persona", methods=["POST"])
def analyze_intent_persona():
    try:
        data = request.get_json()
        html_list = data.get("scraphtml_list", [])
        keyword = data.get("keyword", "")

        if not html_list or not isinstance(html_list, list):
            return jsonify({"error": "scraphtml_list must be a non-empty list"}), 400

        # Claudeに渡す本文
        body_text = "\n\n---\n\n".join(html_list)

        # プロンプト
        prompt = f"""
あなたはSEOマーケティングの専門家です。
以下は「{keyword}」に関する検索上位記事の本文です。これらを読んで、次の3点を出力してください。

1. 検索意図（searchintent）：このキーワードで検索した人は何を知りたいのか？
2. ペルソナ（persona）：年齢層・地域・行動背景・動機などを具体的に
3. 検索インサイト（searchinsights）：検索の裏にある本当の目的や悩み

--- 記事本文 ---
{body_text}
"""

        # Claude API呼び出し
        headers = {
            "x-api-key": os.getenv("ANTHROPIC_API_KEY"),
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        body = {
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 1024,
            "temperature": 0.7,
            "messages": [{"role": "user", "content": prompt}]
        }

        response = requests.post("https://api.anthropic.com/v1/messages", headers=headers, json=body)
        response.raise_for_status()
        content = response.json()["content"][0]["text"]

        # 結果抽出
        result = {
            "searchintent": "",
            "persona": "",
            "searchinsights": ""
        }
        for line in content.splitlines():
            if "検索意図" in line:
                result["searchintent"] = line.split("：", 1)[-1].strip()
            elif "ペルソナ" in line:
                result["persona"] = line.split("：", 1)[-1].strip()
            elif "検索インサイト" in line:
                result["searchinsights"] = line.split("：", 1)[-1].strip()

        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
