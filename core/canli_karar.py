"""Yerel kulliyat zayif kaldiginda Yargitay'dan CANLI karar cekme.

NEDEN VAR
Kararlar bugune kadar elle secilmis anahtar kelimelerle onceden
indiriliyordu: "muris muvazaasi", "manevi tazminat", "ecrimisil"... 55
tane. Bu listeyi bir insan yazdi, veriden cikarilmadi. Dogal sonucu:
listede olmayan bir konu sorulunca karar bolumu BOS geliyor, hem de
Yargitay'da o konuda yuz binlerce karar dururken.

OLCULDU (canli cekim, tek soru):

    arama                0,6 sn
    5 karar metni        3,9 sn
    toplam               4,5 sn      429 hiz siniri: 0 kez

Yani canli cekim mumkun. 429 saatlerce arka arkaya 60'ar belge cekince
cikiyor; bir soruluk kisa istek sorunsuz.

AMA YARGITAY'IN ARAMASI ANLAM BILMIYOR
Dogal cumle verildiginde kelimeleri OR'layip getiriyor. Olculdu:

    soru:  "babam olmeden once tapuyu kardesime devretmis,
            ben mirastan pay alabilir miyim"
    donen: 3 karar da "kadastro oncesi nedene dayali tapu iptali"

Konu komsu ama soru MURIS MUVAZAASI, o degil. Bu yuzden iki kademe
sart: (1) soru once hukuki terime cevriliyor, (2) gelen kararlar kendi
yeniden siralayicimizla soruya gore siralaniyor. Yargitay'in siralamasi
oldugu gibi kullanilirsa avukatin kendi sitede yapacagindan farki
kalmaz; deger kattigimiz yer tam olarak burasi.

TERIM UYDURMA SORUNU
Model sicakligi 0 olmasina ragmen ayni soruya farkli terimler
uretebiliyor ve bazen OLMAYAN bir dava adi yaziyor. Olculdu:

    soru  "patent hakkina tecavuz halinde ne talep edilebilir"
    bir kez  "patent hakkina tecavuz tazminati"   dogru
    bir kez  "patent infisahi tazminat"           BOYLE BIR DAVA YOK
                                                  (infisah = sona erme)

Yanlis terim sessizce yanlis kararlar getiriyor; hata mesaji yok.
Istem bu yuzden ornekli ve "terimi uydurma" kuralli.

TASARIM: YEREL ONCE, CANLI SONRA
Once yerel indekse bakilir -- anlik ve internetsiz calisir. Yalnizca
sonuc zayifsa aga cikilir. Cekilen kararlar onbellege yaziliyor, yani
kulliyat GERCEK SORULARDAN buyuyor; bir daha ayni konu soruldugunda
yerelden aninda geliyor.
"""
from __future__ import annotations

import logging
import os

import config

log = logging.getLogger(__name__)

SISTEM = """Sen bir Türk hukuku uzmanısın. Sana bir olay ya da soru
verilir, sen onun Yargıtay karar aramasında kullanılacak HUKUKİ TERİMİNİ
yazarsın.

Kurallar:
1. Sadece arama terimini yaz, en fazla 4 kelime.
2. Davanın/kurumun YERLEŞİK teknik adını kullan. Terimi UYDURMA; emin
   değilsen daha genel ama doğru olan terimi yaz.
3. Açıklama yapma, tırnak kullanma, cümle kurma.
4. Soru hukuki değilse ya da terim çıkaramıyorsan yalnızca YOK yaz.
5. Terimden sonra "|" koyup hangi yüksek mahkemede aranacağını yaz:
   YARGITAY  -> kişiler arası uyuşmazlıklar ve bütün ceza davaları
                (boşanma, miras, kira, iş, ticaret, tazminat, suç)
   DANISTAY  -> kişi ile DEVLET arasındaki uyuşmazlıklar
                (memur, disiplin, atama, vergi, imar, kamulaştırma,
                 ruhsat, ihale, öğrenci işleri)

Örnekler:
Olay: babam ölmeden önce tapuyu kardeşime devretmiş, pay alabilir miyim
Terim: muris muvazaası | YARGITAY

Olay: kiracı iki kez ihtar aldı, tahliye edebilir miyim
Terim: iki haklı ihtar nedeniyle tahliye | YARGITAY

Olay: başkası markamı izinsiz kullanıyor, ne yapabilirim
Terim: markaya tecavüz | YARGITAY

Olay: patentimi taklit ettiler, tazminat isteyebilir miyim
Terim: patent hakkına tecavüz | YARGITAY

Olay: komşum arsamı kullanıyor, kira gibi bedel isteyebilir miyim
Terim: ecrimisil | YARGITAY

Olay: memura verilen kademe ilerlemesinin durdurulması cezası iptal olur mu
Terim: disiplin cezasının iptali | DANISTAY

Olay: belediye imar planını değiştirdi, arsam yeşil alan oldu
Terim: imar planının iptali | DANISTAY

Olay: vergi cezası kesildi, itiraz edebilir miyim
Terim: vergi ceza ihbarnamesinin iptali | DANISTAY

Olay: kahve nasıl demlenir
Terim: YOK"""

