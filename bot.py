import os
import uuid
import json
import asyncio
import requests
import re
from collections import defaultdict, deque

import discord
from discord.ext import commands
from discord import app_commands
from pydub import AudioSegment

# ------------------- 設定項目 -------------------
TOKEN = "あなたのBOTトークン" # 自身のDiscord Botのトークンに置き換えてください
VOICEVOX_URL = "http://127.0.0.1:50021"

# ファイル・ディレクトリのパス
SETTINGS_FILE = "server_settings.json"
GLOBAL_DICT_FILE = "global_dictionary.json"
SERVER_DICT_DIR = "dictionaries"

DEFAULT_SETTINGS = {
    "speaker_id": 2,
    "volume_scale": 2.0,
    "speed_scale": 1.1
}

# ------------------- 初期セットアップ -------------------
# 必要なディレクトリやファイルがなければ作成
if not os.path.exists(SERVER_DICT_DIR):
    os.makedirs(SERVER_DICT_DIR)
if not os.path.exists(SETTINGS_FILE):
    with open(SETTINGS_FILE, 'w') as f: json.dump({}, f)
if not os.path.exists(GLOBAL_DICT_FILE):
    with open(GLOBAL_DICT_FILE, 'w') as f: json.dump({}, f)


# ------------------- Botの準備 -------------------
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.voice_states = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

active_voice_connections = {}
play_queues = defaultdict(deque)

