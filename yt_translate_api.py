#!/usr/bin/env python3
"""
YouTube Studio 自動翻訳（Google API + OpenAI API）
- YouTube Data API v3 で動画情報取得・翻訳をアップロード
- OpenAI API で日本語→英語翻訳
"""

import os
import json
import time
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# ─────────────────────────────────────────
# パス設定
# ─────────────────────────────────────────
BASE_DIR       = Path(os.getenv("BGM_BASE_DIR") or Path(__file__).resolve().parent)
ENV_FILE       = BASE_DIR / ".claude" / ".env"
CLIENT_SECRET  = BASE_DIR / ".claude" / "client_secret.json"
TOKEN_FILE     = BASE_DIR / ".claude" / "token.json"

# ─────────────────────────────────────────
# 環境変数読み込み
# ─────────────────────────────────────────
load_dotenv(ENV_FILE)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY が .env に見つかりません")

# ─────────────────────────────────────────
# 翻訳対象の動画リスト
# ─────────────────────────────────────────
VIDEOS = [
    ("x5OO58mEjyk", "抹茶"),
    ("Z5pYZbxTq4c", "ゼリー"),
    ("J2lXLa4hbZE", "たいやき"),
    ("ZhFmfN_imsc",  "キウイ"),
    ("CFC8Ht8xuDQ", "マーブルチョコ"),
    ("IYTQpaZG0i4", "ドーナツ"),
    ("hOqpOQsA4ok", "チョコケーキ"),
    ("dnvidnKDk_Y", "プリン"),
    ("ACs59Jz0_vY", "パイナップル"),
    ("9Tv4XULyruA", "おいも"),
    ("jJMV-LLOp7I", "クレープ"),
    ("z8u5vBWYBIY", "スイカ"),
    ("1oA9MQGGtzY", "プレッツェル"),
    ("7--0DJbxMbM", "コロネ"),
    ("g4fHt9773fc", "イチゴ"),
    ("jAVL2Sdn1cg", "お団子"),
    ("w7H_UunwfM4", "パンケーキ"),
    ("rBih9Y4V8Fk", "ワッフル"),
    ("9CFASV-S1J4", "バナナ"),
    ("XEkC_hCAbEY", "りんご"),
]

# ─────────────────────────────────────────
# Google OAuth 認証
# ─────────────────────────────────────────
SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]

def get_youtube_client():
    creds = None

    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CLIENT_SECRET), SCOPES)
            creds = flow.run_local_server(port=0)

        TOKEN_FILE.write_text(creds.to_json())
        print("  ✅ Google認証完了・トークン保存")

    return build("youtube", "v3", credentials=creds)

# ─────────────────────────────────────────
# 動画の日本語タイトル・説明を取得
# ─────────────────────────────────────────
def get_jp_content(youtube, video_id):
    res = youtube.videos().list(
        part="snippet",
        id=video_id
    ).execute()

    if not res.get("items"):
        return "", ""

    snippet = res["items"][0]["snippet"]
    title = snippet.get("title", "")
    desc  = snippet.get("description", "")
    return title, desc

# ─────────────────────────────────────────
# OpenAI で英語翻訳
# ─────────────────────────────────────────
SYSTEM_PROMPT = """\
You are the English translator for the YouTube channel "ゆる朝カフェのすみっこ" (Yuru Asa Cafe no Sumikko).
Translate the Japanese title and description into English.

━━━━━━━━━━━━━━━━━━━━━━━
CHANNEL CONCEPT
━━━━━━━━━━━━━━━━━━━━━━━
A cozy BGM channel where a tiny fairy guides you through the world of delicious Japanese sweets.
Soft jazz plays quietly in the corner of a relaxed morning café.
The mood is warm, gentle, and poetic — like a slow morning you never want to rush.

━━━━━━━━━━━━━━━━━━━━━━━
TRANSLATION RULES
━━━━━━━━━━━━━━━━━━━━━━━
1. Do NOT translate literally. Adapt into natural, poetic English.
   - Use sensory imagery: taste, texture, warmth, light, sound
   - Draw on cozy English-speaking café culture (slow living, cottagecore aesthetics)
   - Write like a short poem or a hand-written café menu — not a textbook

2. TITLE:
   - Keep all original emojis
   - Format: [emoji] [Food name] Jazz for [Mood/Use] [emoji] [Vibe phrase] | 1 Hour
   - Example: "🫐 Blueberry Jam Jazz for Morning Focus ☕ Cozy Toast Café | 1 Hour"

3. DESCRIPTION — follow this structure exactly:

   [LINE A — copy verbatim]
   This channel lets you explore delicious and sweet Japanese foods together with a tiny fairy.

   [LINE B — copy verbatim]
   Subscribe here 👉https://www.youtube.com/channel/UCjaEFXP9cDVPOMv-5xGfk7g?sub_confirmation=1

   [LINE C — adapt emoji and food to match current video, keep the structure]
   🍰 This is gentle jazz
   softly flowing in the corner of a relaxed morning café ☕️

   [POETIC PARAGRAPH — 3 to 5 lines, unique to each food]
   Write an original poetic passage about the specific food in this video.
   Describe how it looks, how it tastes, and the quiet feeling it brings on a slow morning.
   Use imagery that an English-speaking audience would find warm and relatable.

   [LINE D — adapt slightly to match the food's mood]
   Perfect for work, morning routines, getting ready, or reading —
   a playlist for mornings you want to start properly and with intention.

   [LINE E — copy verbatim]
   🎧 Perfect for

   Morning work or desk tasks
   Makeup and getting ready
   A slow, relaxed breakfast
   Resetting your mood

   [LINE F — copy verbatim]
   We'll be waiting for you again,
   right here in the cozy corner.

   [HASHTAGS]
   - Always include: #morningjazz #focusjazz #workbgm #jazzplaylist #relaxingjazz #backgroundmusic #slowmorning #cozycafe
   - Add 2–3 food-specific English hashtags (e.g. #matchaicecream #greentea)

━━━━━━━━━━━━━━━━━━━━━━━
OUTPUT FORMAT (strictly follow — no extra text)
━━━━━━━━━━━━━━━━━━━━━━━
TITLE: [English title here]
DESCRIPTION:
[Full English description here]
END_DESCRIPTION\
"""

