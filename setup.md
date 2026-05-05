# セットアップガイド

このリポジトリ（whisper-api）を新しい PC で 1 から動かすための手順。
全ステップを上から順に実行すれば、ローカル文字起こし＋要約が動く状態になる。

> 本プロジェクトは **完全ローカル動作**（外部 API なし）で設計されている。クラウド LLM/STT には一切接続しない。

---

## 0. 動作確認済み環境

- **OS**: Windows 11 Home（24H2 / build 26200）
- **GPU**: NVIDIA GeForce RTX 4060（8 GB VRAM）
- **シェル**: PowerShell 5.1 / 7.x
- **ブラウザ**: Chrome 最新（フロント PWA の動作確認用）

Linux / macOS でも動作する余地はあるが、本ドキュメントは **Windows 11 + NVIDIA GPU** を前提に手順を記載する。

---

## 1. ハードウェア要件

### 1.1 必須

| 項目 | 要件 | 備考 |
|------|------|------|
| OS | Windows 10 / 11（64bit） | WSL は未検証 |
| CPU | x64、4 コア以上推奨 | ffmpeg と Vite の同時稼働を考慮 |
| メモリ | 16 GB 以上推奨 | Ollama 起動中はワーキングセットが肥大化する |
| ストレージ | 空き 20 GB 以上 | Whisper モデル ~3GB、Qwen2.5 モデル ~4.7GB、venv ~3GB、node_modules ~0.5GB |
| マイク or 音声ファイル | いずれか | 録音 or ファイル取り込みのどちらでも可 |

### 1.2 GPU を使う場合（強く推奨）

| 項目 | 要件 |
|------|------|
| GPU | NVIDIA、CUDA 12 系対応（Compute Capability 7.0 以降目安） |
| VRAM | **8 GB 以上**（Whisper large-v3 fp16 + Qwen2.5 7B Q4_K_M を直列実行できる最低ライン） |
| ドライバ | NVIDIA Driver **551.61 以降**（CUDA 12.4 ランタイム対応バージョン） |

> CUDA Toolkit のシステムインストールは **不要**。本プロジェクトは pip パッケージ（`nvidia-cublas-cu12` / `nvidia-cudnn-cu12` / `nvidia-cuda-runtime-cu12` / `nvidia-cuda-nvrtc-cu12`）で完結し、`backend/app/transcribe.py` の `_add_cuda_dll_directories()` が venv 内の DLL を実行時に登録する。

### 1.3 GPU が無い／VRAM が不足する場合

- `WHISPER_DEVICE=cpu` / `WHISPER_COMPUTE_TYPE=int8` に切り替えれば CPU でも動く（速度は数倍〜十数倍遅くなる）
- 要約を使わないなら `WHISPER_SUMMARY_ENABLED=false` で Ollama 系は不要

---

## 2. 事前にインストールするソフトウェア

以下を **全部** 入れる。順番は問わない。

| # | ソフト | バージョン目安 | 用途 |
|---|--------|----------------|------|
| 1 | Git for Windows | 2.40 以降 | リポジトリ取得 |
| 2 | NVIDIA グラフィックドライバ | 551.61 以降 | GPU 推論（GPU 利用時のみ） |
| 3 | uv | 0.4 以降 | Python パッケージマネージャ（venv も自動管理） |
| 4 | Python | 3.12 系（uv が自動取得するので明示インストール不要） | バックエンド |
| 5 | Node.js | 20 LTS 以降 | フロントエンド（Vite） |
| 6 | ffmpeg | 6.x 以降 | 入力音声を 16kHz mono WAV に正規化 |
| 7 | Ollama | 最新 | ローカル LLM ランナー（要約用） |

各ソフトの詳細手順は次セクション。

---

## 3. ソフトウェアのインストール手順

以降のコマンドは **PowerShell** で実行する想定。

### 3.1 Git

