# VOICEVOX 読み上げDiscord Bot

Discordのテキストチャンネルに投稿されたメッセージを、VOICEVOXの音声でリアルタイムに読み上げるBotです。サーバーごとの設定や辞書機能を備えており、快適なボイスチャット環境を提供します。

## ✨ 特徴

* **リアルタイム読み上げ**: テキストチャンネルへの投稿を、参加しているボイスチャンネルで即座に読み上げます。
* **VOICEVOX連携**: 高品質な音声合成エンジンVOICEVOXに対応し、様々なキャラクターの声で読み上げが可能です。
* **柔軟なカスタマイズ**: 読み上げの声（話者）、音量、速度をサーバーごとにコマンドで簡単に設定できます。
* **サーバー辞書機能**: 固有名詞や専門用語の読み方を登録することで、誤読を減らし、より自然な読み上げを実現します。
* **簡単なコマンド操作**: DiscordのUIに統合されたスラッシュコマンドで、直感的にBotを操作できます。
* **URL・画像・スタンプ対応**: メッセージ中のURLや添付された画像、スタンプなどを「URLを送信しました」のような定型文で読み上げます。

## 🖥️ 導入と使い方

### 事前準備

1.  [Python](https://www.python.org/) (バージョン3.8以上を推奨) がインストールされていること。
2.  [VOICEVOX](https://voicevox.hiroshiba.jp/) をダウンロードし、`run.exe` を実行してローカルで起動していること。
3.  [Discord Developer Portal](https://discord.com/developers/applications) でBotを作成し、**TOKEN** を取得していること。
    * Botの `Privileged Gateway Intents` (`SERVER MEMBERS INTENT` と `MESSAGE CONTENT INTENT`) を有効にする必要があります。

### セットアップ

1.  このリポジトリをクローン、またはダウンロードします。
    ```bash
    git clone [リポジトリのURL]
    cd [リポジトリ名]
    ```
2.  必要なPythonライブラリをインストールします。
    ```bash
    pip install -r requirements.txt
    ```
    (`requirements.txt`がない場合は、`pip install discord.py python-dotenv pydub requests` を実行してください)
3.  以下の箇所にBOTトークンを設定します。
    ```.py
    DISCORD_BOT_TOKEN="あなたのBotのトークン"
    ```
4.  以下のコマンドでBotを起動します。
    ```bash
    python bot.py 
    ```
    (※ `bot.py` の部分は実際のファイル名に合わせてください)

### Botの操作

1.  **Botを招待**: Discord Developer Portalの `OAuth2 > URL Generator` から、`bot` と `applications.commands` のスコープにチェックを入れ、生成されたURLであなたのサーバーにBotを招待します。
2.  **VCに参加**: あなたが参加したいボイスチャンネルに入った状態で、テキストチャンネルで `/vcjoin` コマンドを実行します。
3.  **読み上げ開始**: `/vcjoin` を実行したVCテキストチャンネルにメッセージを投稿すると、Botがボイスチャンネルで読み上げを開始します。
4.  **VCから退出**: `/vcleave` コマンドでBotをボイスチャンネルから退出させます。

## 🛠️ コマンド一覧

### 接続コマンド
* `/vcjoin` : Botを現在参加しているボイスチャンネルに接続させます。
* `/vcleave`: Botをボイスチャンネルから退出させます。

### 設定コマンド
* `/set_speaker [speaker_id]` : 読み上げに使う話者IDを変更します。（例: `/set_speaker 3`）
* `/set_volume [volume]` : 音量を変更します。（例: `/set_volume 1.5`）
* `/set_speed [speed]` : 読み上げ速度を変更します。（例: `/set_speed 1.2`）

### 辞書コマンド
* `/add_word [単語] [読み方]` : 辞書に単語と読み方を登録します。
* `/remove_word [単語]` : 辞書から単語を削除します。
* `/list_words` : サーバー辞書に登録されている単語の一覧を表示します。

## 📄 ライセンス

このプロジェクトは [MITライセンス](LICENSE) の下で公開されています。
