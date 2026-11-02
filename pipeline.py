#!/usr/bin/env python3
"""
BGM Video Full Pipeline
Usage: python pipeline.py <food_name>
Example: python pipeline.py クッキー

Steps:
  1. Auto-detect next video number
  2. Edit video (freeze + reverse + normal + loop, 60min)
  3. Generate JP title & description with OpenAI
  4. Upload to YouTube
  5. Set thumbnail
  6. Schedule publish at 7:00 AM JST next available day
  7. Add 16-language translations
"""
import os, re, sys, time, math, random, tempfile, shutil, subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv
from openai import OpenAI
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# ─────────────────────────────────────────
# Paths
# ─────────────────────────────────────────
BASE_DIR      = Path(os.getenv("BGM_BASE_DIR") or Path(__file__).resolve().parent)
MAKING_DIR    = BASE_DIR / "メイキング"
ENV_FILE      = BASE_DIR / ".claude" / ".env"
CLIENT_SECRET = BASE_DIR / ".claude" / "client_secret.json"
TOKEN_FILE    = BASE_DIR / ".claude" / "token.json"
load_dotenv(ENV_FILE)

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]

FFMPEG  = "ffmpeg"
FFPROBE = "ffprobe"
# 本編の最低尺。これを超えた直後の「映像ループの切れ目」で終わる
MIN_BODY_SEC = 3600
TARGET_SEC   = 3600   # BGM生成の基準（実際の尺は実行時に決まる）

# 先頭に付けるオープニング（音声はオープニング自身のものを使う）
OPENING = BASE_DIR / "素材" / "オープニング.mp4"

PLAYLIST_ID = "PLLWUT1rrlxXiSue4X81ZGhoG9j-g6GhTf"  # ゆる朝BGMプレイリスト
FREEZE_DUR  = 2.0
REV_DUR     = 5.0
SAMPLE_N    = 150
FADE_DUR    = 12.0

# 静止区間カット: 描画が止まっている時間を自動で詰める
# mpdecimate が直前フレームとほぼ同一のフレームを落とす。
# 値を小さくするほど「同一」の判定が厳しくなり、描画を削るリスクが下がる。
CUT_STATIC   = True
DECIMATE_OPT = "hi=64*3:lo=64*2:frac=0.05"

JST = timezone(timedelta(hours=9))
PUBLISH_HOUR = 7  # 7:00 AM JST

