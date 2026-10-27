"""Download the free offline Piper voices used for read-aloud and voice mode.

    python scripts/download_voices.py

Saves to data/voices/ (git-ignored, ~127 MB). Run once per computer.
Voices come from the official Piper voices repository (rhasspy/piper-voices).
"""
from __future__ import annotations

import sys
from pathlib import Path

import requests

BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/main"
VOICES = {
    "hi_IN-pratham-medium": "hi/hi_IN/pratham/medium",   # Hindi, male
    "en_US-ryan-medium": "en/en_US/ryan/medium",         # English, male
}
TARGET = Path(__file__).resolve().parents[1] / "data" / "voices"


def download(url: str, path: Path) -> None:
    if path.exists() and path.stat().st_size > 0:
        print(f"  already there: {path.name}")
        return
    tmp = path.with_suffix(path.suffix + ".part")
    with requests.get(url, stream=True, timeout=60) as response:
        response.raise_for_status()
        total = int(response.headers.get("content-length") or 0)
        done = 0
        with open(tmp, "wb") as out:
            for chunk in response.iter_content(1 << 20):
                out.write(chunk)
                done += len(chunk)
                if total:
                    print(f"\r  {path.name}: {done * 100 // total}%", end="", flush=True)
    tmp.replace(path)
    print(f"\r  {path.name}: done            ")


def main() -> int:
    TARGET.mkdir(parents=True, exist_ok=True)
    for name, folder in VOICES.items():
        print(name)
        for suffix in (".onnx", ".onnx.json"):
            download(f"{BASE}/{folder}/{name}{suffix}", TARGET / f"{name}{suffix}")
        card = TARGET / f"{name}.MODEL_CARD"
        download(f"{BASE}/{folder}/MODEL_CARD", card)
    print(f"Voices saved in {TARGET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
