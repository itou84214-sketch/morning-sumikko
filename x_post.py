#!/usr/bin/env python3
"""
X (Twitter) auto-post for new BGM videos.
Reads OAuth1.0a keys from .claude/.env, uploads the thumbnail, and posts:

  [emoji]はっけん！今日のメニューは〇〇。

  https://www.youtube.com/watch?v=<video_id>

  #すみっこくん #作業用BGM #スイーツ #朝活 #カフェ #リラックス #〇〇

Usage (test):
  python x_post.py <food_name> <video_id> <emoji> [thumbnail_path]
Example:
  python x_post.py タピオカ eYQh37-cZIg 🥤
"""
import os, sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv
import tweepy

BASE_DIR   = Path(os.getenv("BGM_BASE_DIR") or Path(__file__).resolve().parent)
MAKING_DIR = BASE_DIR / "メイキング"
ENV_FILE   = BASE_DIR / ".claude" / ".env"
load_dotenv(ENV_FILE)

HASHTAGS = "#すみっこくん #作業用BGM #スイーツ #朝活 #カフェ #リラックス"


def _first_env(*names):
    for n in names:
        v = os.getenv(n)
        if v:
            return v.strip()
    return None

def get_keys():
    keys = {
        "api_key":             _first_env("X_API_KEY", "X_consumer_key"),
        "api_secret":          _first_env("X_API_SECRET", "X_consumer_secret"),
        "access_token":        _first_env("X_ACCESS_TOKEN", "X_Access_token"),
        "access_token_secret": _first_env("X_ACCESS_TOKEN_SECRET", "X_Access_secret"),
    }
    missing = [k for k, v in keys.items() if not v]
    if missing:
        raise SystemExit(f"ERROR: .env に未設定のキーがあります: {missing}")
    return keys


def build_text(emoji, food_name, video_id):
    url = f"https://www.youtube.com/watch?v={video_id}"
    return (
        f"{emoji}はっけん！今日のメニューは{food_name}。\n\n"
        f"{url}\n\n"
        f"{HASHTAGS} #{food_name}"
    )


def post_to_x(text, image_path=None):
    k = get_keys()
    # OAuth1.0a user context (needed for both media upload v1.1 and create_tweet v2)
    media_ids = None
    if image_path:
        auth = tweepy.OAuth1UserHandler(
            k["api_key"], k["api_secret"], k["access_token"], k["access_token_secret"])
        api_v1 = tweepy.API(auth)
        media = api_v1.media_upload(filename=str(image_path))
        media_ids = [media.media_id]

    client = tweepy.Client(
        consumer_key=k["api_key"], consumer_secret=k["api_secret"],
        access_token=k["access_token"], access_token_secret=k["access_token_secret"])
    resp = client.create_tweet(text=text, media_ids=media_ids)
    tweet_id = resp.data["id"]
    return tweet_id


def post_for_video(food_name, video_id, emoji, thumbnail_path=None):
    if thumbnail_path is None:
        thumbnail_path = MAKING_DIR / f"{food_name}.png"
        if not thumbnail_path.exists():
            thumbnail_path = MAKING_DIR / f"{food_name}.jpg"
    if not Path(thumbnail_path).exists():
        print(f"WARNING: thumbnail not found ({thumbnail_path}); posting without image")
        thumbnail_path = None

    text = build_text(emoji, food_name, video_id)
    print("=== post text ===")
    print(text)
    print("=== image ===")
    print(thumbnail_path)
    tweet_id = post_to_x(text, thumbnail_path)
    print(f"\nPOSTED! tweet id: {tweet_id}")
    print(f"URL: https://x.com/su359n/status/{tweet_id}")
    return tweet_id


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python x_post.py <food_name> <video_id> <emoji> [thumbnail_path]")
        sys.exit(1)
    food_name = sys.argv[1]
    video_id  = sys.argv[2]
    emoji     = sys.argv[3]
    thumb     = sys.argv[4] if len(sys.argv) >= 5 else None
    post_for_video(food_name, video_id, emoji, thumb)
