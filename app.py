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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
