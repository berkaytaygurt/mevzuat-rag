"""Belgedeki kanun atiflarini kulliyata karsi denetler.

NEDEN BU OZELLIK

Genel amacli bir dil modeli hukukta en cok ATIF UYDURUYOR: olmayan bir
madde numarasi, yururlukten kalkmis bir hukum, ya da soylediginden
baska sey diyen bir madde. Kullanici bunu ancak elle kontrol ederek
yakalayabiliyor -- ve modelin kendisine "dogru mu" diye sormak ise
yaramiyor, cunku kulliyat onun elinde yok.

Bizde kulliyat VAR. Yani bu, dil modelinin yapisal olarak yapamadigi,
bizim ise kesin olarak yapabildigimiz bir is.

NE YAPMIYOR

"Bu madde iddiayi desteklemiyor" DEMIYOR. Oyle bir yargi hukuki
degerlendirme olur ve olculen dogruluk onu tasimaz. Bunun yerine
maddenin GERCEK METNINI yanina koyuyor; kararı avukat veriyor.

DURUMLAR
    tamam        : madde kulliyatta var ve yururlukte
    mulga        : madde yururlukten kalkmis
    kismi_mulga  : maddenin bir kismi kalkmis
    bulunamadi   : o kanunda o numarali madde yok
    kanun_yok    : kanun adi/numarasi cozulemedi
"""
from __future__ import annotations

import logging
import re

from .atif import atiflari_cikar
from .atif_grafi import AD_NUMARA

log = logging.getLogger(__name__)

# Karar atiflari: "2019/1234 E. 2021/567 K." ya da "2019/1234 esas"
KARAR_RE = re.compile(
    r"(\d{4})\s*/\s*(\d{1,6})\s*(?:E\.?|[Ee]sas)"
    r"(?:[^\n]{0,40}?(\d{4})\s*/\s*(\d{1,6})\s*(?:K\.?|[Kk]arar))?")

EN_FAZLA_ATIF = 80


def _ad_cozumle(kaynak: str) -> str | None:
    """Kanun adini ya da numarasini mevzuat numarasina cevirir."""
    k = (kaynak or "").strip()
    if k.isdigit():
        return k
    # SIRA ONEMLI: once katla, sonra kucult. Python'da "İ".lower()
    # "i" + birlesen nokta (U+0307) veriyor; once lower() cagrilirsa
    # sonraki replace hicbir sey bulamiyor ve "İş Kanunu" hicbir zaman
    # eslesmiyordu -- yani en sik atif yapilan kanun cozumlenemiyordu.
    dusuk = k.replace("İ", "i").replace("I", "ı").lower()
    if dusuk in AD_NUMARA:
        return AD_NUMARA[dusuk]
    # "4857 sayılı İş Kanunu" gibi birlesik yazimlar
    for ad, no in AD_NUMARA.items():
        if ad in dusuk:
            return no
    return None


