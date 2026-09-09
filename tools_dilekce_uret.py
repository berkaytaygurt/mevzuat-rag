"""Deneme icin sentetik dilekce kulliyati uretir.

    .venv\\Scripts\\python tools_dilekce_uret.py --adet 4

NEDEN SENTETIK

"Avukat kendi eski dilekcesini bulabiliyor mu" sorusunu olcmek icin bir
dilekce yigini lazim ve gercek dilekceler gizli. Konuyu BIZ verdigimiz
icin altin etiket bedava geliyor: hangi dosyanin hangi konuda oldugunu
zaten biliyoruz.

DURUSTLUK NOTU

Sentetik kulliyat gercekten KOLAY bir sinav. Gemini'nin urettigi
dilekceler birbirinden daha net ayrilir, dili daha duzenlidir, ayni
konu farkli kelimelerle anlatilmaz. Gercek bir buro arsivinde ayni
konuda on dilekce vardir ve hepsi birbirine benzer. Buradan cikacak
sayi TAVAN sayilmali, beklenti degil.

Uretilen dosyalar data/ altinda; depoya girmiyor.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

import config
from core.generate import Generator

HEDEF = config.ROOT / "data" / "dilekce_deneme"

# (konu_kodu, hukuk alani, dilekce konusu). Arama sorgusu da bu
# konudan turetiliyor, o yuzden dilekcenin ICINDE bu cumlenin aynen
# gecmemesi onemli -- yoksa olcum kelime eslesmesine doner.
KONULAR = [
    ("is-savunma", "iş hukuku", "işçinin savunması alınmadan iş sözleşmesinin feshi"),
    ("is-ihbar", "iş hukuku", "ihbar tazminatı ödenmemesi"),
    ("is-fazlacalisma", "iş hukuku", "ödenmeyen fazla çalışma ücreti"),
    ("is-yillikizin", "iş hukuku", "kullandırılmayan yıllık ücretli izin"),
    ("is-mobbing", "iş hukuku", "işyerinde psikolojik taciz nedeniyle haklı fesih"),
    ("is-kazasi", "iş hukuku", "iş kazası nedeniyle maddi ve manevi tazminat"),
    ("is-sendika", "iş hukuku", "sendikal nedenle fesih ve sendikal tazminat"),
    ("kira-temerrut", "kira hukuku", "kira bedelinin ödenmemesi nedeniyle tahliye"),
    ("kira-ihtiyac", "kira hukuku", "konut ihtiyacı nedeniyle tahliye"),
    ("kira-tespit", "kira hukuku", "kira bedelinin tespiti"),
    ("kira-tahliyetaah", "kira hukuku", "tahliye taahhüdüne dayalı tahliye"),
    ("bos-siddetli", "aile hukuku", "evlilik birliğinin sarsılması nedeniyle boşanma"),
    ("bos-zina", "aile hukuku", "zina nedeniyle boşanma"),
    ("bos-nafaka", "aile hukuku", "yoksulluk nafakasının artırılması"),
    ("bos-velayet", "aile hukuku", "velayetin değiştirilmesi"),
    ("mir-tapuiptal", "miras hukuku", "muris muvazaası nedeniyle tapu iptali ve tescil"),
    ("mir-tenkis", "miras hukuku", "saklı payın ihlali nedeniyle tenkis"),
    ("mir-ret", "miras hukuku", "mirasın hükmen reddi"),
    ("tic-cek", "ticaret hukuku", "karşılıksız çeke dayalı alacak"),
    ("tic-haksizrekabet", "ticaret hukuku", "haksız rekabetin tespiti ve önlenmesi"),
    ("tic-ortaklik", "ticaret hukuku", "limited şirket ortaklığından çıkarılma"),
    ("tuk-ayipli", "tüketici hukuku", "ayıplı mal nedeniyle bedel iadesi"),
    ("tuk-cayma", "tüketici hukuku", "mesafeli sözleşmede cayma hakkı"),
    ("cez-hakaret", "ceza hukuku", "hakaret suçundan şikâyet"),
    ("cez-dolandiricilik", "ceza hukuku", "nitelikli dolandırıcılık suçundan şikâyet"),
    ("cez-yaralama", "ceza hukuku", "kasten yaralama suçundan şikâyet"),
    ("cez-tehdit", "ceza hukuku", "tehdit ve şantaj suçundan şikâyet"),
    ("idr-disiplin", "idare hukuku", "memura verilen disiplin cezasının iptali"),
    ("idr-atama", "idare hukuku", "naklen atama işleminin iptali"),
    ("idr-imar", "idare hukuku", "imar planı değişikliğinin iptali"),
    ("idr-vergi", "vergi hukuku", "vergi ziyaı cezasının kaldırılması"),
    ("icr-itiraz", "icra hukuku", "icra takibine itirazın iptali"),
    ("icr-istihkak", "icra hukuku", "haczedilen mal üzerinde istihkak iddiası"),
    ("bor-haksizfiil", "borçlar hukuku", "trafik kazası nedeniyle tazminat"),
    ("bor-sebepsiz", "borçlar hukuku", "sebepsiz zenginleşme nedeniyle iade"),
    ("bor-genelislem", "borçlar hukuku", "genel işlem koşullarının geçersizliği"),
    ("kvk-silme", "kişisel veriler", "kişisel verilerin silinmesi talebinin reddi"),
    ("fik-marka", "fikri mülkiyet", "marka hükümsüzlüğü ve terkin"),
    ("gay-elatma", "eşya hukuku", "taşınmaza elatmanın önlenmesi"),
    ("gay-ortaklik", "eşya hukuku", "ortaklığın giderilmesi"),
]

SISTEM = """Sen deneyimli bir Türk avukatısın. Sana bir hukuki konu
verilir, sen o konuda mahkemeye sunulacak gerçekçi bir dilekçe
yazarsın.