def translate_with_openai(client, jp_title, jp_desc):
    user_msg = f"日本語タイトル:\n{jp_title}\n\n日本語概要欄:\n{jp_desc}"

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_msg},
        ],
        temperature=0.7,
    )

    text = response.choices[0].message.content.strip()

    # パース
    import re
    title_m = re.search(r"TITLE:\s*\n?(.+)", text)
    desc_m  = re.search(r"DESCRIPTION:\s*\n(.*?)(?:END_DESCRIPTION|$)", text, re.DOTALL)

    if not title_m or not desc_m:
        print(f"  ❌ パース失敗。返答:\n{text[:300]}")
        return None, None

    en_title = title_m.group(1).strip()
    en_desc  = desc_m.group(1).strip()
    return en_title, en_desc

# ─────────────────────────────────────────
# YouTubeに英語翻訳を書き込む
# ─────────────────────────────────────────
def delete_auto_en_caption(youtube, video_id):
    """自動生成の英語字幕を削除"""
    try:
        res = youtube.captions().list(part="snippet", videoId=video_id).execute()
        for cap in res.get("items", []):
            if (cap["snippet"].get("language", "").startswith("en") and
                    cap["snippet"].get("trackKind") == "asr"):
                youtube.captions().delete(id=cap["id"]).execute()
                print(f"  → 自動字幕削除OK")
                return True
        print("  → 自動字幕なし")
        return True
    except Exception as e:
        print(f"  → 字幕削除スキップ: {e}")
        return True


def upload_translation(youtube, video_id, en_title, en_desc):
    # 現在の情報を取得
    res = youtube.videos().list(
        part="localizations,snippet",
        id=video_id
    ).execute()

    if not res.get("items"):
        print("  ❌ 動画が見つかりません")
        return False

    item = res["items"][0]
    snippet = item.get("snippet", {})
    localizations = item.get("localizations", {})

    # 英語翻訳を追加
    localizations["en"] = {
        "title":       en_title,
        "description": en_desc,
    }

    # Step1: defaultLanguageが未設定なら先にsnippetだけ更新
    if not snippet.get("defaultLanguage"):
        youtube.videos().update(
            part="snippet",
            body={
                "id": video_id,
                "snippet": {
                    "title":           snippet.get("title", ""),
                    "description":     snippet.get("description", ""),
                    "categoryId":      snippet.get("categoryId", "10"),
                    "defaultLanguage": "ja",
                },
            }
        ).execute()
        print("  → defaultLanguage=ja を設定")

    # Step2: localizationsだけを単独で更新（snippetと同時にしない）
    youtube.videos().update(
        part="localizations",
        body={
            "id":            video_id,
            "localizations": localizations,
        }
    ).execute()

    return True

# ─────────────────────────────────────────
# メイン
# ─────────────────────────────────────────
def main():
    print("=" * 50)
    print("YouTube 自動翻訳（API版）")
    print("=" * 50)

    print("\nGoogle認証中...")
    youtube = get_youtube_client()
    print("✅ YouTube API 接続OK")

    openai_client = OpenAI(api_key=OPENAI_API_KEY)
    print("✅ OpenAI API 接続OK")

    results = {}

    for video_id, label in VIDEOS:
        print(f"\n{'='*40}")
        print(f"[>>] {label} ({video_id})")

        try:
            # Step1: JP取得
            print("  Step1: JP取得...")
            jp_title, jp_desc = get_jp_content(youtube, video_id)
            if not jp_title:
                results[label] = "❌ JP取得失敗"
                continue
            print(f"  JP: {jp_title[:40]}")

            # Step2: OpenAI翻訳
            print("  Step2: OpenAI翻訳...")
            en_title, en_desc = translate_with_openai(openai_client, jp_title, jp_desc)
            if not en_title:
                results[label] = "❌ 翻訳失敗"
                continue
            print(f"  EN: {en_title[:50]}")

            # Step3: 自動字幕を削除
            print("  Step3: 自動字幕削除...")
            delete_auto_en_caption(youtube, video_id)

            # Step4: YouTube APIで書き込み
            print("  Step4: YouTubeに書き込み...")
            ok = upload_translation(youtube, video_id, en_title, en_desc)
            if ok:
                print("  ✅ 完了！")
                results[label] = "✅"
            else:
                results[label] = "❌ 書き込み失敗"

            time.sleep(1)  # API制限対策

        except Exception as e:
            print(f"  ❌ エラー: {e}")
            results[label] = f"❌ {str(e)[:40]}"

    print("\n" + "=" * 50)
    print("完了！結果:")
    for label, status in results.items():
        print(f"  {status}  {label}")


if __name__ == "__main__":
    main()
