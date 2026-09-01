"""AIBARS_TAM_RAPOR.md icerigini PDF olarak uretir.

Markdown dosyasi kaynak; bu betik onu bicimlendirir. Boylece rapor tek
yerde guncelleniyor ve PDF her seferinde yeniden uretiliyor.
"""
from __future__ import annotations

import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (HRFlowable, ListFlowable, ListItem,
                                Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

KOK = Path(__file__).resolve().parent

# Turkce karakterler icin Arial sart. Varsayilan Helvetica'da i-noktasiz,
# s-cedilli, g-yumusak yok; ilk surumde bu harfler PDF'te siyah kutu
# olarak cikiyordu.
FONTS = Path("C:/Windows/Fonts")
pdfmetrics.registerFont(TTFont("Arial", str(FONTS / "arial.ttf")))
pdfmetrics.registerFont(TTFont("Arial-Bold", str(FONTS / "arialbd.ttf")))
pdfmetrics.registerFont(TTFont("Arial-Italic", str(FONTS / "ariali.ttf")))
pdfmetrics.registerFontFamily("Arial", normal="Arial", bold="Arial-Bold",
                              italic="Arial-Italic")
LACIVERT = colors.HexColor("#1f3a5f")
ACIK = colors.HexColor("#eef2f7")
GRI = colors.HexColor("#5a5a5a")

H1 = ParagraphStyle("H1", fontName="Arial-Bold", fontSize=18,
                    textColor=LACIVERT, spaceAfter=3, leading=21)
ALT = ParagraphStyle("ALT", fontName="Arial-Italic", fontSize=9,
                     textColor=GRI, spaceAfter=10, leading=13)
H2 = ParagraphStyle("H2", fontName="Arial-Bold", fontSize=12.5,
                    textColor=LACIVERT, spaceBefore=14, spaceAfter=6)
H3 = ParagraphStyle("H3", fontName="Arial-Bold", fontSize=10,
                    textColor=colors.HexColor("#333333"),
                    spaceBefore=9, spaceAfter=4)
P = ParagraphStyle("P", fontName="Arial", fontSize=9.3, leading=13.5,
                   spaceAfter=6)
LI = ParagraphStyle("LI", fontName="Arial", fontSize=9.3, leading=13,
                    spaceAfter=2)


def satir_ici(t: str) -> str:
    """Markdown vurgu ve kod isaretlerini PDF etiketlerine cevirir."""
    t = t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"(?<!\*)\*([^*]+?)\*(?!\*)", r"<i>\1</i>", t)
    t = re.sub(r"`(.+?)`", r'<font face="Courier" size="8.4">\1</font>', t)
    return t


def tablo_yap(satirlar: list[list[str]], toplam_genislik: float = 16.8):
    """Markdown tablosunu reportlab tablosuna cevirir."""
    n = max(len(s) for s in satirlar)
    ilk_genis = 1.9 if n > 2 else 1.0
    kalan = (toplam_genislik - ilk_genis * toplam_genislik / n) / max(1, n - 1)
    genislikler = [ilk_genis * toplam_genislik / n * cm] + [kalan * cm] * (n - 1)

    hucreler = []
    for i, satir in enumerate(satirlar):
        stil = ParagraphStyle(
            f"h{i}", fontName="Arial-Bold" if i == 0 else "Arial",
            fontSize=8.2, leading=11)
        satir = satir + [""] * (n - len(satir))
        hucreler.append([Paragraph(satir_ici(h), stil) for h in satir])

    t = Table(hucreler, colWidths=genislikler, repeatRows=1)
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cfcfcf")),
        ("BACKGROUND", (0, 0), (-1, 0), ACIK),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
    ]))
    return t


