"""Deneme dilekcelerini PDF'e cevirir.

    .venv\\Scripts\\python tools_dilekce_pdf.py

NEDEN: avukat dilekcelerini PDF olarak tutuyor, TXT olarak degil.
Olcumu TXT uzerinde yapmak, gercek kullanimdan bir adim uzakta bir
sinav olurdu -- PDF'ten metin cikarma kendi hatalarini getiriyor
(kirilmaz bosluk, satir sonu bolunmesi, bagli harf).
"""
from __future__ import annotations

import sys
from pathlib import Path

import config
from core.belge import pdfe_dok

KAYNAK = config.ROOT / "data" / "dilekce_deneme"
HEDEF = config.ROOT / "data" / "dilekce_pdf"


def main() -> None:
    if not KAYNAK.is_dir():
        sys.exit("kaynak klasor yok: %s" % KAYNAK)
    HEDEF.mkdir(parents=True, exist_ok=True)

    yazilan = atlanan = 0
    for yol in sorted(KAYNAK.glob("*.txt")):
        cikti = HEDEF / (yol.stem + ".pdf")
        if cikti.exists():
            atlanan += 1
            continue
        metin = yol.read_text("utf-8")
        cikti.write_bytes(pdfe_dok(metin, baslik=yol.stem))
        yazilan += 1
        if yazilan % 25 == 0:
            print("  %d PDF yazildi" % yazilan)

    # konular.json da tasiniyor: olcum etiketleri PDF adlarina bakacak
    etiket = KAYNAK / "konular.json"
    if etiket.exists():
        import json
        veri = json.loads(etiket.read_text("utf-8"))
        pdf_veri = {k.replace(".txt", ".pdf"): v for k, v in veri.items()}
        (HEDEF / "konular.json").write_text(
            json.dumps(pdf_veri, ensure_ascii=False, indent=1), "utf-8")

    print("toplam %d yeni PDF, %d zaten vardi -> %s"
          % (yazilan, atlanan, HEDEF))


if __name__ == "__main__":
    main()
