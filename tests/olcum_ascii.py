"""Olcum setinin Turkce karakter kullanilmadan yazilmis hali.

Kullanicilarin cogu sorgusunu boyle yazar. Ayni sorulari iki bicimde de
olcmek, sistemin yazim farkina ne kadar duyarli oldugunu gosterir.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.retrieve import _tr_katla  # noqa: E402
from tests.olcum_seti import SORULAR as _AKSANLI  # noqa: E402

SORULAR = [(_tr_katla(s), k, m) for s, k, m in _AKSANLI]
