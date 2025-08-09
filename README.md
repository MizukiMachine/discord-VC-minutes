# Discord議事録Bot

Discord ボイスチャットを自動で文字起こし・要約するBotです

## 概要

- VC参加と同時に自動録音開始
- 「📜今まで」ボタンで即座に議事録生成
- 過去2時間分の会話をいつでも要約可能

## 機能


| 機能 | 説明 |
|------|------|
| **完全自動録音** | VC参加と同時にBot自動参加・録音開始 |
| **2時間バッファ** | Redis TTL=7200秒で音声データを自動保持 |
| **オンデマンド要約** | 「📜今まで」ボタンでワンクリック要約生成 |
| **常設コントロールパネル** | 全VCテキストチャットにパネル常時表示 |
| **シンプルUI** | ボタン1個のみ。複雑な録音制御を完全排除 |

---

## システム構成

```
Discord音声 → Whisper文字起こし → Redis保存 → GPT-4o-mini要約 → Discord投稿
```

## セットアップ

### 環境変数

```bash
export DISCORD_BOT_TOKEN="your-token"
export OPENAI_API_KEY="your-key"
export REDIS_URL="redis://localhost:6379"
export VIBE_URL="http://localhost:3022"
```

### インストール

```bash
# 依存関係
pip install -r requirements.txt

# Whisperサーバー起動
docker run -d --gpus all ghcr.io/thewh1teagle/vibe:latest --server --port 3022

# Bot起動
python main.py
```

## Docker

```bash
docker build -t discord-minutes-bot .
docker run --env-file .env discord-minutes-bot
```


## 必要な権限

- 音声チャンネルに接続
- メッセージの送信
- メッセージの管理（ピン留め用）
