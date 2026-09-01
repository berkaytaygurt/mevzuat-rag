"""Indirmeler bittikten sonra calistirilacak tam sira.

Adimlarin sirasi onemli ve elle hatirlanmasi gereken birkac tuzak var:

1. Sunucu kapatilmali. Embedding GPU'yu doldurur; sunucu ayaktayken ikisi 4
   GB'lik kartta cakisiyor ve ikisi de kilitleniyor (olculdu: sunucu 200
   saniyede bile cevap veremedi).
2. Mevzuat indeksi ile karar indeksi ayri; ikisi de yeniden kurulmali.
3. Olcum ancak indeksleme bittikten SONRA anlamli.

    .venv\Scripts\python yeniden_kur.py
    .venv\Scripts\python yeniden_kur.py --olcum      # olcumu da calistir
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

KOK = Path(__file__).resolve().parent
PY = KOK / ".venv" / "Scripts" / "python.exe"


def calistir(baslik: str, *arg: str) -> bool:
    print(f"\n=== {baslik} ===", flush=True)
    t = time.time()
    sonuc = subprocess.run([str(PY), *arg], cwd=KOK)
    sure = time.time() - t
    if sonuc.returncode != 0:
        print(f"!!! {baslik} basarisiz (kod {sonuc.returncode})", flush=True)
        return False
    print(f"--- {baslik}: {sure/60:.1f} dk", flush=True)
    return True


def sunucuyu_durdur() -> None:
    subprocess.run(["powershell", "-NoProfile", "-Command",
                    "Get-CimInstance Win32_Process -Filter \"Name like '%python%'\" | "
                    "Where-Object { $_.CommandLine -like '*server.py*' } | "
                    "ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"],
                   capture_output=True)
    time.sleep(3)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--olcum", action="store_true", help="sonunda olcumu calistir")
    ap.add_argument("--sunucu", action="store_true", help="sonunda sunucuyu baslat")
    args = ap.parse_args()

    for ad, yol in (("maddeler", "data/raw/maddeler.json"),
                    ("kararlar", "data/raw/kararlar.json")):
        p = KOK / yol
        if p.exists():
            n = len(json.loads(p.read_text(encoding="utf-8")))
            print(f"{ad}: {n:,} kayit")
        else:
            print(f"{ad}: dosya yok")

    print("\nsunucu durduruluyor (GPU cakismasi olmasin)")
    sunucuyu_durdur()

    if not calistir("mevzuat indeksi (~2 saat)", "cli.py", "indeksle"):
        sys.exit(1)
    if (KOK / "data/raw/kararlar.json").exists():
        calistir("karar indeksi", "cli.py", "karar-indeksle")

    if args.olcum:
        calistir("olcum", "_cekirdek_olc.py")

    if args.sunucu:
        subprocess.Popen([str(PY), "server.py"], cwd=KOK)
        print("sunucu baslatildi")

    print("\nBITTI")


if __name__ == "__main__":
    main()
