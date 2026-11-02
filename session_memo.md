# BGM動画制作 セッションメモ

## 作業フォルダ
```
<リポジトリのパス>\
```

---

## Claudeへの指示（引継ぎ事項）

- **ファイルの移動は許可確認不要**。ビデオフォルダ等からメイキングフォルダへのmp4移動など、ファイル操作は確認せず即実行してよい。
- 作業フォルダ外（ビデオ、ピクチャ等）のディレクトリも自由に操作してよい。

---

## フォルダ構成

```
BGM動画\
├── 001.mp4 〜 (番号付き完成動画)
├── *.mp3           (BGM素材)
├── used illust\    (使用済みイラスト)
└── メイキング\
    ├── お団子.mp4
    ├── ころね.mp4
    ├── 2お団子.mp4  (静止カット処理済み・保留)
    └── 2ころね.mp4  (静止カット処理済み・保留)
```

---

## スクリプト一覧

| ファイル | 用途 |
|---------|------|
| `%TEMP%\make_videos.py` | イラスト画像 + ランダムBGMで動画作成（001〜010） |
| `%TEMP%\make_videos_loop.py` | メイキングmp4ループ + ランダムBGMで動画作成（006〜） |
| `%TEMP%\make_making_template.py` | メイキング動画編集（逆再生+通常再生ループ）+ ランダムBGMループで動画作成（012以降） |
| `%TEMP%\make_videos_making.py` | 旧版: メイキング動画編集（フリーズ+逆再生+通常再生）011まで使用 |
| `%TEMP%\remake_videos.py` | 特定動画を動画ごと自動cropで作り直す（005・006用） |
| `%TEMP%\cut_static.py` | freezedetect で静止区間カット（初版・過剰カットで没） |
| `%TEMP%\cut_static2.py` | ピクセル単位の差分比較で静止区間カット（改良版） |

---

## Suno BGM生成ワークフロー

