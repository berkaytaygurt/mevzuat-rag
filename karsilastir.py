"""Yerel model ile Gemini'yi ayni sorular ve ayni maddelerle karsilastirir.

Getirilen maddeler bir kez hesaplanir ve iki saglayiciya da aynisi verilir;
boylece olculen tek sey cevap uretme kalitesi olur, arama degil.

    .venv\Scripts\python karsilastir.py
"""
from __future__ import annotations

import io
import logging
import time

import config
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
    "Uzayda arsa almak için ne gerekir?",   # kulliyat disi -- reddetmeli
]


def main() -> None:
    store = MevzuatStore()
    retriever = Retriever(store, Embedder())

    # Maddeleri bir kez getir, iki saglayiciya da aynisini ver
    getirilen = {s: retriever.ara(s, limit=5) for s in SORULAR}
    store.close()

    saglayicilar = ["local"]
    if config.GEMINI_API_KEY:
        saglayicilar.append("gemini")
    else:
        print("GEMINI_API_KEY yok, yalnizca yerel model calistirilacak.")

    out = io.StringIO()
    ozet: dict[str, dict] = {}

    for saglayici in saglayicilar:
        g = Generator(provider=saglayici)
        sayac = {"sure": 0.0, "supheli_atif": 0, "supheli_sayi": 0, "red": 0}
        out.write(f"\n{'='*70}\n{saglayici.upper()}\n{'='*70}\n")

        for soru in SORULAR:
            maddeler = getirilen[soru]
            t = time.time()
            try:
                cevap = g.cevapla(soru, maddeler)
            except Exception as exc:
                cevap = f"(HATA: {exc})"
            sure = time.time() - t
            sayac["sure"] += sure

            baglam = baglam_kur(maddeler)
            atif = atiflari_dogrula(cevap, maddeler)
            sayi = sayilari_dogrula(cevap, baglam)
            sayac["supheli_atif"] += len(atif)
            sayac["supheli_sayi"] += len(sayi)
            sayac["red"] += "dayanak bulamad" in cevap.lower()

            out.write(f"\n--- {soru}  ({sure:.1f} sn)\n{cevap}\n")
            if atif:
                out.write(f"    [supheli atif] {atif}\n")
            if sayi:
                out.write(f"    [supheli sayi] {sayi}\n")

        ozet[saglayici] = sayac

    out.write(f"\n\n{'='*70}\nOZET\n{'='*70}\n")
    out.write(f"{'saglayici':<12}{'toplam sure':>13}{'supheli atif':>15}"
              f"{'supheli sayi':>15}{'reddetti':>11}\n")
    for ad, s in ozet.items():
        out.write(f"{ad:<12}{s['sure']:>11.1f}sn{s['supheli_atif']:>15}"
                  f"{s['supheli_sayi']:>15}{s['red']:>11}\n")
    out.write("\nsupheli atif/sayi: dusuk olan iyi. reddetti: kulliyat disi soruyu\n"
              "reddetme sayisi (5 sorudan 1'i kulliyat disi, 1 olmali).\n")

    with open("karsilastirma.txt", "w", encoding="utf-8") as f:
        f.write(out.getvalue())
    print("sonuc -> karsilastirma.txt")


if __name__ == "__main__":
    main()
