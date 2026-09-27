"""Cok olgulu soruyu hukuki meselelere ayirip her birini ayri arar.

OLCULEN SORUN
Avukat somut bir dosyayla gelir ve soruyu olgularla yazar:

    "isci 4 yil 11 ay calisti, isveren devamsizlik nedeniyle savunma
     almadan feshetti, fesih gecerli mi"

Bu soru UC ayri hukuki meseleyi birden tasiyor: devamsizlik nedeniyle
fesih, savunma alma zorunlulugu, gecerli sebep. Sistem tek bir vektor
uretince o vektor uc meselenin bulanik ortalamasi oluyor ve hicbirinin
maddesini tam bulamiyor -- olculdu, bu soruda "mevzuatta dayanak
bulamadim" dedi, oysa cevap Is Kanunu m.19'da.

COZUM
Soru once meselelere ayriliyor, her mesele AYRI aratiliyor, sonuclar RRF
ile birlestiriliyor. Boylece her mesele kendi maddesini getirebiliyor.

MALIYET
Mesele basina bir arama. Yalnizca uzun/olgulu sorularda calisiyor;
kisa sorular tek aramada kaliyor.
"""
from __future__ import annotations

import logging
import re

import config

log = logging.getLogger(__name__)


class SaglayiciTukendi(RuntimeError):
    """Bulut saglayicinin kotasi/kredisi bitti -- gecici ve faturalik."""

# OLCULMEDI. 7. kural gercek bir dosyada goruldugu icin eklendi: delil
# tespiti talebi yuklenince sistem yalnizca usul maddelerini ariyordu,
# oysa dosyanin esasi arac ayibiydi (6502 m.11/15). Kural Gemini kredisi
# bitikken yazildi, olculemedi. Kredi gelince
# `python olcum_belge.py` ile ayrica olcun -- olcum setinde usul basligi
# altinda iki kayit var.
# ONEMLI: her mesele KENDI BASINA aranacagi icin baglami tasimali.
# Olculdu -- "Savunma alma zorunlulugu" diye ayri aratildiginda sistem
# Sivil Savunma Kanunu'nu ve Turk Silahli Kuvvetleri yonetmeligini
# getiriyordu; "savunma" kelimesi is hukuku baglamindan kopunca baska
# anlama geliyor. Bu yuzden her satirda hukuk alani da yazdiriliyor.
SISTEM = """Sen bir hukuk arama yardımcısısın. Sana bir olay anlatımı
verilir. Sen o olaydaki AYRI hukuki meseleleri listelersin.

Kurallar:
1. Her satıra bir mesele yaz, kısa arama terimi olarak (cümle kurma).
2. En fazla 4 mesele.
3. Her mesele KENDİ BAŞINA anlaşılmalı: hangi hukuk alanına ait olduğu
   satırdan anlaşılsın. "Savunma alma zorunluluğu" yerine "iş
   sözleşmesinin feshinde işçinin savunmasının alınması" yaz.
4. Hukuk alanının adını sonuna etiket gibi ekleme; cümlenin içine yedir.
   YANLIŞ: "işçinin savunmasının alınması zorunluluğu iş hukuku"
   DOĞRU : "iş sözleşmesinin feshinde işçinin savunmasının alınması"
5. Olayın kendi ayrıntılarını (süre, isim, tarih) yazma; hukuki kavramı yaz.
6. Tek bir mesele varsa tek satır yaz.
7. Belge bir USUL talebiyse (delil tespiti, ihtiyati tedbir, ihtiyati
   haciz, tespit davası, ihtarname), yalnızca usul kurumunu yazma.
   Talebin ARKASINDAKİ esas uyuşmazlığı da yaz. Bir şeyin tespiti
   isteniyorsa, o şey hangi hukuki uyuşmazlığın konusuysa onu da çıkar.
   YANLIŞ: yalnızca "delil tespiti istenmesinin şartları"
   DOĞRU : "delil tespiti istenmesinin şartları" + "satılan malın
           ayıplı olması ve alıcının seçimlik hakları""""

