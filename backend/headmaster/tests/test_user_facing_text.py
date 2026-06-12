"""User-facing text should stay readable UTF-8, not mojibake."""

from pathlib import Path

MOJIBAKE_MARKERS = ("�", "쨌", "醫", "紐", "怨", "??/")


def test_no_mojibake_in_user_facing_sources() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    paths = [repo_root / "README.md", *sorted((repo_root / "frontend" / "src").rglob("*"))]
    checked = [
        path
        for path in paths
        if path.is_file() and path.suffix in {".md", ".ts", ".tsx", ".css"}
    ]
    assert checked
    offenders: list[str] = []
    for path in checked:
        text = path.read_text(encoding="utf-8")
        if any(marker in text for marker in MOJIBAKE_MARKERS):
            offenders.append(str(path.relative_to(repo_root)))
    assert offenders == []
