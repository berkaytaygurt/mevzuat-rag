"""Aibars durum raporunu uretir (2 sayfa PDF).

Turkce karakterler icin Windows'un Arial fontu gomulur; ReportLab'in yerlesik
fontlari 'ğ, ş, ı, İ' harflerini icermiyor ve bunlar siyah kutu olarak cikiyor.
"""
from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

FONTS = Path(r"C:\Windows\Fonts")
pdfmetrics.registerFont(TTFont("Arial", str(FONTS / "arial.ttf")))
pdfmetrics.registerFont(TTFont("Arial-Bold", str(FONTS / "arialbd.ttf")))
pdfmetrics.registerFontFamily("Arial", normal="Arial", bold="Arial-Bold")

LACIVERT = colors.HexColor("#1f3a5f")
BORDO = colors.HexColor("#7b2d26")
GRI = colors.HexColor("#555555")
ACIK = colors.HexColor("#f2f0ec")

ss = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=ss["Title"], fontName="Arial-Bold",
                    fontSize=19, textColor=LACIVERT, spaceAfter=2, alignment=0)
ALT = ParagraphStyle("ALT", parent=ss["Normal"], fontName="Arial",
                     fontSize=10, textColor=GRI, spaceAfter=14)
H2 = ParagraphStyle("H2", parent=ss["Heading2"], fontName="Arial-Bold",
                    fontSize=12.5, textColor=BORDO, spaceBefore=15, spaceAfter=7)
P = ParagraphStyle("P", parent=ss["Normal"], fontName="Arial", fontSize=10.2,
                   leading=15.5, alignment=TA_JUSTIFY, spaceAfter=8)
KUCUK = ParagraphStyle("KUCUK", parent=P, fontSize=9, textColor=GRI, leading=13)
HUCRE = ParagraphStyle("HUCRE", parent=ss["Normal"], fontName="Arial",
                       fontSize=9.3, leading=12.5)
HUCRE_B = ParagraphStyle("HUCRE_B", parent=HUCRE, fontName="Arial-Bold")


def tablo(veri, genislikler, basliklar=True, vurgu_satir=None):
    satirlar = []
    for i, satir in enumerate(veri):
        stil = HUCRE_B if (basliklar and i == 0) else HUCRE
        satirlar.append([Paragraph(str(h), stil) for h in satir])
    t = Table(satirlar, colWidths=genislikler, hAlign="LEFT")
    stil = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("LINEBELOW", (0, 0), (-1, -2), 0.4, colors.HexColor("#dddad4")),
    ]
    if basliklar:
        stil += [("BACKGROUND", (0, 0), (-1, 0), ACIK),
                 ("LINEBELOW", (0, 0), (-1, 0), 0.9, LACIVERT)]
    if vurgu_satir is not None:
        stil.append(("BACKGROUND", (0, vurgu_satir), (-1, vurgu_satir), ACIK))
    t.setStyle(TableStyle(stil))
    return t


