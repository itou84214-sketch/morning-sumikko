#!/usr/bin/env python3
"""
Translate all 27 videos into all target languages.
Skips languages already present. Verifies at the end.
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

# Target languages (ja/en/ko/zh-Hant already done)
TARGET_LANGS = [
    ("zh-Hans", "Simplified Chinese / 简体中文 (mainland China, warm and natural)"),
    ("zh-HK",   "Traditional Chinese / 繁體中文 (Hong Kong style, warm and natural)"),
    ("no",      "Norwegian Bokmål (warm and natural, café atmosphere)"),
    ("fr",      "French (warm, poetic, café-style)"),
    ("fi",      "Finnish (warm and natural, slow morning feel)"),
    ("de",      "German (warm, cozy, Gemütlichkeit atmosphere)"),
    ("es",      "Spanish (warm, natural, Latin American style)"),
    ("sv",      "Swedish (warm and natural, lagom slow morning feel)"),
    ("nl",      "Dutch (warm and natural, café atmosphere)"),
    ("it",      "Italian (warm, poetic, café-style)"),
    ("ar",      "Arabic / العربية (Modern Standard Arabic, warm and inviting)"),
    ("da",      "Danish (warm and natural, hygge atmosphere)"),
]

# Already-done language codes (prefix match)
DONE_PREFIXES = ["ja", "en", "ko", "zh-Hant", "zh_TW", "zh_HK"]

SYSTEM_PROMPT = """\
You are the translator for the YouTube channel "ゆる朝カフェのすみっこ" (Cozy Morning Café Corner).
Translate the Japanese video title and description into the target language specified by the user.

CHANNEL CONCEPT:
A cozy BGM channel where a tiny fairy guides listeners through the world of delicious Japanese sweets.
Soft jazz plays quietly in the corner of a relaxed morning café.
The mood is warm, gentle, and poetic — like a slow morning you never want to rush.

TRANSLATION RULES:
1. Do NOT translate literally. Adapt into natural, poetic language appropriate for the target culture.
   - Use sensory imagery: taste, texture, warmth, light, sound
   - Draw on local café / slow morning culture of the target language region
   - Write like a short poem or a hand-written café menu

2. TITLE:
   - Keep all original emojis
   - Adapt the food name and mood naturally into the target language
   - Keep it concise and inviting
   - End with | 1 [hour word in target language] or equivalent

3. DESCRIPTION — follow this structure:

   [LINE A] Introduce the channel warmly (tiny fairy + Japanese sweets world)
   [LINE B — copy verbatim] Subscribe here 👉https://www.youtube.com/channel/UCjaEFXP9cDVPOMv-5xGfk7g?sub_confirmation=1
   [LINE C] Gentle jazz flowing in the corner of a relaxed morning café ☕️
   [POETIC PARAGRAPH] 3-5 lines about the specific food — sensory, poetic, warm
   [LINE D] Perfect for work, morning routines, getting ready, reading — adapt slightly to food mood
   [LINE E] 🎧 Perfect for / Morning work or desk tasks / Makeup and getting ready / A slow breakfast / Resetting your mood
   [LINE F] Closing warm farewell — waiting here in the cozy corner
   [HASHTAGS] 6-8 relevant hashtags in the target language + 2-3 food-specific ones

OUTPUT FORMAT (strictly follow — no extra text):
TITLE: [title in target language]
DESCRIPTION:
[full description in target language]
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

def translate(client, lang_desc, jp_title, jp_desc):
    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content":
                f"Target language: {lang_desc}\n\n"
                f"Japanese title:\n{jp_title}\n\n"
                f"Japanese description:\n{jp_desc}"},
        ],
        temperature=0.7,
    )
    text = resp.choices[0].message.content.strip()
    title_m = re.search(r"TITLE:\s*\n?(.+)", text)
    desc_m  = re.search(r"DESCRIPTION:\s*\n(.*?)(?:END_DESCRIPTION|$)", text, re.DOTALL)
    t = title_m.group(1).strip() if title_m else None
    d = desc_m.group(1).strip()  if desc_m  else None
    return t, d

