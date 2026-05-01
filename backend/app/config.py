from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="WHISPER_")

    data_dir: Path = Path("data")
    model_size: str = "large-v3"
    device: str = "cuda"
    compute_type: str = "float16"
    default_language: str | None = "ja"
    initial_prompt: str | None = None
    paragraph_gap_seconds: float = 2.0

    summary_enabled: bool = True
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:latest"
    ollama_timeout_seconds: float = 600.0
    summary_prompt: str = (
        "以下は会議または講演の音声を文字起こししたものです。\n"
        "日本語の議事メモにまとめてください。次の構成・要件に従ってください:\n"
        "\n"
        "## 議題ごとの要点\n"
        "- 議題・主要トピックを見出し（### 形式）にし、箇条書きで要点を整理\n"
        "\n"
        "## 決定事項\n"
        "- 確定した方針・合意事項を列挙\n"
        "\n"
        "## アクションアイテム\n"
        "- 担当・期日が明示されたものを列挙（不明なら『担当: 不明』）\n"
        "\n"
        "## サマリ\n"
        "- 200〜300 字程度の段落で全体を要約\n"
        "\n"
        "ルール:\n"
        "- 相槌・繰り返し・雑談は省く\n"
        "- 元の発言意図を歪めない、推測で補完しない\n"
        "- 該当セクションに記載すべき内容が無ければ『該当なし』と明記\n"
    )


settings = Settings()
(settings.data_dir / "jobs").mkdir(parents=True, exist_ok=True)
(settings.data_dir / "templates").mkdir(parents=True, exist_ok=True)


def _seed_default_templates() -> None:
    tdir = settings.data_dir / "templates"
    if any(tdir.glob("*.md")):
        return
    meeting = (
        "---\n"
        "name: 会議\n"
        "description: 議事メモ形式（議題・決定事項・アクション・サマリ）\n"
        "---\n"
        + settings.summary_prompt
    )
    seminar = (
        "---\n"
        "name: セミナー\n"
        "description: 講演・セミナー向け（テーマ・要点・引用・サマリ）\n"
        "---\n"
        "以下はセミナー・講演の音声を文字起こししたものです。\n"
        "次の構成で日本語にまとめてください:\n"
        "\n"
        "## テーマ\n"
        "- 講演全体のテーマを 1〜2 行で\n"
        "\n"
        "## 主要な論点\n"
        "- 話題ごとに見出し（### 形式）で要点を箇条書き\n"
        "\n"
        "## 注目ポイント・引用\n"
        "- 印象的な発言・データ・事例を抜粋\n"
        "\n"
        "## 全体サマリ\n"
        "- 300 字程度の段落で総括\n"
        "\n"
        "ルール:\n"
        "- 相槌・繰り返しは省く\n"
        "- 元の発言意図を歪めない、推測で補完しない\n"
    )
    (tdir / "meeting.md").write_text(meeting, encoding="utf-8")
    (tdir / "seminar.md").write_text(seminar, encoding="utf-8")


_seed_default_templates()

CORS_ORIGINS: list[str] = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
