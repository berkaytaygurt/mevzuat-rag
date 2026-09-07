"""aibars.html icindeki script'i GERCEK bir ayristiriciyla denetler.

NEDEN VAR
test_arayuz.py tirnak ve parantez SAYIYOR. Bu kaba yontem bugun uc kez
yanlis alarm verdi (Turkce kesme isareti, blok yorum, karakter sinifi
icindeki kapanis parantezi) ve bir GERCEK hatayi kacirdi:

    const ad = prompt("Dosya adı (örn. "Kiracı tahliye — Ahmet Y.")");
                                       ^ dizgi burada kapaniyor

Belirti her zamanki gibi sinsiydi: sunucu calisiyor, sayfa aciliyor,
ama tum script tek bir SyntaxError ile devre disi kaliyor ve hicbir sey
tepki vermiyor.

node --check bu hatayi satir numarasiyla soyluyor. Sayma testleri
DURUYOR -- ucuz ve node olmayan ortamda da calisiyorlar -- ama asil
guvence burasi.
"""
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ARAYUZ = Path(__file__).resolve().parent.parent / "web" / "aibars.html"


@pytest.mark.skipif(shutil.which("node") is None,
                    reason="node kurulu degil; sayma testleri yine calisiyor")
def test_script_gecerli_javascript(tmp_path):
    h = ARAYUZ.read_text(encoding="utf-8")
    m = re.search(r"<script>(.*?)</script>", h, re.S)
    assert m, "aibars.html icinde <script> bulunamadi"

    yol = tmp_path / "arayuz.js"
    yol.write_text(m.group(1), encoding="utf-8")
    sonuc = subprocess.run(["node", "--check", str(yol)],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=60)
    assert sonuc.returncode == 0, (
        "arayuz script'i gecerli JavaScript degil:\n" + (sonuc.stderr or "")[:1500])
