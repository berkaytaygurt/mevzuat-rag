"""Indeksleme bitince olcumu calistirir.

Ayni anda calistirilamaz: indeksleme GPU'yu doldurur, olcum de GPU ister.
Olculdu -- ikisi acikken arama 1.5 saniye yerine 67 saniye suruyor.
"""
from __future__ import annotations

import subprocess
import time
from pathlib import Path

KOK = Path(__file__).resolve().parent
PY = KOK / ".venv" / "Scripts" / "python.exe"


def calisiyor(kalip: str) -> bool:
    c = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         f"(Get-CimInstance Win32_Process -Filter \"Name like '%python%'\" | "
         f"Where-Object {{ $_.CommandLine -like '*{kalip}*' }}).Count"],
        capture_output=True, text=True)
    return (c.stdout or "0").strip() not in ("", "0")


def log(m: str) -> None:
    print(f"[{time.strftime('%H:%M')}] {m}", flush=True)


def main() -> None:
    while calisiyor("gece_bitir") or calisiyor("cli.py indeksle"):
        log("indeksleme suruyor, 5 dk sonra bakilacak")
        time.sleep(300)

    log("indeksleme bitti, olcum basliyor")
    subprocess.run([str(PY), "-u", "_genislet_olc.py"], cwd=KOK)
    log("olcum bitti -> genislet_olcum.txt")


if __name__ == "__main__":
    main()