Kurallar:
1. Gerçek dilekçe düzenini kullan: mahkeme adı, TARAFLAR, KONU,
   AÇIKLAMALAR (numaralı), HUKUKİ SEBEPLER, DELİLLER, SONUÇ VE İSTEM.
2. Olayı SOMUT yaz: tarihler, süreler, tutarlar, kişi adları uydur.
3. İlgili kanun maddelerine atıf yap.
4. Sana verilen konu cümlesini AYNEN kullanma; olayı kendi
   kelimelerinle anlat.
5. 250-400 kelime. Başlık veya açıklama ekleme, doğrudan dilekçeyi yaz."""

ISTEM = """Hukuk alanı: {alan}
Konu: {konu}
Bu olayda geçen ek ayrıntı: {ayrinti}

Bu konuda bir dilekçe yaz."""

AYRINTILAR = [
    "taraflardan biri şirket, diğeri gerçek kişi",
    "olay bir taşra ilçesinde geçiyor",
    "arada yazılı bir sözleşme var",
    "taraflar arasında daha önce de uyuşmazlık yaşanmış",
    "olayda tanık beyanları belirleyici",
    "bilirkişi incelemesi talep ediliyor",
    "karşı taraf zamanaşımı def'i ileri sürmüş",
    "ihtarname gönderilmiş ama sonuç alınamamış",
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--adet", type=int, default=4,
                    help="konu basina uretilecek dilekce sayisi")
    args = ap.parse_args()

    HEDEF.mkdir(parents=True, exist_ok=True)
    etiket_yolu = HEDEF / "konular.json"
    etiketler = json.loads(etiket_yolu.read_text("utf-8")) if etiket_yolu.exists() else {}

    uretici = Generator(provider="gemini")
    rastgele = random.Random(20260910)
    basla = time.time()
    yeni = 0

    for kod, alan, konu in KONULAR:
        for i in range(1, args.adet + 1):
            ad = f"{kod}-{i}.txt"
            yol = HEDEF / ad
            if yol.exists():
                continue                      # yeniden calistirilabilir olsun
            istem = ISTEM.format(alan=alan, konu=konu,
                                 ayrinti=rastgele.choice(AYRINTILAR))
            try:
                metin = uretici._gemini(istem, sistem=SISTEM,
                                        model=config.GEMINI_HIZLI_MODEL)
            except Exception as exc:
                print(f"  {ad}: HATA {str(exc)[:70]}")
                # Butce tavani gibi durumlarda devam etmenin anlami yok
                if "tavan" in str(exc).lower() or "quota" in str(exc).lower():
                    sys.exit("durduruldu")
                continue
            if not metin or len(metin) < 250:
                print(f"  {ad}: cok kisa, atlandi")
                continue
            yol.write_text(metin.strip(), encoding="utf-8")
            etiketler[ad] = {"konu_kodu": kod, "alan": alan, "konu": konu}
            yeni += 1
            if yeni % 10 == 0:
                etiket_yolu.write_text(
                    json.dumps(etiketler, ensure_ascii=False, indent=1), "utf-8")
                print(f"  {yeni} dilekce uretildi ({time.time() - basla:.0f} sn)")

    etiket_yolu.write_text(
        json.dumps(etiketler, ensure_ascii=False, indent=1), "utf-8")
    print(f"\ntoplam {len(etiketler)} dilekce, bu calistirmada {yeni} yeni")
    print(f"sure: {time.time() - basla:.0f} sn")
    from core import butce
    print("butce:", butce.durum())


if __name__ == "__main__":
    main()
