"""Uzun madde cocuk parcalari.

NEDEN VAR
Gomme penceresi 512 token ve maddelerin %17,9'u bunu asiyor; asan kismin
vektorde karsiligi yok. Olculdu (40 uzun kanun maddesi, saf vektor):
maddenin BASINDAN alinan ifade 36/40 bulunuyor, SONUNDAN alinan 13/40.

Cocuklar yalnizca KUYRUK icin uretiliyor -- maddenin basi zaten mevcut
vektorde kapsanmis durumda.
"""
from core.cocuk import cocuklari_uret, COCUK_TOKEN, BINDIRME_TOKEN


class SahteTokenizer:
    """Kelime = token sayan basit tokenizer; testin modele ihtiyaci olmasin."""

    def encode(self, metin, add_special_tokens=False):
        return metin.split()

    def decode(self, tokenlar):
        return " ".join(tokenlar)


def embed_metni(m):
    return m.get("metin", "")


def test_kisa_madde_cocuk_uretmiyor(monkeypatch):
    import config
    monkeypatch.setattr(config, "EMBED_MAX_SEQ", 50)
    kayit = {"chunk_id": "K-1", "metin": " ".join(["kelime"] * 30)}
    assert cocuklari_uret([kayit], SahteTokenizer(), embed_metni) == []


def test_uzun_madde_kuyruk_icin_cocuk_uretiyor(monkeypatch):
    import config
    monkeypatch.setattr(config, "EMBED_MAX_SEQ", 50)
    kayit = {"chunk_id": "K-1", "mevzuat_no": "4857",
             "metin": " ".join(["kelime"] * 400)}
    c = cocuklari_uret([kayit], SahteTokenizer(), embed_metni)
    assert c, "uzun madde icin cocuk uretilmedi"
    assert all(x["ana_chunk_id"] == "K-1" for x in c)
    assert len({x["chunk_id"] for x in c}) == len(c), "cocuk id'leri cakisiyor"
    # Ana kaydin alanlari tasinmali
    assert all(x["mevzuat_no"] == "4857" for x in c)


def test_cocuk_parcasi_pencereye_siginiyor(monkeypatch):
    import config
    monkeypatch.setattr(config, "EMBED_MAX_SEQ", 50)
    kayit = {"chunk_id": "K-1", "metin": " ".join(["kelime"] * 900)}
    tok = SahteTokenizer()
    for c in cocuklari_uret([kayit], tok, embed_metni):
        assert len(tok.encode(c["cocuk_metin"])) <= COCUK_TOKEN, c["chunk_id"]


def test_fikra_sinirindan_bolunuyor(monkeypatch):
    """Kanun metni '(1)', '(2)' ile bolunmus; parcalar orada kesilmeli."""
    import config
    monkeypatch.setattr(config, "EMBED_MAX_SEQ", 10)
    metin = ("(1) " + " ".join(["bas"] * 12) + " (2) " + " ".join(["orta"] * 12)
             + " (3) " + " ".join(["son"] * 12))
    c = cocuklari_uret([{"chunk_id": "K-1", "metin": metin}],
                       SahteTokenizer(), embed_metni)
    assert c
    # En az bir parca bir fikra isaretiyle basliyor olmali
    assert any(x["cocuk_metin"].startswith("(") for x in c), \
        [x["cocuk_metin"][:20] for x in c]


def test_kuyruk_bindirmeli_basliyor(monkeypatch):
    """Pencere sinirinda kesilen hukum iki tarafta da yarim kalmasin."""
    import config
    monkeypatch.setattr(config, "EMBED_MAX_SEQ", 100)
    kelimeler = [f"k{i}" for i in range(300)]
    kayit = {"chunk_id": "K-1", "metin": " ".join(kelimeler)}
    c = cocuklari_uret([kayit], SahteTokenizer(), embed_metni)
    ilk = c[0]["cocuk_metin"].split()
    # Bindirme kadar geriden basladigi icin 100. kelimeden oncesini de icermeli
    assert ilk[0] == f"k{100 - BINDIRME_TOKEN}", ilk[:3]


def test_baslik_her_cocukta_tekrarlanabiliyor(monkeypatch):
    """Cocuk yalnizca govde parcasi tasir; baslik cagiran tarafta eklenir.

    Baslik olmadan gomulen bir kuyruk parcasi ("(4) Isveren bu sureyi...")
    hangi kanunun hangi maddesi oldugunu soylemiyor ve vektor alakasiz
    cikiyor. Bolme bu yuzden GOVDE uzerinde yapiliyor, baslik uzunlugu
    pencereden dusuluyor.
    """
    import config
    monkeypatch.setattr(config, "EMBED_MAX_SEQ", 40)

    def basliklі_embed(m):
        return f"IS KANUNU Madde 19 {m.get('metin', '')}".strip()

    kayit = {"chunk_id": "K-1", "metin": " ".join(["govde"] * 200)}
    c = cocuklari_uret([kayit], SahteTokenizer(), basliklі_embed)
    assert c
    # Cocuk metninde baslik OLMAMALI; yalnizca govde parcasi
    assert all("IS KANUNU" not in x["cocuk_metin"] for x in c)
    # Baslik eklendiginde pencereye sigmali
    tok = SahteTokenizer()
    for x in c:
        tam = basliklі_embed({**x, "metin": x["cocuk_metin"]})
        assert len(tok.encode(tam)) <= config.EMBED_MAX_SEQ + COCUK_TOKEN
