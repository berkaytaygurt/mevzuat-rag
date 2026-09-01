"""Avukat sorularinda uc yaniti karsilastirir: ciplak Gemini, Aibars, Claude.

TASARIM
Sorular birbirinden bagimsiz oldugu icin is dort asamaya bolundu ve ag
cagrilari paralel calistiriliyor. Ilk surum her soruyu bastan sona sirayla
isliyordu ve soru basina ~2 dakika suruyordu; olculdu -- surenin neredeyse
tamami bekleyen ag cagrisiydi, islem degil.

    1. asama  ciplak Gemini cevaplari   -- paralel (ag)
    2. asama  Aibars aramalari          -- sirali (tek GPU)
    3. asama  Aibars cevap uretimi      -- paralel (ag)
    4. asama  atif dogrulama            -- yerel, aninda

PUANLAMA -- hakem yok
Her cevaptaki madde atiflari kulliyata karsi denetlenir:

    atif    -- cevapta kac madde gosterildi
    var     -- gosterilen madde kulliyatta gercekten var mi
    isabet  -- gosterilen madde sorunun konusuyla ilgili mi

Ilk iki olcut tamamen nesnel. Uslup, akicilik, uzunluk olculmez.
"""
from __future__ import annotations

import argparse
import io
import json
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor

import config
from core import butce
from core.atif import atiflari_cikar, madde_bul

logging.basicConfig(level=logging.ERROR)

CIPLAK_SISTEM = ("Sen Türk iş hukuku bilen bir asistansın. Kısa cevap ver ve "
                 "hangi kanunun hangi maddesine dayandığını mutlaka yaz.")

# Sorunun konusunu tasimayan sik kelimeler
_DURAK = {"nedir", "nasıl", "hangi", "kaç", "için", "olur", "gerekir", "mudur",
          "midir", "hangisi", "kimdir", "kadar", "sonra", "hakkı", "hakları",
          "süresi", "süreleri", "belirlenir", "hesaplanır", "yapılır", "verilir",
          "ödenir", "aranır", "edilir", "olabilir", "yapılabilir", "alabilir",
          "işçi", "işçinin", "işveren", "işverenin", "bir", "ile", "veya",
          "hallerde", "şartlarda", "itibaren", "içinde"}


def anahtar_kelimeler(soru: str) -> set[str]:
    return {k for k in re.findall(r"\w{4,}", soru.lower()) if k not in _DURAK}