### 概要
suno.com でジャズBGMを生成し、MP3をダウンロードして `BGM動画\` に追加する。

### 曲の条件
- ジャンル: **ジャズ**（ボサノバ・フュージョン等の派生ジャンルはなるべく排除）
- サウンド: **アンプラグド・生演奏感**（シンセサイザー等のデジタル音を極力使わない）
- 主旋律: **ピアノ / サックス / アコースティックギター**
- インスピレーションワード: 朝、早朝、深夜、ゆったり、まったり、静か、穏やか、静寂、落ち着く、集中

### 生成手順（Suno Advanced モード）

1. **suno.com/create** を開き、**Advanced** タブを選択
2. **Lyrics** 欄は**空白のまま**（→インストゥルメンタル扱いになる）
3. **Styles** 欄にスタイルタグを入力（例↓）
   ```
   jazz, acoustic piano, saxophone, slow tempo, bebop, cool jazz,
   live performance, improvisation, no synth, acoustic, after rain,
   cafe morning, gentle
   ```
4. **More Options** を展開して **Song Title** を入力（任意）
5. **Create** をクリック（10クレジット消費・2曲生成）
6. 前バッチの生成が**全曲完了してから**次バッチを送信（途中送信するとエラー）
7. クレジットが0になるまで繰り返す（無料: 50クレジット = 5バッチ = 10曲）

### スタイルタグ ベーステンプレート
```
jazz, acoustic piano, saxophone, acoustic guitar,
live performance, no synth, no electronic,
slow tempo, calm, peaceful, quiet, focused
```

### テーマ別スタイルタグ例

| テーマ | スタイルタグ（抜粋） |
|--------|-----------------|
| 朝・早朝 | `jazz, acoustic piano, saxophone, cool jazz, morning, early morning, calm, gentle, no synth` |
| 深夜・静寂 | `jazz, acoustic piano, saxophone, late night, quiet, still, dim light, no synth, acoustic` |
| ゆったり・まったり | `jazz, acoustic piano, acoustic guitar, cool jazz, relaxed, mellow, slow, peaceful, no synth` |
| 落ち着く・集中 | `jazz, acoustic piano, saxophone, focused, calm, introspective, quiet, acoustic, no synth` |

### ダウンロード手順

生成完了後、各曲の **`...`（三点メニュー）→ Download** をクリックしてMP3を保存。
保存先: `<リポジトリのパス>\`

---

## 動画作成ルール

### BGMの組み方
- 作業フォルダ内の `.mp3` を**ランダムにシャッフル**して繋げる
- 重複なし・1本の動画で合計 **約1時間（3600秒以上）** になるまで追加
- 末尾 **10秒フェードアウト** (`afade=t=out:st=X:d=10`)

### 動画トラック
- イラスト版: `-loop 1 -i image.png` + `-tune stillimage` + `-shortest`
- メイキングループ版: `-stream_loop -1 -i making.mp4` + `-shortest`

### エンコード設定
```
映像: libx264, crf=18, preset=fast, pix_fmt=yuv420p, +faststart
音声: aac, 192k
```

### ファイル名ルール
- 連番3桁 (`001.mp4`, `002.mp4` …)
- **空き番号から順番に使う**（削除で欠番が出た場合）

---

## メイキング動画BGM動画作成（`make_videos_making.py`）

### 概要
`メイキング\` フォルダのmp4を編集してBGM動画（連番mp4）を作成する。

### 動画編集構成（create_edited_video）
```
[完成絵フリーズ 2秒]
+ [高速逆再生 5秒: 全体から150フレームを等間隔サンプル→reverse]
+ [通常メイキング再生（キャンバスのみcrop・1920×1080スケール）]
+ [完成絵フリーズ 2秒]
```
→ この4パートをstream_loopで約1時間にループしてBGMと合成
→ 冒頭フリーズ：YouTube再生開始時に完成イラスト（テキスト含む）を視聴者が読める
→ 末尾フリーズ：ループ繋ぎ目で自然に止まる（繋ぎ目は2+2=4秒フリーズになるが許容範囲）

> ⚠️ 旧構成（011.mp4まで）: [フリーズ2秒]+[逆再生]+[通常] だったが廃止

### キャンバス自動検出（detect_crop）
- `format=gray, lut=y='if(between(val,230,255),255,0)', cropdetect` で白領域を検出
- 高さ基準で16:9（w = h×16/9）に補正してx中央合わせ
- 検出失敗時はデフォルト `crop=1148:646:387:246` を使用

### ファイル除外ルール
- `メイキング\` 内のmp4のうち、**ファイル名先頭が `2` のものは除外**（静止カット処理済みの保留版）

### 実行手順
```powershell
python $env:TEMP\make_videos_making.py
```

---

## メイキング静止カット（`cut_static2.py`）

### アルゴリズム
1. ffmpeg で動画を `320×180` グレースケール `5fps` のrawフレームとして書き出し
2. 隣接フレーム間で **1ピクセルでも差分 > 15** なら「動き」と判定
3. **2秒以上**静止が続いたらカット対象
4. カット後のセグメントを `trim + concat` で繋いでエンコード
5. 出力ファイル名: 元ファイル名の先頭に `2` を付ける（例: `2お団子.mp4`）

### パラメータ
```python
SAMPLE_FPS  = 5     # 解析フレームレート
SAMPLE_W    = 320   # ダウンスケール幅
SAMPLE_H    = 180   # ダウンスケール高さ
PIX_THRESH  = 15    # ピクセル差分閾値（0〜255）
MIN_STATIC  = 2.0   # 静止判定の最小秒数
MIN_KEEP    = 0.5   # 残す動的区間の最小秒数
```

### 結果（参考）
| 元ファイル | 元の尺 | 処理後 | 削減率 |
|-----------|-------|--------|--------|
| お団子.mp4 | 680s | 657.6s | 3% |
| ころね.mp4 | 808.7s | 780.6s | 3% |

> ⚠️ 結果が想定と異なったため **一旦保留**

---

## 使用ツール

- **FFmpeg / ffprobe** — 動画・音声処理全般
- **Python 3.14** (`<python.exe のパス>`)
- **Suno AI** (suno.com) — BGM生成（10クレジット/バッチ × 2曲）
- **Microsoft Copilot** (copilot.microsoft.com) — イラスト生成（チャットルーム「すみっこくんとおいしいやつ」）

---

## MP3素材一覧（79本）

| ファイル名 | 尺 |
|-----------|---|
| Amber Dusk 1.mp3 | 226.9s |
| Amber Dusk 2.mp3 | 297.6s |
| Copper Comet 1.mp3 | 215.9s |
| Creamboard Sonata 1.mp3 | 60.0s |
| Creamboard Sonata 2.mp3 | 60.0s |
| Dawn Reverie (1).mp3 | 165.0s |
| Dawn Reverie 3.mp3 | 261.2s |
| Dawn Reverie.mp3 | 196.2s |
| Drowsy Maple 1.mp3 | 283.4s |
| Drowsy Maple 2.mp3 | 204.2s |
| Evening Breeze 1.mp3 | 269.2s |
| Evening Cafe Sax (1).mp3 | 288.8s |
| Evening Cafe Sax.mp3 | 276.2s |
| Jam Jellyfish 1.mp3 | 142.2s |
| Jam Jellyfish 2.mp3 | 200.0s |
| Juniper Rain 1.mp3 | 266.2s |
| Juniper Rain 2.mp3 | 273.6s |
| Late Night Piano Bar (1).mp3 | 275.0s |
| Late Night Piano Bar.mp3 | 257.0s |
| Midnight Smoke 1.mp3 | 349.0s |
| Midnight Smoke 2.mp3 | 319.9s |
| Morning Rain Jazz (1).mp3 | 265.1s |
| Morning Rain Jazz.mp3 | 209.3s |
| Rain Cafe Jazz 1.mp3 | 289.4s |
| Rain Cafe Jazz 2.mp3 | 256.8s |
| Rain Paper Cups 1.mp3 | 225.4s |
| Rain Paper Cups 2.mp3 | 207.7s |
| Satin Whiskey 1.mp3 | 289.7s |
| Satin Whiskey 2.mp3 | 267.4s |
| Saxophone Steam 1.mp3 | 224.0s |
| Saxophone Steam 2.mp3 | 234.1s |
| Sunny Breakfast 1.mp3 | 155.6s |
| Sunny Breakfast 2.mp3 | 128.7s |
| Sunny Breakfast Jazz (1).mp3 | 139.5s |
| Sunny Breakfast Jazz.mp3 | 170.0s |
| Synced Sorrow 1.mp3 | 314.8s |
| Synced Sorrow 2.mp3 | 334.4s |
| Copper Dusk 1.mp3 | 189.1s |
| Copper Dusk 2.mp3 | 204.4s |
| Golden Toast 1.mp3 | 184.4s |
| Golden Toast 2.mp3 | 178.3s |
| Hazy Morning 1.mp3 | 214.5s |
| Hazy Morning 2.mp3 | 218.6s |
| Velvet Metronome 1.mp3 | 255.0s |
| Velvet Metronome 2.mp3 | 290.0s |
| Velvet Oatmilk 1.mp3 | 167.7s |
| Velvet Oatmilk 2.mp3 | 158.8s |
| Velvet Splice 1.mp3 | 174.6s |
| Velvet Splice 2.mp3 | 146.0s |
| Velvet Teacup 1.mp3 | 215.0s |
| Velvet Teacup 2.mp3 | 184.6s |
| Velvet Rain 1.mp3 | 247.2s |
| Velvet Rain 2.mp3 | 297.9s |
| Vinyl Raincoat 1.mp3 | 190.0s |
| Vinyl Raincoat 2.mp3 | 199.6s |
| 雨音喫茶.mp3 | 273.8s |
| 雨上がりのカフェテリア.mp3 | 216.4s |
| 静かなレンガ通り.mp3 | 229.8s |
| 夜更けの三拍子.mp3 | 225.0s |
| Ginger Teacup 1.mp3 | 260.8s |
| Ginger Teacup 2.mp3 | 218.6s |
| Saxophone Rain 1.mp3 | 207.3s |
| Saxophone Rain 2.mp3 | 230.3s |
| Jade Milkshake 1.mp3 | 259.6s |
| Jade Milkshake 2.mp3 | 279.4s |
| Velvet Metronome 3.mp3 | 205.4s |
| Velvet Metronome 4.mp3 | 245.0s |
| Maple Toasters 1.mp3 | 204.6s |
| Maple Toasters 2.mp3 | 233.9s |
| Saxophone Metronome 1.mp3 | 171.2s |
| Saxophone Metronome 2.mp3 | 164.4s |
| Whiskey Metronome 1.mp3 | 317.5s |
| Whiskey Metronome 2.mp3 | 222.7s |
| Piano Steam 1.mp3 | 209.1s |
| Piano Steam 2.mp3 | 294.3s |
| Cinnamon Saxophone 1.mp3 | 212.8s |
| Cinnamon Saxophone 2.mp3 | 254.4s |
| Sunday Espresso 1.mp3 | 211.3s |
| Sunday Espresso 2.mp3 | 204.4s |

---

## トラブルシューティング

### UnicodeDecodeError (cp932)
- Windows の PowerShell で Python を実行すると、FFmpeg の出力に含まれる特定バイトを cp932 でデコードできずエラーになることがある
- `subprocess.run(..., encoding='utf-8', errors='ignore')` で回避

### FFmpeg filter_complex の concat 順序
- 音声あり: `[v0][a0][v1][a1]...concat=n=N:v=1:a=1[outv][outa]`（インターリーブ必須）
- 音声なし: `[v0][v1]...concat=n=N:v=1:a=0[outv]`
- ❌ 間違い: `[v0][v1][a0][a1]concat` → "Media type mismatch" エラー

### freezedetect が描画を「静止」と誤判定する問題
- freezedetect の `noise` 閾値はフレーム全体の**平均**差分
- 細いペン描画（変化ピクセル少）→ 平均差分が閾値以下 → 静止と誤判定
- 解決: rawvideo パイプで1ピクセルずつ比較する方式（`cut_static2.py`）に変更