ISTEM = ("Olay: {soru}\n\n"
         "Aranacak hukuki terim ve hangi yüksek mahkemede aranacağı:")

# Terim bundan uzunsa model kural disina cikmis demektir; kelime yigini
# Yargitay aramasinda OR'lanip alakasiz sonuc getiriyor.
EN_FAZLA_TERIM_KARAKTER = 60

# Canli cekimde kac karar metni indirilecek. Olculdu: 5 belge 3,9 sn.
# 10'un uzerine cikmak cevabi hissedilir yavaslatiyor ve yeniden
# siralayici zaten ilk birkaci seciyor.
CANLI_ADET = 8

# TOPLAM SURE BUTCESI (saniye). Butce dolunca elde ne varsa onunla
# donuluyor.
#
# NEDEN ZORUNLU: EmsalClient 429 gorunce 45 saniye bekliyor ve altiya
# kadar deniyor. Bu davranis CEKIM icin dogru (bir kararin tamamini
# kaybetmektense beklenir) ama KULLANICI ISTEGI icinde felaket: tek bir
# 429 cevabi dakikalarca bekletiyor. Olculdu -- site Cloudflare tuneli
# arkasinda ve tunelin origin zaman asimi 100 saniye; asilinca istek
# "524" ile tumden dusuyor, yani avukat cevabin tamamini kaybediyor.
#
# Butce dolunca elde ne varsa donuyoruz: iki karar, bir cevabin hic
# gelmemesinden iyidir.
CANLI_SURE_BUTCESI = float(os.getenv("CANLI_SURE_BUTCESI", "20"))

# Yerel sonuc bu sayidan azsa aga cikilir.
YETERSIZ_SINIR = 2

# Canli cekilen kararlarin BIRIKTIGI dosya. Aranabilir indekse
# katilmalari icin "python cli.py canli-devral" calistirilir.
#
# NEDEN AYRI DOSYA, NEDEN ISTEK ICINDE INDEKSLENMIYOR
# Akla ilk gelen "geleni dogrudan kararlar.json'a ekle ve indeksi
# tazele" oluyor. Iki sebeple yapilmiyor:
#
#   1. kararlar.json 48 MB. Her istekte oku-degistir-yaz yapmak hem
#      yavas hem tehlikeli: bu dosya daha once tam da boyle bir yazma
#      sirasinda MemoryError alip yarim kalmisti (599 MB -> 69 MB).
#      Kullanicinin sorusu bir yazma catismasina kurban gitmemeli.
#   2. Vektor indeksini tazelemek gomme modelini yukluyor ve dakikalar
#      suruyor. Istek icinde yapilirsa avukat 4,5 saniye degil
#      dakikalarca bekler.
#
# Belge METINLERI zaten EmsalClient onbelleginde (karar_cache/), yani
# devralma sirasinda ag istegi yapilmiyor -- sadece diskten okunuyor.
CANLI_BIRIKIM = config.RAW_DIR / "canli_kararlar.json"


