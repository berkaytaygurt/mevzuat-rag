"""Belge olcum setindeki gold etiketleri kulliyatla karsilastirir.

    .venv\\Scripts\\python -m tests.dogrula_belge

Her (kanun, madde) icin kulliyattaki gercek madde basligini yazar.
Baslik olayla ortusmuyorsa etiket yanlistir. Elle yazilmis etikete
guvenmek, olcumu olculen seyin kendisi kadar supheli yapar.
"""
from __future__ import annotations

from core.vektor import VektorDeposu
from tests.olcum_belge_seti import OLAYLAR


def main() -> None:
    depo = VektorDeposu()
    dizin: dict[tuple[str, str], str] = {}
    for k in depo.tum_kayitlar():
        anahtar = (str(k.get("mevzuat_no") or ""), str(k.get("madde_no") or ""))
        if anahtar not in dizin:
            dizin[anahtar] = (k.get("baslik") or "")[:60]
    depo.close()

    eksik = 0
    for i, (olay, goldler) in enumerate(OLAYLAR, 1):
        print(f"\n{i}. {olay[:78]}...")
        for kanun, madde in goldler:
            baslik = dizin.get((kanun, madde))
            if baslik is None:
                eksik += 1
                print(f"     {kanun:>5} m.{madde:<5}  !! KULLIYATTA YOK !!")
            else:
                print(f"     {kanun:>5} m.{madde:<5}  {baslik}")

    toplam = sum(len(g) for _, g in OLAYLAR)
    print(f"\n{len(OLAYLAR)} olay, {toplam} gold etiket, "
          f"kulliyatta bulunamayan: {eksik}")


if __name__ == "__main__":
    main()
