"""Aibars'i gecici bir internet adresinden erisilebilir yapar.

Cloudflare'in "quick tunnel" ozelligini kullanir: hesap gerekmez, adres
gecicidir ve bu program kapaninca olur. Router ayari, port yonlendirme veya
sabit IP gerektirmez.

    .venv\Scripts\python paylas.py

GUVENLIK: Tunel acilinca sayfa internete acilir. Bu yuzden .env icinde
AIBARS_KULLANICI ve AIBARS_SIFRE tanimli degilse program baslamaz -- sifresiz
bir adres sizarsa Gemini kotani harcar ve makineni gereksiz yere acar.
"""
from __future__ import annotations

import re
import subprocess
import sys
import threading
import time
from pathlib import Path

import config

KOK = Path(__file__).parent
CLOUDFLARED = KOK / "tools" / "cloudflared.exe"
ADRES_RE = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")


def _sunucu_ayakta() -> bool:
    import urllib.error
    import urllib.request

    try:
        urllib.request.urlopen(f"http://127.0.0.1:{config.PORT}/", timeout=3)
        return True
    except urllib.error.HTTPError:
        return True          # 401 de "ayakta" demektir
    except Exception:
        return False


def main() -> None:
    if not (config.KULLANICI and config.SIFRE):
        sys.exit("Once .env icine AIBARS_KULLANICI ve AIBARS_SIFRE ekle.\n"
                 "Sifresiz bir adresi internete acmak guvenli degil.")

    if not CLOUDFLARED.exists():
        sys.exit(f"cloudflared bulunamadi: {CLOUDFLARED}")

    sunucu = None
    if not _sunucu_ayakta():
        print("Aibars sunucusu baslatiliyor...")
        sunucu = subprocess.Popen([sys.executable, str(KOK / "server.py")],
                                  cwd=str(KOK))
        for _ in range(40):
            if _sunucu_ayakta():
                break
            time.sleep(2)
        else:
            sunucu.terminate()
            sys.exit("Sunucu baslatilamadi.")
    print("Sunucu hazir. Tunel aciliyor...\n")

    # cloudflared ciktisini boruya degil dosyaya aliyoruz: boru tamponlandigi
    # icin adres satiri programa hic ulasmiyordu.
    gunluk = KOK / "tunel.log"
    gunluk.unlink(missing_ok=True)
    tunel = subprocess.Popen(
        [str(CLOUDFLARED), "tunnel", "--url", f"http://127.0.0.1:{config.PORT}",
         "--logfile", str(gunluk)])

    def oku() -> None:
        gorulen = False
        for _ in range(60):
            time.sleep(2)
            if gorulen or not gunluk.exists():
                continue
            metin = gunluk.read_text(encoding="utf-8", errors="replace")
            if m := ADRES_RE.search(metin):
                gorulen = True
                print("\n" + "=" * 62)
                print("  ADRES     :", m.group(0))
                print("  KULLANICI :", config.KULLANICI)
                print("  SIFRE     :", config.SIFRE)
                print("=" * 62)
                print("\n  Bu adresi kuzenine gonder. Tarayici kullanici adi ve")
                print("  sifre soracak. Bu pencereyi kapatinca adres olur.\n")

    threading.Thread(target=oku, daemon=True).start()

    try:
        tunel.wait()
    except KeyboardInterrupt:
        print("\nkapatiliyor...")
    finally:
        tunel.terminate()
        if sunucu:
            # Sunucuyu bilerek ayakta birakiyoruz. Onceki surumde tunel
            # kapaninca sunucu da oluyordu; tuneli yeniden baslatmak isteyen
            # kullanici 502 Bad Gateway ile karsilasiyordu.
            print(f"\nTunel kapandi. Sunucu http://localhost:{config.PORT} "
                  "adresinde calismaya devam ediyor.")


if __name__ == "__main__":
    main()
