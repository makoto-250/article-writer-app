FROM python:3.11-slim

RUN apt update && \
    apt install -y mecab libmecab-dev mecab-ipadic-utf8 git curl xz-utils file && \
    git clone --depth 1 https://github.com/neologd/mecab-ipadic-neologd.git && \
    cd mecab-ipadic-neologd && \
    ./bin/install-mecab-ipadic-neologd -n -y && \
    cd .. && rm -rf mecab-ipadic-neologd && \
    apt clean && \
    rm -rf /var/lib/apt/lists/*

# 作業ディレクトリ
WORKDIR /app

# Pythonライブラリのインストール
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# ★ MeCab Pythonバインディングのインストール（←ここが追加）
RUN pip install mecab-python3

# アプリケーションのコードをコピー
COPY . .

# アプリ起動コマンド
CMD ["python", "app.py"]
