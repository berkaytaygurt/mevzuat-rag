"""Proje geneli ayarlar. .env varsa oradan okur, yoksa makul varsayilanlar."""
from pathlib import Path
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

ROOT = Path(__file__).parent
RAW_DIR = ROOT / "data" / "raw"
INDEX_DIR = ROOT / "data" / "index"
CERT_BUNDLE = ROOT / "certs" / "mevzuat-ca-bundle.pem"

for d in (RAW_DIR, INDEX_DIR):
    d.mkdir(parents=True, exist_ok=True)

# --- scraper ---
BASE_URL = "https://www.mevzuat.gov.tr"
SCRAPE_DELAY = float(os.getenv("SCRAPE_DELAY", "1.5"))
SCRAPE_CONTACT = os.getenv("SCRAPE_CONTACT", "")
USER_AGENT = (
    f"mevzuat-rag/0.1 (kisisel arastirma projesi"
    + (f"; iletisim: {SCRAPE_CONTACT}" if SCRAPE_CONTACT else "")
    + ")"
)

# --- embedding ---
EMBED_MODEL = os.getenv("EMBED_MODEL", "Qwen/Qwen3-Embedding-0.6B")
EMBED_DEVICE = os.getenv("EMBED_DEVICE", "cuda")
EMBED_BATCH = int(os.getenv("EMBED_BATCH", "8"))
EMBED_MAX_SEQ = int(os.getenv("EMBED_MAX_SEQ", "512"))

# --- yeniden siralama (cross-encoder) ---
RERANK = os.getenv("RERANK", "1") not in ("0", "false", "hayir")
RERANK_MODEL = os.getenv("RERANK_MODEL", "BAAI/bge-reranker-v2-m3")
RERANK_BATCH = int(os.getenv("RERANK_BATCH", "6"))
# Cross-encoder maddenin ilk max_seq token'ini goruyor. 256 token
# (~768 karakter) kulliyattaki 58.975 maddeyi (%34) kesiyordu.
# Olculdu (150 soruluk sette, tek yonlu artis):
#     256 -> MRR 0.447, ilk-5 85
#     384 -> MRR 0.457, ilk-5 85
#     512 -> MRR 0.474, ilk-5 89
# Bedeli sorgu basina 1.21 sn yerine 1.45 sn. Yigin 12'den 6'ya
# dusuruldu: 4 GB VRAM'de uzun dizi ile 12'lik yigin sigmiyor.
RERANK_MAX_SEQ = int(os.getenv("RERANK_MAX_SEQ", "512"))
# Ilk asamadan kac aday alinip yeniden siralanacak.
# Olculen en iyi nokta 25. Genisletmek tavani yukseltiyor (12 adayda ilk
# asama dogru maddeyi %88, 50 adayda %97 oranda havuza sokuyor) ama cikti
# degismiyor: darbogaz aday havuzu degil, siralayicinin karari. 50 ile 25
# ayni sonucu veriyor, 25 daha hizli.
RERANK_ADAY = int(os.getenv("RERANK_ADAY", "25"))
# Cross-encoder girdilerinde Turkce harfleri ASCII'ye katla
RERANK_KATLA = os.getenv("RERANK_KATLA", "1") not in ("0", "false", "hayir")
# Nihai siralamada cross-encoder puaninin agirligi (kalani ilk asamanin RRF'i).
# 1.0 = yalnizca cross-encoder, 0.0 = yalnizca ilk asama.
RERANK_AGIRLIK = float(os.getenv("RERANK_AGIRLIK", "0.9"))
# Ek/Gecici maddelere verilen kucuk siralama cezasi (0 = kapali)
EK_MADDE_CEZASI = float(os.getenv("EK_MADDE_CEZASI", "0.05"))
# Normlar hiyerarsisine gore siralama (kanun > yonetmelik > teblig)
HIYERARSI = os.getenv("HIYERARSI", "1") not in ("0", "false", "hayir")

# --- yazim duzeltme ---
# Aksansiz yazilan sorguyu kulliyattan cikarilan sozlukle gercek yazimina cevirir
YAZIM_DUZELT = os.getenv("YAZIM_DUZELT", "1") not in ("0", "false", "hayir")

# --- sorgu genisletme ---
# Sorguyu aramadan once LLM'e verip hukuk terimleriyle zenginlestirir.
# Her aramaya bir LLM cagrisi ekler; varsayilan kapali.
SORGU_GENISLET = os.getenv("SORGU_GENISLET", "0") not in ("0", "false", "hayir")
# Genisletmeyi hangi model yapsin. Cevap ureticisinden ayri tutuluyor: bu is
# basit (8 terim uretmek) ve gecikmeye cok duyarli, cevap uretimi ise degil.
GENISLET_PROVIDER = os.getenv("GENISLET_PROVIDER", os.getenv("PROVIDER", "local")).lower()
# Uyarlamali genisletme esigi: en iyi adayin cross-encoder puani bunun
# altindaysa sorgu genisletilip tekrar aranir. Yuksek esik = daha cok
# genisletme = daha yavas ama daha isabetli.
GENISLET_ESIK = float(os.getenv("GENISLET_ESIK", "0.5"))

