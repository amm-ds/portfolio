"""Regenerate the committed mixed-document analysis PDF fixtures."""

from pathlib import Path

from document_intelligence.fixtures import write_fixture_set


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    write_fixture_set(root / "fixtures")
    write_fixture_set(root / "web" / "public" / "fixtures")


if __name__ == "__main__":
    main()
