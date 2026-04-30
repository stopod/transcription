# whisper-api

カンファレンスや会議の音声を録音／ファイル取り込みし、ローカルの faster-whisper で文字起こしする個人用ツール。
要件・アーキテクチャ判断の詳細は [project-adr.md](project-adr.md) を参照。

---

## 使用技術

### バックエンド (`backend/`)

| 種別 | 技術 |
|------|------|
| 言語・ランタイム | Python 3.12（[uv](https://docs.astral.sh/uv/) 管理） |
| Web フレームワーク | FastAPI + uvicorn |
| 文字起こしエンジン | [faster-whisper](https://github.com/SYSTRAN/faster-whisper) 1.2（CTranslate2 ベース、CUDA 12 系） |
| 既定モデル | `large-v3` / fp16 / GPU |
| 音声前処理 | ffmpeg（受信音声を 16kHz mono WAV に正規化してから推論に渡す） |
| 要約エンジン | [Ollama](https://ollama.com/)（既定モデル `qwen2.5:latest`、7.6B / Q4_K_M、HTTP API 経由） |
| 保存先 | ファイルシステム（`backend/data/jobs/{job_id}/`） |

### フロントエンド (`frontend/`)

| 種別 | 技術 |
|------|------|
| ビルド | Vite 7 |
| 言語 | vanilla TypeScript |
| PWA | vite-plugin-pwa（manifest 同梱、Service Worker 自動更新） |
| 録音 | MediaRecorder API（既定: WebM/Opus） |
| ファイル取り込み | `<input type="file" accept="audio/*">` |
| バックエンド接続 | 開発サーバの `/api` → `127.0.0.1:8000` プロキシ |

### ハードウェア前提（開発機）

- NVIDIA GeForce RTX 4060（8 GB VRAM）
- CUDA Toolkit のシステムインストール **不要**。pip パッケージ（`nvidia-cublas-cu12` / `nvidia-cudnn-cu12` / `nvidia-cuda-runtime-cu12` / `nvidia-cuda-nvrtc-cu12`）で完結

---

## ディレクトリ構成

```
whisper-api/
├── README.md
├── project-adr.md             要件・ADR
├── backend/
│   ├── pyproject.toml
│   ├── .python-version        (3.12)
│   ├── .env.example
│   └── app/
│       ├── main.py            FastAPI ルート定義
│       ├── config.py          設定（WHISPER_* env で上書き可）
│       ├── schemas.py         Pydantic モデル
│       ├── storage.py         ジョブのファイル保存
│       └── transcribe.py      faster-whisper 呼び出し（ThreadPool で 1 件ずつ実行）
└── frontend/
    ├── vite.config.ts         /api プロキシ + PWA 設定
    ├── index.html
    └── src/
        ├── main.ts            UI とポーリング
        ├── api.ts             バックエンド API クライアント
        ├── recorder.ts        MediaRecorder ラッパ
        └── style.css
```

---

## 起動方法

ターミナル（PowerShell）を **2 枚** 開いて、それぞれで以下を実行する。

### 0. Ollama の稼働確認（要約機能を使う場合）

Windows 版 Ollama はインストール時にスタートアップ自動登録されるため、サインイン状態であれば通常は何もしなくて良い。確認:

```powershell
Get-Process ollama -ErrorAction SilentlyContinue
```

止まっていた場合は次で再起動：

```powershell
Start-Process "$env:LOCALAPPDATA\Programs\Ollama\ollama app.exe"
```

要約モデルが pull されているかは `ollama list` で確認。`qwen2.5:latest` が既定。

### 1. バックエンド

```powershell
cd c:\dev\whisper-api\backend
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

初回起動後の **最初の文字起こしジョブ** で `large-v3` モデル（約 3 GB）が `%USERPROFILE%\.cache\huggingface\hub\` にダウンロードされる。以降はキャッシュから即時ロード。

### 2. フロントエンド

```powershell
cd c:\dev\whisper-api\frontend
npm run dev
```

起動したら、ブラウザで [http://localhost:5173](http://localhost:5173) を開く。

---

## 停止方法

通常は各ターミナルで `Ctrl+C`。

ターミナルを閉じてしまった場合や、バックグラウンドで動かしている場合の強制停止：

```powershell
Get-Process python, node -ErrorAction SilentlyContinue |
  Where-Object { $_.Path -like '*whisper-api*' } |
  Stop-Process
```

---

## 使い方

ブラウザで [http://localhost:5173](http://localhost:5173) を開く。

| アクション | 操作 |
|------------|------|
| 録音 | **録音開始** → しばらく話す → **録音停止**。停止と同時にアップロード〜文字起こしジョブ投入まで自動 |
| 既存ファイルから | **ファイルを取り込み** ボタンでファイル選択。aac / m4a / mp3 / wav / webm / ogg / flac / opus 等に対応 |
| 進捗確認 | 画面中段「現在のジョブ」が 2 秒間隔でポーリング更新 |
| 履歴 | 下段リストから過去ジョブを再表示できる |
| コピー | 完了後の文字起こしの下に「全文コピー」ボタン |

文字起こし結果は **発言単位（segment）で改行**、間が 2 秒以上空いたところは段落区切り（空行）として整形される。

---

## 設定

`backend/.env`（テンプレートとして `.env.example` をコピーして使用）で上書きできる主な項目：

| 環境変数 | 既定値 | 説明 |
|----------|--------|------|
| `WHISPER_MODEL_SIZE` | `large-v3` | `medium` / `small` 等に切替可 |
| `WHISPER_DEVICE` | `cuda` | GPU が無いマシンでは `cpu` |
| `WHISPER_COMPUTE_TYPE` | `float16` | CPU の場合は `int8` を推奨 |
| `WHISPER_DEFAULT_LANGUAGE` | `ja` | 空にすると自動判定 |
| `WHISPER_PARAGRAPH_GAP_SECONDS` | `2.0` | 段落区切りとみなす無音長（秒） |
| `WHISPER_INITIAL_PROMPT` | （未設定） | Whisper への前置きテキスト。設定するとハルシネーションを誘発しやすいので注意 |
| `WHISPER_SUMMARY_ENABLED` | `True` | Ollama での要約生成を有効化 |
| `WHISPER_OLLAMA_URL` | `http://localhost:11434` | Ollama HTTP API |
| `WHISPER_OLLAMA_MODEL` | `qwen2.5:latest` | 要約モデル（`gemma3:4b` 等に変更可） |
| `WHISPER_OLLAMA_TIMEOUT_SECONDS` | `600.0` | 1 ジョブの要約タイムアウト |
| `WHISPER_SUMMARY_PROMPT` | （議事録風プロンプト同梱） | 要約プロンプトの上書き |

---

## API（バックエンド）

| メソッド | パス | 用途 |
|----------|------|------|
| `GET` | `/health` | サーバ稼働確認・モデル設定の表示 |
| `POST` | `/jobs` | 音声をアップロード（multipart `audio`、任意の `language`）、ジョブ作成 |
| `GET` | `/jobs` | ジョブ一覧（新しい順） |
| `GET` | `/jobs/{id}` | ジョブ詳細（完了していれば全文 + セグメント） |
| `GET` | `/jobs/{id}/transcript` | 文字起こし全文（plain text） |
| `GET` | `/jobs/{id}/summary` | 要約全文（plain text） |

OpenAPI ドキュメントは起動中に [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) から閲覧可能。

---

## データの保存場所

| 種別 | 場所 |
|------|------|
| 音声・メタ・文字起こし | `backend/data/jobs/{job_id}/` |
| Whisper モデル | `%USERPROFILE%\.cache\huggingface\hub\` |

`backend/data/` は `.gitignore` 対象。古いジョブを消すにはディレクトリごと削除すれば良い。
