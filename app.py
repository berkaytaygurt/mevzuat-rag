"""Streamlit arayuzu: mevzuata dayali soru-cevap."""
from __future__ import annotations

import streamlit as st

import config
from core.embedder import Embedder
from core.generate import Generator
from core.retrieve import Retriever
from core.store import MevzuatStore

st.set_page_config(page_title="Mevzuat RAG", page_icon="§", layout="wide")


@st.cache_resource
def kaynaklari_yukle():
    store = MevzuatStore()
    return store, Retriever(store, Embedder()), Generator()


st.title("Mevzuat Asistanı")
st.caption("Türk mevzuatı üzerinde, yalnızca getirilen maddelere dayanan soru-cevap.")

try:
    store, retriever, generator = kaynaklari_yukle()
except Exception as exc:
    st.error(f"Başlatılamadı: {exc}")
    st.info("Önce `python cli.py cek --pilot` ve `python cli.py indeksle` çalıştırın.")
    st.stop()

with st.sidebar:
    st.metric("İndekslenmiş madde", f"{store.sayi():,}")
    st.write(f"**Sağlayıcı:** `{config.PROVIDER}`")
    st.write(f"**Embedding:** `{config.EMBED_MODEL.split('/')[-1]}`")
    k = st.slider("Getirilecek madde sayısı", 3, 15, 5)
    mulga_haric = st.checkbox("Mülga maddeleri hariç tut", value=True)
    st.divider()
    st.caption("Bu araç genel bilgi verir, hukuki görüş yerine geçmez.")

soru = st.text_input("Sorunuz", placeholder="Yıllık ücretli izin süresi kaç gündür?")

if soru:
    with st.spinner("İlgili maddeler aranıyor..."):
        maddeler = retriever.ara(soru, limit=k, mulga_haric=mulga_haric)

    if not maddeler:
        st.warning("İlgili madde bulunamadı.")
    else:
        with st.spinner("Cevap hazırlanıyor..."):
            cevap = generator.cevapla(soru, maddeler)
        st.markdown("### Cevap")
        st.markdown(cevap)

        st.markdown("### Dayanak Maddeler")
        for m in maddeler:
            etiket = (f"{m['mevzuat_adi']} — Madde {m['madde_no']}"
                      + (f": {m['baslik']}" if m.get("baslik") else ""))
            if m.get("mulga"):
                etiket += "  ⚠ MÜLGA"
            elif m.get("kismi_mulga"):
                etiket += "  ⚠ bir fıkrası mülga"
            with st.expander(etiket):
                st.caption(f"skor {m['skor']:.4f} · eşleşme: {', '.join(m['kaynaklar'])}"
                           + (f" · {m['bolum']}" if m.get("bolum") else ""))
                st.write(m["metin"])
                if m.get("degisiklikler"):
                    st.caption("Değişiklikler: " + " ".join(m["degisiklikler"][:5]))