def lang_already_done(existing_keys, lang_code):
    # Check if this lang code (or a variant) is already in localizations
    code_base = lang_code.lower().replace("-", "_")
    for k in existing_keys:
        k_base = k.lower().replace("-", "_")
        if k_base == code_base or k_base.startswith(code_base.split("_")[0] + "_"):
            # Special case: zh variants must match exactly
            if lang_code.startswith("zh"):
                if k_base == code_base:
                    return True
            else:
                return True
    return False

def fetch_all_videos(youtube):
    videos = []
    next_page = None
    while True:
        res = youtube.search().list(
            part="snippet", forMine=True, type="video",
            maxResults=50, pageToken=next_page,
        ).execute()
        for item in res.get("items", []):
            videos.append((item["id"]["videoId"], item["snippet"]["title"]))
        next_page = res.get("nextPageToken")
        if not next_page:
            break
    return videos

youtube = get_youtube()
client  = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

print("Fetching all videos from channel...")
all_videos = fetch_all_videos(youtube)
print(f"Total: {len(all_videos)} videos\n")

results = {}  # video_label -> {lang: "ok"/"skip"/"error"}

for i, (video_id, title_preview) in enumerate(all_videos, 1):
    label = title_preview[:40]
    print(f"\n[{i}/{len(all_videos)}] {label}")
    results[video_id] = {"title": title_preview, "langs": {}}

    try:
        res = youtube.videos().list(part="snippet,localizations", id=video_id).execute()
        if not res.get("items"):
            print("  video not found, skipping")
            continue

        item    = res["items"][0]
        snippet = item["snippet"]
        jp_title = snippet["title"]
        jp_desc  = snippet["description"]
        localizations = item.get("localizations", {})
        existing_keys = list(localizations.keys())

        needs_update = False
        for lang_code, lang_desc in TARGET_LANGS:
            if lang_already_done(existing_keys, lang_code):
                print(f"  [{lang_code}] skip (already exists)")
                results[video_id]["langs"][lang_code] = "skip"
                continue

            print(f"  [{lang_code}] translating...")
            try:
                t, d = translate(client, lang_desc, jp_title, jp_desc)
                if t and d:
                    localizations[lang_code] = {"title": t, "description": d}
                    results[video_id]["langs"][lang_code] = "ok"
                    print(f"    -> {t[:55]}")
                    needs_update = True
                else:
                    results[video_id]["langs"][lang_code] = "parse_error"
                    print(f"    -> parse failed")
                time.sleep(1)
            except Exception as e:
                results[video_id]["langs"][lang_code] = f"error"
                print(f"    -> ERROR: {e}")
                time.sleep(2)

        if needs_update:
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
            print(f"  uploaded!")
            time.sleep(2)
        else:
            print(f"  no update needed")

    except Exception as e:
        print(f"  FATAL ERROR: {e}")
        results[video_id] = {"title": title_preview, "langs": {"_": "fatal_error"}}
        time.sleep(3)

# ======== Final verification ========
print("\n\n" + "=" * 60)
print("FINAL VERIFICATION")
print("=" * 60)

all_target_codes = [lc for lc, _ in TARGET_LANGS]
all_required = ["en", "ko", "zh-Hant"] + all_target_codes

missing_report = []
for video_id, title_preview in all_videos:
    res = youtube.videos().list(part="localizations", id=video_id).execute()
    if not res.get("items"):
        continue
    saved_keys = list(res["items"][0].get("localizations", {}).keys())
    missing = []
    for req in all_required:
        if not lang_already_done(saved_keys, req):
            missing.append(req)
    status = "OK" if not missing else f"MISSING: {missing}"
    print(f"  {title_preview[:45]:45} {status}")
    if missing:
        missing_report.append((title_preview[:45], missing))

print("\n" + "=" * 60)
if missing_report:
    print(f"Videos with missing languages: {len(missing_report)}")
    for t, m in missing_report:
        print(f"  {t}: {m}")
else:
    print("All videos fully translated!")
