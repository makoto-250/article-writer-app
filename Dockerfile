FROM python:3.11-slim

# 必要なライブラリをインストール
RUN apt update && \
    apt install -y mecab libmecab-dev mecab-ipadic-utf8 build-essential curl && \
    apt clean && \
    rm -rf /var/lib/apt/lists/*

# 作業ディレクトリ
WORKDIR /app

# Pythonライブラリのインストール
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションのコードをコピー
COPY . .

# アプリ起動コマンド
CMD ["python", "app.py"]
