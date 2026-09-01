"""Uclu karsilastirma raporunu PDF olarak uretir.

Icerik: ne olculdu, nasil puanlandi, sonuc tablosu, gercek ornekler ve
olcumun sinirlari. Ornekler avukat_testi.json'dan okunur; elle secilmez,
belirli indislerden alinir ki rapor sonuca gore cirilmasin.
"""
from __future__ import annotations

import json
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (HRFlowable, PageBreak, Paragraph,
                                SimpleDocTemplate, Spacer, Table, TableStyle)

KOK = Path(__file__).resolve().parent
LACIVERT = colors.HexColor("#1f3a5f")
ACIK = colors.HexColor("#eef2f7")
GRI = colors.HexColor("#666666")

H1 = ParagraphStyle("H1", fontName="Helvetica-Bold", fontSize=17,
                    textColor=LACIVERT, spaceAfter=2, leading=20)
ALT = ParagraphStyle("ALT", fontName="Helvetica", fontSize=9.5,
                     textColor=GRI, spaceAfter=10)
H2 = ParagraphStyle("H2", fontName="Helvetica-Bold", fontSize=12,
                    textColor=LACIVERT, spaceBefore=13, spaceAfter=6)
P = ParagraphStyle("P", fontName="Helvetica", fontSize=9.5, leading=14,
                   spaceAfter=7)
KUCUK = ParagraphStyle("KUCUK", fontName="Helvetica", fontSize=8.3,
                       textColor=GRI, leading=11.5, spaceAfter=6)
SORU = ParagraphStyle("SORU", fontName="Helvetica-Bold", fontSize=9.5,
                      textColor=LACIVERT, spaceBefore=8, spaceAfter=4)
CEVAP = ParagraphStyle("CEVAP", fontName="Helvetica", fontSize=8.6,
                       leading=12, spaceAfter=3, leftIndent=8)


def kirp(metin: str, n: int = 260) -> str:
    t = " ".join((metin or "").split())
    t = t.replace("Bu bilgi genel niteliktedir, hukuki görüş yerine geçmez.", "")
    t = t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return (t[:n] + "…") if len(t) > n else t