# ─────────────────────────────────────────
# Prompts
# ─────────────────────────────────────────
JP_TITLE_DESC_PROMPT = """\
あなたはYouTubeチャンネル「ゆる朝カフェのすみっこ」の動画タイトルと概要欄を作成するアシスタントです。

チャンネルコンセプト:
朝の時間に合う、やさしいジャズBGMを中心に、作業用・朝活・リラックス用の音楽を配信するチャンネル。
小さな妖精がかわいい日本のスイーツの世界を案内してくれる、ゆるくてかわいい雰囲気。

━━━━━━━━━━━━━━━━━━━━━━━
参考例（このトーン・構成を必ず踏襲すること）
━━━━━━━━━━━━━━━━━━━━━━━

【例1】
🐟️たいやきをふわふわ食べながら聴きたいジャズプレイリスト【朝活・作業用・1時間】

チャンネル登録👉️https://www.youtube.com/channel/UCjaEFXP9cDVPOMv-5xGfk7g?sub_confirmation=1

X(Twitter)👉️https://x.com/su359n

ゆる朝カフェのすみっこで
静かに流れているジャズです☕️

サクふわアツアツのたいやきを
大胆にしっぽからパクっと食べつつ
あんこの甘さをゆっくり噛みしめる朝の時間。

まだシーンとした部屋で
たいやきと見つめ合う
そんな空気をイメージしています。

作業・朝活・身支度・読書など、
"眠いけどやらなきゃ"な時間にどうぞ。


---

🎧 こんなときに
・朝の作業やデスクワーク
・メイクや身支度の時間
・ゆっくり朝ごはんを食べたいとき
・静かに集中したいとき

---

また、すみっこでお待ちしています。



#ゆる朝 #朝活 #作業用BGM
#ジャズ #リラックス #スイーツ #たいやき
#メイキングイラスト #和菓子 #甘味
#つぶあん #小倉
#ながら聴き  #すみっこ

【例2】
🍩揚げたてドーナツをモフモフかじりながら流す静かなジャズプレイリスト☕【朝活・作業用・1時間】

チャンネル登録👉️https://www.youtube.com/channel/UCjaEFXP9cDVPOMv-5xGfk7g?sub_confirmation=1

X(Twitter)👉️https://x.com/su359n

ゆる朝カフェのすみっこで、
静かに流れているジャズです☕️

ちょっと高めなドーナツを食べながら、
ゆっくりはじまる朝の時間。

まだ少し眠たい部屋で、
無理せず整えていくような空気をイメージしています。

作業・朝活・身支度・読書など、
"眠いけどやらなきゃ"な時間にどうぞ。


---

🎧 こんなときに
・朝の作業やデスクワーク
・メイクや身支度の時間
・ゆっくり朝ごはんを食べたいとき
・静かに集中したいとき

---

また、すみっこでお待ちしています。



#ゆる朝 #朝活 #作業用BGM
#ジャズ #リラックス #スイーツ #ドーナツ
#メイキングイラスト #ながら聴き  #すみっこ

━━━━━━━━━━━━━━━━━━━━━━━
作成ルール
━━━━━━━━━━━━━━━━━━━━━━━
- 上記2例のトーン・文体・構成を忠実に踏襲すること
- タイトルは食べ物の食感・動作を擬音語で表現し、ジャズプレイリスト【朝活・作業用・<尺表記>】で締める
  <尺表記>はユーザー入力の「尺表記:」の値を一字一句そのまま使うこと。参考例の「1時間」は無視すること
- 概要欄は必ずチャンネル登録URLを2行目に入れること
- チャンネル登録URLの次の行に「X(Twitter)👉️https://x.com/su359n」を必ず入れること（URLは一字一句そのまま）
- 食べ物の食感・食べ方・香りなどを具体的に描写すること（直訳的・説明的にならないこと）
- "〇〇な時間にどうぞ"のキャッチフレーズは食べ物の雰囲気に合わせて変えること
- ハッシュタグは食べ物に関連する具体的なものを2〜3個追加すること

出力フォーマット（厳守・余分なテキスト不要）:
TITLE: [タイトル]
DESCRIPTION:
[概要欄全文]
END_DESCRIPTION\
"""

MULTILANG_SYSTEM_PROMPT = """\
You are the translator for the YouTube channel "ゆる朝カフェのすみっこ" (Cozy Morning Café Corner).
Translate the Japanese video title and description into the target language specified by the user.

CHANNEL CONCEPT:
A cozy BGM channel where a tiny fairy guides listeners through the world of delicious Japanese sweets.
Soft jazz plays quietly in the corner of a relaxed morning café.
The mood is warm, gentle, and poetic — like a slow morning you never want to rush.

TRANSLATION RULES:
1. Do NOT translate literally. Adapt into natural, poetic language appropriate for the target culture.
2. TITLE: Keep emojis, adapt food name and mood naturally, end with | <the duration phrase given in
   the user's DURATION NOTE, adapted naturally into the target language>. Never write a bare "1 Hour".
3. DESCRIPTION structure:
   [LINE A] Introduce channel warmly (tiny fairy + Japanese sweets world)
   [LINE B — verbatim] Subscribe here 👉https://www.youtube.com/channel/UCjaEFXP9cDVPOMv-5xGfk7g?sub_confirmation=1
   [LINE B2 — verbatim] X(Twitter)👉https://x.com/su359n
   [LINE C] Gentle jazz flowing in the corner of a relaxed morning café ☕️
   [POETIC PARAGRAPH] 3-5 lines about the specific food — sensory, poetic, warm
   [LINE D] Perfect for work / morning routines / getting ready / reading
   [LINE E] 🎧 Perfect for / Morning work / Makeup & getting ready / Slow breakfast / Resetting mood
   [LINE F] Warm closing farewell — waiting in the cozy corner
   [HASHTAGS] 6-8 relevant + 2-3 food-specific

OUTPUT FORMAT:
TITLE: [title]
DESCRIPTION:
[description]
END_DESCRIPTION\
"""

