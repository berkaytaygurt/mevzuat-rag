"""Cevap uretimi. PROVIDER=local (GGUF) veya PROVIDER=gemini.

Prompt'un tek isi modeli getirilen maddelere baglamak. Hukukta uydurulmus bir
madde numarasi, yanlis cevaptan daha zararlidir -- kullanici onu dogru sanip
kaynak diye kullanir. Bu yuzden model kaynak gostermeye ve bilgi yoksa
"bulamadim" demeye zorlanir.
"""
from __future__ import annotations

import logging
import os
import re
import time
from pathlib import Path

import config
from core import butce

log = logging.getLogger(__name__)

# Prompt'un tek isi modeli getirilen maddelere baglamak.
#
# Iki tuzaga dikkat:
#  - Metin Turkce karakterlerle yazilmali; aksansiz yazildiginda kucuk modeller
#    ciktiyi da bozuk Turkce uretiyor.
#  - Ornek cumle KULLANMA. Soyut sablon yazildiginda ("(Kanun Adi m.X)") model
#    "Kanun Adi" ifadesini kopyaliyordu; somut ornek yazildiginda ise ornegin
#    kendisini cevap sanip "Hirsizligin cezasi nedir?" sorusuna "Isciye en az
#    on dort gun izin verilir (Is Kanunu m.53)" diye cevap verdi. Bicimi
#    tarif ediyoruz, gostermiyoruz.
#
# 3. kuralin ifadesi olculdu. "Verilen maddeler soruyu cevaplamiyorsa reddet"
# denildiginde, baglama mahkeme kararlari da eklenince model bes denemenin
# dordunde reddediyordu -- oysa dogru madde baglamdaydi. Kararlarin soruyu
# tam karsilamamasi tum cevabi reddetmeye yetiyor. "Bir kismi ilgisiz
# olabilir, ilgili olani kullan" ifadesiyle red 0/5'e dustu.
SISTEM = """Sen Türk mevzuatı konusunda yardımcı olan bir asistansın.

Kurallar:

1. Yalnızca sana verilen mevzuat maddelerine dayanarak cevap ver. Kendi
   bilginden madde numarası, süre, tutar veya tarih ekleme.

2. Her bilgiden sonra, o bilgiyi aldığın maddeyi parantez içinde göster.
   Parantezin içine sana verilen kanunun adını ve madde numarasını yaz.
   Sana verilmeyen bir kanun adı yazma.

3. Verilen maddelerin bir kısmı soruyla ilgisiz olabilir; ilgili olanları
   kullan. HİÇBİRİ ilgili değilse şunu yaz ve dur: "Verilen mevzuatta bu
   soruya dayanak bulamadım." Tahmin yürütme.

4. Bir madde yürürlükten kalkmışsa bunu mutlaka belirt.

5. Kısa ve düz yaz. Sorulmayan şeyi anlatma, yorum ekleme.

6. Cevabın EN SONUNA, ayrı bir satır olarak tam şu cümleyi ekle:
   Bu bilgi genel niteliktedir, hukuki görüş yerine geçmez."""

# Kararli istem. ILK SURUM CEVABI BOZUYORDU: mevzuat bolumu dogru maddeyi
# tasidigi halde model uc denemenin ikisinde "dayanak bulamadim" diyordu
# (kararsiz istemde sifir). Sebep, iki bolumlu yapinin sistem promptundaki
# "dayanak yoksa reddet" kuralini one cikarmasiydi -- model kararlarin
# soruyu tam karsilamadigini gorup tumunu reddediyordu.
#
# Duzeltme: mevzuat bolumunun ASIL cevap oldugu, kararlarin yalnizca EK
# oldugu acikca yaziliyor ve reddetme kurali yalnizca mevzuat bolumu icin
# gecerli kiliniyor.
KULLANICI_KARARLI = """Aşağıda sorunun ilgili olabileceği mevzuat maddeleri
ve bu konuda verilmiş mahkeme kararları var.

--- MEVZUAT ---
{baglam}
--- MEVZUAT SONU ---

--- MAHKEME KARARLARI ---
{kararlar}
--- MAHKEME KARARLARI SONU ---

Soru: {soru}

ASIL CEVAP mevzuat bölümünden gelir. Yukarıdaki maddelerden soruyla ilgili
olanlara dayanarak cevapla; her cümlenin sonunda kanun adını ve madde
numarasını parantez içinde göster. Maddelerin tamamı ilgili olmayabilir,
ilgili olanı kullan.

Yalnızca mevzuat bölümünde soruyla ilgili HİÇBİR madde yoksa "Verilen
mevzuatta bu soruya dayanak bulamadım." yaz. Kararların soruyu tam
karşılamaması bu cümleyi yazmak için sebep değildir.

Cevabın ardından "Mahkeme kararları:" başlıklı ayrı bir bölüm ekle ve
kararların bu konuda ne dediğini en fazla iki cümleyle yaz. Karardaki bir
ifadeyi kanun hükmü gibi gösterme; kararlar örnektir, bağlayıcı kural
maddedir. Kararlar ilgisizse bu bölümü hiç yazma."""


