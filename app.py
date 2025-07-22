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
    
@app.route("/generate-heading", methods=["POST"])
def generate_heading():
    try:
        import random

        def generate_experience_flags(num_blocks=6, ratio=0.3):
            flags = [1 if random.random() < ratio else 0 for _ in range(num_blocks)]
            if sum(flags) == 0:
                flags[random.randint(0, num_blocks - 1)] = 1
            return flags

        data = request.get_json()

        # 必須キーの確認
        required_keys = [
            "keyword", "kyoukigo_list", "kyoukigo_top5",
            "lsi_list", "paa_list", "persona",
            "searchintent", "searchinsights"
        ]
        for key in required_keys:
            if key not in data:
                return jsonify({"error": f"{key} is required"}), 400

        # experienceフラグ生成（block:1〜6）
        experience_flags = generate_experience_flags()

        # テンプレート読み込み
        with open("prompts/promptheading.txt", "r", encoding="utf-8") as f:
            template = f.read()

        # プレースホルダ置換（experience_flag1〜6も含む）
        prompt = template.format(
            keyword=data["keyword"],
            kyoukigo_list=", ".join(data["kyoukigo_list"]),
            kyoukigo_top5=", ".join(data["kyoukigo_top5"]),
            lsi_list=", ".join(data["lsi_list"]),
            paa_list=", ".join(data["paa_list"]),
            persona=data["persona"],
            searchintent=data["searchintent"],
            searchinsights=data["searchinsights"],
            experience_flag1=experience_flags[0],
            experience_flag2=experience_flags[1],
            experience_flag3=experience_flags[2],
            experience_flag4=experience_flags[3],
            experience_flag5=experience_flags[4],
            experience_flag6=experience_flags[5]
        )

        # Claude API 呼び出し
        headers = {
            "x-api-key": os.getenv("CLAUDE_API_KEY"),
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        body = {
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 3000,
            "temperature": 0.7,
            "messages": [{"role": "user", "content": prompt}]
        }

        response = requests.post("https://api.anthropic.com/v1/messages", headers=headers, json=body)
        response.raise_for_status()
        content = response.json()["content"][0]["text"]

        return jsonify({"heading_html": content})

    except Exception as e:
        return jsonify({"error": "Claude error", "detail": str(e)}), 500
    
from flask import request, jsonify
from datetime import datetime
import os, re

@app.route("/generate-body", methods=["POST"])
def generate_body():
    data = request.get_json()

    # --- 共通パラメータ取得 ---
    keyword = data.get("keyword", "")
    lsi_list = data.get("lsi_list", [])
    kyoukigo_list = data.get("kyoukigo_list", [])
    paa_list = data.get("paa_list", [])
    searchintent = data.get("searchintent", "")
    searchinsights = data.get("searchinsights", "")
    persona = data.get("persona", "")
    blocks = data.get("blocks", [])

    year = datetime.now().strftime("%Y")
    month = datetime.now().strftime("%m")

    # --- slug生成（1回のみ） ---
    slug_prompt = f"""
#目的  
キーワードを渡しますのでURLに使用するslugを生成してください。  

#生成ルール  
キーワードを英語ほんやくしてください  
すべて小文字にしてください  
記号は-に変換してください  
スペースは-に変換してください  

例）  
キーワード：私は男  
翻訳例：I 'm a man  
slug：i-m-a-man

キーワード：{keyword}
出力形式：slug：
"""
    slug_response = call_claude(slug_prompt)
    match = re.search(r"slug\s*[:：]\s*(.+)", slug_response, re.IGNORECASE)
    slug = match.group(1).strip() if match else "no-slug"

    # --- テンプレート読み込み ---
    with open("prompts/promptmaintext.txt", "r", encoding="utf-8") as f:
        prompt_template = f.read()

    # --- 各ブロックの生成 ---
    results = {}
    for block in blocks:
        block_n = block.get("block_n", "")
        block_title = block.get("block_title", "")
        topic1 = block.get("topic1", "")
        topic2 = block.get("topic2", "")
        topic3 = block.get("topic3", "")
        experience_flag = block.get("experience", 0)

        # experienceコメント
        experience_note = (
            "※筆者の実体験を1つ含めてください。自然な形で1回だけ実体験を挿入してください。\n"
            "「私の場合は〜」「以前住んでいた部屋では〜」など。"
            if experience_flag == 1 else ""
        )

        # プレースホルダ置換
        prompt = prompt_template.format(
            keyword=keyword,
            lsi_list=", ".join(lsi_list),
            kyoukigo_list=", ".join(kyoukigo_list),
            paa_list=", ".join(paa_list),
            searchintent=searchintent,
            searchinsights=searchinsights,
            persona=persona,
            block_n=block_n,
            block_title=block_title,
            topic1=topic1,
            topic2=topic2,
            topic3=topic3,
            experience=experience_note,
            year=year,
            month=month,
            slug=slug
        )

        # Claude呼び出し
        try:
            response = call_claude(prompt)
            results[f"block{block_n}_html"] = response
        except Exception as e:
            return jsonify({"error": f"Block {block_n} failed: {str(e)}"}), 500

    # --- 全結果返却 ---
    results["slug"] = slug
    return jsonify(results)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
