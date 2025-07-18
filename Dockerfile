FROM python:3.11-slim

# 必要なライブラリインストール
RUN apt update && apt install -y \
    git \
    curl \
    make \
    file \
    sudo \
    xz-utils \
    mecab \
    libmecab-dev \
    mecab-ipadic-utf8 \
    && apt clean && rm -rf /var/lib/apt/lists/*

# NEologdインストール
RUN git clone --depth 1 https://github.com/neologd/mecab-ipadic-neologd.git \
    && echo yes | mecab-ipadic-neologd/install.sh \
    && rm -rf mecab-ipadic-neologd

# dicdir（辞書パス）を取得して保存（パス確認に使用）
RUN echo $(mecab-config --dicdir)/mecab-ipadic-neologd > /usr/local/etc/mecabrc.dicdir

# 作業ディレクトリ
WORKDIR /app

# Pythonライブラリインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリのコードをコピー
COPY . .

# アプリ起動
CMD ["python", "app.py"]