# --- generation ---
PROVIDER = os.getenv("PROVIDER", "local").lower()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
# Olculdu: buyuk model ayni istegi 36.7 saniyede donduruyor ve sik sik 503
# veriyor; flash-lite 0.9 saniyede ve dogru cevapliyor. Bu isin (verilen
# maddeyi okuyup ozetlemek) buyuk modele ihtiyaci yok.
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-lite-latest")
# Birincil model mesgulse (503) sirayla denenir
# Cevap uretimi icin toplam sure butcesi (saniye). Asilirsa hizli hata
# verilir; tunel zaten 100 saniyede kopuyor.
GEMINI_SURE_BUTCESI = float(os.getenv("GEMINI_SURE_BUTCESI", "45"))
GEMINI_YEDEK_MODELLER = [
    m.strip() for m in os.getenv(
        "GEMINI_YEDEK_MODELLER", "gemini-3.5-flash,gemini-3.7-flash,gemini-flash-latest"
    ).split(",") if m.strip()
]
LOCAL_MODEL_PATH = os.getenv("LOCAL_MODEL_PATH", "models/qwen2.5-3b-instruct-q4_k_m.gguf")
# 3B model tamamen GPU'ya alindiginda (=-1) 4 GB kartta arama modelleriyle
# cakisiyor. Windows hata vermiyor, sessizce sistem bellegine tasiyor ve
# arama 1.5 saniye yerine 67 saniye suruyordu. Olculdu: temiz kartta 3.46 GB
# bos var; embedding 1.2 + siralayici 1.1 + 3B model 2.0 = 4.3 GB.
# Cevap uretimi islemcide yavas ama arama hizli kaliyor -- dogru takas bu,
# cunku her sorgu arama yapiyor, cevap ise istege bagli.
LOCAL_GPU_LAYERS = int(os.getenv("LOCAL_GPU_LAYERS", "0"))
LOCAL_CTX = int(os.getenv("LOCAL_CTX", "8192"))

# mevzuat.gov.tr tur kodlari (MevzuatTur parametresi)
MEVZUAT_TURLERI = {
    1: "Kanun",
    2: "Cumhurbaskanligi Kararnamesi",
    3: "Kanun Hukmunde Kararname",
    4: "Tuzuk",
    7: "Cumhurbaskanligi Yonetmeligi",
    8: "Kurum ve Kurulus Yonetmeligi",
    9: "Teblig",
    21: "Yonetmelik",
}


# --- sunucu ---
# Varsayilan olarak yalnizca kendi makinende dinler. Baskasinin erisebilmesi
# icin HOST=0.0.0.0 yapilir; o durumda sifre zorunludur (bkz. server.py).
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8000"))
KULLANICI = os.getenv("AIBARS_KULLANICI", "")
SIFRE = os.getenv("AIBARS_SIFRE", "")

# Mahkeme kararlari cevaba ayri bir bolum olarak eklensin mi. Kapatildiginda
# kararlar yalnizca arayuzde listelenir, uretilen cevaba girmez -- yerel
# modelin baglam penceresi dar oldugu icin bu bazen mevzuat cevabini
# zayiflatiyor.
KARARLARI_CEVABA_KAT = os.getenv("KARARLARI_CEVABA_KAT", "1") == "1"

# Sorgunun soru kaliplarindan arindirilmis halini de ayri bir sinyal olarak
# aramak. Olculen sorun: "kidem tazminati sartlari" dogru maddeyi 1. sirada
# getiriyor, ayni seyi soran dogal cumle 21. siraya dusuruyor.
CEKIRDEK_SORGU = os.getenv("CEKIRDEK_SORGU", "1") not in ("0", "false", "hayir")
CEKIRDEK_AGIRLIK = float(os.getenv("CEKIRDEK_AGIRLIK", "1.0"))

# Gemini icin gunluk sert istek tavani. Google'in butce uyarisi harcamayi
# durdurmaz, yalnizca haber verir; bu sayac durdurur. Sayac diske yaziliyor,
# surec yeniden baslasa da gunluk toplam korunuyor.
GEMINI_GUNLUK_SINIR = int(os.getenv("GEMINI_GUNLUK_SINIR", "1500"))

# Genisletme uyarlamali calisir: yalnizca ilk arama zayif sonuc verdiginde
# tetiklenir. Olculdu -- 448 sorgunun yalnizca 28'inde (%6) devreye girdi,
# yani fikir test bile edilmemis oldu. Bu bayrak esigi atlayip her sorguda
# genisletir; fikrin gercek etkisini olcmek icin.
GENISLET_HEP = os.getenv("GENISLET_HEP", "0") not in ("0", "false", "hayir")