KULLANICI = """Aşağıda, sorunun ilgili olabileceği mevzuat maddeleri var.

--- MEVZUAT ---
{baglam}
--- MEVZUAT SONU ---

Soru: {soru}

Yalnızca yukarıdaki maddelere dayanarak cevapla. Her cümlenin sonunda, bilgiyi
aldığın maddenin kanun adını ve numarasını parantez içinde göster."""


def _cuda_dll_yolunu_ekle() -> None:
    """Windows'ta llama-cpp'nin CUDA calisma zamanini bulmasini saglar.

    llama_cpp/lib icinde ggml-cuda.dll var ama bagimli oldugu cudart64_12.dll
    ve cublas64_12.dll yok; onlar torch ile birlikte geliyor. Windows bu
    klasoru kendiliginden aramadigi icin llama.dll "modul bulunamadi" hatasi
    veriyor. Import'tan once torch'un lib klasorunu arama yoluna ekliyoruz.
    """
    if not hasattr(os, "add_dll_directory"):
        return  # Windows disi
    try:
        import torch

        lib = Path(torch.__file__).parent / "lib"
        if lib.is_dir():
            os.add_dll_directory(str(lib))
    except Exception as exc:  # torch yoksa CPU derlemesi yine de calisabilir
        log.debug("CUDA dll yolu eklenemedi: %s", exc)


# "(Ek cumle: 10/9/2014-6552/5 md.)" gibi mevzuat bakim notlari. Hukuki
# icerik tasimazlar ama model bunlari cevaba kopyaliyor; kullaniciya
# anlamsiz gorunuyor. Modele gondermeden once temizliyoruz -- metnin tam
# hali arayuzde zaten gosteriliyor.
# Not: alternatifleri uzunluk sirasina gore yazmak yerine tarih zorunlulugu
# koyuyoruz. "Ek|Ek cumle" gibi bir alternasyonda regex once kisa olani
# eslestirip basarisiz oluyordu; bu notlarin hepsi tarih tasidigi icin tarihi
# sart kosmak hem daha saglam hem de gercek hukmu yanlislikla silmiyor.
BAKIM_NOTU_RE = re.compile(
    r"\(\s*(?:Ek|Değişik|Degisik|Mülga|Mulga|İptal|Iptal|Yeniden)\b"
    r"[^)]{0,80}?\d{1,2}/\d{1,2}/\d{4}[^)]{0,80}\)",
    re.IGNORECASE)


def temizle(metin: str) -> str:
    return re.sub(r"\s{2,}", " ", BAKIM_NOTU_RE.sub("", metin)).strip()


def karar_baglami(kararlar: list[dict], max_karakter: int = 4000) -> str:
    """Mahkeme kararlarini AYRI bir baglam blogu olarak hazirlar.

    Maddelerle ayni bloga konmuyor: model ikisini karistirip karardaki bir
    ifadeyi kanun hukmu gibi gosterebiliyor. Ayri blok ve ayri talimat,
    cevapta da ayri bolum uretiyor.
    """
    parcalar, toplam = [], 0
    for k in kararlar:
        etiket = f"[{k.get('kisa_ad') or k.get('daire','?')}]"
        p = f"{etiket}\n{temizle(k.get('gerekce') or k.get('metin',''))}"
        if toplam + len(p) > max_karakter:
            break
        parcalar.append(p)
        toplam += len(p)
    return "\n\n".join(parcalar)


def baglam_kur(maddeler: list[dict], max_karakter: int = 12000) -> str:
    parcalar, toplam = [], 0
    for m in maddeler:
        etiket = f"[{m.get('mevzuat_adi','?')} - Madde {m.get('madde_no','?')}"
        if m.get("baslik"):
            etiket += f": {m['baslik']}"
        etiket += "]"
        if m.get("mulga"):
            etiket += " (DİKKAT: bu madde yürürlükten kalkmıştır)"
        p = f"{etiket}\n{temizle(m.get('metin',''))}"
        if toplam + len(p) > max_karakter:
            break
        parcalar.append(p)
        toplam += len(p)
    return "\n\n".join(parcalar)


