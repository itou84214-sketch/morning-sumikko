#!/usr/bin/env python3
"""
YouTube Studio 自動翻訳 v2
- YouTube Data API v3：JP タイトル・説明を取得
- OpenAI API：reference スタイルで英訳
- ブラウザ自動化：自動翻訳行削除 → 英語追加 → 入力 → 公開
"""

import os, re, time, pickle
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys

# ─────────────────────────────────────────
# パス設定
# ─────────────────────────────────────────
BASE_DIR      = Path(os.getenv("BGM_BASE_DIR") or Path(__file__).resolve().parent)
ENV_FILE      = BASE_DIR / ".claude" / ".env"
CLIENT_SECRET = BASE_DIR / ".claude" / "client_secret.json"
TOKEN_FILE    = BASE_DIR / ".claude" / "token.json"
COOKIE_FILE   = BASE_DIR / ".claude" / "yt_cookies.pkl"
REF_FILE      = BASE_DIR / ".claude" / "reference_yt_title_description.md"

load_dotenv(ENV_FILE)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError(".env に OPENAI_API_KEY がありません")

# ─────────────────────────────────────────
# 動画リスト
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
# YouTube Data API 認証
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
            flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET), SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_FILE.write_text(creds.to_json())
    return build("youtube", "v3", credentials=creds)

# ─────────────────────────────────────────
# JP タイトル・説明を取得
# ─────────────────────────────────────────
def get_jp_content(youtube, video_id):
    res = youtube.videos().list(part="snippet", id=video_id).execute()
    if not res.get("items"):
        return "", ""
    snippet = res["items"][0]["snippet"]
    return snippet.get("title", ""), snippet.get("description", "")

# ─────────────────────────────────────────
# OpenAI で英訳（reference スタイル参考）
# ─────────────────────────────────────────
def build_system_prompt():
    ref = REF_FILE.read_text(encoding="utf-8")
    return f"""\
あなたはYouTubeチャンネル「ゆる朝カフェのすみっこ」の翻訳担当です。
日本語のタイトルと概要欄を英語に翻訳してください。

【参考スタイル（このスタイルに合わせること）】
{ref}

【ルール】
- 絵文字はそのまま使う
- 食べ物・雰囲気・用途（Morning Routine / Focus / Work BGM など）をタイトルに含める
- 概要欄は温かく詩的なトーンを保つ
- チャンネル登録URLはそのまま残す
- ハッシュタグは英語に変換（例：#朝活 → #morningroutine）
- Subscribe リンクは必ず入れる：https://www.youtube.com/channel/UCjaEFXP9cDVPOMv-5xGfk7g?sub_confirmation=1

必ず以下の形式のみで出力してください：

TITLE: [英語タイトル]
DESCRIPTION:
[英語概要欄]
END_DESCRIPTION"""

def translate_with_openai(client, system_prompt, jp_title, jp_desc):
    user_msg = f"日本語タイトル:\n{jp_title}\n\n日本語概要欄:\n{jp_desc}"
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_msg},
        ],
        temperature=0.7,
    )
    text = response.choices[0].message.content.strip()
    title_m = re.search(r"TITLE:\s*\n?(.+)", text)
    desc_m  = re.search(r"DESCRIPTION:\s*\n(.*?)(?:END_DESCRIPTION|$)", text, re.DOTALL)
    if not title_m or not desc_m:
        print(f"  ❌ パース失敗:\n{text[:200]}")
        return None, None
    return title_m.group(1).strip(), desc_m.group(1).strip()

# ─────────────────────────────────────────
# ブラウザ: Chrome 起動
# ─────────────────────────────────────────
def make_driver():
    opts = uc.ChromeOptions()
    opts.add_argument("--start-maximized")
    opts.add_argument("--lang=ja")
    return uc.Chrome(options=opts, version_main=148)

def load_cookies(driver):
    if not COOKIE_FILE.exists():
        return False
    with open(COOKIE_FILE, "rb") as f:
        data = pickle.load(f)
    for domain, cookies in data.items():
        try:
            driver.get(f"https://{domain}")
            time.sleep(1)
            for c in cookies:
                try: driver.add_cookie(c)
                except: pass
        except: pass
    return True

def save_cookies(driver):
    data = {}
    for domain in ["youtube.com", "studio.youtube.com", "google.com"]:
        try:
            driver.get(f"https://{domain}")
            time.sleep(1)
            data[domain] = driver.get_cookies()
        except: pass
    with open(COOKIE_FILE, "wb") as f:
        pickle.dump(data, f)

def ensure_login(driver):
    driver.get("https://studio.youtube.com")
    time.sleep(4)
    if "studio.youtube.com/channel" in driver.current_url:
        print("  ✅ ログイン済み")
        return True
    print("  ⚠️ ログインが必要です")
    input("  >> YouTubeにログインして Enter を押してください...")
    save_cookies(driver)
    return True

