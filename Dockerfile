FROM python:3.11-slim

# 必要パッケージのインストール
RUN apt update && \
    apt install -y mecab libmecab-dev mecab-ipadic-utf8 git curl xz-utils file build-essential && \
    apt clean && \
    rm -rf /var/lib/apt/lists/*

# neologd 辞書をインストール
RUN git clone --depth 1 https://github.com/neologd/mecab-ipadic-neologd.git && \
    cd mecab-ipadic-neologd && \
    ./bin/install-mecab-ipadic-neologd -n -y && \
    cd .. && rm -rf mecab-ipadic-neologd

# 作業ディレクトリ
WORKDIR /app

# Pythonライブラリのインストール
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# アプリコードのコピー
COPY . .

# アプリ起動
CMD ["python", "app.py"]