def isabetli_mi(madde: dict, soru: str) -> bool:
    """Gosterilen madde sorunun konusuyla ilgili mi.

    Kaba bir olcut: anahtar kelimelerden biri madde metninde ya da basliginda
    geciyorsa ilgili sayilir. Uc yanit da ayni olcutle degerlendirildigi icin
    karsilastirma adil kalir.
    """
    metin = ((madde.get("metin") or "") + " " + (madde.get("baslik") or "")).lower()
    anahtarlar = anahtar_kelimeler(soru)
    return bool(anahtarlar) and any(k[:6] in metin for k in anahtarlar)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--adet", type=int, default=52)
    ap.add_argument("--isci", type=int, default=6, help="paralel ag istegi")
    args = ap.parse_args()

    from core.embedder import Embedder
    from core.generate import Generator
    from core.retrieve import Retriever
    from core.vektor import VektorDeposu
    from tests.avukat_sorulari import SORULAR
    from claude_cevaplari import CEVAPLAR as CLAUDE

    maddeler = json.loads(
        (config.RAW_DIR / "maddeler.json").read_text(encoding="utf-8"))
    sorular = SORULAR[:args.adet]
    g = Generator(provider="gemini")
    basla = time.time()

    def ciplak(soru: str) -> str:
        try:
            return g._gemini(soru + "\nKısa cevap ver.", sistem=CIPLAK_SISTEM) or ""
        except Exception as exc:
            return f"(hata: {str(exc)[:60]})"

    print("1/4 ciplak Gemini cevaplari...", flush=True)
    with ThreadPoolExecutor(max_workers=args.isci) as h:
        ciplak_cevaplar = list(h.map(ciplak, sorular))
    print(f"    bitti ({time.time()-basla:.0f} sn)", flush=True)

    print("2/4 Aibars aramalari...", flush=True)
    store = VektorDeposu()
    r = Retriever(store, Embedder())
    bulunanlar = [r.ara(s, limit=6) for s in sorular]
    print(f"    bitti ({time.time()-basla:.0f} sn)", flush=True)

    def aibars(ikili) -> str:
        soru, bulunan = ikili
        try:
            return g.cevapla(soru, bulunan) or ""
        except Exception as exc:
            return f"(hata: {str(exc)[:60]})"

    print("3/4 Aibars cevaplari...", flush=True)
    with ThreadPoolExecutor(max_workers=args.isci) as h:
        aibars_cevaplar = list(h.map(aibars, list(zip(sorular, bulunanlar))))
    print(f"    bitti ({time.time()-basla:.0f} sn)", flush=True)

    print("4/4 atif dogrulama...", flush=True)
    puan = {k: {"atif": 0, "var": 0, "isabet": 0, "atifsiz": 0}
            for k in ("ciplak", "aibars", "claude")}
    kayit = []

    for soru, a, b in zip(sorular, ciplak_cevaplar, aibars_cevaplar):
        c = CLAUDE.get(soru, "")
        satir = {"soru": soru, "ciplak": a, "aibars": b, "claude": c}
        for etiket, cevap in (("ciplak", a), ("aibars", b), ("claude", c)):
            atiflar = atiflari_cikar(cevap)
            if not atiflar:
                puan[etiket]["atifsiz"] += 1
            satir[f"{etiket}_atif"] = [f"{k} m.{n}" for k, n in atiflar]
            bulunanlar_m = []
            for kaynak, madde_no in atiflar:
                puan[etiket]["atif"] += 1
                m = madde_bul(maddeler, kaynak, madde_no)
                if m is None:
                    continue
                puan[etiket]["var"] += 1
                if isabetli_mi(m, soru):
                    puan[etiket]["isabet"] += 1
                bulunanlar_m.append(m)
            satir[f"{etiket}_var"] = len(bulunanlar_m)
        kayit.append(satir)

    _yaz(puan, kayit, len(sorular), time.time() - basla)
    store.close()
    print(f"BITTI -- {time.time()-basla:.0f} sn", flush=True)


def _yaz(puan: dict, kayit: list, toplam: int, sure: float) -> None:
    o = io.StringIO()
    o.write(f"AVUKAT SORULARI TESTI -- {toplam} soru, {sure:.0f} saniye\n")
    o.write("(is hukuku, elle yazilmis gercek sorular)\n\n")
    o.write(f"{'':<18}{'atıf':>7}{'var':>13}{'isabet':>9}{'atıfsız':>9}\n")
    o.write("-" * 58 + "\n")
    for etiket, ad in (("ciplak", "çıplak Gemini"), ("aibars", "Aibars"),
                       ("claude", "Claude (ben)")):
        p = puan[etiket]
        oran = f"({100*p['var']/p['atif']:.0f}%)" if p["atif"] else "(-)"
        o.write(f"{ad:<18}{p['atif']:>7}{p['var']:>7} {oran:>6}"
                f"{p['isabet']:>8}{p['atifsiz']:>9}\n")
    o.write("\natıf    = cevapta gösterilen madde sayısı\n")
    o.write("var     = bu maddelerden külliyatta gerçekten bulunanlar\n")
    o.write("isabet  = bulunan maddenin sorunun konusuyla ilgili olması\n")
    o.write("atıfsız = hiç madde göstermeyen cevap sayısı\n")
    o.write(f"\n{butce.durum()}\n")
    with open("avukat_testi.txt", "w", encoding="utf-8") as f:
        f.write(o.getvalue())
    with open("avukat_testi.json", "w", encoding="utf-8") as f:
        json.dump(kayit, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
