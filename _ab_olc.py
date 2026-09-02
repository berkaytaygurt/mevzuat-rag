"""Iki kulliyati AYNI kosullarda olcer (dipnot duzeltmesi oncesi/sonrasi).

Artimli indeksleme sayesinde ikinci indeksi kurmak ~30 dakika; tam gomme
olsaydi 6.8 saat surerdi ve bu karsilastirma yapilamazdi.
"""
import argparse, gc, json, logging, sys, time
from pathlib import Path
sys.path.insert(0, ".")
logging.basicConfig(level=logging.INFO, format="%(message)s")

import config

ap = argparse.ArgumentParser()
ap.add_argument("--kulliyat", required=True)
ap.add_argument("--dizin", required=True)
ap.add_argument("--kaynak", default=None, help="vektorleri buradan yeniden kullan")
ap.add_argument("--kur", action="store_true", help="indeksi kur (yoksa sadece olc)")
a = ap.parse_args()

hedef = Path(a.dizin)
import cli
from core.embedder import Embedder
from core.retrieve import Retriever
from core.vektor import VektorDeposu

emb = Embedder()

if a.kur:
    import numpy as np
    from core.yazim import sozluk_kur

    maddeler = json.loads(Path(a.kulliyat).read_text(encoding="utf-8"))
    metinler = [cli._embed_metni(m) for m in maddeler]
    print(f"SONUC kulliyat: {len(maddeler)} madde", flush=True)

    config.INDEX_DIR = Path(a.kaynak) if a.kaynak else hedef
    satirlar, maske = cli._onceki_vektorler(metinler)
    config.INDEX_DIR = hedef

    if maske is not None and maske.any():
        eksik = [j for j in range(len(metinler)) if not maske[j]]
        print(f"SONUC yeniden kullanilan {int(maske.sum())}, gomulecek {len(eksik)}",
              flush=True)
        if eksik:
            satirlar[eksik] = emb.encode_documents([metinler[j] for j in eksik])
        vektorler = satirlar
    else:
        vektorler = emb.encode_documents(metinler)

    norm = np.linalg.norm(vektorler, axis=1, keepdims=True)
    norm[norm == 0] = 1.0
    store = VektorDeposu(hedef)
    store.kaydet(maddeler, vektorler / norm)
    sozluk_kur(maddeler, hedef / "yazim.json")
    del vektorler, satirlar, maddeler, metinler, norm
    gc.collect()
    Retriever(store, emb, bm25_yol=hedef / "bm25.pkl").bm25_kur()
    print("SONUC indeks kuruldu", flush=True)

# --- olcum ---
config.INDEX_DIR = hedef
from tests.olcum_seti import SORULAR

r = Retriever(VektorDeposu(hedef), emb, bm25_yol=hedef / "bm25.pkl")
config.MESELE_AYIR = False
config.SORGU_GENISLET = False
sıralar = []
bas = time.time()
for soru, kanun, madde in SORULAR:
    s = r.ara(soru, limit=10)
    yer = None
    for i, m in enumerate(s, 1):
        if m.get("mevzuat_no") == kanun and (madde is None or m.get("madde_no") == madde):
            yer = i
            break
    sıralar.append(yer)
n = len(sıralar)
ilk1 = sum(1 for x in sıralar if x == 1)
ilk3 = sum(1 for x in sıralar if x and x <= 3)
ilk5 = sum(1 for x in sıralar if x and x <= 5)
mrr = sum(1 / x for x in sıralar if x) / n
print(f"SONUC ==== {a.dizin}")
print(f"SONUC ilk-1 {ilk1}/{n} | ilk-3 {ilk3}/{n} | ilk-5 {ilk5}/{n} | MRR {mrr:.3f}"
      f" | {time.time()-bas:.0f} sn")
print("SONUC siralar:", sıralar)
