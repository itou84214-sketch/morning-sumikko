#!/usr/bin/env python3
"""
Add Korean (ko) and Traditional Chinese (zh-Hant) translations
to all 22 videos.
"""
import os, re, sys, time
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

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

load_dotenv(ENV_FILE)
SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]

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
    ("qBx2gy0_tgk", "ピーナッツ"),
    ("f7PTGTrQgyA", "カップケーキ"),
]

SYSTEM_PROMPT_KO = """\
You are the Korean translator for the YouTube channel "ゆる朝カフェのすみっこ" (유루 아사 카페의 구석).
Translate the Japanese title and description into natural, warm Korean.

CHANNEL CONCEPT:
A cozy BGM channel where a tiny fairy guides you through the world of delicious Japanese sweets.
Soft jazz plays quietly in the corner of a relaxed morning café.
The mood is warm, gentle, and poetic — like a slow morning you never want to rush.

TRANSLATION RULES:
1. Do NOT translate literally. Adapt into natural, poetic Korean.
   - Use warm, soft expressions common in Korean café / slow-life culture
   - The tone should feel like a handwritten café menu or a short poem
   - Avoid stiff or formal language — keep it cozy and inviting

2. TITLE:
   - Keep all original emojis
   - Format: [emoji] [Food name] [mood/activity] 재즈 플레이리스트 [emoji] [vibe phrase] | 1시간
   - Example: "🫐 블루베리잼 향기를 맡으며 듣는 아침 재즈 플레이리스트 ☕ 카페 구석 | 1시간"

3. DESCRIPTION — follow this structure exactly:

   [LINE A — translate naturally]
   이 채널은 작은 요정과 함께 맛있고 달콤한 일본 음식의 세계를 여행하는 BGM 채널입니다.

   [LINE B — copy verbatim]
   구독하기 👉https://www.youtube.com/channel/UCjaEFXP9cDVPOMv-5xGfk7g?sub_confirmation=1

   [LINE C — adapt emoji and food to match current video]
   🍰 따뜻한 재즈가
   느긋한 아침 카페 구석에 조용히 흐릅니다 ☕️

   [POETIC PARAGRAPH — 3 to 5 lines, unique to each food]
   Write an original poetic passage in Korean about the specific food in this video.
   Describe how it looks, tastes, and the quiet feeling it brings on a slow morning.

   [LINE D — adapt slightly to match the food's mood]
   작업, 아침 루틴, 준비, 독서 등
   제대로 시작하고 싶은 아침 시간에 함께하세요.

   [LINE E — copy verbatim]
   🎧 이런 순간에

   아침 작업이나 책상 앞에서
   메이크업이나 외출 준비
   느긋한 아침 식사
   기분을 전환하고 싶을 때

   [LINE F — copy verbatim]
   또 기다리고 있을게요,
   카페의 아늑한 구석에서.

   [HASHTAGS]
   - Always include: #아침재즈 #집중재즈 #작업BGM #재즈플레이리스트 #릴렉싱재즈 #배경음악 #느긋한아침 #카페BGM
   - Add 2-3 food-specific Korean hashtags

OUTPUT FORMAT (strictly follow):
TITLE: [Korean title here]
DESCRIPTION:
[Full Korean description here]
END_DESCRIPTION\
"""

