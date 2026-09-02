"""Gece programi: indirmeleri sinirla, sonra her seyi yeniden kur.

SIRA VE SEBEBI
  06:00'a kadar  indirmeler surer (ag isi, GPU bos)
  06:00          indirmeler durdurulur
                 -> devam ederlerse indeksleme yarim veriyle calisir
  06:00-09:00    mevzuat indeksi (GPU, ~3 saat)
                 -> sunucu bu sirada KAPALI: 4 GB kartta ikisi ayni anda
                    calisamiyor, olculdu (arama 1.8 sn yerine 67 sn)
  09:00          karar indeksi + atif zinciri (birkac dakika)
  09:10          sunucu acilir
  09:15          olcum calisir, sonuc dosyaya yazilir

Her adim gece_programi.log'a zaman damgasiyla yazilir; sabah ne olduğu
oradan okunur.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

KOK = Path(__file__).resolve().parent
PY = KOK / ".venv" / "Scripts" / "python.exe"
GUNLUK = KOK / "gece_programi.log"

# Indirmelerin durdurulacagi saat. Yeniden indeksleme ~3 saat surdugu ve
# 12:00'de her sey hazir olmasi gerektigi icin 06:00 secildi.
DURDURMA_SAATI = 6


def log(mesaj: str) -> None:
    satir = f"[{datetime.now():%H:%M}] {mesaj}"
    print(satir, flush=True)
    with open(GUNLUK, "a", encoding="utf-8") as f:
        f.write(satir + "\n")


def surecleri_durdur(kalip: str) -> int:
    """Komut satirinda kalip gecen python sureclerini durdurur."""
    komut = (
        "Get-CimInstance Win32_Process -Filter \"Name like '%python%'\" | "
        f"Where-Object {{ $_.CommandLine -like '*{kalip}*' }} | "
        "ForEach-Object { Stop-Process -Id $_.ProcessId -Force; 'durduruldu' }"
    )
    c = subprocess.run(["powershell", "-NoProfile", "-Command", komut],
                       capture_output=True, text=True)
    return (c.stdout or "").count("durduruldu")


def calistir(baslik: str, *arg: str, zorunlu: bool = True) -> bool:
    log(f"BASLADI: {baslik}")
    t = time.time()
    sonuc = subprocess.run([str(PY), *arg], cwd=KOK,
                           capture_output=True, text=True)
    if sonuc.returncode != 0:
        son = (sonuc.stderr or "").strip().splitlines()[-3:]
        log(f"BASARISIZ: {baslik} -- {' | '.join(son)[:200]}")
        if zorunlu:
            sys.exit(1)
        return False
    log(f"BITTI: {baslik} ({(time.time()-t)/60:.0f} dk)")
    return True


def sayilar() -> str:
    try:
        m = len(json.loads((KOK / "data/raw/maddeler.json").read_text(encoding="utf-8")))
    except Exception:
        m = -1
    k = len(list((KOK / "data/raw/karar_cache").glob("*.json")))
    return f"{m:,} madde, {k:,} karar"


def main() -> None:
    log(f"=== gece programi basladi -- {sayilar()} ===")

    # 1) Indirmeler DURDURMA_SAATI'ne kadar sursun
    hedef = datetime.now().replace(hour=DURDURMA_SAATI, minute=0, second=0)
    if hedef < datetime.now():
        hedef += timedelta(days=1)
    log(f"indirmeler {hedef:%H:%M}'a kadar surecek")

    while datetime.now() < hedef:
        time.sleep(900)                       # 15 dakikada bir
        log(f"indirme suruyor -- {sayilar()}")

    log("indirmeler durduruluyor")
    n = surecleri_durdur("cli.py") + surecleri_durdur("server.py")
    log(f"{n} surec durduruldu -- {sayilar()}")
    time.sleep(10)

    # 2) Mevzuat indeksi
    calistir("mevzuat indeksi", "cli.py", "indeksle")

    # 3) Karar indeksi
    calistir("karar indeksi", "cli.py", "karar-indeksle", zorunlu=False)

    # 4) Atif zinciri
    calistir("atif zinciri", "zincir_kur.py", zorunlu=False)

    # 5) Sunucu
    subprocess.Popen([str(PY), "server.py"], cwd=KOK,
                     stdout=open(KOK / "server.log", "w"),
                     stderr=open(KOK / "server.err.log", "w"))
    log("sunucu baslatildi, hazir olmasi bekleniyor")
    time.sleep(180)

    # 6) Olcum
    calistir("olcum", "_genislet_olc.py", zorunlu=False)

    log(f"=== BITTI -- {sayilar()} ===")


if __name__ == "__main__":
    main()
