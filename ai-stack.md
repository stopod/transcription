# AI スタック

本プロジェクトで使用している AI 関連のモデル・ライブラリ・ランタイムを一覧する。
**すべてローカル実行**で、外部 API（OpenAI / Anthropic / Google 等のクラウド LLM・STT）は一切利用しない。

---

## 概要図

```
[マイク録音 / 音声ファイル取り込み]
        │
        ▼  ffmpeg で 16kHz mono WAV に正規化
        │
        ▼
[ faster-whisper ─────► CTranslate2 (CUDA)  ── 推論
        │              └─► Silero VAD       ── 無音除去
        │
        ▼  文字起こし全文（.txt）
        │
        ▼
[ Ollama HTTP API (:11434) ]
        │
        ▼  Qwen2.5 (Q4_K_M) 推論
        │
        ▼
   議事録風の要約（.txt）
```

---

## 1. 音声認識（Speech-to-Text）

### Whisper（モデル: large-v3）
- **役割**: 録音／取り込んだ音声を文字に起こす（多言語、日本語精度高め）
- **配布元**: OpenAI（リリース先は HuggingFace の `Systran/faster-whisper-large-v3` から自動 DL）
- **パラメータ数**: 約 1.55B
- **VRAM 占有**: fp16 で約 5 GB
- **キャッシュ場所**: `%USERPROFILE%\.cache\huggingface\hub\`
- **ライセンス**: MIT
- **本プロジェクトでの設定**: `WHISPER_MODEL_SIZE=large-v3` / `WHISPER_COMPUTE_TYPE=float16`

### faster-whisper（Python ライブラリ）
- **役割**: Whisper モデルを動かすラッパー。CTranslate2 経由で PyTorch 版より 4 倍高速
- **VAD 内蔵**: Silero VAD を `vad_filter=True` で自動適用
- **本プロジェクトでの設定**: `vad_filter=True` / `beam_size=5`
- **公式**: <https://github.com/SYSTRAN/faster-whisper>

### CTranslate2（推論エンジン、C++）
- **役割**: faster-whisper の内部で実際にテンソル計算を回す。INT8 / FP16 / FP32 量子化対応、CUDA / CPU 両対応
- **公式**: <https://github.com/OpenNMT/CTranslate2>

### Silero VAD（Voice Activity Detection）
- **役割**: 無音区間を検出して文字起こし対象から除外
- **配布**: faster-whisper に同梱、別途インストール不要
- **公式**: <https://github.com/snakers4/silero-vad>

---

## 2. 要約（Summarization）

### Qwen2.5（モデル: `qwen2.5:latest` / 7.6B / Q4_K_M）
- **役割**: 文字起こしされた全文から議事録風の要約を生成
- **開発元**: Alibaba（Qwen チーム）
- **パラメータ数**: 7.6B、量子化 Q4_K_M（4-bit）
- **VRAM 占有**: 約 4.7 GB
- **対応言語**: 多言語（日本語含む）
- **キャッシュ場所**: `%USERPROFILE%\.ollama\models\` 以下
- **ライセンス**: Apache 2.0
- **本プロジェクトでの設定**: `WHISPER_OLLAMA_MODEL=qwen2.5:latest` / `temperature=0.3`

### Ollama（ローカル LLM ランナー）
- **役割**: モデルの管理（pull / list / rm）と HTTP API による推論
- **既定ポート**: `11434`
- **配置**: `C:\Users\<user>\AppData\Local\Programs\Ollama\`
- **常駐**: Windows ではインストール時にスタートアップ登録され、サインイン時に自動起動
- **公式**: <https://ollama.com>

---

## 3. プロンプト

### Whisper の `initial_prompt`
- **既定**: 未設定（`None`）
- **理由**: 設定すると Whisper がプロンプト本文を出力にループバックさせるハルシネーションを誘発しやすい。動作実験の結果、未設定が最も安全と判断
- **オーバーライド**: `WHISPER_INITIAL_PROMPT` 環境変数

### 要約プロンプト（`WHISPER_SUMMARY_PROMPT`）
- **構成**: 議題ごとの要点 / 決定事項 / アクションアイテム / 200〜300 字のサマリ段落、の議事録形式
- **ハードコード位置**: [backend/app/config.py](backend/app/config.py)
- **オーバーライド**: `WHISPER_SUMMARY_PROMPT` 環境変数

---

## 4. ハードウェア・ランタイム前提

| 項目 | 値 |
|------|----|
| GPU | NVIDIA GeForce RTX 4060（8 GB VRAM） |
| NVIDIA Driver | 591.86 以降（CUDA 12 系をサポート） |
| CUDA Toolkit（システム） | **不要**。pip パッケージで完結 |

pip 経由で venv 内に入れている NVIDIA ランタイム：

- `nvidia-cublas-cu12`（cuBLAS）
- `nvidia-cudnn-cu12`（cuDNN）
- `nvidia-cuda-runtime-cu12`（cudart）
- `nvidia-cuda-nvrtc-cu12`（NVRTC）

これらの DLL は [backend/app/transcribe.py](backend/app/transcribe.py) の `_add_cuda_dll_directories()` で実行時に DLL 検索パスへ追加している。

---

## 5. VRAM の占有と直列実行

| ステージ | モデル | VRAM |
|----------|--------|------|
| 文字起こし | Whisper large-v3 (fp16) | 約 5 GB |
| 要約 | Qwen2.5:7b (Q4_K_M) | 約 4.7 GB |

8 GB に両方は同時に乗らないため、**1 ジョブにつき直列実行**（文字起こし → 要約）。Ollama は VRAM が不足すると一部レイヤーを CPU にオフロードするため、停止することはなく、多少遅くなるだけ。
詳細は [project-adr.md](project-adr.md) の **ADR-008** を参照。

---

## 6. 切り替え可能な設定（環境変数）

| 変数 | 用途 |
|------|------|
| `WHISPER_MODEL_SIZE` | Whisper モデルサイズ（`large-v3`, `medium`, `small`, …） |
| `WHISPER_COMPUTE_TYPE` | 計算精度（`float16`, `int8_float16`, `int8`） |
| `WHISPER_DEVICE` | `cuda` / `cpu` |
| `WHISPER_DEFAULT_LANGUAGE` | 既定の言語タグ（`ja`、空で自動判定） |
| `WHISPER_INITIAL_PROMPT` | Whisper への前置きテキスト |
| `WHISPER_SUMMARY_ENABLED` | 要約パイプラインの ON/OFF |
| `WHISPER_OLLAMA_URL` | Ollama HTTP API |
| `WHISPER_OLLAMA_MODEL` | 要約モデル名（`gemma3:4b`, `qwen3:8b` など） |
| `WHISPER_OLLAMA_TIMEOUT_SECONDS` | 1 ジョブの要約タイムアウト |
| `WHISPER_SUMMARY_PROMPT` | 要約プロンプト全文 |

---

## 7. 採用していないもの（参考）

- **クラウド系 STT/LLM**（OpenAI Whisper API、GPT-4o、Claude、Gemini など）
  - プライバシー（カンファレンス会場の他者音声を含む可能性）と月額固定費の回避が理由。詳細は **ADR-002 / ADR-005 / ADR-008** を参照
- **PyTorch 版 Whisper**
  - 依存が重く、CPU 性能で faster-whisper（CTranslate2）に劣るため不採用
- **whisper.cpp**
  - Python バックエンドとの統合より subprocess 呼び出しになる分一段複雑になるため、初期実装では faster-whisper を選択（**ADR-002**）
- **要約用クラウド API（Claude / GPT 等）**
  - Ollama でローカル要約が成立したため、当面不要（**ADR-008**）

---

## 8. 関連リンク

- Whisper（OpenAI 本家）: <https://github.com/openai/whisper>
- faster-whisper: <https://github.com/SYSTRAN/faster-whisper>
- CTranslate2: <https://github.com/OpenNMT/CTranslate2>
- Silero VAD: <https://github.com/snakers4/silero-vad>
- Qwen2.5: <https://huggingface.co/Qwen/Qwen2.5-7B-Instruct>
- Ollama: <https://ollama.com>
