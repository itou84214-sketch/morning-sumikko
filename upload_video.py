#!/usr/bin/env python3
"""
YouTube video uploader
Usage: python upload_video.py
Edit the CONFIG section below before running.
"""
import os, sys, time
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

BASE_DIR      = Path(os.getenv("BGM_BASE_DIR") or Path(__file__).resolve().parent)
CLIENT_SECRET = BASE_DIR / ".claude" / "client_secret.json"
TOKEN_FILE    = BASE_DIR / ".claude" / "token.json"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload",
          "https://www.googleapis.com/auth/youtube.force-ssl"]

# ============================================================
# CONFIG -- ここを編集してから実行
# ============================================================
VIDEO_FILE   = str(BASE_DIR / "026.mp4")          # アップロードする動画ファイル
THUMBNAIL    = ""                                  # サムネ画像パス（不要なら空文字）

TITLE        = "🍪クッキーをサクサクかじりながら聴きたいジャズプレイリスト【朝活・作業用・1時間】"
DESCRIPTION  = """\
#クッキー #スイーツ #作業用BGM
ゆる朝カフェのすみっこで
静かに流れているジャズです☕️

サクサクのクッキーを
ひとつずつかじりつつ
バターの香りにほっとする朝の時間。

作業・朝活・身支度・読書など、
ゆっくり始めたい時間にどうぞ。


---

🎧 こんなときに
・朝の作業やデスクワーク
・メイクや身支度の時間
・ゆっくり朝ごはんを食べたいとき
・静かに集中したいとき

---

また、すみっこでお待ちしています。



#ゆる朝 #朝活 #作業用BGM
#ジャズ #リラックス #スイーツ #クッキー
#メイキングイラスト #焼き菓子 #ほっこり
#ながら聴き  #すみっこ
"""

TAGS         = ["ジャズ", "作業用BGM", "朝活", "リラックス", "クッキー", "jazz", "bgm", "lofi"]
CATEGORY_ID  = "10"        # 10 = Music
PRIVACY      = "private"   # "private" / "unlisted" / "public"
# ============================================================

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

def upload_video(youtube):
    if not os.path.exists(VIDEO_FILE):
        print(f"ERROR: video file not found: {VIDEO_FILE}")
        return None

    file_mb = os.path.getsize(VIDEO_FILE) / 1024 / 1024
    print(f"Uploading: {os.path.basename(VIDEO_FILE)} ({file_mb:.1f}MB)")
    print(f"Title: {TITLE}")
    print(f"Privacy: {PRIVACY}")
    print()

    body = {
        "snippet": {
            "title":       TITLE,
            "description": DESCRIPTION,
            "tags":        TAGS,
            "categoryId":  CATEGORY_ID,
            "defaultLanguage": "ja",
        },
        "status": {
            "privacyStatus": PRIVACY,
        },
    }

    media = MediaFileUpload(
        VIDEO_FILE,
        mimetype="video/mp4",
        resumable=True,
        chunksize=10 * 1024 * 1024,  # 10MB chunks
    )

    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            pct = int(status.progress() * 100)
            print(f"  uploading... {pct}%", end="\r")

    video_id = response["id"]
    print(f"\n  upload done! video ID: {video_id}")
    print(f"  URL: https://www.youtube.com/watch?v={video_id}")
    return video_id

def set_thumbnail(youtube, video_id):
    if not THUMBNAIL or not os.path.exists(THUMBNAIL):
        print("  thumbnail: skipped")
        return
    ext = Path(THUMBNAIL).suffix.lower()
    mime = {"jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}.get(ext, "image/jpeg")
    youtube.thumbnails().set(
        videoId=video_id,
        media_body=MediaFileUpload(THUMBNAIL, mimetype=mime),
    ).execute()
    print(f"  thumbnail: set ({os.path.basename(THUMBNAIL)})")

def main():
    print("=" * 50)
    print("YouTube Video Uploader")
    print("=" * 50)

    youtube = get_youtube()
    print("Google auth OK\n")

    video_id = upload_video(youtube)
    if not video_id:
        return

    set_thumbnail(youtube, video_id)

    print(f"\ndone!")
    print(f"  video ID : {video_id}")
    print(f"  privacy  : {PRIVACY}")
    print(f"  URL      : https://www.youtube.com/watch?v={video_id}")
    print()
    print("Next steps:")
    print("  1. YouTube Studioで内容を確認")
    print("  2. 多言語翻訳: translate_all_langs.py に video_id を追加して実行")
    print("  3. 公開設定を変更して投稿")

if __name__ == "__main__":
    main()
