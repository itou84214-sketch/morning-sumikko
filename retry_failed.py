#!/usr/bin/env python3
"""Retry failed videos: イチゴ・バナナ・りんご"""
import os, re, time
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from yt_translate_api import SYSTEM_PROMPT, delete_auto_en_caption

BASE_DIR      = Path(os.getenv("BGM_BASE_DIR") or Path(__file__).resolve().parent)
ENV_FILE      = BASE_DIR / ".claude" / ".env"
CLIENT_SECRET = BASE_DIR / ".claude" / "client_secret.json"
TOKEN_FILE    = BASE_DIR / ".claude" / "token.json"

load_dotenv(ENV_FILE)
SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]

RETRY_VIDEOS = [
    ("g4fHt9773fc", "イチゴ"),
    ("9CFASV-S1J4", "バナナ"),
    ("XEkC_hCAbEY", "りんご"),
]

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

youtube = get_youtube()
client  = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

for video_id, label in RETRY_VIDEOS:
    print(f"\n[>>] {label} ({video_id})")
    try:
        # JP取得
        res = youtube.videos().list(part="snippet,localizations", id=video_id).execute()
        item    = res["items"][0]
        snippet = item["snippet"]
        jp_title = snippet["title"]
        jp_desc  = snippet["description"]
        print(f"  JP: {jp_title[:50]}")
        print(f"  defaultLanguage: {snippet.get('defaultLanguage', '未設定')}")

        # 翻訳
        resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"日本語タイトル:\n{jp_title}\n\n日本語概要欄:\n{jp_desc}"},
            ],
            temperature=0.7,
        )
        text = resp.choices[0].message.content.strip()
        title_m = re.search(r"TITLE:\s*\n?(.+)", text)
        desc_m  = re.search(r"DESCRIPTION:\s*\n(.*?)(?:END_DESCRIPTION|$)", text, re.DOTALL)
        en_title = title_m.group(1).strip() if title_m else None
        en_desc  = desc_m.group(1).strip()  if desc_m  else None
        print(f"  EN: {en_title}")

        # 自動字幕削除
        delete_auto_en_caption(youtube, video_id)

        # snippet + localizations を1回のAPIコールでまとめて送る
        localizations = item.get("localizations", {})
        localizations["en"] = {"title": en_title, "description": en_desc}
        youtube.videos().update(
            part="localizations,snippet",
            body={
                "id": video_id,
                "snippet": {
                    "title":           snippet["title"],
                    "description":     snippet["description"],
                    "categoryId":      snippet.get("categoryId", "10"),
                    "defaultLanguage": "ja",
                },
                "localizations": localizations,
            }
        ).execute()
        print("  ✅ 完了！")

    except Exception as e:
        print(f"  ❌ エラー: {e}")
