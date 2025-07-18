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
以下は「{keyword}」に関する検索上位記事の本文です。これらを読んで、次の3点を**必ずすべて**それぞれ100文字以上で出力してください。

1. 検索意図（searchintent）
2. ペルソナ（persona）
3. 検索インサイト（searchinsights）

出力形式（Markdown）：

## 1. 検索意図（searchintent）
[検索意図の説明文]

## 2. ペルソナ（persona）
[ペルソナの説明文]

## 3. 検索インサイト（searchinsights）
[検索インサイトの説明文]

--- 記事本文 ---
{body_text}
"""

        # Claude API呼び出し
        headers = {
            "x-api-key": os.getenv("CLAUDE_API_KEY"),
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        body = {
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 2048,
            "temperature": 0.7,
            "messages": [{"role": "user", "content": prompt}]
        }

        response = requests.post("https://api.anthropic.com/v1/messages", headers=headers, json=body)
        response.raise_for_status()
        content = response.json()["content"][0]["text"]

        # 結果抽出（マルチライン対応）
        result = {
            "searchintent": "",
            "persona": "",
            "searchinsights": ""
        }

        current_key = None
        buffer = []

        for line in content.splitlines():
            if "検索意図" in line:
                if current_key and buffer:
                    result[current_key] = "\n".join(buffer).strip()
                    buffer = []
                current_key = "searchintent"
            elif "ペルソナ" in line:
                if current_key and buffer:
                    result[current_key] = "\n".join(buffer).strip()
                    buffer = []
                current_key = "persona"
            elif "検索インサイト" in line:
                if current_key and buffer:
                    result[current_key] = "\n".join(buffer).strip()
                    buffer = []
                current_key = "searchinsights"
            elif current_key:
                buffer.append(line.strip())

        if current_key and buffer:
            result[current_key] = "\n".join(buffer).strip()

        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/get-lsi-paa", methods=["POST"])
def get_lsi_paa():
    try:
        data = request.get_json()
        keyword = data.get("keyword", "").strip()
        if not keyword:
            return jsonify({"error": "keyword is required"}), 400

        api_key = os.getenv("SERPAPI_API_KEY")
        params = {
            "engine": "google",
            "q": keyword,
            "hl": "ja",
            "gl": "jp",
            "api_key": api_key
        }

        response = requests.get("https://serpapi.com/search", params=params)
        response.raise_for_status()
        result = response.json()

        lsi_list = []
        paa_list = []

        if "related_searches" in result:
            lsi_list = [item.get("query") for item in result["related_searches"] if item.get("query")]

        if "related_questions" in result:
            paa_list = [item.get("question") for item in result["related_questions"] if item.get("question")]

        return jsonify({
            "lsi_list": lsi_list,
            "paa_list": paa_list
        })

    except Exception as e:
        return jsonify({"error": "SerpAPI error", "detail": str(e)}), 500

from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException

@app.route("/get-related-terms", methods=["POST"])
def get_related_terms():
    try:
        data = request.get_json()
        keyword_text = data.get("keyword", "").strip()
        if not keyword_text:
            return jsonify({"error": "keyword is required"}), 400

        # 環境変数から設定を読み込む
        developer_token = os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN")
        client_id = os.getenv("GOOGLE_ADS_CLIENT_ID")
        client_secret = os.getenv("GOOGLE_ADS_CLIENT_SECRET")
        refresh_token = os.getenv("GOOGLE_ADS_REFRESH_TOKEN")
        login_customer_id = os.getenv("GOOGLE_ADS_LOGIN_CUSTOMER_ID")

        credentials = {
            "developer_token": developer_token,
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "login_customer_id": login_customer_id
        }

        client = GoogleAdsClient.load_from_dict({
            "developer_token": developer_token,
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "login_customer_id": login_customer_id,
            "use_proto_plus": True
        }, version="v16")

        keyword_plan_idea_service = client.get_service("KeywordPlanIdeaService")

        keyword_seed = [keyword_text]
        location_ids = [2392]  # 日本のlocation_id（東京など）
        language_id = 1005     # 日本語のlanguage_id

        request_obj = client.get_type("GenerateKeywordIdeasRequest")
        request_obj.customer_id = login_customer_id
        request_obj.keyword_seed.keywords.extend(keyword_seed)
        request_obj.language = f"languageConstants/{language_id}"
        request_obj.geo_target_constants.append(f"geoTargetConstants/{location_ids[0]}")
        request_obj.include_adult_keywords = False

        response = keyword_plan_idea_service.generate_keyword_ideas(request=request_obj)

        related_terms = []
        for idea in response:
            if idea.text:
                related_terms.append(idea.text)
            if len(related_terms) >= 30:
                break

        return jsonify({"related_terms": related_terms})

    except GoogleAdsException as ex:
        return jsonify({"error": "GoogleAds API Error", "detail": str(ex)}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