# Cevaptaki "(Is Kanunu m.53)" bicimindeki kaynak gosterimleri
ATIF_RE = re.compile(r"\(([^()]{3,80}?)\s+m\.\s*([\w/]+)\)", re.IGNORECASE)

_ONEK_AT = re.compile(r"\b(kanunu|kanun|kararnamesi|yonetmeligi|yönetmeliği"
                      r"|tuzugu|tüzüğü|teblig|tebliği)\b", re.IGNORECASE)


def _ad_anahtari(ad: str) -> set[str]:
    """Kanun adini karsilastirilabilir kelime kumesine cevirir."""
    from .retrieve import _tr_katla

    sade = _ONEK_AT.sub(" ", _tr_katla(ad))
    kelimeler = re.findall(r"\w+", sade)
    uzun = {k for k in kelimeler if len(k) > 3}
    # "IS KANUNU" gibi kisa adlarda jenerik ek atilinca geriye yalnizca "is"
    # kaliyor ve uzunluk elemesi kumeyi bosaltiyordu; bos kume hicbir seyle
    # eslesmedigi icin gecerli atif uydurma sanilıyordu.
    return uzun or set(kelimeler)


def atiflari_dogrula(cevap: str, maddeler: list[dict]) -> list[str]:
    """Cevaptaki kaynak gosterimlerini getirilen maddelerle karsilastirir.

    Kucuk modeller var olmayan kanun adi uydurabiliyor (gozlenen ornek:
    gercek kaynak TMK m.170 iken cevapta "(Isciye Mevzuati m.12)" yazmasi).
    Kullanici uydurma bir atfi dogru sanip dayanak yapabilecegi icin bunu
    sessizce gecmiyoruz.
    """
    gecerli_no = {str(m.get("madde_no", "")).lower() for m in maddeler}
    anahtarlar = [_ad_anahtari(m.get("mevzuat_adi", "")) for m in maddeler]

    suphe = []
    for ad, no in ATIF_RE.findall(cevap):
        atif_anahtar = _ad_anahtari(ad)
        ad_uyar = any(atif_anahtar & a for a in anahtarlar if a)
        no_uyar = no.lower() in gecerli_no
        if not (ad_uyar and no_uyar):
            suphe.append(f"{ad.strip()} m.{no}")
    return suphe


# Mevzuat metni sayilari yaziyla yazar ("ondört", "yirmialtı"); model ise
# rakamla cevaplar ("14", "24"). Karsilastirabilmek icin yazi->rakam esleme.
_BIRLER = {"sıfır": 0, "bir": 1, "iki": 2, "üç": 3, "dört": 4, "beş": 5,
           "altı": 6, "yedi": 7, "sekiz": 8, "dokuz": 9}
_ONLAR = {"on": 10, "yirmi": 20, "otuz": 30, "kırk": 40, "elli": 50,
          "altmış": 60, "yetmiş": 70, "seksen": 80, "doksan": 90}


def _yazili_sayilar(metin: str) -> set[int]:
    """Metindeki yaziyla yazilmis sayilari bulur ("ondört" -> 14)."""
    from .retrieve import _tr_katla

    katli = _tr_katla(metin)
    bulunan: set[int] = set()
    for on_ad, on_deger in _ONLAR.items():
        on_k = _tr_katla(on_ad)
        if on_k not in katli:
            continue
        bulunan.add(on_deger)
        for bir_ad, bir_deger in _BIRLER.items():
            # "ondört", "on dört", "yirmialtı" hepsi ayni sayi
            if re.search(rf"{on_k}\s*{_tr_katla(bir_ad)}", katli):
                bulunan.add(on_deger + bir_deger)
    for bir_ad, bir_deger in _BIRLER.items():
        if re.search(rf"\b{_tr_katla(bir_ad)}\b", katli):
            bulunan.add(bir_deger)
    return bulunan