def arama_hedefi(soru: str, uretici) -> tuple[str, str]:
    """Olayi (hukuki terim, mahkeme) ciftine cevirir.

    MAHKEME NEDEN SORULUYOR
    Turkiye'de yargi ikiye ayriliyor ve ikisinin karar arsivi AYRI:

        Yargitay  kisiler arasi uyusmazliklar + butun ceza davalari
        Danistay  kisi ile DEVLET arasindaki uyusmazliklar
                  (memur, disiplin, vergi, imar, kamulastirma, ihale)

    Yanlis arsivde aramak bos sonuc demek. Memur disiplin cezasi
    Yargitay'da yok; orada aramak "bu konuda karar bulunamadi" der,
    oysa Danistay'da binlercesi var.

    Mahkeme AYRI BIR CAGRI ILE sorulmuyor: terim uretilirken ayni
    istemde soruluyor, yani ek maliyet ve ek gecikme yok.

    Doner: (terim, "yargitay" | "danistay"). Terim uretilemezse ("", "").
    """
    try:
        c = uretici._gemini(ISTEM.format(soru=soru), sistem=SISTEM,
                            model=config.GEMINI_HIZLI_MODEL)
    except Exception as exc:
        log.warning("arama terimi uretilemedi: %s", str(exc)[:80])
        return "", ""
    ham = (c or "").strip().strip('"').strip()
    # HyDE'de ogrenildi: istem "terim yaz" diye emrederse model hukuki
    # olmayan soruyu da zorla terime cevirmeye calisiyor. Cikis yolu sart.
    if ham.upper().startswith("YOK") or len(ham) < 3:
        return "", ""

    mahkeme = "yargitay"
    if "|" in ham:
        terim, _, kuyruk = ham.partition("|")
        if "DANI" in kuyruk.upper():
            mahkeme = "danistay"
    else:
        # Model kurali atlamis olabilir; terim yine kullanilir.
        terim = ham
    terim = terim.strip().strip('"').strip()
    if len(terim) < 3:
        return "", ""
    return terim[:EN_FAZLA_TERIM_KARAKTER], mahkeme


def arama_terimi(soru: str, uretici) -> str:
    """Yalnizca terim; mahkeme gerekmeyen cagiranlar icin."""
    return arama_hedefi(soru, uretici)[0]


