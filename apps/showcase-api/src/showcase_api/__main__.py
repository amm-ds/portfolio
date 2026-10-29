"""Console launcher for the showcase API."""

import uvicorn


def main() -> None:
    """Serve the application with uvicorn."""
    uvicorn.run("showcase_api.main:app", host="0.0.0.0", port=8000)  # noqa: S104


if __name__ == "__main__":
    main()