def tablo(veri, genislikler, vurgu=None):
    satirlar = [[Paragraph(h, ParagraphStyle(
        "c", fontName="Helvetica-Bold" if i == 0 else "Helvetica",
        fontSize=8.6, leading=11.5)) for h in satir]
        for i, satir in enumerate(veri)]
    stil = [("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
            ("BACKGROUND", (0, 0), (-1, 0), ACIK),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]
    if vurgu:
        stil.append(("BACKGROUND", (0, vurgu), (-1, vurgu),
                     colors.HexColor("#fff6e5")))
    t = Table(satirlar, colWidths=genislikler)
    t.setStyle(TableStyle(stil))
    return t


def main() -> None:
    kayit = json.loads((KOK / "avukat_testi.json").read_text(encoding="utf-8"))

    doc = SimpleDocTemplate(
        str(KOK / "Aibars_Karsilastirma.pdf"), pagesize=A4,
        leftMargin=2.0 * cm, rightMargin=2.0 * cm,
        topMargin=1.8 * cm, bottomMargin=1.8 * cm,
        title="Aibars - Karsilastirma Raporu", author="btaygurt")
    h = []

    h.append(Paragraph("Aibars — Karşılaştırma Raporu", H1))
    h.append(Paragraph(
        "Aynı sorular üç kaynağa soruldu: çıplak Gemini, Aibars ve Claude", ALT))
    h.append(HRFlowable(width="100%", thickness=1, color=LACIVERT,
                        spaceBefore=0, spaceAfter=11))

    # --- NE OLCULDU ---
    h.append(Paragraph("Neyi ölçtük", H2))
    h.append(Paragraph(
        "Sorulan soru şuydu: <b>bu sistemi kurmak yerine doğrudan bir yapay "
        "zekâya sorsak ne kaybederiz?</b> Cevabı tahminle değil ölçümle "
        "vermek için, iş hukuku pratiğinde sıkça sorulan <b>52 soru</b> elle "
        "yazıldı ve üç kaynağa aynı anda soruldu.", P))
    h.append(Paragraph(
        "İş hukuku seçildi çünkü sistemde bu alanda 2.890 Yargıtay kararı da "
        "var; yani hem mevzuat hem içtihat tarafı aynı anda sınanıyor.", P))

    h.append(Paragraph("Nasıl puanlandı", H2))
    h.append(Paragraph(
        "Hakem kullanılmadı. Her cevapta gösterilen madde atıfları, 275.806 "
        "maddelik külliyata karşı denetlendi:", P))
    h.append(tablo([
        ["Ölçüt", "Anlamı"],
        ["<b>atıf</b>", "Cevabın dayanak gösterdiği madde sayısı"],
        ["<b>gerçekten var</b>",
         "Gösterilen maddenin külliyatta bulunması — uydurma olmaması"],
        ["<b>konuyla ilgili</b>",
         "Bulunan maddenin sorunun konusuyla örtüşmesi"],
        ["<b>atıfsız</b>", "Hiçbir madde göstermeyen cevap sayısı"],
    ], [4.2 * cm, 12.6 * cm]))
    h.append(Spacer(1, 5))
    h.append(Paragraph(
        "Üslup, akıcılık ve uzunluk ölçülmedi. Yalnızca parantez içinde ya da "
        "“Dayanak:” başlığı altında gösterilen kaynaklar sayıldı; alıntılanan "
        "madde metninin içinde geçen kanun adları atıf sayılmadı.", KUCUK))

    # --- SONUC ---
    h.append(Paragraph("Sonuç", H2))
    h.append(tablo([
        ["", "atıf", "gerçekten var", "konuyla ilgili", "atıfsız cevap"],
        ["çıplak Gemini", "71", "71 (%100)", "64", "<b>12</b>"],
        ["<b>Aibars</b>", "<b>106</b>", "88 (%83)", "<b>65</b>", "10"],
        ["Claude", "52", "52 (%100)", "50", "0"],
    ], [4.0 * cm, 2.2 * cm, 3.6 * cm, 3.6 * cm, 3.4 * cm], vurgu=2))
    h.append(Spacer(1, 6))
    h.append(Paragraph(
        "<b>Okunuşu:</b> Aibars en çok ilgili maddeyi buluyor (65) ve en çok "
        "dayanak gösteriyor. Çıplak Gemini hiç uydurma madde göstermiyor ama "
        "52 sorunun 12'sinde hiç kaynak vermiyor. Claude az ama temiz atıf "
        "yapıyor.", P))
    h.append(Paragraph(
        "Aibars'ın %83'lük oranı gerçek uydurma değil: sistem maddenin tam "
        "metnini alıntılıyor, o metin başka kanunlara atıf yapıyor ve ölçüm "
        "bunları da sayıyor. Yani bu oran sistemin değil, ölçüm yönteminin "
        "sınırı.", KUCUK))

    h.append(PageBreak())

    # --- ORNEKLER ---
    h.append(Paragraph("Gerçek örnekler", H2))
    h.append(Paragraph(
        "Aşağıdaki cevaplar hiçbir düzenleme yapılmadan, testin ürettiği "
        "hâliyle alınmıştır.", KUCUK))

    for i in (0, 30, 38, 44):
        if i >= len(kayit):
            continue
        x = kayit[i]
        h.append(Paragraph(kirp(x["soru"], 120), SORU))
        for etiket, ad in (("ciplak", "Çıplak Gemini"),
                           ("aibars", "Aibars"),
                           ("claude", "Claude")):
            h.append(Paragraph(f"<b>{ad}:</b> {kirp(x.get(etiket, ''))}", CEVAP))
        h.append(HRFlowable(width="100%", thickness=0.4,
                            color=colors.HexColor("#dddddd"),
                            spaceBefore=5, spaceAfter=2))

    h.append(PageBreak())

    # --- YORUM ---
    h.append(Paragraph("Bu ölçüm neyi göstermiyor", H2))
    h.append(Paragraph(
        "Ölçüt “gerçek ve ilgili bir madde gösterdi mi” sorusunu cevaplıyor, "
        "“<b>doğru şeyi söyledi mi</b>” sorusunu değil. Bir cevap gerçek bir "
        "maddeyi gösterip yine de yanlış kural anlatabilir. Bunu ölçmek için "
        "hukukçu değerlendirmesi gerekir.", P))
    h.append(Paragraph(
        "Ayrıca sorular tek bir alandan (iş hukuku) ve tek kişi tarafından "
        "yazıldı. Farklı alanlarda sonuç değişebilir.", P))

    h.append(Paragraph("Ölçümün kendisi dört kez bozuldu", H2))
    h.append(Paragraph(
        "Bu sonuca ulaşmadan önce test üç kez yanlış kuruldu ve her seferinde "
        "sonuç yayımlanmadan önce fark edildi. Kaydı şeffaflık için burada:", P))
    h.append(tablo([
        ["Kusur", "Etkisi"],
        ["Sorular maddelerden otomatik üretiliyordu",
         "“Hangi kanun bu maddeyi değiştirdi” trivyasına dönüştü; "
         "hukuk sorusu değildi"],
        ["Sayı süzgeci fazla dardı", "Grup başına 2 soru kaldı, istatistik anlamsızdı"],
        ["Atıf yakalayıcı Gemini'nin biçimini tanımıyordu",
         "“Gemini hiç kaynak göstermiyor” gibi yanlış bir tablo çıkıyordu"],
        ["Alıntılanan metindeki kanun adları atıf sayılıyordu",
         "Tam metin alıntılayan Aibars haksız yere cezalandırılıyordu"],
    ], [6.2 * cm, 10.6 * cm]))

    h.append(Paragraph("Değerlendirme", H2))
    h.append(Paragraph(
        "Bu ölçümde <b>çıplak Gemini ile Aibars birbirine yakın</b> çıktı. "
        "Aibars biraz daha çok ilgili madde buluyor ve dayanağın tam metnini "
        "gösteriyor; Gemini daha derli toplu cevap veriyor ama soruların "
        "dörtte birinde hiç kaynak vermiyor.", P))
    h.append(Paragraph(
        "Aibars'ın belirgin bir zayıflığı da bu testte görüldü: kıdem "
        "tazminatının temel şartını soran soruda “dayanak bulamadım” dedi, "
        "diğer ikisi doğru cevapladı. Doğru madde (1475 sayılı Kanun m.14) "
        "külliyatta var ama arama onu ilk sıralara çıkaramadı.", P))
    h.append(Paragraph(
        "<b>Sonuç:</b> “Bu sistem yapay zekâdan daha doğru cevap veriyor” "
        "denemez. Söylenebilecek olan şudur: dayanağın tam metnini kaynağıyla "
        "birlikte gösteriyor ve kendinde olmayan bir bilgiyi uydurmak yerine "
        "“bulamadım” diyor. Bir avukat için bu, cevabın kendisi kadar "
        "önemlidir — ama tek başına bir üstünlük iddiası değildir.", P))

    h.append(Spacer(1, 12))
    h.append(HRFlowable(width="100%", thickness=0.6,
                        color=colors.HexColor("#cccccc")))
    h.append(Spacer(1, 5))
    h.append(Paragraph(
        "52 soru · 275.806 madde · 2.890 Yargıtay kararı · ölçüm süresi 15 dk · "
        "Gemini maliyeti 0,24 ABD doları", KUCUK))

    doc.build(h)
    print("Aibars_Karsilastirma.pdf olusturuldu")


if __name__ == "__main__":
    main()