# Sorgu genisletme gibi KUCUK isler icin ayri, hizli model. Olculdu --
# ayni onemsiz istek ("tek kelime yaz") su surelerde donuyor:
#     gemini-3.6-flash          36.7 sn  (ve sik sik 503)
#     gemini-flash-lite-latest   0.6 sn
# Genisletme kisa bir terim listesi uretiyor; buyuk model gereksiz.
GEMINI_HIZLI_MODEL = os.getenv("GEMINI_HIZLI_MODEL", "gemini-flash-lite-latest")

# Sorunun kulliyatla ilgili olup olmadigini ayiran esik (KULLANICININ ham
# sorusunun vektor benzerligi; genisletilmis sorgudan olculemez cunku
# genisletme hukuk terimleri ekleyip alakasiz sorularin puanini da
# yukseltiyor -- "kahve nasil demlenir" 0.631'den 0.728'e cikiyor).
#
# Olculdu (69 gercek hukuk sorusu + 10 alakasiz soru):
#
#     gercek sorular    en dusuk 0.548   ortanca 0.701
#     alakasiz sorular  en yuksek 0.631  ortanca 0.508
#
# Araliklar CAKISIYOR. Esik tablosu:
#
#     esik   yanlis engellenen   yakalanan sacma
#     0.50           0                5/10
#     0.55           1                6/10
#     0.60           6                9/10
#
# 0.50 secildi: gercek bir soruyu engellemek, sacma bir soruyu kacirmaktan
# cok daha kotu -- kacan sacma soruyu zaten modelin "bulamadim" kurali
# yakaliyor. Ilk denemede 0.60 konulmustu ve 69 sorunun 6'sini engelliyordu.
GUVEN_ESIGI = float(os.getenv("GUVEN_ESIGI", "0.50"))

# Madde metninde soruyla ilgili cumleyi isaretleme. VARSAYILAN KAPALI:
# olculdu, cross-encoder ile madde basina 3 saniye suruyor (6 madde = 18
# saniye) ve bu, zaten 6-12 saniye olan sorguyu kullanilamaz hale getiriyor.
#
# Isabet olculdu (10 soru): gomme benzerligiyle %60, cross-encoder ile %86.
# Yani ozellik CALISIYOR, yalnizca pahali. Kullanici istedigi sorguda
# acabilsin diye istek basina da verilebiliyor (Soru.vurgu).
# Varsayilan ACIK: kullanici istedi. Bedeli yukarida yazili --
# madde basina ~1-3 saniye, 10 maddede sorguya 10-30 saniye ekliyor.
VURGU = os.getenv("VURGU", "1") not in ("0", "false", "hayir")

# Sorgu genisletme yalnizca ZAYIF sorgularda calissin. Ham sorgunun vektor
# benzerligi bu degerin USTUNDEYSE genisletme atlanir.
#
# Olculdu: genisletme sorgu basina +4.09 saniye ekliyor (ham arama 0.66,
# yeniden siralama 0.83). Bu, toplam surenin yarisindan fazlasi. Oysa
# genisletmenin faydasi zayif sorgularda -- guclu bir sorgu zaten dogru
# maddeyi buluyor.
#
# Gercek soru puanlarinin ortancasi 0.701; 0.72 esigi sorgularin yaklasik
# yarisini genisletmeden gecirir.
GENISLET_YETER = float(os.getenv("GENISLET_YETER", "0.72"))

# Cok olgulu sorulari hukuki meselelere ayirip her birini ayri arama.
# Olculen sorun: avukat somut dosyayla gelir ("isci 4 yil 11 ay calisti,
# devamsizlik nedeniyle savunma almadan feshetti, fesih gecerli mi") ve tek
# vektor bu uc meselenin bulanik ortalamasi oluyor; sistem hicbirinin
# maddesini bulamayip "dayanak bulamadim" diyordu.
MESELE_AYIR = os.getenv("MESELE_AYIR", "1") not in ("0", "false", "hayir")


# --- olcum gunlugu ---
# Hangi sorgunun yavas ya da zayif oldugunu ancak gercek kullanimda
# gorebiliyoruz; sure ve guven puani kayitli olmazsa elimizde "avukat
# sikayet etti" disinda isaret kalmiyor.
#
# VARSAYILAN KAPALI. Kayit SORU METNINI de tutuyor ve site disariya
# aciksa baskalarinin sorgulari da yazilir; bu, sahibinin bilerek
# vermesi gereken bir karar.
METRIK = os.getenv("METRIK", "0") not in ("0", "false", "hayir")
METRIK_YOLU = ROOT / "data" / "metrik.jsonl"