[https://git-scm.com/download/win](https://git-scm.com/download/win) からインストーラを取得し、デフォルト設定で OK。

確認:

```powershell
git --version
```

### 3.2 NVIDIA ドライバ（GPU を使う場合のみ）

[https://www.nvidia.com/Download/index.aspx](https://www.nvidia.com/Download/index.aspx) から「Game Ready Driver」または「Studio Driver」を取得。

確認（CUDA 12 が認識できているか）:

```powershell
nvidia-smi
```

出力の `CUDA Version: 12.x` が表示されれば OK。

### 3.3 uv（Python マネージャ）

PowerShell から:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

ターミナルを開き直してから確認:

```powershell
uv --version
```

> uv は `backend/.python-version`（= `3.12`）に従って Python 3.12 を自動 DL する。Python 本体を別途インストールする必要はない。

### 3.4 Node.js

LTS 版を [https://nodejs.org/ja/download](https://nodejs.org/ja/download) からインストール。または [Volta](https://volta.sh/) や `winget install OpenJS.NodeJS.LTS` でも可。

確認:

```powershell
node --version
npm --version
```

### 3.5 ffmpeg

公式の Windows ビルド（gyan.dev 配布）を利用するのが手軽:

```powershell
winget install Gyan.FFmpeg
```

`winget` が無い環境では [https://www.gyan.dev/ffmpeg/builds/](https://www.gyan.dev/ffmpeg/builds/) から zip を取得し、展開先（`bin/ffmpeg.exe` のあるフォルダ）を **ユーザー環境変数 `Path`** に追加する。

確認:

```powershell
ffmpeg -version
```

> ffmpeg が `Path` に無い場合、バックエンドはアップロードされた音声をそのまま faster-whisper に渡す（警告ログが出る）。精度・速度のため必ずインストールすること。

### 3.6 Ollama（要約機能を使う場合）

[https://ollama.com/download/windows](https://ollama.com/download/windows) からインストーラを取得し実行。

- インストールすると **Windows スタートアップに自動登録** され、サインイン時に常駐起動する
- 既定ポートは `11434`

確認:

```powershell
Get-Process ollama -ErrorAction SilentlyContinue
ollama --version
```

止まっていた場合の起動:

```powershell
Start-Process "$env:LOCALAPPDATA\Programs\Ollama\ollama app.exe"
```

---

## 4. リポジトリの取得

任意のフォルダで:

```powershell
git clone <このリポジトリのURL> c:\dev\whisper-api
cd c:\dev\whisper-api
```

> 以降のパス例は `c:\dev\whisper-api` 前提。別パスに置く場合は読み替えること。

---

## 5. バックエンドのセットアップ

### 5.1 依存関係のインストール

```powershell
cd c:\dev\whisper-api\backend
uv sync
```

これで以下が自動的に行われる:

- `.python-version` に従い Python 3.12 を取得
- `backend/.venv/` が作られ、`pyproject.toml` / `uv.lock` の依存（FastAPI、faster-whisper、CUDA ランタイムパッケージ等）がインストールされる

完了確認:

```powershell
uv run python -c "import faster_whisper, fastapi; print('ok')"
```

### 5.2 環境変数ファイルの用意

```powershell
Copy-Item .env.example .env
```

GPU が使えない環境の場合は `.env` を編集して以下に変更:

```
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8
```

要約を使わない場合は:

```
WHISPER_SUMMARY_ENABLED=false
```

設定可能な環境変数の全リストは [README.md](README.md#設定) を参照。

### 5.3 GPU 動作確認（GPU 利用時のみ）

```powershell
uv run python -c "from faster_whisper import WhisperModel; m = WhisperModel('tiny', device='cuda', compute_type='float16'); print('CUDA OK')"
```

`CUDA OK` が表示されれば GPU 推論の経路が通っている。`CUDA failed with error ...` が出る場合は NVIDIA ドライバのバージョンを確認すること（§3.2）。

---

## 6. 要約モデル（Qwen2.5）の取得

要約機能を使う場合のみ必要。

```powershell
ollama pull qwen2.5:latest
```

ダウンロードサイズは約 **4.7 GB**。`%USERPROFILE%\.ollama\models\` 以下にキャッシュされる。

確認:

```powershell
ollama list
```

`qwen2.5:latest` が表示されていれば OK。

> 別モデルを使いたい場合は `ollama pull <モデル名>` の後、`backend/.env` の `WHISPER_OLLAMA_MODEL` を書き換える。例: `gemma3:4b`、`qwen3:8b` など。

---

## 7. フロントエンドのセットアップ

```powershell
cd c:\dev\whisper-api\frontend
npm install
```

`node_modules/` が作られれば OK。

---

## 8. 起動

PowerShell を **2 枚** 開いて、それぞれで以下を実行する。

### 8.1 バックエンド

```powershell
cd c:\dev\whisper-api\backend
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

- 初回の **最初の文字起こしジョブ** で Whisper `large-v3` モデル（約 3 GB）が `%USERPROFILE%\.cache\huggingface\hub\` にダウンロードされる。以降はキャッシュから即時ロード
- ログに `Loading WhisperModel size=large-v3 device=cuda compute_type=float16` が出れば起動完了

ヘルスチェック:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

### 8.2 フロントエンド

```powershell
cd c:\dev\whisper-api\frontend
npm run dev
```

ブラウザで [http://localhost:5173](http://localhost:5173) を開く。

> Vite 開発サーバは `/api/*` を `127.0.0.1:8000` にプロキシする（`vite.config.ts`）。

---

## 9. 動作確認

ブラウザで [http://localhost:5173](http://localhost:5173) を開き:

1. **録音開始** で 5〜10 秒ほど話す → **録音停止**
2. 自動でアップロード → 文字起こしジョブ作成
3. 「現在のジョブ」が 2 秒間隔でポーリング更新され、完了すると全文と要約（有効時）が表示される
4. 「全文コピー」ボタンが押せれば一通りの動作 OK

OpenAPI ドキュメント（バックエンド）は起動中に [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) で確認可能。

---

## 10. 停止

各ターミナルで `Ctrl+C`。

ターミナルを閉じてしまった場合の強制停止:

```powershell
Get-Process python, node -ErrorAction SilentlyContinue |
  Where-Object { $_.Path -like '*whisper-api*' } |
  Stop-Process
```

Ollama を完全停止したい場合（通常は常駐のままで問題ない）:

```powershell
Get-Process ollama -ErrorAction SilentlyContinue | Stop-Process
```

---

## 11. データの保存場所

| 種別 | 場所 | 削除可否 |
|------|------|----------|
| ジョブ（音声・メタ・文字起こし・要約） | `backend/data/jobs/{job_id}/` | フォルダごと削除可 |
| 要約テンプレート | `backend/data/templates/*.md` | 初回起動時に既定が再生成される |
| Whisper モデル | `%USERPROFILE%\.cache\huggingface\hub\` | 削除すると次回起動時に再 DL |
| Qwen2.5 モデル | `%USERPROFILE%\.ollama\models\` | `ollama rm qwen2.5:latest` で削除 |

`backend/data/` は `.gitignore` 対象。新環境では空の状態から始まる。

---

## 12. トラブルシューティング

### 12.1 `uv sync` が NVIDIA パッケージで失敗する

`pyproject.toml` の `nvidia-*-cu12` 系は **PyPI 公式ホストのみ提供** されている。社内プロキシで PyPI 直アクセスできない場合は uv の index 設定を見直す。

### 12.2 起動時に `Could not load library cudnn_ops_infer64_8.dll` 等

NVIDIA ドライバのバージョンが古い。§3.2 を参照して 551.61 以降にアップデート。

### 12.3 要約だけ失敗する（文字起こしは成功）

- Ollama が起動しているか: `Get-Process ollama`
- モデルが pull 済か: `ollama list` で `qwen2.5:latest` が見えるか
- 直接叩いて確認:

  ```powershell
  Invoke-RestMethod http://localhost:11434/api/tags
  ```

### 12.4 ffmpeg 警告が出る

ログに `ffmpeg not found; passing ... as-is` が出る場合、§3.5 で ffmpeg を `Path` に通せていない。新しい PowerShell を開き直す or 環境変数の見直しが必要。

### 12.5 ブラウザでマイクが使えない

`http://localhost:5173`（= localhost）は安全な origin として扱われるため通常問題ない。LAN 内の他端末から `http://<PCのIP>:5173` で開くと **HTTPS でないと MediaRecorder が動かない**。スマホ等で使う場合は HTTPS リバースプロキシ（Caddy / cloudflared 等）の構築が別途必要。

### 12.6 ポートが既に使われている

```powershell
# 8000 番を誰が掴んでいるか
Get-NetTCPConnection -LocalPort 8000 -State Listen
# 5173 番
Get-NetTCPConnection -LocalPort 5173 -State Listen
```

別ポートで起動する例:

```powershell
uv run uvicorn app.main:app --host 127.0.0.1 --port 8010
```

ポートを変えた場合は `frontend/vite.config.ts` のプロキシ先も合わせて変更する。

---

## 13. 参考リンク

- プロジェクト全体の概要: [README.md](README.md)
- 使用している AI モデル/ランタイムの詳細: [ai-stack.md](ai-stack.md)
- 設計判断（ADR）: [project-adr.md](project-adr.md)