class Denetci:
    """Kulliyati bir kez okuyup atiflari denetler."""

    def __init__(self, kayitlar: list[dict]):
        # (mevzuat_no, madde_no) -> kayit. Ayni maddenin birden cok
        # parcasi olabiliyor; ilki yeterli.
        self._dizin: dict[tuple[str, str], dict] = {}
        self._kanun_adlari: dict[str, str] = {}
        for k in kayitlar:
            no = str(k.get("mevzuat_no") or "")
            madde = str(k.get("madde_no") or "")
            if no and madde:
                self._dizin.setdefault((no, madde), k)
            if no and no not in self._kanun_adlari:
                self._kanun_adlari[no] = k.get("mevzuat_adi") or ""

    def kanun_var_mi(self, no: str) -> bool:
        return no in self._kanun_adlari

    def denetle(self, metin: str) -> dict:
        """Metindeki atiflari denetleyip rapor doner."""
        atiflar = atiflari_cikar(metin or "", en_fazla=EN_FAZLA_ATIF)
        sonuclar = []
        gorulen = set()

        for kaynak, madde_no in atiflar:
            kanun_no = _ad_cozumle(kaynak)
            anahtar = (kanun_no or kaynak, madde_no)
            if anahtar in gorulen:
                continue
            gorulen.add(anahtar)

            if not kanun_no:
                sonuclar.append({
                    "kaynak": kaynak, "madde_no": madde_no,
                    "durum": "kanun_yok", "kanun_adi": "", "baslik": "",
                    "metin": "",
                    "not_": "Kanun adı çözümlenemedi; külliyatta karşılığı aranamadı.",
                })
                continue

            kayit = self._dizin.get((kanun_no, madde_no))
            if kayit is None:
                sonuclar.append({
                    "kaynak": kaynak, "kanun_no": kanun_no,
                    "madde_no": madde_no, "durum": "bulunamadi",
                    "kanun_adi": self._kanun_adlari.get(kanun_no, ""),
                    "baslik": "", "metin": "",
                    # Kulliyat YURURLUKTEKI mevzuati tutuyor. Kanunun
                    # tamami yoksa en olasi aciklama yururlukten
                    # kalkmis olmasi (ornek: 818 sayili Borclar
                    # Kanunu, 6098 ile degistirildi). Kesin konusmak
                    # yerine olasiligi soyluyoruz.
                    "not_": ("Bu kanunda bu numarada madde bulunamadı."
                             if self.kanun_var_mi(kanun_no)
                             else "Bu kanun külliyatta yok — yürürlükten "
                                  "kalkmış olabilir."),
                })
                continue

            if kayit.get("mulga"):
                durum, aciklama = "mulga", "Bu madde yürürlükten kalkmış."
            elif kayit.get("kismi_mulga"):
                durum, aciklama = "kismi_mulga", "Maddenin bir kısmı yürürlükten kalkmış."
            else:
                durum, aciklama = "tamam", ""

            sonuclar.append({
                "kaynak": kaynak, "kanun_no": kanun_no, "madde_no": madde_no,
                "durum": durum,
                "kanun_adi": kayit.get("mevzuat_adi") or "",
                "baslik": kayit.get("baslik") or "",
                # Gercek metin veriliyor ki avukat KENDISI karsilastirsin.
                # "Bu madde iddiani desteklemiyor" demek hukuki
                # degerlendirme olurdu.
                "metin": (kayit.get("metin") or "")[:1200],
                "degisiklikler": (kayit.get("degisiklikler") or "")[:400],
                "not_": aciklama,
            })

        return {
            "atiflar": sonuclar,
            "kararlar": self._kararlar(metin),
            "ozet": self._ozet(sonuclar),
        }

    @staticmethod
    def _kararlar(metin: str) -> list[dict]:
        """Karar atiflarini listeler; DOGRULAMIYOR.

        Kararlar kulliyatta degil, canli aramadan geliyor. Burada
        "dogruladik" demek yanlis olur; yalnizca "bunlari gordum,
        denetlenmedi" diyoruz -- uydurma karar numarasi hukukta en sik
        gorulen yapay zeka hatasi ve kullanicinin bundan haberi olmali.
        """
        bulunan, gorulen = [], set()
        for m in KARAR_RE.finditer(metin or ""):
            esas = f"{m.group(1)}/{m.group(2)}"
            karar = f"{m.group(3)}/{m.group(4)}" if m.group(3) else ""
            if esas in gorulen:
                continue
            gorulen.add(esas)
            bulunan.append({"esas": esas, "karar": karar,
                            "durum": "denetlenmedi"})
        return bulunan[:40]

    @staticmethod
    def _ozet(sonuclar: list[dict]) -> dict:
        ozet = {"toplam": len(sonuclar), "tamam": 0, "mulga": 0,
                "kismi_mulga": 0, "bulunamadi": 0, "kanun_yok": 0}
        for s in sonuclar:
            ozet[s["durum"]] = ozet.get(s["durum"], 0) + 1
        return ozet
