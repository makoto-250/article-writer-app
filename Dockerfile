# Python公式イメージを使う
FROM python:3.11-slim

# 作業ディレクトリ作成
WORKDIR /app

# 必要ファイルコピー
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# アプリをコピー
COPY . .

# Flask起動（ポート指定）
CMD ["python", "app.py"]