LANG_EN_PROMPT = """\
You are the English translator for the YouTube channel "ゆる朝カフェのすみっこ" (Yuru Asa Cafe no Sumikko).
Translate the Japanese title and description into English.

CHANNEL CONCEPT:
A cozy BGM channel where a tiny fairy guides you through the world of delicious Japanese sweets.
Soft jazz plays quietly in the corner of a relaxed morning café.

TRANSLATION RULES:
1. Do NOT translate literally. Adapt into natural, poetic English.
2. TITLE format: [emoji] [Food name] Jazz for [Mood/Use] [emoji] [Vibe phrase] | <duration phrase from
   the user's DURATION NOTE, e.g. "A Little Over 1 Hour">. Never write a bare "1 Hour".
3. DESCRIPTION structure:
   This channel lets you explore delicious and sweet Japanese foods together with a tiny fairy.
   Subscribe here 👉https://www.youtube.com/channel/UCjaEFXP9cDVPOMv-5xGfk7g?sub_confirmation=1
   X(Twitter)👉https://x.com/su359n
   🍰 This is gentle jazz / softly flowing in the corner of a relaxed morning café ☕️
   [POETIC PARAGRAPH about the food]
   Perfect for work, morning routines, getting ready, or reading —
   🎧 Perfect for / Morning work or desk tasks / Makeup and getting ready / A slow, relaxed breakfast / Resetting your mood
   We'll be waiting for you again, / right here in the cozy corner.
   [HASHTAGS] #morningjazz #focusjazz #workbgm #jazzplaylist #relaxingjazz #backgroundmusic #slowmorning #cozycafe + food hashtags

OUTPUT FORMAT:
TITLE: [title]
DESCRIPTION:
[description]
END_DESCRIPTION\
"""

LANGUAGES = [
    ("en",      LANG_EN_PROMPT, None),
    ("ko",      MULTILANG_SYSTEM_PROMPT, "Korean (자연스럽고 따뜻한 한국어)"),
    ("zh-Hant", MULTILANG_SYSTEM_PROMPT, "Traditional Chinese / 繁體中文 (Taiwan style)"),
    ("zh-Hans", MULTILANG_SYSTEM_PROMPT, "Simplified Chinese / 简体中文 (mainland China, warm and natural)"),
    ("zh-HK",   MULTILANG_SYSTEM_PROMPT, "Traditional Chinese / 繁體中文 (Hong Kong style)"),
    ("no",      MULTILANG_SYSTEM_PROMPT, "Norwegian Bokmål (warm and natural, café atmosphere)"),
    ("fr",      MULTILANG_SYSTEM_PROMPT, "French (warm, poetic, café-style)"),
    ("fi",      MULTILANG_SYSTEM_PROMPT, "Finnish (warm and natural, slow morning feel)"),
    ("de",      MULTILANG_SYSTEM_PROMPT, "German (warm, cozy, Gemütlichkeit atmosphere)"),
    ("es",      MULTILANG_SYSTEM_PROMPT, "Spanish (warm, natural, Latin American style)"),
    ("sv",      MULTILANG_SYSTEM_PROMPT, "Swedish (warm and natural, lagom slow morning feel)"),
    ("nl",      MULTILANG_SYSTEM_PROMPT, "Dutch (warm and natural, café atmosphere)"),
    ("it",      MULTILANG_SYSTEM_PROMPT, "Italian (warm, poetic, café-style)"),
    ("ar",      MULTILANG_SYSTEM_PROMPT, "Arabic / العربية (Modern Standard Arabic, warm and inviting)"),
    ("da",      MULTILANG_SYSTEM_PROMPT, "Danish (warm and natural, hygge atmosphere)"),
]

# ─────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────
def run(cmd):
    return subprocess.run(cmd, check=True, capture_output=True, encoding="utf-8", errors="ignore")

