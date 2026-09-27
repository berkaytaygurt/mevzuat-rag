"""Her kaynak dosya DERLENEBILIYOR mu.

NEDEN BOYLE BIR TESTE IHTIYAC VAR

core/mesele.py bir sozdizimi hatasiyla IKI KEZ commit'lendi ve 360
testin hicbiri fark etmedi -- cunku o dosyayi import eden bir test
yoktu. Hata ancak olcum calistirilinca ortaya cikti:

    SyntaxError: unterminated string literal (line 67)

Test paketi "kod dogru calisiyor mu" diye bakiyordu; "kod hic
calisiyor mu" diye bakan yoktu. Bu dosya o bosluga bakiyor.

NEDEN IMPORT DEGIL DE DERLEME

Import etmek daha cok sey yakalardi ama yan etkisi var: core/embedder
ve core/rerank modelleri yukluyor, GPU tutuyor ve test paketini
dakikalarca bekletirdi. Derleme sozdizimi hatalarini yakalamaya
yetiyor -- yakalanmayan hata tam olarak buydu.
"""
from __future__ import annotations

from pathlib import Path

import pytest

KOK = Path(__file__).resolve().parent.parent


def _kaynaklar() -> list[Path]:
    dosyalar = sorted((KOK / "core").glob("*.py"))
    dosyalar += sorted((KOK / "tests").glob("*.py"))
    dosyalar += sorted((KOK / "tools").glob("*.py")) if (KOK / "tools").is_dir() else []
    # Kok dizindeki betikler: server.py, cli.py, olcum*.py ...
    dosyalar += sorted(p for p in KOK.glob("*.py"))
    return dosyalar


@pytest.mark.parametrize("yol", _kaynaklar(),
                         ids=lambda p: f"{p.parent.name}/{p.name}")
def test_derleniyor(yol: Path):
    kaynak = yol.read_text(encoding="utf-8")
    try:
        compile(kaynak, str(yol), "exec")
    except SyntaxError as exc:
        pytest.fail(f"{yol.relative_to(KOK)}:{exc.lineno} {exc.msg}\n"
                    f"    {(exc.text or '').strip()}")
