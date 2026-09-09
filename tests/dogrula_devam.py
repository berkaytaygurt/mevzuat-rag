"""Devam olcum setindeki gold etiketleri kulliyatla karsilastirir.

    .venv\\Scripts\\python -m tests.dogrula_devam

Her (kanun, madde) icin kulliyattaki gercek madde basligini yazar.
Baslik sorunun konusuyla ortusmuyorsa etiket yanlistir ve setten
duzeltilmelidir -- elle yazilmis bir etikete guvenmek, olcumu
olculen seyin kendisi kadar supheli yapar.
"""
from __future__ import annotations

from core.vektor import VektorDeposu
from tests.olcum_devam_seti import DEVAM, KONU_DEGISIMI


def main() -> None:
    depo = VektorDeposu()
    dizin: dict[tuple[str, str], str] = {}
    for k in depo.tum_kayitlar():
        anahtar = (str(k.get("mevzuat_no") or ""), str(k.get("madde_no") or ""))
        if anahtar not in dizin:
            dizin[anahtar] = (k.get("baslik") or "")[:70]
    depo.close()

    eksik = 0
    for ad, kume in (("A (devam)", DEVAM), ("B (konu degisimi)", KONU_DEGISIMI)):
        print(f"\n{'=' * 92}\n{ad}\n{'=' * 92}")
        for _onceki, kisa, _tam, kanun, madde, _devam in kume:
            if madde is None:
                print(f"  {kanun:>5} m.{'-':<5}  (yalnizca kanun)      {kisa[:38]}")
                continue
            baslik = dizin.get((kanun, madde))
            if baslik is None:
                eksik += 1
                print(f"  {kanun:>5} m.{madde:<5}  !! KULLIYATTA YOK !!  {kisa[:38]}")
            else:
                print(f"  {kanun:>5} m.{madde:<5}  {baslik:<48}  <- {kisa[:34]}")

    print(f"\nkulliyatta bulunamayan etiket: {eksik}")


if __name__ == "__main__":
    main()
