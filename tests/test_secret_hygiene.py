from pathlib import Path
from subprocess import run


def test_env_files_are_ignored() -> None:
    result = run(["git", "check-ignore", ".env"], check=False, capture_output=True, text=True)

    assert result.returncode == 0


def test_env_example_contains_no_secret_values() -> None:
    content = Path(".env.example").read_text(encoding="utf-8")

    for key in [
        "TUSHARE_TOKEN",
        "LLM_API_KEY",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "MINIMAX_API_KEY",
        "MOONSHOT_API_KEY",
    ]:
        for line in content.splitlines():
            if line.startswith(f"{key}="):
                assert line == f"{key}="
