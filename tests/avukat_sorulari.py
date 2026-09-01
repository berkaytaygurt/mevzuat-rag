"""Bir avukatin gercekten sorabilecegi is hukuku sorulari.

Neden bu set: onceki karsilastirma testi maddelerden sayi cikarip soru
uretiyordu ve sorular yapay kaliyordu ("... 135 inci maddesinde gecen KHK
numarasi nedir"). Gercek bir avukat oyle sormaz.

Bu sorular is hukuku pratiginde siklikla karsilasilan konulardan yazildi.
Is hukuku secildi cunku karar indeksi (2.890 Yargitay karari) bu alanda --
yani hem mevzuat hem ictihat tarafi ayni anda sinaniyor.

Puanlama: cevaplarda gosterilen madde atiflari kulliyata karsi
dogrulanir. "Var olmayan madde gosterme" ve "yanlis madde gosterme"
nesnel olarak olculebilir; uslup ya da akicilik olculmez.
"""

SORULAR: list[str] = [
    # --- kıdem ve ihbar ---
    "Kıdem tazminatına hak kazanmak için en az ne kadar çalışmak gerekir?",
    "Kıdem tazminatı hesabında hangi ödemeler giydirilmiş ücrete dahil edilir?",
    "Kıdem tazminatı tavanı nedir ve neye göre belirlenir?",
    "İhbar önelleri çalışma süresine göre nasıl belirlenir?",
    "İhbar öneli içinde işçiye iş arama izni verilmesi zorunlu mudur?",
    "İşçi istifa ederse kıdem tazminatı alabilir mi?",
    "Emeklilik nedeniyle işten ayrılan işçi kıdem tazminatı alabilir mi?",
    "Askerlik nedeniyle işten ayrılan işçinin kıdem tazminatı hakkı var mıdır?",
    "Evlilik nedeniyle işten ayrılan kadın işçinin kıdem tazminatı hakkı nedir?",
    "İşyeri devrinde işçinin kıdemi nasıl hesaplanır?",

    # --- fesih ---
    "İşveren hangi hallerde haklı nedenle derhal fesih yapabilir?",
    "İşçi hangi hallerde haklı nedenle derhal fesih yapabilir?",
    "Haklı nedenle fesih hakkı ne kadar süre içinde kullanılmalıdır?",
    "Geçerli sebeple fesih ile haklı sebeple fesih arasındaki fark nedir?",
    "Fesih bildiriminin yazılı yapılması zorunlu mudur?",
    "İşçinin savunması alınmadan iş sözleşmesi feshedilebilir mi?",
    "Devamsızlık nedeniyle fesih için kaç gün devamsızlık gerekir?",
    "İşçinin işverene hakaret etmesi haklı fesih sebebi midir?",

    # --- işe iade ---
    "İşe iade davası açabilmek için hangi şartlar aranır?",
    "İşe iade davası ne kadar süre içinde açılmalıdır?",
    "İşe iade davası kazanılırsa işçiye hangi haklar doğar?",
    "İşe iade kararı sonrası işçi kaç gün içinde başvurmalıdır?",
    "İşveren işe başlatmazsa ödenecek tazminat ne kadardır?",
    "İş güvencesi hükümlerinden yararlanmak için kaç işçi çalışması gerekir?",

    # --- ücret ---
    "Ücret ne zaman ödenmelidir ve gecikirse ne olur?",
    "Ücreti ödenmeyen işçi çalışmaktan kaçınabilir mi?",
    "Asgari ücret nasıl belirlenir?",
    "Ücretin bankadan ödenmesi zorunlu mudur?",
    "İşçinin ücretinden hangi kesintiler yapılabilir?",
    "Ücret alacaklarında zamanaşımı süresi nedir?",

    # --- çalışma süreleri ---
    "Haftalık normal çalışma süresi kaç saattir?",
    "Fazla çalışma ücreti nasıl hesaplanır?",
    "Yılda en fazla kaç saat fazla çalışma yaptırılabilir?",
    "Fazla çalışma için işçinin onayı gerekir mi?",
    "Denkleştirme uygulaması nedir ve nasıl yapılır?",
    "Gece çalışması en fazla kaç saat olabilir?",
    "Ara dinlenme süreleri nasıl belirlenir?",
    "Hafta tatili ücreti nasıl hesaplanır?",

    # --- izinler ---
    "Yıllık ücretli izin süreleri kaç gündür?",
    "Yıllık izne hak kazanmak için ne kadar çalışmak gerekir?",
    "Kullanılmayan yıllık izin ücreti ne zaman ödenir?",
    "Doğum izni süreleri ne kadardır?",
    "Süt izni günde kaç saattir?",
    "Mazeret izinleri hangi hallerde verilir?",

    # --- diğer ---
    "İş kazası halinde işverenin sorumluluğu nedir?",
    "Mobbing iddiasında ispat yükü kimdedir?",
    "Belirli süreli iş sözleşmesi hangi hallerde yapılabilir?",
    "Deneme süresi en fazla ne kadar olabilir?",
    "Rekabet yasağı sözleşmesi hangi şartlarda geçerlidir?",
    "İş davalarında arabuluculuk zorunlu mudur?",
    "Alt işveren (taşeron) ilişkisinde asıl işverenin sorumluluğu nedir?",
    "İşçilik alacaklarında faiz hangi tarihten itibaren işler?",
]