def get_duration(path):
    r = subprocess.run(
        [FFPROBE, "-v", "quiet", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, encoding="utf-8", errors="ignore")
    return float(r.stdout.strip())

def get_fps(path):
    r = subprocess.run(
        [FFPROBE, "-v", "quiet", "-select_streams", "v:0",
         "-show_entries", "stream=r_frame_rate",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, encoding="utf-8", errors="ignore")
    num, den = r.stdout.strip().split("/")
    return float(num) / float(den)

def detect_crop(path):
    r = subprocess.run(
        [FFMPEG, "-i", str(path), "-vf",
         "format=gray,lut=y='if(between(val,230,255),255,0)',cropdetect=limit=24:round=2:skip=2",
         "-t", "60", "-f", "null", "-"],
        capture_output=True, encoding="utf-8", errors="ignore")
    best = None
    for line in (r.stdout + r.stderr).splitlines():
        if "crop=" in line and "Parsed_cropdetect" in line:
            s = line[line.index("crop="):].split()[0]
            best = s
    if not best:
        return "crop=1148:646:387:246"
    parts = best.replace("crop=", "").split(":")
    w, h, x, y = int(parts[0]), int(parts[1]), int(parts[2]), int(parts[3])
    w16 = int(h * 16 / 9)
    x16 = max(0, x - (w16 - w) // 2)
    return f"crop={w16}:{h}:{x16}:{y}"

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

def next_available_7am_jst(youtube):
    """公開予約日時を決める。
    - 0:00〜6:59にアップ: 重複しない限り当日の朝7時
    - 7:00〜23:59にアップ: 翌日の朝7時
    いずれも直前動画と同日以前なら、重複を避けて翌日以降にずらす。
    """
    ch = youtube.channels().list(part="contentDetails", mine=True).execute()
    uploads_id = ch["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

    pl = youtube.playlistItems().list(
        part="snippet", playlistId=uploads_id, maxResults=1
    ).execute()
    last_video_id = pl["items"][0]["snippet"]["resourceId"]["videoId"]

    v = youtube.videos().list(part="status,snippet", id=last_video_id).execute()["items"][0]
    pub_at = v["status"].get("publishAt") or v["snippet"].get("publishedAt")
    last_date = datetime.fromisoformat(pub_at.replace("Z", "+00:00")).astimezone(JST).date()

    now = datetime.now(JST)
    # アップ時刻が朝7時より前なら当日、7時以降なら翌日を起点にする
    if now.hour < PUBLISH_HOUR:
        candidate_date = now.date()
    else:
        candidate_date = (now + timedelta(days=1)).date()
    # 直前動画と同日以前なら重複回避で翌日以降へずらす
    while candidate_date <= last_date:
        candidate_date += timedelta(days=1)

    candidate = datetime(candidate_date.year, candidate_date.month, candidate_date.day,
                         PUBLISH_HOUR, 0, 0, tzinfo=JST)

    print(f"  now: {now:%Y-%m-%d %H:%M} / last video: {last_date} → next: {candidate.date()}")
    return candidate.isoformat()

def sanitize_meta(text, limit):
    """YouTubeのメタデータ制約に合わせて整える。
    < > を含むと invalidVideoMetadata で弾かれるため置換し、文字数上限で切る。
    """
    t = text.replace("<", "(").replace(">", ")").strip()
    if len(t) > limit:
        t = t[:limit].rstrip()
    return t

def duration_phrases(total_sec):
    """実尺から日本語・英語の尺表記を作る。
    端数20分未満 → 「1時間ちょっと」、20〜49分 → 「1時間半」、50分以上 → 「1時間55分」。
    尺を多めに言わない（切り上げない）方針。
    """
    h = int(total_sec // 3600)
    m = int((total_sec % 3600) // 60)
    if h < 1:
        h, m = 1, 0
    plural = "s" if h > 1 else ""
    if m < 20:
        jp = f"{h}時間ちょっと"
        en = f"a little over {h} hour{plural}"
    elif m < 50:
        jp = f"{h}時間半"
        en = ("about an hour and a half" if h == 1
              else f"about {h} and a half hours")
    else:
        jp = f"{h}時間{m}分"
        en = f"about {h} hour{plural} {m} minutes"
    return jp, en

def duration_note(total_sec):
    """翻訳プロンプトに添える尺の注意書き。"""
    _, en = duration_phrases(total_sec)
    mins = int(round(total_sec / 60))
    return (f"DURATION NOTE: this video runs about {mins} minutes, i.e. {en}. "
            f"In the title use a phrase meaning '{en}' that sounds natural in the target language. "
            f"Do not write an exact '1 Hour'.")

def translate_text(client, system_prompt, user_content):
    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_content},
        ],
        temperature=0.7,
    )
    text = resp.choices[0].message.content.strip()
    title_m = re.search(r"TITLE:\s*\n?(.+)", text)
    desc_m  = re.search(r"DESCRIPTION:\s*\n(.*?)(?:END_DESCRIPTION|$)", text, re.DOTALL)
    t = title_m.group(1).strip() if title_m else None
    d = desc_m.group(1).strip()  if desc_m  else None
    return t, d

# ─────────────────────────────────────────
# Step 1: Detect next video number
# ─────────────────────────────────────────
def detect_next_number():
    existing = sorted([
        int(f.stem) for f in BASE_DIR.glob("???.mp4")
        if f.stem.isdigit()
    ])
    return (existing[-1] + 1) if existing else 1

# ─────────────────────────────────────────
# Step 2: Video editing
# ─────────────────────────────────────────
def create_edited_video(src, out, crop_str):
    total_dur = get_duration(src)
    fps = get_fps(src)
    total_frames = int(total_dur * fps)
    step = max(1, total_frames // SAMPLE_N)
    print(f"  source: {total_dur:.1f}s  {total_frames}f  fps={fps:.2f}")

    tmp = tempfile.mkdtemp()
    try:
        last_frame = os.path.join(tmp, "last.png")
        run([FFMPEG, "-y", "-sseof", "-3", "-i", str(src), "-vframes", "1",
             "-vf", crop_str + ",scale=1920:1080:flags=lanczos", last_frame])
        freeze = os.path.join(tmp, "freeze.mp4")
        run([FFMPEG, "-y", "-loop", "1", "-i", last_frame,
             "-t", str(FREEZE_DUR), "-vf", "fps=30",
             "-c:v", "libx264", "-preset", "fast", "-crf", "18",
             "-pix_fmt", "yuv420p", freeze])

        frames = []
        for i in range(SAMPLE_N - 1, -1, -1):
            t = (i * step) / fps
            fn = os.path.join(tmp, f"f{i:04d}.png")
            subprocess.run(
                [FFMPEG, "-y", "-ss", str(t), "-i", str(src), "-vframes", "1",
                 "-vf", crop_str + ",scale=1920:1080:flags=lanczos", fn],
                capture_output=True)
            if os.path.exists(fn):
                frames.append(fn)
        flist = os.path.join(tmp, "frames.txt")
        frame_dur = REV_DUR / len(frames)
        with open(flist, "w") as f:
            for fn in frames:
                f.write(f"file '{fn}'\nduration {frame_dur}\n")
        reverse = os.path.join(tmp, "reverse.mp4")
        run([FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", flist,
             "-vf", "fps=30", "-c:v", "libx264", "-preset", "fast", "-crf", "18",
             "-pix_fmt", "yuv420p", reverse])

        normal = os.path.join(tmp, "normal.mp4")
        if CUT_STATIC:
            # mpdecimate で静止フレームを落とし、setpts で詰め直す
            norm_vf = (crop_str + ",scale=1920:1080:flags=lanczos,"
                       f"mpdecimate={DECIMATE_OPT},setpts=N/FRAME_RATE/TB,fps=30")
        else:
            norm_vf = crop_str + ",scale=1920:1080:flags=lanczos,fps=30"
        run([FFMPEG, "-y", "-i", str(src),
             "-vf", norm_vf,
             "-c:v", "libx264", "-preset", "fast", "-crf", "18",
             "-pix_fmt", "yuv420p", "-an", normal])
        if CUT_STATIC:
            nd = get_duration(normal)
            print(f"  static-cut: {total_dur:.1f}s -> {nd:.1f}s "
                  f"({(1 - nd / total_dur) * 100:.0f}% cut)")

        concat_list = os.path.join(tmp, "concat.txt")
        with open(concat_list, "w") as f:
            f.write(f"file '{freeze}'\nfile '{reverse}'\nfile '{normal}'\nfile '{freeze}'\n")
        run([FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", concat_list,
             "-c:v", "libx264", "-preset", "fast", "-crf", "18",
             "-pix_fmt", "yuv420p", "-an", str(out)])

        dur = get_duration(out)
        print(f"  edited: {dur:.1f}s")
        return dur
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

def select_and_build_bgm(out_audio, target_sec=None):
    target = target_sec if target_sec else TARGET_SEC
    mp3s = [f for f in BASE_DIR.glob("*.mp3")]
    random.shuffle(mp3s)
    selected = []
    total = 0.0
    while total < target:
        for mp3 in mp3s:
            if total >= target:
                break
            d = get_duration(mp3)
            selected.append((mp3, d))
            total += d
        if total < target:
            random.shuffle(mp3s)

    tmp = tempfile.mkdtemp()
    try:
        flist = os.path.join(tmp, "bgm.txt")
        with open(flist, "w", encoding="utf-8") as f:
            for mp3, _ in selected:
                f.write(f"file '{str(mp3).replace(chr(92), '/')}'\n")
        concat_audio = os.path.join(tmp, "concat.aac")
        run([FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", flist,
             "-c:a", "aac", "-b:a", "192k", concat_audio])
        fade_start = target - FADE_DUR
        run([FFMPEG, "-y", "-i", concat_audio,
             "-af", f"afade=t=out:st={fade_start:.1f}:d={FADE_DUR:.1f}",
             "-t", f"{target:.3f}", "-c:a", "aac", "-b:a", "192k", str(out_audio)])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return selected

def save_bgm_log(out_num, food_name, selected, target_sec=None):
    """選曲タイムラインをテキスト保存。何分何秒からどの曲かを記録。"""
    log_dir = BASE_DIR / "BGMログ"
    log_dir.mkdir(exist_ok=True)
    log_path = log_dir / f"{out_num:03d}_{food_name}.txt"
    target = target_sec if target_sec else TARGET_SEC

    def fmt(sec):
        h = int(sec // 3600)
        m = int((sec % 3600) // 60)
        s = int(sec % 60)
        return f"{h:01d}:{m:02d}:{s:02d}"

    lines = [
        f"動画番号 : {out_num:03d}.mp4",
        f"食べ物   : {food_name}",
        f"総尺     : {fmt(target)}（{target:.0f}秒）",
        "=" * 50,
        "開始       終了       曲名",
        "-" * 50,
    ]
    t = 0.0
    for mp3, dur in selected:
        if t >= target:
            break
        end = min(t + dur, target)
        lines.append(f"{fmt(t):<10} {fmt(end):<10} {mp3.name}")
        t += dur

    log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"  BGM log saved: {log_path.name}")
    return log_path

# ─────────────────────────────────────────
# Main pipeline
# ─────────────────────────────────────────
def main():
    if len(sys.argv) < 2:
        print("Usage: python pipeline.py <food_name> [number]")
        print("Example: python pipeline.py クッキー")
        print("Example: python pipeline.py クッキー 027")
        sys.exit(1)

    food_name = sys.argv[1]
    src_video = MAKING_DIR / f"{food_name}.mp4"
    thumbnail = MAKING_DIR / f"{food_name}.png"
    if not thumbnail.exists():
        thumbnail = MAKING_DIR / f"{food_name}.jpg"

    if not src_video.exists():
        print(f"ERROR: {src_video} not found")
        sys.exit(1)

    if len(sys.argv) >= 3:
        out_num = int(sys.argv[2])
    else:
        out_num = detect_next_number()
    out_path   = BASE_DIR / f"{out_num:03d}.mp4"
    tmp_edited = MAKING_DIR / f"edited_{out_num:03d}.mp4"

    print("=" * 60)
    print(f"BGM Video Pipeline: {food_name}")
    print(f"Output: {out_num:03d}.mp4")
    print("=" * 60)

    # ── Step 2: Video editing ──────────────────────────
    print(f"\n[1/7] Video editing")
    if tmp_edited.exists():
        print(f"  edited video already exists, skipping")
    else:
        print("  detecting crop area...")
        crop_str = detect_crop(src_video)
        print(f"  crop: {crop_str}")
        create_edited_video(src_video, tmp_edited, crop_str)

    # 映像ループの切れ目で終わるよう、本編尺をループ長の整数倍に切り上げる
    loop_len = get_duration(tmp_edited)
    loops = math.ceil(MIN_BODY_SEC / loop_len)
    body_sec = loop_len * loops
    print(f"  loop={loop_len:.1f}s x{loops} -> body={body_sec:.1f}s ({body_sec/60:.1f}min)")

    print("  building BGM...")
    tmp_audio = Path(tempfile.gettempdir()) / f"bgm_{out_num:03d}.aac"
    selected = select_and_build_bgm(tmp_audio, body_sec)
    save_bgm_log(out_num, food_name, selected, body_sec)

    print("  final render...")
    body = MAKING_DIR / f"body_{out_num:03d}.mp4"
    subprocess.run([
        FFMPEG, "-y",
        "-stream_loop", str(loops - 1), "-i", str(tmp_edited),
        "-i", str(tmp_audio),
        "-t", f"{body_sec:.3f}",
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        str(body)
    ], check=True, capture_output=False)
    tmp_audio.unlink(missing_ok=True)

    print("  prepending opening...")
    subprocess.run([
        FFMPEG, "-y", "-i", str(OPENING), "-i", str(body),
        "-filter_complex",
        "[0:v]scale=1920:1080,fps=30,setsar=1[v0];"
        "[1:v]scale=1920:1080,fps=30,setsar=1[v1];"
        "[0:a]aresample=48000,asetpts=PTS-STARTPTS[a0];"
        "[1:a]aresample=48000,asetpts=PTS-STARTPTS[a1];"
        "[v0][a0][v1][a1]concat=n=2:v=1:a=1[v][a]",
        "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        str(out_path)
    ], check=True, capture_output=False)
    body.unlink(missing_ok=True)

    mb = out_path.stat().st_size / 1024 / 1024
    print(f"  done! {mb:.1f}MB -> {out_path.name}")

    # ── Step 3: Generate JP title & description ────────
    print(f"\n[2/7] Generating JP title & description")
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    total_sec = get_duration(out_path)
    dur_jp, _ = duration_phrases(total_sec)
    dur_note = duration_note(total_sec)
    print(f"  duration: {total_sec:.1f}s -> 尺表記「{dur_jp}」")
    jp_title, jp_desc = translate_text(
        client, JP_TITLE_DESC_PROMPT,
        f"食べ物の名前: {food_name}\n尺表記: {dur_jp}"
    )
    print(f"  title: {jp_title}")

    # ── Step 4: Upload to YouTube ──────────────────────
    print(f"\n[3/7] Uploading to YouTube")
    youtube = get_youtube()
    publish_at = next_available_7am_jst(youtube)
    print(f"  scheduled: {publish_at}")

    body = {
        "snippet": {
            "title":           jp_title,
            "description":     jp_desc,
            "categoryId":      "10",
            "defaultLanguage": "ja",
        },
        "status": {
            "privacyStatus":             "private",
            "publishAt":                 publish_at,
            "selfDeclaredMadeForKids":   True,
        },
    }
    media = MediaFileUpload(str(out_path), mimetype="video/mp4",
                            resumable=True, chunksize=10*1024*1024)
    request = youtube.videos().insert(
        part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"  uploading... {int(status.progress()*100)}%", end="\r")
    video_id = response["id"]
    print(f"\n  uploaded! ID: {video_id}")
    print(f"  URL: https://www.youtube.com/watch?v={video_id}")

    # ── Step 5: Set thumbnail ──────────────────────────
    print(f"\n[4/7] Setting thumbnail")
    if thumbnail.exists():
        ext = thumbnail.suffix.lower()
        mime = "image/png" if ext == ".png" else "image/jpeg"
        youtube.thumbnails().set(
            videoId=video_id,
            media_body=MediaFileUpload(str(thumbnail), mimetype=mime),
        ).execute()
        print(f"  set: {thumbnail.name}")
    else:
        print(f"  thumbnail not found ({thumbnail.name}), skipped")

    # ── Step 6: Already set publishAt above ───────────
    print(f"\n[5/7] Publish schedule: {publish_at}")

    # ── Step 6b: Add to playlist ───────────────────────
    print(f"\n[6/7] Adding to playlist")
    if PLAYLIST_ID and PLAYLIST_ID != "YOUR_PLAYLIST_ID":
        try:
            youtube.playlistItems().insert(
                part="snippet",
                body={
                    "snippet": {
                        "playlistId": PLAYLIST_ID,
                        "resourceId": {
                            "kind":    "youtube#video",
                            "videoId": video_id,
                        },
                    }
                }
            ).execute()
            print(f"  added to playlist: {PLAYLIST_ID}")
        except Exception as e:
            print(f"  playlist add failed: {e}")
    else:
        print(f"  PLAYLIST_ID not set, skipped")

    # ── Step 7: 16-language translations ──────────────
    print(f"\n[7/7] Translating into 16 languages")
    localizations = {}
    for lang_code, system_prompt, lang_desc in LANGUAGES:
        print(f"  [{lang_code}] ...", end=" ", flush=True)
        try:
            if lang_desc:
                user_content = (
                    f"Target language: {lang_desc}\n\n"
                    f"{dur_note}\n\n"
                    f"Japanese title:\n{jp_title}\n\n"
                    f"Japanese description:\n{jp_desc}"
                )
            else:
                user_content = (
                    f"{dur_note}\n\n"
                    f"日本語タイトル:\n{jp_title}\n\n日本語概要欄:\n{jp_desc}"
                )
            t, d = translate_text(client, system_prompt, user_content)
            if t and d:
                t = sanitize_meta(t, 100)
                d = sanitize_meta(d, 5000)
                localizations[lang_code] = {"title": t, "description": d}
                print(t[:45])
            else:
                print("parse error")
            time.sleep(1)
        except Exception as e:
            print(f"ERROR: {e}")
            time.sleep(2)

    res = youtube.videos().list(part="snippet,localizations", id=video_id).execute()
    item = res["items"][0]
    existing_locs = item.get("localizations", {})
    existing_locs.update(localizations)

    def push_locs(locs):
        youtube.videos().update(
            part="localizations,snippet",
            body={
                "id": video_id,
                "snippet": {
                    "title":           jp_title,
                    "description":     jp_desc,
                    "categoryId":      "10",
                    "defaultLanguage": "ja",
                },
                "localizations": locs,
            }
        ).execute()

    try:
        push_locs(existing_locs)
        print(f"  uploaded {len(localizations)} languages")
    except Exception as e:
        # 1言語でも弾かれると全体が400になるため、1言語ずつ入れ直して原因を切り分ける
        print(f"  batch update rejected: {e}")
        print("  retrying one language at a time...")
        accepted = {"ja": {"title": jp_title, "description": jp_desc}}
        push_locs(accepted)
        rejected = []
        for code, loc in existing_locs.items():
            if code == "ja":
                continue
            trial = dict(accepted)
            trial[code] = loc
            try:
                push_locs(trial)
                accepted = trial
            except Exception:
                rejected.append(code)
            time.sleep(1)
        print(f"  uploaded {len(accepted) - 1} languages")
        if rejected:
            print(f"  REJECTED languages: {rejected}")

    # ── Final report ───────────────────────────────────
    print("\n" + "=" * 60)
    print("COMPLETE!")
    print("=" * 60)
    print(f"  video     : {out_num:03d}.mp4  ({mb:.1f}MB)")
    print(f"  video ID  : {video_id}")
    print(f"  URL       : https://www.youtube.com/watch?v={video_id}")
    print(f"  title     : {jp_title}")
    print(f"  publish   : {publish_at}")
    print(f"  languages : ja + {len(localizations)} languages")
    print(f"  thumbnail : {'set' if thumbnail.exists() else 'not set'}")

if __name__ == "__main__":
    main()