class CanliKararArayici:
    """Yargitay'dan canli karar ceker ve yeniden siralar.

    Ag hatasi cevabi ENGELLEMEMELI: her sey bos listeye duser. Canli
    cekim bir ek, bir bagimlilik degil.
    """

    def __init__(self, uretici, reranker=None, istemci=None):
        self.uretici = uretici
        self.reranker = reranker
        self._istemci = istemci
        self._danistay = None
        self.son_terim = ""
        self.son_mahkeme = ""

    def _istemciyi_kur(self, mahkeme: str = "yargitay"):
        """Ilgili mahkemenin istemcisini doner, bir kez kurar.

        Iki AYRI arsiv var ve ikisi ayri sitede. Yanlis arsivde aramak
        bos sonuc demek: memur disiplin cezasi Yargitay'da yok.
        """
        if mahkeme == "danistay":
            if self._danistay is None:
                from scraper.danistay import DanistayClient
                self._danistay = DanistayClient(delay=0.5)
            return self._danistay
        if self._istemci is None:
            from scraper.ictihat import EmsalClient
            # Gecikme kisa: tek soruluk kisa istek 429 uretmiyor ve
            # kullanici cevabi bekliyor.
            self._istemci = EmsalClient(delay=0.5)
        return self._istemci

    def _birik(self, adaylar: list[dict]) -> None:
        """Canli gelen kararlari birikim dosyasina ekler.

        Yazma HATASI CEVABI ENGELLEMEZ: birikim bir kolaylik, sistemin
        calismasi buna bagli degil. Ayni karar iki kez eklenmesin diye
        id'ye gore tekillestiriliyor.
        """
        import json

        try:
            mevcut = {}
            if CANLI_BIRIKIM.exists():
                for k in json.loads(CANLI_BIRIKIM.read_text(encoding="utf-8")):
                    mevcut[k.get("karar_id", "")] = k
            yeni_sayi = 0
            for a in adaylar:
                if a["karar_id"] not in mevcut:
                    mevcut[a["karar_id"]] = a
                    yeni_sayi += 1
            if not yeni_sayi:
                return
            # Atomik yazma: yarim kalan dosya bir dahaki okumada patlar.
            gecici = CANLI_BIRIKIM.with_suffix(".tmp")
            gecici.write_text(json.dumps(list(mevcut.values()),
                                         ensure_ascii=False),
                              encoding="utf-8")
            import os
            os.replace(gecici, CANLI_BIRIKIM)
            log.info("canli birikim: +%d karar (toplam %d)",
                     yeni_sayi, len(mevcut))
        except Exception as exc:
            log.warning("canli birikim yazilamadi: %s", str(exc)[:80])

    def ara(self, soru: str, limit: int = 3) -> list[dict]:
        terim, mahkeme = arama_hedefi(soru, self.uretici)
        self.son_terim = terim
        self.son_mahkeme = mahkeme
        if not terim:
            return []

        try:
            istemci = self._istemciyi_kur(mahkeme)
            kayitlar = istemci.ara(terim, en_fazla=CANLI_ADET,
                                   sayfa_boyu=CANLI_ADET)
        except Exception as exc:
            log.warning("canli arama basarisiz: %s", str(exc)[:120])
            return []

        import time

        bitis = time.time() + CANLI_SURE_BUTCESI
        adaylar: list[dict] = []
        for k in kayitlar:
            if time.time() > bitis:
                log.info("canli cekim sure butcesi doldu, %d karar ile donuluyor",
                         len(adaylar))
                break
            try:
                if mahkeme == "danistay":
                    # Danistay ham HTML donuyor; Yargitay istemcisi
                    # temizligi kendi yapiyor.
                    #
                    # KUNYE MUTLAKA ATILMALI. Danistay karari uzun bir
                    # usul basligiyla basliyor (TEMYIZ EDEN, VEKILI,
                    # DAVALI, DAVANIN KONUSU...). Eleme modeli metnin
                    # basini okudugu icin bu basliktan oteye gecemiyor
                    # ve alaka puani cok dusuk cikiyordu -- olculdu,
                    # Danistay kararlari 0,03-0,17 alirken Yargitay
                    # kararlari 0,999 aliyordu. Ayni havuzda
                    # birlestirilince Danistay hep dibe gomuluyordu.
                    from scraper.karar_parser import html_metne, kunye_at
                    metin = kunye_at(html_metne(istemci.belge(k.id, terim)))
                else:
                    metin = istemci.belge(k.id)
            except Exception as exc:
                log.debug("canli belge alinamadi (%s): %s", k.id, exc)
                continue
            if not metin:
                continue
            ad = "Danıştay" if mahkeme == "danistay" else "Yargıtay"
            adaylar.append({
                "karar_id": k.id,
                "chunk_id": f"canli-{k.id}",
                "kisa_ad": f"{ad} {k.daire} {k.esas_no} E. {k.karar_no} K.",
                "mahkeme": ad,
                "daire": k.daire,
                "esas_no": k.esas_no,
                "karar_no": k.karar_no,
                "karar_tarihi": k.karar_tarihi,
                "metin": metin,
                "canli": True,
                "arama_terimi": terim,
            })

        if not adaylar:
            return []

        self._birik(adaylar)

        # Yargitay'in kendi siralamasi tarihe gore; soruyla ilgisi yok.
        # Deger kattigimiz yer burasi: kararlari SORUYA gore siraliyoruz.
        if self.reranker is not None:
            try:
                adaylar = self.reranker.sirala(soru, adaylar, limit=limit)
            except Exception as exc:
                log.warning("canli yeniden siralama basarisiz: %s",
                            str(exc)[:80])
        return adaylar[:limit]