ISTEM = """Olay: {soru}

Bu olaydaki ayrı hukuki meseleleri satır satır yaz."""

# Bu uzunlugun altindaki sorular tek mesele sayilir; ayirmanin maliyeti
# faydasindan buyuk olur.
EN_AZ_UZUNLUK = 55
# Birden fazla olgu tasidiginin isareti: virgul, "ve", noktali virgul
COK_OLGU_RE = re.compile(r",|;|\bve\b|\bama\b|\bfakat\b", re.IGNORECASE)


def cok_olgulu_mu(soru: str) -> bool:
    """Soru birden fazla hukuki mesele tasiyor gorunuyor mu."""
    if len(soru) < EN_AZ_UZUNLUK:
        return False
    return len(COK_OLGU_RE.findall(soru)) >= 2


def meseleleri_ayir(soru: str, uretici, en_az: int = 2) -> list[str]:
    """Soruyu hukuki meselelere ayirir.

    en_az=2 (varsayilan): tek mesele ciktiginda BOS doner. Mevzuat
    aramasinda dogru davranis, cunku cagiran taraf normal aramaya
    devam ediyor ve tek meseleyi ayrica aramanin faydasi yok.

    en_az=1: tek mesele de kullanilsin. BELGE ANALIZINDE sart --
    orada yedek yok. Ustelik modelin yazdigi tek satir, belgenin ham
    KONU cumlesinden cok daha iyi bir arama sorgusu: usul dili yerine
    hukuki kavram tasiyor. Olculdu: ham KONU cumlesiyle arama "ucak
    alti bagajinin taranmasi" gibi maddeler getiriyordu.
    """
    try:
        c = uretici.kisa(ISTEM.format(soru=soru), sistem=SISTEM,
                            model=config.GEMINI_HIZLI_MODEL)
    except Exception as exc:
        # SAGLAYICI HATASI SESSIZ KALMAMALI. Onceden her hata bos liste
        # donuyordu; kredi bitince (402 RESOURCE_EXHAUSTED) belge analizi
        # ham KONU cumlesine dusup "ucak alti bagajinin taranmasi" gibi
        # sonuclar veriyordu. Kullanici sistemin bozuk oldugunu saniyor,
        # oysa yalnizca fatura sorunu var.
        mesaj = str(exc)
        if any(iz in mesaj for iz in ("402", "RESOURCE_EXHAUSTED", "429",
                                      "credits are depleted", "quota")):
            raise SaglayiciTukendi(
                "Gemini kotası/kredisi tükenmiş. Belge analizi ve soru "
                "yeniden yazma bu yüzden çalışmıyor; arşiv araması ve "
                "atıf denetimi etkilenmez (onlar yerel)."
            ) from exc
        log.warning("mesele ayrilamadi: %s", mesaj[:80])
        return []

    satirlar = []
    for satir in (c or "").split("\n"):
        s = re.sub(r"^\s*(?:\d+[.)]\s*|[-*•]\s*)", "", satir).strip()
        # Markdown vurgusu temizleniyor. Gemini duz satir donduruyor,
        # bu yuzden gerekmiyordu; kucuk yerel modeller ise listelerini
        # kalinlastiriyor ("**iscinin savunmasinin alinmasi**"). Yildizlar
        # kalirsa arama terimine giriyor ve eslesmeyi bozuyor.
        s = re.sub(r"[*_]{1,3}", "", s).strip()
        # Ust sinir 140: meselelerin baglam tasimasini istedigimiz icin
        # satirlar uzadi ("is sozlesmesinin feshinde iscinin savunmasinin
        # alinmasi zorunlulugu" = 66 karakter). 90 sinirindayken uzun
        # meseleler eleniyor ve liste bosaliyordu.
        if 6 <= len(s) <= 140:
            satirlar.append(s)
    return satirlar[:4] if len(satirlar) >= en_az else []
