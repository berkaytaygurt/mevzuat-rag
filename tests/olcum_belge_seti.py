"""Cok meseleli olay anlatimlari: mesele cikarimini olcmek icin.

NE OLCUYORUZ

Bir dilekce ya da olay ozeti birden fazla hukuki mesele tasir. Sistem
once meseleleri ayirir (core/mesele.py), sonra her birini ayri arar.
Sorulan soru su: BU AYIRMA ISINI YEREL MODEL DE YAPABILIR MI?

Onemi buyuk. Yapabiliyorsa avukatin dilekcesi bilgisayarindan hic
cikmaz; yapamiyorsa dilekce Google'a gitmek zorunda kalir ve butun
gizlilik gerekcesi cokerti.

NEDEN COKLU GOLD

Onceki setlerde her sorunun tek dogru maddesi vardi. Burada olmaz:
"savunma alinmadan fesih, kidem ve ihbar tazminati odenmemis" cumlesi
UC ayri maddeye dayanir. Olculen sey "ilk sirada dogru madde var mi"
degil, "olayin dayandigi maddelerin KACINI getirdi".

HER KAYIT
    (olay, [(kanun, madde), ...])

Gold etiketler `python -m tests.dogrula_belge` ile kulliyattaki gercek
madde basliklariyla karsilastirilip duzeltildi.
"""
from __future__ import annotations

Kayit = tuple[str, list[tuple[str, str]]]

OLAYLAR: list[Kayit] = [
    # --- Is hukuku ---
    ("Müvekkilim davalı şirkette 8 yıldır çalışmaktadır. İşveren "
     "performans düşüklüğü gerekçe göstererek ve savunması alınmadan iş "
     "akdini feshetmiştir. İhbar tazminatı da ödenmemiştir.",
     [("4857", "19"), ("4857", "18"), ("4857", "17")]),

    ("İşçi haftada altmış saat çalıştırılmış, fazla çalışma ücreti "
     "ödenmemiş ve üç yıldır yıllık ücretli izin kullandırılmamıştır.",
     [("4857", "41"), ("4857", "63"), ("4857", "53")]),

    ("İşveren, işçinin işyerinde hırsızlık yaptığını ileri sürerek iş "
     "sözleşmesini derhal feshetmiştir. İşçi feshin geçersizliğini ve "
     "işe iadesini talep etmektedir.",
     [("4857", "25"), ("4857", "18"), ("4857", "20")]),

    # --- Kira / borclar ---
    ("Kiracı son üç aydır kira bedelini ödememektedir. Kendisine iki kez "
     "yazılı ihtar gönderilmiş, buna rağmen ödeme yapılmamıştır. "
     "Kiralananın tahliyesini talep ediyoruz.",
     [("6098", "315"), ("6098", "352")]),

    ("Davalı, sözleşmeye eklediği ve müzakere edilmeyen standart bir "
     "hükümle sorumluluğunu tamamen kaldırmıştır. Bu hükmün geçersiz "
     "sayılmasını ve uğradığımız zararın tazminini istiyoruz.",
     [("6098", "20"), ("6098", "21"), ("6098", "49")]),

    ("Müvekkil trafik kazasında yaralanmış, aracı hasar görmüştür. Kaza "
     "tarihinden bu yana üç yıl geçmiştir. Maddi ve manevi tazminat "
     "talep ediyoruz.",
     [("6098", "49"), ("6098", "56"), ("6098", "72")]),

    # --- Aile / miras ---
    ("Taraflar beş yıldır evlidir. Ortak hayat müvekkilim bakımından "
     "çekilmez hale gelmiştir. Boşanma, müşterek çocuğun velayeti ve "
     "yoksulluk nafakası talep edilmektedir.",
     [("4721", "166"), ("4721", "182"), ("4721", "175")]),

    ("Muris, ölümünden kısa süre önce taşınmazını mirasçılardan "
     "kaçırmak amacıyla satış göstererek devretmiştir. Tapu kaydının "
     "iptalini ve mirasçılık belgesi verilmesini talep ediyoruz.",
     [("4721", "598"), ("6098", "19")]),

    # --- Ceza ---
    ("Sanık, gece vakti kapalı işyerinin kilidini kırarak içeri girmiş "
     "ve kasadaki parayı almıştır. Olay sırasında işyeri sahibine "
     "hakaret etmiştir.",
     [("5237", "142"), ("5237", "143"), ("5237", "125")]),

    ("Fail, kendisine saldıran kişiye karşı savunma yapmış ancak "
     "saldırgan kaçarken arkasından ateş ederek yaralamıştır. "
     "Müvekkilin meşru savunma sınırını aştığı iddia edilmektedir.",
     [("5237", "25"), ("5237", "27"), ("5237", "86")]),

    # --- KVKK ---
    ("Şirket, müşterilerinin kişisel verilerini rızaları olmadan "
     "işlemiş, aydınlatma yükümlülüğünü yerine getirmemiştir. İlgili "
     "kişi olarak verilerimizin silinmesini talep ettik, cevap "
     "verilmedi.",
     [("6698", "5"), ("6698", "10"), ("6698", "11")]),

    # --- Usul ---
    ("Davalı borcunu ödememekte, mal kaçırma girişiminde bulunmaktadır. "
     "Dava açmadan önce taşınmazları üzerine ihtiyati tedbir konulmasını "
     "ve dava dilekçemizin kabulünü talep ediyoruz.",
     [("6100", "389"), ("6100", "119")]),
]