def sayilari_dogrula(cevap: str, baglam: str) -> list[str]:
    """Cevaptaki rakamlarin kaynak metinde gecip gecmedigini kontrol eder.

    Gozlenen hata: kanun "ondört / yirmi / yirmialtı gün" derken model
    "14 gün ... 24 gün" yazdi. Hukuki metinde uydurulmus bir sure, yanlis
    cevaptan daha zararlidir; kullanici rakami dogru sanip dayanak yapar.
    Atif dogrulama bunu yakalayamiyor cunku kaynak adi dogru olabiliyor.
    """
    gecerli = {int(x) for x in re.findall(r"\b\d{1,4}\b", baglam)}
    gecerli |= _yazili_sayilar(baglam)

    suphe = []
    for ham in re.findall(r"\b\d{1,4}\b", cevap):
        sayi = int(ham)
        # Madde numaralari ve yil gibi degerler zaten atif kontrolunden gecer;
        # burada yalnizca baglamda hic gecmeyen sayilari isaretliyoruz.
        if sayi not in gecerli:
            suphe.append(ham)
    return sorted(set(suphe), key=int)


class Generator:
    def __init__(self, provider: str | None = None):
        self.provider = (provider or config.PROVIDER).lower()
        self._client = None

    def cevapla(self, soru: str, maddeler: list[dict],
                kararlar: list[dict] | None = None) -> str:
        # Her cagrida sifirlanir; sunucu cevaptan sonra okur.
        self.son_dogrulama = {"atif_tutuyor": None, "sayi_tutuyor": None,
                              "uyarilar": [], "madde_sayisi": len(maddeler)}
        if not maddeler:
            return ("Verilen mevzuatta bu soruya dayanak bulamadım.\n\n"
                    "Bu bilgi genel niteliktedir, hukuki görüş yerine geçmez.")
        baglam = baglam_kur(maddeler)
        # Kararlar istege bagli: yoksa istem eskisi gibi yalnizca mevzuatla
        # kuruluyor, yani karar tarafi cevap kalitesini etkilemiyor.
        if kararlar and config.KARARLARI_CEVABA_KAT:
            istem = KULLANICI_KARARLI.format(
                baglam=baglam, kararlar=karar_baglami(kararlar), soru=soru)
        else:
            istem = KULLANICI.format(baglam=baglam, soru=soru)
        cevap = self._gemini(istem) if self.provider == "gemini" else self._local(istem)

        uyarilar = []
        atif_suphesi = atiflari_dogrula(cevap, maddeler)
        if suphe := atif_suphesi:
            log.warning("dogrulanamayan atif: %s", suphe)
            uyarilar.append("Kaynak gösterimi dayanak maddelerle eşleşmiyor: "
                            + "; ".join(suphe))
        # Sayi denetimi kararlarin metnini de kapsamali: karar kunyesindeki
        # numaralar ("9. Hukuk Dairesi 2015/1 E.") baglamda gecmedigi icin
        # her cevapta yanlis alarm veriyordu.
        denetim_baglami = baglam
        if kararlar and config.KARARLARI_CEVABA_KAT:
            denetim_baglami += "\n" + karar_baglami(kararlar)
        sayi_suphesi = sayilari_dogrula(cevap, denetim_baglami)
        if suphe := sayi_suphesi:
            log.warning("kaynakta bulunmayan sayi: %s", suphe)
            uyarilar.append("Şu sayılar dayanak maddelerde geçmiyor: "
                            + ", ".join(suphe))

        # Dogrulama sonucu ayrica saklaniyor: cagiran taraf GECEN denetimi de
        # gosterebilsin. Onceki surum yalnizca hata durumunda konusuyordu;
        # oysa "bu cevap kaynak metinle dogrulandi" bilgisi de kullaniciya
        # lazim -- cevabin modelin tahmini mi yoksa metinden mi geldigini
        # ayirt etmesini saglayan sey bu.
        self.son_dogrulama = {
            "atif_tutuyor": not atif_suphesi,
            "sayi_tutuyor": not sayi_suphesi,
            "uyarilar": uyarilar,
            "madde_sayisi": len(maddeler),
        }
        if uyarilar:
            cevap += "\n\n[!] Doğrulanmalı — " + " | ".join(uyarilar)
        return cevap

    # ---------- saglayicilar ----------
    def _gemini(self, istem: str, sistem: str | None = None,
                model: str | None = None) -> str:
        """Gemini'ye istem gonderir.

        model: kucuk isler icin hizli modeli sececek cagirici verir.
        Olculdu -- ayni onemsiz istekte buyuk model 36.7 saniye ve sik
        sik 503 donerken flash-lite 0.6 saniyede cevapliyor.
        """
        if self._client is None:
            from google import genai
            if not config.GEMINI_API_KEY:
                raise RuntimeError("GEMINI_API_KEY tanimli degil (.env dosyasina ekleyin)")
            self._client = genai.Client(api_key=config.GEMINI_API_KEY)

        from google.genai import types

        ayar = types.GenerateContentConfig(
            system_instruction=sistem or SISTEM, temperature=0.0)

        # Ucretsiz katmanda "503 UNAVAILABLE / high demand" sik gorulur ve
        # gecicidir. Tek denemede vazgecmek kullaniciya bos ekran gosteriyor;
        # once ayni modeli bekleyerek tekrar dener, olmazsa yedek modele geceriz.
        if model:
            modeller = [model, config.GEMINI_MODEL]
        else:
            modeller = [config.GEMINI_MODEL] + [
                m for m in config.GEMINI_YEDEK_MODELLER
                if m != config.GEMINI_MODEL
            ] + [config.GEMINI_HIZLI_MODEL]
        son_hata: Exception | None = None

        # Toplam sure butcesi. Onceki surumde 3 deneme x 4 model x ustel
        # bekleme, tek bir 503'u 290 saniyelik beklemeye ceviriyordu; tunel
        # 100 saniyede pes edip 524 donduruyor ve kullanici bes dakika bos
        # ekrana bakiyordu. Uzun beklemektense hizli hata vermek iyidir.
        baslangic = time.monotonic()

        for model in modeller:
            for deneme in range(2):
                if time.monotonic() - baslangic > config.GEMINI_SURE_BUTCESI:
                    raise RuntimeError(
                        f"Gemini {config.GEMINI_SURE_BUTCESI:.0f} saniyede cevap "
                        "vermedi (yogunluk). Birazdan tekrar deneyin.")
                try:
                    # Sert tavan: gunluk sinir asilmissa istek hic yapilmaz.
                    # Ucretsiz katmanda toplu is calistirirken kotayi
                    # tuketmistim; ucretli katmanda ayni hata para demek.
                    butce.izin_iste()
                    resp = self._client.models.generate_content(
                        model=model, contents=istem, config=ayar)
                    kullanim = getattr(resp, "usage_metadata", None)
                    butce.kaydet(
                        getattr(kullanim, "prompt_token_count", 0) or 0,
                        getattr(kullanim, "candidates_token_count", 0) or 0)
                    if model != config.GEMINI_MODEL:
                        log.info("yedek model kullanildi: %s", model)
                    return resp.text
                except butce.ButceAsildi:
                    raise            # tavan asildi: yeniden denemek anlamsiz
                except Exception as exc:
                    son_hata = exc
                    gecici = any(k in str(exc) for k in ("503", "UNAVAILABLE", "429"))
                    if not gecici:
                        break               # kalici hata: model degistirmeyi dene
                    log.warning("%s mesgul (%d/2)", model, deneme + 1)
                    time.sleep(1.5)

        raise RuntimeError(f"Gemini cevap veremedi: {son_hata}")

    def _local(self, istem: str, sistem: str | None = None,
               max_token: int = 1024) -> str:
        if self._client is None:
            yol = Path(config.LOCAL_MODEL_PATH)
            if not yol.is_absolute():
                yol = config.ROOT / yol
            if not yol.exists():
                raise RuntimeError(
                    f"Yerel model bulunamadi: {yol}\n"
                    "README'deki model indirme adimini calistirin veya "
                    ".env icinde PROVIDER=gemini yapin.")
            _cuda_dll_yolunu_ekle()

            # 4 GB VRAM'de embedding modeli zaten yerlesik oldugu icin sohbet
            # modelinin tum katmanlari GPU'ya sigmayabilir. Once istenen
            # ayarla dener, bellek yetmezse kademeli olarak CPU'ya kaydirir;
            # yavaslar ama calisir.
            from llama_cpp import Llama

            denemeler = [config.LOCAL_GPU_LAYERS, 20, 10, 0]
            son_hata: Exception | None = None
            for katman in denemeler:
                try:
                    self._client = Llama(
                        model_path=str(yol), n_ctx=config.LOCAL_CTX,
                        n_gpu_layers=katman, verbose=False)
                    log.info("yerel model yuklendi (GPU katmani: %s)", katman)
                    break
                except Exception as exc:
                    son_hata = exc
                    log.warning("GPU katmani %s ile yuklenemedi: %s", katman,
                                str(exc)[:120])
            if self._client is None:
                raise RuntimeError(f"Yerel model yuklenemedi: {son_hata}")
        resp = self._client.create_chat_completion(
            messages=[{"role": "system", "content": sistem or SISTEM},
                      {"role": "user", "content": istem}],
            temperature=0.0, max_tokens=max_token,
        )
        return resp["choices"][0]["message"]["content"]