def paragraflari_birlestir(satirlar: list[str]) -> list[str]:
    """Markdown'da tek satir sonu paragraf bitirmez, satiri sarar.

    Ilk surum her satiri ayri paragraf sayiyordu; metin PDF'te parca parca
    cikiyor ve liste maddelerinin devami listeden kopuyordu. Burada ard
    arda gelen duz metin satirlari tek paragrafa toplaniyor. Baslik, tablo,
    liste ve ayirici satirlari kendi basina kalir.
    """
    ozel = ("|", "#", "---", "- ", "* ")
    cikti: list[str] = []
    tampon: list[str] = []

    def bosalt():
        if tampon:
            cikti.append(" ".join(tampon))
            tampon.clear()

    for ham_satir in satirlar:
        s = ham_satir.rstrip()
        if not s:
            bosalt()
            cikti.append("")
            continue
        if s.startswith(ozel) or re.match(r"^\d+\.\s", s):
            bosalt()
            cikti.append(s)
            continue
        # Onceki satir liste maddesiyse bu satir onun devamidir
        if cikti and (cikti[-1].startswith(("- ", "* "))
                      or re.match(r"^\d+\.\s", cikti[-1])) and not tampon:
            cikti[-1] = cikti[-1] + " " + s.strip()
            continue
        tampon.append(s.strip())
    bosalt()
    return cikti


def main() -> None:
    ham = (KOK / "AIBARS_TAM_RAPOR.md").read_text(encoding="utf-8")
    satirlar = paragraflari_birlestir(ham.split("\n"))

    doc = SimpleDocTemplate(
        str(KOK / "Aibars_Tam_Rapor.pdf"), pagesize=A4,
        leftMargin=2.0 * cm, rightMargin=2.0 * cm,
        topMargin=1.8 * cm, bottomMargin=1.8 * cm,
        title="Aibars - Tam Rapor", author="btaygurt")

    h: list = []
    tablo_tampon: list[list[str]] = []
    liste_tampon: list[str] = []

    def tabloyu_bosalt():
        nonlocal tablo_tampon
        if tablo_tampon:
            h.append(Spacer(1, 3))
            h.append(tablo_yap(tablo_tampon))
            h.append(Spacer(1, 7))
            tablo_tampon = []

    def listeyi_bosalt():
        nonlocal liste_tampon
        if liste_tampon:
            tur = liste_tampon[0][0]
            h.append(ListFlowable(
                [ListItem(Paragraph(satir_ici(x[1]), LI), leftIndent=14)
                 for x in liste_tampon],
                bulletType="1" if tur == "numara" else "bullet",
                bulletFontSize=8 if tur == "numara" else 5,
                bulletFontName="Arial", leftIndent=14, bulletOffsetY=1))
            h.append(Spacer(1, 5))
            liste_tampon = []

    for satir in satirlar:
        s = satir.rstrip()

        if s.startswith("|"):
            listeyi_bosalt()
            hucre = [c.strip() for c in s.strip("|").split("|")]
            if all(re.fullmatch(r":?-{2,}:?", c) for c in hucre if c):
                continue                       # ayirici satir
            tablo_tampon.append(hucre)
            continue
        tabloyu_bosalt()

        if s.startswith("- ") or s.startswith("* "):
            liste_tampon.append(("nokta", s[2:]))
            continue
        if re.match(r"^\d+\.\s", s):
            liste_tampon.append(("numara", re.sub(r"^\d+\.\s", "", s)))
            continue
        listeyi_bosalt()

        if not s:
            continue
        if s.startswith("---"):
            h.append(HRFlowable(width="100%", thickness=0.5,
                                color=colors.HexColor("#cccccc"),
                                spaceBefore=6, spaceAfter=6))
        elif s.startswith("# "):
            h.append(Paragraph(satir_ici(s[2:]), H1))
            h.append(HRFlowable(width="100%", thickness=1.1, color=LACIVERT,
                                spaceBefore=2, spaceAfter=9))
        elif s.startswith("## "):
            h.append(Paragraph(satir_ici(s[3:]), H2))
        elif s.startswith("### "):
            h.append(Paragraph(satir_ici(s[4:]), H3))
        elif s.startswith("*") and s.rstrip().endswith("*") and len(s) > 2:
            # Tumu italik bir blok (rapor girisi gibi): yildizlar sadece
            # ucta oldugu icin satir_ici() bunlari yakalayamiyor.
            h.append(Paragraph(satir_ici(s.strip().strip("*")), ALT))
        else:
            h.append(Paragraph(satir_ici(s), P))

    tabloyu_bosalt()
    listeyi_bosalt()
    doc.build(h)
    print("Aibars_Tam_Rapor.pdf olusturuldu")


if __name__ == "__main__":
    main()