def load_json(path, default_data=None):
    if default_data is None: default_data = {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default_data

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# --- テキスト・音声処理 ---
def apply_dictionaries(text: str, guild_id: int) -> str:
    """辞書を適用してテキストを置換する"""
    server_dict_path = os.path.join(SERVER_DICT_DIR, f"{guild_id}.json")
    server_dict = load_json(server_dict_path)
    global_dict = load_json(GLOBAL_DICT_FILE)

    # サーバー辞書を優先して置換
    for word, reading in server_dict.items():
        text = text.replace(word, reading)
    # グローバル辞書で置換
    for word, reading in global_dict.items():
        text = text.replace(word, reading)
    return text

async def synthesize_and_play_queue(guild_id: int, voice_client: discord.VoiceClient):

    while play_queues[guild_id]:
        text = play_queues[guild_id].popleft()
        try:
            settings = load_json(SETTINGS_FILE).get(str(guild_id), DEFAULT_SETTINGS)

            query_resp = requests.post(
                f"{VOICEVOX_URL}/audio_query",
                params={"text": text, "speaker": settings["speaker_id"]}
            )
            query_resp.raise_for_status()
            query = query_resp.json()

            query["volumeScale"] = settings["volume_scale"]
            query["speedScale"] = settings["speed_scale"]

            synth_resp = requests.post(
                f"{VOICEVOX_URL}/synthesis",
                params={"speaker": settings["speaker_id"]}, json=query
            )
            synth_resp.raise_for_status()

            file_id = str(uuid.uuid4())
            wav_path = f"tmp_{file_id}.wav"
            mp3_path = f"tmp_{file_id}.mp3"

            with open(wav_path, "wb") as f:
                f.write(synth_resp.content)

            AudioSegment.from_wav(wav_path).export(mp3_path, format="mp3")
            audio_source = discord.FFmpegPCMAudio(mp3_path)
            voice_client.play(audio_source)

            while voice_client.is_playing():
                await asyncio.sleep(0.5)

            os.remove(wav_path)
            os.remove(mp3_path)
        except Exception as e:
            print(f"[読み上げエラー] {e}")

async def enqueue_message(guild_id: int, message: discord.Message, voice_client: discord.VoiceClient):
    # メッセージを整形してキューに追加する
    content = message.content.strip()

    # URLを「URLを送信しました」という文字列に置換する
    content = re.sub(r'https?://[\w/:%#\$&\?\(\)~\.=\+\-]+', 'URLを送信しました', content)

    if not content:
        if message.attachments: content = "画像を送信しました"
        elif message.stickers: content = "スタンプを送信しました"
        else: return

    full_text = f"{content}"
    processed_text = apply_dictionaries(full_text, guild_id)
    
    play_queues[guild_id].append(processed_text)

    if not voice_client.is_playing():
        await synthesize_and_play_queue(guild_id, voice_client)

# --- Botイベントリスナー ---
@bot.event
async def on_ready():
    print(f"Bot起動完了：{bot.user}")
    await tree.sync()
    print("コマンドを同期しました。")

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return

    guild_id = message.guild.id
    if guild_id not in active_voice_connections:
        return

    config = active_voice_connections[guild_id]
    if message.channel.id != config["text_channel_id"]:
        return

    await enqueue_message(guild_id, message, config["vc"])

@bot.event
async def on_voice_state_update(member, before, after):
    """
    ボイスチャンネルの状態変化を検知するイベント
    Botが切断された場合に後処理を行う
    """
    if member.id == bot.user.id and before.channel and not after.channel:
        guild_id = before.channel.guild.id
        
        if guild_id in active_voice_connections:
            play_queues[guild_id].clear()
            del active_voice_connections[guild_id]
            print(f"サーバーID: {guild_id} でVCからの切断を検知し、クリーンアップしました。")

# --- スラッシュコマンド ---
@tree.command(name="vcjoin", description="今いるVCにBotを参加させます")
async def vcjoin(interaction: discord.Interaction):
    # ユーザーがVCにいるかチェック
    if not interaction.user.voice or not interaction.user.voice.channel:
        await interaction.response.send_message("VCに入ってから実行してください。", ephemeral=True)
        return

    await interaction.response.defer()

    guild_id = interaction.guild.id
    vc_channel = interaction.user.voice.channel

    try:
        # ボットが既にVCに接続している場合
        if guild_id in active_voice_connections:
            vc = active_voice_connections[guild_id]["vc"]
            # 同じチャンネルにいるなら何もしない
            if vc.channel == vc_channel:
                await interaction.followup.send(f"既に参加しています。", ephemeral=True)
                return
            # 違うチャンネルなら移動する
            await vc.move_to(vc_channel)
        # まだ接続していない場合
        else:
            vc = await vc_channel.connect()

        # 接続情報を保存
        active_voice_connections[guild_id] = {"vc": vc, "text_channel_id": interaction.channel.id}
        
        await interaction.followup.send(f"**{vc_channel.name}** に参加しました。")

    except Exception as e:
        print(f"VCへの接続に失敗しました: {e}")
        await interaction.followup.send(f"VCへの接続に失敗しました。Botに適切な権限があるか確認してください。", ephemeral=True)

@tree.command(name="vcleave", description="BotをVCから退出させます")
async def vcleave(interaction: discord.Interaction):
    guild_id = interaction.guild.id
    if guild_id not in active_voice_connections:
        await interaction.response.send_message("VCに接続していません。", ephemeral=True)
        return
    await active_voice_connections[guild_id]["vc"].disconnect()
    del active_voice_connections[guild_id]
    await interaction.response.send_message("VCから退出しました。")

# --- 設定変更コマンド ---
@tree.command(name="set_speaker", description="読み上げに使う話者IDを変更します")
@app_commands.describe(speaker_id="VOICEVOXの話者ID")
async def set_speaker(interaction: discord.Interaction, speaker_id: int):
    settings = load_json(SETTINGS_FILE)
    gid = str(interaction.guild.id)
    if gid not in settings: settings[gid] = DEFAULT_SETTINGS.copy()
    settings[gid]["speaker_id"] = speaker_id
    save_json(SETTINGS_FILE, settings)
    await interaction.response.send_message(f"話者IDを {speaker_id} に変更しました。", ephemeral=True)

@tree.command(name="set_volume", description="音量を変更します")
@app_commands.describe(volume="音量倍率（例: 2.0）")
async def set_volume(interaction: discord.Interaction, volume: float):
    settings = load_json(SETTINGS_FILE)
    gid = str(interaction.guild.id)
    if gid not in settings: settings[gid] = DEFAULT_SETTINGS.copy()
    settings[gid]["volume_scale"] = volume
    save_json(SETTINGS_FILE, settings)
    await interaction.response.send_message(f"音量を {volume} に変更しました。", ephemeral=True)

@tree.command(name="set_speed", description="読み上げ速度を変更します")
@app_commands.describe(speed="速度倍率（例: 1.1）")
async def set_speed(interaction: discord.Interaction, speed: float):
    settings = load_json(SETTINGS_FILE)
    gid = str(interaction.guild.id)
    if gid not in settings: settings[gid] = DEFAULT_SETTINGS.copy()
    settings[gid]["speed_scale"] = speed
    save_json(SETTINGS_FILE, settings)
    await interaction.response.send_message(f"速度を {speed} に変更しました。", ephemeral=True)

# --- 辞書管理コマンド ---
@tree.command(name="add_word", description="サーバー辞書に単語を追加/編集します")
@app_commands.describe(word="登録する単語", reading="単語の読み方（ひらがな/カタカナ）")
async def add_word(interaction: discord.Interaction, word: str, reading: str):
    dict_path = os.path.join(SERVER_DICT_DIR, f"{interaction.guild.id}.json")
    server_dict = load_json(dict_path)
    server_dict[word] = reading
    save_json(dict_path, server_dict)
    await interaction.response.send_message(f"辞書に「{word}」を「{reading}」として登録しました。", ephemeral=True)

@tree.command(name="remove_word", description="サーバー辞書から単語を削除します")
@app_commands.describe(word="削除する単語")
async def remove_word(interaction: discord.Interaction, word: str):
    dict_path = os.path.join(SERVER_DICT_DIR, f"{interaction.guild.id}.json")
    server_dict = load_json(dict_path)
    if word in server_dict:
        del server_dict[word]
        save_json(dict_path, server_dict)
        await interaction.response.send_message(f"辞書から「{word}」を削除しました。", ephemeral=True)
    else:
        await interaction.response.send_message(f"辞書に「{word}」は見つかりませんでした。", ephemeral=True)

@tree.command(name="list_words", description="サーバー辞書の登録単語一覧を表示します")
async def list_words(interaction: discord.Interaction):
    dict_path = os.path.join(SERVER_DICT_DIR, f"{interaction.guild.id}.json")
    server_dict = load_json(dict_path)
    if not server_dict:
        await interaction.response.send_message("このサーバーの辞書には何も登録されていません。", ephemeral=True)
        return
    embed = discord.Embed(title=f"サーバー辞書", color=discord.Color.blue())
    description = "\n".join(f"**{word}** → `{reading}`" for word, reading in server_dict.items())
    embed.description = description
    await interaction.response.send_message(embed=embed, ephemeral=True)

bot.run(TOKEN)