# ─────────────────────────────────────────
# ブラウザ: 翻訳ページを操作
# ─────────────────────────────────────────
def set_translation_browser(driver, video_id, en_title, en_desc):
    url = f"https://studio.youtube.com/video/{video_id}/translations"
    driver.get(url)
    time.sleep(4)

    # ── 英語行の状態を確認 ──
    rows = driver.find_elements(By.TAG_NAME, "tr")
    en_row = None
    for row in rows:
        if row.text.strip().startswith("英語") and "自動" not in row.text:
            en_row = row
            break

    if not en_row:
        # 英語行がなければ追加
        print("  → 英語行を追加...")
        add_btns = driver.find_elements(By.XPATH,
            "//ytcp-button[normalize-space(.)='言語を追加'] | //button[normalize-space(.)='言語を追加']")
        if not add_btns:
            print("  ❌ 言語を追加ボタンなし")
            return False
        add_btns[-1].click()
        time.sleep(1.5)
        opts = driver.find_elements(By.CSS_SELECTOR, "[role='option']")
        for opt in opts:
            if opt.text.strip() == "英語":
                opt.click()
                time.sleep(2.5)
                break
        else:
            print("  ❌ 英語オプションなし")
            return False

    # ── 編集フォームに入力 ──
    # 字幕削除後 or 新規追加後：編集ボタンが通常表示になっているはず
    print("  → 編集ボタンを探す...")
    edit_btns = driver.find_elements(By.XPATH,
        "//ytcp-button[normalize-space(.)='編集'] | //button[normalize-space(.)='編集']")
    if edit_btns:
        edit_btns[-1].click()
        time.sleep(2)
    else:
        print("  → 編集ボタンなし、textareaを直接探す...")

    try:
        WebDriverWait(driver, 8).until(
            EC.presence_of_element_located((By.TAG_NAME, "textarea")))
    except:
        print("  ❌ textareaが出てこない")
        return False

    textareas = driver.find_elements(By.TAG_NAME, "textarea")
    en_title_ta = en_desc_ta = None
    for ta in textareas:
        ph  = ta.get_attribute("placeholder") or ""
        val = driver.execute_script("return arguments[0].value;", ta) or ""
        if not val:
            if "タイトル" in ph and not en_title_ta:
                en_title_ta = ta
            elif "説明" in ph and not en_desc_ta:
                en_desc_ta = ta

    if not en_title_ta or not en_desc_ta:
        print(f"  ❌ textarea不足（タイトル:{en_title_ta is not None}, 説明:{en_desc_ta is not None}）")
        # プレースホルダーに関わらず空のtextareaを使う
        empty = [t for t in textareas
                 if not (driver.execute_script("return arguments[0].value;", t) or "").strip()]
        if len(empty) >= 2:
            en_title_ta, en_desc_ta = empty[0], empty[1]
        elif len(empty) == 1:
            en_title_ta = empty[0]
        else:
            print("  ❌ 空のtextareaなし")
            return False

    # タイトル入力
    print("  → タイトル入力...")
    en_title_ta.click()
    en_title_ta.clear()
    en_title_ta.send_keys(en_title)
    time.sleep(0.5)

    # 説明入力（クリップボード経由）
    if en_desc_ta:
        print("  → 説明入力...")
        import subprocess
        subprocess.run("clip", input=en_desc.encode("utf-16"), check=True)
        en_desc_ta.click()
        time.sleep(0.3)
        en_desc_ta.send_keys(Keys.CONTROL, "a")
        en_desc_ta.send_keys(Keys.CONTROL, "v")
        time.sleep(0.5)

    # 公開ボタン
    print("  → 公開...")
    pub_btns = driver.find_elements(By.XPATH,
        "//ytcp-button[normalize-space(.)='公開'] | //button[normalize-space(.)='公開']")
    if not pub_btns:
        print("  ❌ 公開ボタンなし")
        return False
    pub_btns[-1].click()
    time.sleep(3)
    print("  ✅ 公開完了！")
    return True


def delete_auto_en_caption(youtube, video_id):
    """Captions API で自動生成の英語字幕を削除する"""
    try:
        res = youtube.captions().list(part="snippet", videoId=video_id).execute()
        deleted = False
        for cap in res.get("items", []):
            lang = cap["snippet"].get("language", "")
            kind = cap["snippet"].get("trackKind", "")
            if lang.startswith("en") and kind == "asr":
                youtube.captions().delete(id=cap["id"]).execute()
                print(f"  → 自動字幕削除OK ({lang})")
                deleted = True
        if not deleted:
            print("  → 自動字幕なし（スキップ）")
        return True
    except Exception as e:
        print(f"  → 字幕削除エラー: {e}")
        return False

# ─────────────────────────────────────────
# メイン
# ─────────────────────────────────────────
def main():
    print("=" * 50)
    print("YouTube 自動翻訳 v2（API + ブラウザ）")
    print("=" * 50)

    # YouTube Data API
    print("\nGoogle認証中...")
    youtube = get_youtube_client()
    print("✅ YouTube API OK")

    # OpenAI
    openai_client = OpenAI(api_key=OPENAI_API_KEY)
    system_prompt = build_system_prompt()
    print("✅ OpenAI API OK")

    # ブラウザ起動
    print("\nChrome起動中...")
    driver = make_driver()
    load_cookies(driver)
    ensure_login(driver)

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
            en_title, en_desc = translate_with_openai(
                openai_client, system_prompt, jp_title, jp_desc)
            if not en_title:
                results[label] = "❌ 翻訳失敗"
                continue
            print(f"  EN: {en_title[:50]}")

            # Step3: 自動字幕を削除（タイトルと説明を編集可能にする）
            print("  Step3: 自動字幕削除...")
            delete_auto_en_caption(youtube, video_id)
            time.sleep(1)

            # Step4: ブラウザで翻訳を入力
            print("  Step4: YouTubeStudioに入力...")
            ok = set_translation_browser(driver, video_id, en_title, en_desc)
            results[label] = "✅" if ok else "❌ 書き込み失敗"


            time.sleep(1)

        except Exception as e:
            print(f"  ❌ エラー: {e}")
            results[label] = f"❌ {str(e)[:50]}"
            try:
                driver.get("https://studio.youtube.com")
                time.sleep(2)
            except: pass

    print("\n" + "=" * 50)
    print("完了！結果:")
    for label, status in results.items():
        print(f"  {status}  {label}")

    save_cookies(driver)
    input("\nEnterで閉じます...")
    driver.quit()


if __name__ == "__main__":
    main()