SYSTEM_PROMPT_ZH = """\
You are the Traditional Chinese translator for the YouTube channel "ゆる朝カフェのすみっこ" (悠閒早晨咖啡廳的角落).
Translate the Japanese title and description into natural, warm Traditional Chinese (zh-Hant, Taiwan style).

CHANNEL CONCEPT:
A cozy BGM channel where a tiny fairy guides you through the world of delicious Japanese sweets.
Soft jazz plays quietly in the corner of a relaxed morning café.
The mood is warm, gentle, and poetic — like a slow morning you never want to rush.

TRANSLATION RULES:
1. Do NOT translate literally. Adapt into natural, poetic Traditional Chinese.
   - Use warm, inviting expressions common in Taiwanese café / slow-life culture
   - The tone should feel like a handwritten café menu or a short poem
   - Use Traditional Chinese characters (繁體中文), Taiwan usage preferred

2. TITLE:
   - Keep all original emojis
   - Format: [emoji] [Food name] 一邊[activity]一邊聆聽的爵士樂播放清單 [emoji] [vibe phrase] | 1小時
   - Example: "🫐 一邊品嚐藍莓果醬一邊聆聽的晨間爵士樂 ☕ 咖啡廳的角落 | 1小時"

3. DESCRIPTION — follow this structure exactly:

   [LINE A — translate naturally]
   這個頻道是與小精靈一起探索美味甜蜜的日本食物世界的 BGM 頻道。

   [LINE B — copy verbatim]
   訂閱頻道 👉https://www.youtube.com/channel/UCjaEFXP9cDVPOMv-5xGfk7g?sub_confirmation=1

   [LINE C — adapt emoji and food to match current video]
   🍰 這是輕柔的爵士樂
   靜靜地流淌在悠閒早晨咖啡廳的角落 ☕️

   [POETIC PARAGRAPH — 3 to 5 lines, unique to each food]
   Write an original poetic passage in Traditional Chinese about the specific food in this video.
   Describe how it looks, tastes, and the quiet feeling it brings on a slow morning.

   [LINE D — adapt slightly to match the food's mood]
   適合工作、晨間例行、準備出門或閱讀——
   想要認真而從容地開始的早晨時光。

   [LINE E — copy verbatim]
   🎧 適合這些時刻

   早晨工作或在書桌前
   化妝或準備出門
   悠閒享用早餐
   想要轉換心情的時候

   [LINE F — copy verbatim]
   我們會在這裡等你，
   就在咖啡廳溫馨的角落。

   [HASHTAGS]
   - Always include: #晨間爵士 #專注爵士 #工作BGM #爵士播放清單 #放鬆爵士 #背景音樂 #慢節奏早晨 #咖啡廳BGM
   - Add 2-3 food-specific Traditional Chinese hashtags

OUTPUT FORMAT (strictly follow):
TITLE: [Traditional Chinese title here]
DESCRIPTION:
[Full Traditional Chinese description here]
END_DESCRIPTION\
"""

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

def translate(client, system_prompt, jp_title, jp_desc):
    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"日本語タイトル:\n{jp_title}\n\n日本語概要欄:\n{jp_desc}"},
        ],
        temperature=0.7,
    )
    text = resp.choices[0].message.content.strip()
    title_m = re.search(r"TITLE:\s*\n?(.+)", text)
    desc_m  = re.search(r"DESCRIPTION:\s*\n(.*?)(?:END_DESCRIPTION|$)", text, re.DOTALL)
    title = title_m.group(1).strip() if title_m else None
    desc  = desc_m.group(1).strip()  if desc_m  else None
    return title, desc

youtube = get_youtube()
client  = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

results = {}

for video_id, label in VIDEOS:
    print(f"\n[>>] {label} ({video_id})")
    try:
        res = youtube.videos().list(part="snippet,localizations", id=video_id).execute()
        item    = res["items"][0]
        snippet = item["snippet"]
        jp_title = snippet["title"]
        jp_desc  = snippet["description"]
        print(f"  JP: {jp_title[:50]}")

        localizations = item.get("localizations", {})

        # Korean
        print("  translating KO...")
        ko_title, ko_desc = translate(client, SYSTEM_PROMPT_KO, jp_title, jp_desc)
        if ko_title:
            localizations["ko"] = {"title": ko_title, "description": ko_desc}
            print(f"  KO: {ko_title[:50]}")
        else:
            print("  KO: parse failed")

        time.sleep(1)

        # Traditional Chinese
        print("  translating ZH-HANT...")
        zh_title, zh_desc = translate(client, SYSTEM_PROMPT_ZH, jp_title, jp_desc)
        if zh_title:
            localizations["zh-Hant"] = {"title": zh_title, "description": zh_desc}
            print(f"  ZH: {zh_title[:50]}")
        else:
            print("  ZH: parse failed")

        # Upload all localizations at once
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
        print("  done!")
        results[label] = "OK"

        time.sleep(2)

    except Exception as e:
        print(f"  ERROR: {e}")
        results[label] = f"ERROR: {str(e)[:60]}"

print("\n" + "=" * 50)
print("Results:")
for label, status in results.items():
    mark = "OK" if status == "OK" else "NG"
    print(f"  [{mark}] {label}  {status}")
