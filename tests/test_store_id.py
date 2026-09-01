"""Nokta id uretiminin surecten surece kararli kalmasini dogrular."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.store import _nokta_id  # noqa: E402


def test_id_beklenen_sabit_deger():
    """Sabit deger, yerlesik hash()'e geri donulurse testi bozar."""
    assert _nokta_id("Kanun-4857-53") == 6499422463074368886


def test_id_farkli_sureclerde_ayni():
    """PYTHONHASHSEED degisse bile id degismemeli.

    Yerlesik hash() string'ler icin surec basina rastgelelestirilir; onunla
    uretilen id yeniden indekslemede kaydi guncellemek yerine kopyasini ekler.
    """
    kod = ("import sys; sys.path.insert(0, r'%s');"
           "from core.store import _nokta_id; print(_nokta_id('Kanun-4857-53'))" % ROOT)
    degerler = set()
    for seed in ("0", "1", "12345"):
        out = subprocess.run([sys.executable, "-c", kod], capture_output=True,
                             text=True, env={"PYTHONHASHSEED": seed, "PATH": ""})
        degerler.add(out.stdout.strip())
    assert len(degerler) == 1, f"id surecler arasinda degisti: {degerler}"


def test_id_farkli_maddeler_farkli():
    idler = {_nokta_id(f"Kanun-4857-{n}") for n in range(1, 200)}
    assert len(idler) == 199