def main() -> None:
    doc = SimpleDocTemplate(
        "Aibars_Ozet.pdf", pagesize=A4,
        leftMargin=2.1 * cm, rightMargin=2.1 * cm,
        topMargin=1.9 * cm, bottomMargin=1.9 * cm,
        title="Aibars - Mevzuat Arama Sistemi", author="btaygurt",
    )
    h = []

    h.append(Paragraph("Aibars — Mevzuat Arama Sistemi", H1))
    h.append(Paragraph("Durum raporu — kapsam, ölçüm sonuçları ve yol haritası", ALT))
    h.append(HRFlowable(width="100%", thickness=1, color=LACIVERT,
                        spaceBefore=0, spaceAfter=12))

    # ---------------- YAPILAN IS ----------------
    h.append(Paragraph("Yapılan iş", H2))
    h.append(Paragraph(
        "Türk mevzuatı, devletin resmî sitesinden (<b>mevzuat.gov.tr</b>) "
        "indirilerek madde bazında aranabilir hâle getirildi. Bir soru "
        "yazıldığında ilgili maddeler bulunuyor ve yapay zekâ bu maddelere "
        "dayanarak Türkçe cevap üretiyor. Yapay zekâ <b>kendi hafızasından "
        "konuşmuyor</b>; yalnızca verilen madde metnini okuyup açıklıyor. Her "
        "cevabın altında dayanak maddeler tam metinleriyle listeleniyor ve "
        "resmî kaynağa bağlantı veriliyor.", P))

    h.append(tablo([
        ["Külliyat", ""],
        ["Belge", "10.601 mevzuat"],
        ["Madde", "245.923"],
        ["Metin hacmi", "199 milyon karakter (~99.600 sayfa)"],
        ["Mahkeme kararı", "150 karar (iş hukuku, indirme sürüyor)"],
        ["Kaynak", "mevzuat.gov.tr ve karararama.yargitay.gov.tr"],
    ], [4.6 * cm, 11.6 * cm]))

    # ---------------- KAPSAM ----------------
    h.append(Paragraph("Kapsam", H2))
    h.append(Paragraph(
        "Kanunların tamamına yakını indekslendi. Tebliğ ve yönetmeliklerde "
        "kapsam uzun süre düşük göründü; sebebi iki sessiz hataydı: belge "
        "adresi tür bazında değişiyor ve yanlış adres hata yerine boş dosya "
        "döndürüyordu, ayrıca numaralı madde içermeyen belgeler tümüyle "
        "atılıyordu. İkisi de düzeltildi.", P))
    h.append(tablo([
        ["Tür", "Sitede", "İndeks", "Kapsam"],
        ["<b>Kanun</b>", "916", "<b>907</b>", "<b>%99</b>"],
        ["Tüzük", "63", "63", "%100"],
        ["Yönetmelik", "178", "177", "%99"],
        ["Cumhurbaşkanlığı Kararnamesi", "107", "102", "%95"],
        ["Cumhurbaşkanlığı Yönetmeliği", "3.653", "3.003", "%82"],
        ["Kurum ve Kuruluş Yönetmeliği", "5.049", "3.384", "%67"],
        ["Tebliğ", "4.470", "2.965", "%66"],
        ["Kanun Hükmünde Kararname", "8.851", "0", "%0"],
        ["<b>Toplam (KHK hariç)</b>", "<b>14.436</b>", "<b>10.601</b>",
         "<b>%73</b>"],
    ], [6.4 * cm, 2.6 * cm, 2.9 * cm, 2.5 * cm]))
    h.append(Spacer(1, 6))
    h.append(Paragraph(
        "Bir gün önce toplam kapsam %30'du. Artış yeni bir çalışmadan değil, "
        "belgelerin neden alınamadığının bulunmasından geldi; indirme "
        "sürdüğü için oranlar yükselmeye devam edecek.", KUCUK))

    h.append(PageBreak())

    # ---------------- OLCUM ----------------
    h.append(Paragraph("Ölçüm sonuçları", H2))
    h.append(Paragraph(
        "Arama isabeti, cevabı önceden bilinen soru setleriyle ölçülüyor. "
        "İki değer izleniyor: doğru maddenin <b>ilk sırada</b> gelmesi ve "
        "yapay zekâya gönderilen maddeler <b>arasında bulunması</b>. İkincisi "
        "daha belirleyici, çünkü model gönderilen maddelerin hepsini okuyor.", P))
    h.append(tablo([
        ["Soru seti", "Nasıl üretildi", "İlk sırada", "MRR"],
        ["El yazımı (34)", "elle yazıldı, cevabı doğrulandı", "23/34 (%68)",
         "0,724"],
        ["Yerel üretim (150)", "yerel model üretti, dili çoğu kez bozuk",
         "59/150 (%39)", "0,474"],
        ["<b>Gemini üretimi (40)</b>", "<b>doğal Türkçe, günlük dil</b>",
         "<b>9/40 (%23)</b>", "<b>0,261</b>"],
    ], [4.3 * cm, 6.0 * cm, 3.1 * cm, 2.4 * cm], vurgu_satir=3))
    h.append(Spacer(1, 6))
    h.append(Paragraph(
        "Son satır sistemin asıl zayıflığını gösteriyor: soru ne kadar doğal "
        "yazılırsa isabet o kadar düşüyor. Kullanıcılar bu biçimde soruyor. "
        "Bu ölçüm bir düzeltmeye de yol açtı: sıralama modeli maddenin "
        "yalnızca ilk 768 karakterini görüyordu ve külliyattaki maddelerin "
        "%34'ü bundan uzun. Görülen metin iki katına çıkarıldığında yerel "
        "sette isabet 0,447'den <b>0,474</b>'e çıktı; kıdem tazminatı "
        "örneğinde doğru madde 21. sıradan 6. sıraya yükseldi.", KUCUK))
    h.append(tablo([
        ["Aşama", "1. sırada", "Cevaba dahil", "Süre"],
        ["Başlangıç", "12/34 (%35)", "—", "0,7 sn"],
        ["+ yeniden sıralama", "18/34 (%53)", "—", "1,0 sn"],
        ["+ yazım düzeltme", "20/34 (%59)", "—", "1,0 sn"],
        ["+ puan harmanlama", "24/34 (%71)", "28/34 (%82)", "1,7 sn"],
        ["+ gönderilen madde 5→10", "24/34 (%71)", "<b>31/34 (%91)</b>", "1,7 sn"],
        ["Külliyat 5 kat büyüdü", "21/34 (%62)", "26/34 (%76)", "5,3 sn"],
        ["<b>+ arama yönteminin değişmesi</b>", "<b>23/34 (%68)</b>",
         "<b>26/34 (%76)</b>", "<b>1,5 sn</b>"],
    ], [5.6 * cm, 3.2 * cm, 3.4 * cm, 2.2 * cm], vurgu_satir=7))
    h.append(Spacer(1, 6))
    h.append(Paragraph(
        "Külliyatı büyütmek isabeti <b>düşürdü</b>: bir soru artık yüzlerce "
        "kurum yönetmeliğiyle yarışıyor. Normlar hiyerarşisi eklenerek "
        "kısmen telafi edildi. Son satırda arama yöntemi değişti — 174 bin "
        "madde tek tek geziliyordu, yerine tek bir matris işlemi kondu.",
        KUCUK))

    # ---------------- SIRADAKI ----------------
    h.append(Paragraph("Sıradaki işler", H2))
    h.append(tablo([
        ["İş", "Süre", "Beklenen sonuç"],
        ["<b>Doğal dilde arama</b><br/>"
         "<font size=8 color='#777777'>asıl darboğaz</font>",
         "belirsiz",
         "Sistem anahtar kelimede iyi, günlük cümlede zayıf. Ölçüldü: doğal "
         "yazılmış sorularda isabet %68'den %23'e düşüyor. Bunun ne kadar "
         "iyileşeceği önceden söylenemez; ölçerek ilerlenecek."],
        ["<b>Hukukçu yazımı ölçüm seti</b><br/>"
         "<font size=8 color='#777777'>200+ gerçek soru</font>",
         "1-2 gün",
         "Mevcut setler ya küçük ya da makine üretimi. Gerçek soruların "
         "nasıl sorulduğunu yalnızca hukuk bilen biri yazabilir. Bu set "
         "olmadan hangi değişikliğin fayda sağladığı ölçülemiyor."],
        ["<b>Yeniden indeksleme</b><br/>"
         "<font size=8 color='#777777'>yeni belgelerin eklenmesi</font>",
         "2 saat",
         "İndirme biter bitmez gerekiyor. Yeni belgeler ancak bundan sonra "
         "aramaya girer."],
        ["<b>Mahkeme kararlarının artması</b><br/>"
         "<font size=8 color='#777777'>şu an 150 karar, iş hukuku</font>",
         "sürüyor",
         "Kaynak sitenin koruma sistemi istek hızını sınırlıyor; 12 saniye "
         "aralıkla sorunsuz çalışıyor. Bu sınır aşılmaya çalışılmıyor."],
    ], [5.2 * cm, 2.1 * cm, 8.9 * cm]))

    h.append(Spacer(1, 8))
    h.append(Paragraph(
        "Önceki raporda sıradaki iş olarak gösterilen hız düzeltmesi, eksik "
        "kapsamın tamamlanması ve mahkeme kararlarına erişim tamamlandı. "
        "Arama 3,4 saniyeden 1,5 saniyeye indi, kapsam %30'dan %73'e çıktı, "
        "kararlar sisteme bağlandı. Geriye kalan iki iş de ölçümle ilgili: "
        "sistemin gerçek zayıflığı doğal dilde arama ve bunu düzgün ölçecek "
        "bir soru seti henüz yok.", P))

    h.append(Spacer(1, 14))
    h.append(HRFlowable(width="100%", thickness=0.6, color=colors.HexColor("#cccccc")))
    h.append(Spacer(1, 6))
    h.append(Paragraph(
        "Aibars genel bilgi verir, hukuki görüş yerine geçmez. Cevaplar "
        "indekslenmiş mevzuat metinlerine dayanır; doktrin içermez. Mahkeme "
        "kararları yalnızca iş hukuku alanında ve sınırlı sayıda bulunmaktadır, "
        "ayrı bir bölümde örnek olarak gösterilir — bağlayıcı olan maddedir. "
        "Sistem, kendisinde bulunmayan bir düzenlemenin varlığını bilemez; bu "
        "nedenle cevabın altındaki dayanak maddeler okunmalıdır.", KUCUK))

    doc.build(h)
    print("Aibars_Ozet.pdf olusturuldu")


if __name__ == "__main__":
    main()
