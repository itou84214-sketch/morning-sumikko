#!/usr/bin/env python3
"""1本だけテスト：翻訳内容と書き込み結果を確認"""

import os, re
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

BASE_DIR      = Path(os.getenv("BGM_BASE_DIR") or Path(__file__).resolve().parent)
ENV_FILE      = BASE_DIR / ".claude" / ".env"
CLIENT_SECRET = BASE_DIR / ".claude" / "client_secret.json"
TOKEN_FILE    = BASE_DIR / ".claude" / "token.json"
REF_FILE      = BASE_DIR / ".claude" / "reference_yt_title_description.md"

load_dotenv(ENV_FILE)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]

def get_youtube():
    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET), SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_FILE.write_text(creds.to_json())
    return build("youtube", "v3", credentials=creds)

# ── テスト対象（抹茶） ──
VIDEO_ID = "x5OO58mEjyk"

youtube = get_youtube()
client  = OpenAI(api_key=OPENAI_API_KEY)

# ── Step1: JP取得 ──
print("=== Step1: JP取得 ===")
res = youtube.videos().list(part="snippet,localizations", id=VIDEO_ID).execute()
item    = res["items"][0]
snippet = item["snippet"]
jp_title = snippet["title"]
jp_desc  = snippet["description"]
print(f"JP タイトル: {jp_title}")
print(f"現在のlocalizations: {list(item.get('localizations', {}).keys())}")

# ── Step2: OpenAI翻訳 ──
print("\n=== Step2: OpenAI翻訳 ===")
from yt_translate_api import SYSTEM_PROMPT
system = SYSTEM_PROMPT
user_msg = f"日本語タイトル:\n{jp_title}\n\n日本語概要欄:\n{jp_desc}"

response = client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {"role": "system", "content": system},
        {"role": "user",   "content": user_msg},
    ]
)
text = response.choices[0].message.content.strip()
print("OpenAI返答全文:")
print(text)
print()

title_m = re.search(r"TITLE:\s*\n?(.+)", text)
desc_m  = re.search(r"DESCRIPTION:\s*\n(.*?)(?:END_DESCRIPTION|$)", text, re.DOTALL)
en_title = title_m.group(1).strip() if title_m else None
en_desc  = desc_m.group(1).strip()  if desc_m  else None
print(f"パース結果 タイトル: {en_title}")
print(f"パース結果 説明(先頭): {(en_desc or '')[:80]}")

if not en_title or not en_desc:
    print("❌ パース失敗。終了")
    exit()

# ── Step3: 書き込み ──
print("\n=== Step3: YouTube APIに書き込み ===")
localizations = item.get("localizations", {})
localizations["en"] = {"title": en_title, "description": en_desc}

# defaultLanguageが未設定なら先にsnippetだけ更新
if not snippet.get("defaultLanguage"):
    youtube.videos().update(
        part="snippet",
        body={
            "id": VIDEO_ID,
            "snippet": {
                "title":           snippet["title"],
                "description":     snippet["description"],
                "categoryId":      snippet.get("categoryId", "10"),
                "defaultLanguage": "ja",
            },
        }
    ).execute()
    print("  → defaultLanguage=ja を設定")

# localizationsだけを単独更新
youtube.videos().update(
    part="localizations",
    body={
        "id":            VIDEO_ID,
        "localizations": localizations,
    }
).execute()

print("書き込み完了！")

# ── Step4: 書き込み確認（読み返し） ──
print("\n=== Step4: 書き込み確認 ===")
verify = youtube.videos().list(part="localizations", id=VIDEO_ID).execute()
saved = verify["items"][0].get("localizations", {})
print(f"保存されたlocalizations keys: {list(saved.keys())}")
if "en" in saved:
    print(f"英語タイトル: {saved['en'].get('title')}")
    print(f"英語説明(先頭): {saved['en'].get('description','')[:80]}")
else:
    print("❌ 'en' が保存されていない！")
