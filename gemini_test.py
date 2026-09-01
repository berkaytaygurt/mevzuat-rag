"""Gemini saglayicisiyla ornek sorulari calistirir ve ciktiyi dosyaya yazar."""
from __future__ import annotations

import io
import logging
import time

from core.embedder import Embedder
from core.generate import Generator, atiflari_dogrula, baglam_kur, sayilari_dogrula
from core.retrieve import Retriever
from core.store import MevzuatStore

logging.basicConfig(level=logging.ERROR)

SORULAR = [
    "Yıllık ücretli izin süresi kaç gündür?",
    "Boşanma sebepleri nelerdir?",
    "Hırsızlık suçunun cezası nedir?",
    "Kişisel verilerin işlenme şartları nelerdir?",
    "Kira sözleşmesini kiracı nasıl feshedebilir?",
    "Uzayda arsa almak için ne gerekir?",      # kulliyat disi -- reddetmeli
]


def main() -> None:
    store = MevzuatStore()
    retriever = Retriever(store, Embedder())
    getirilen = {s: retriever.ara(s, limit=5) for s in SORULAR}
    store.close()

    uretici = Generator(provider="gemini")
    out = io.StringIO()
    toplam_sure = 0.0
    toplam_suphe = 0

    for soru in SORULAR:
        maddeler = getirilen[soru]
        basla = time.time()
        try:
            cevap = uretici.cevapla(soru, maddeler)
        except Exception as exc:
            cevap = f"(HATA: {str(exc)[:200]})"
        sure = time.time() - basla
        toplam_sure += sure

        atif = atiflari_dogrula(cevap, maddeler)
        sayi = sayilari_dogrula(cevap, baglam_kur(maddeler))
        toplam_suphe += len(atif) + len(sayi)

        out.write("\n" + "=" * 68 + "\n")
        out.write(f"SORU: {soru}   ({sure:.1f} sn)\n")
        out.write("=" * 68 + "\n")
        out.write(cevap + "\n\n")

        dayanak = " | ".join(
            f"{m['mevzuat_adi'][:26]} m.{m['madde_no']}" for m in maddeler[:4]
        )
        out.write(f"[getirilen maddeler] {dayanak}\n")
        if atif or sayi:
            out.write(f"[SUPHELI] atif={atif}  sayi={sayi}\n")

    out.write("\n\n" + "=" * 68 + "\n")
    out.write(f"TOPLAM {toplam_sure:.1f} sn  "
              f"({toplam_sure / len(SORULAR):.1f} sn/soru)  |  "
              f"supheli isaret: {toplam_suphe}\n")

    with open("gemini_test.txt", "w", encoding="utf-8") as f:
        f.write(out.getvalue())
    print("bitti -> gemini_test.txt")


if __name__ == "__main__":
    main()
