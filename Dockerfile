# 1. Pythonベース
FROM python:3.11-slim

# 2. 必要なパッケージ
RUN apt update && \
    apt install -y git mecab libmecab-dev mecab-ipadic-utf8 curl make xz-utils file sudo && \
    apt clean && \
    rm -rf /var/lib/apt/lists/*

# 3. NEologdインストール
RUN git clone --depth 1 https://github.com/neologd/mecab-ipadic-neologd.git && \
    echo yes | mecab-ipadic-neologd/install.sh && \
    rm -rf mecab-ipadic-neologd

# 4. 作業ディレクトリとPythonライブラリ
WORKDIR /app
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# 5. コードコピーと起動
COPY . .
CMD ["python", "app.py"]
