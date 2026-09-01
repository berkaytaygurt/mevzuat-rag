"""Ictihat indirmesi bitince karar indeksini kurar ve siteyi acar.

ONCEKI SURUM COKTU: calisan surecleri powershell cagirarak kontrol ediyordu,
"powershell" o ortamda PATH'te bulunamayinca FileNotFoundError atti ve zincir
koptu -- indeksleme bitti ama sonraki adimlar hic calismadi.

Simdi disariya hic komut calistirmadan, kararlar.json'un son degisiklik
zamanina bakiyoruz: dosya bir suredir buyumuyorsa indirme bitmis demektir.
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

KOK = Path(__file__).resolve().parent
PY = KOK / ".venv" / "Scripts" / "python.exe"
KARAR_YOLU = KOK / "data" / "raw" / "kararlar.json"
DURGUNLUK = 900          # 15 dakika degismediyse indirme bitti sayilir


def log(m: str) -> None:
    print(f"[{time.strftime('%H:%M')}] {m}", flush=True)


def main() -> None:
    son_boyut, son_degisim = -1, time.time()
    bitis = time.time() + 4 * 3600

    while time.time() < bitis:
        boyut = KARAR_YOLU.stat().st_size if KARAR_YOLU.exists() else 0
        if boyut != son_boyut:
            son_boyut, son_degisim = boyut, time.time()
            log(f"ictihat suruyor ({boyut/1e6:.1f} MB)")
        elif time.time() - son_degisim > DURGUNLUK:
            log("ictihat durdu, devam ediliyor")
            break
        time.sleep(120)

    log("karar indeksi kuruluyor")
    subprocess.run([str(PY), "cli.py", "karar-indeksle"], cwd=KOK)
    log("sunucu baslatiliyor")
    subprocess.Popen([str(PY), "server.py"], cwd=KOK)
    log("hazir -- http://localhost:8000")


if __name__ == "__main__":
    main()
