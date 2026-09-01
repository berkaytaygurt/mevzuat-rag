"""Claude'un (bu asistanin) avukat sorularina kendi bilgisinden verdigi cevaplar.

Kulliyata BAKILMADAN yazildi -- ciplak Gemini ile ayni sartlarda. Amac,
"bu sistemi kurmak yerine dogrudan bir dil modeline sorsak ne olur"
sorusunu ucuncu bir yanitla da sinamak.

Ayni dogrulamadan geciyor: gosterilen madde kulliyatta var mi, metni
iddiayi destekliyor mu.
"""

CEVAPLAR: dict[str, str] = {
 "Kıdem tazminatına hak kazanmak için en az ne kadar çalışmak gerekir?":
  "En az bir yıl çalışmış olmak gerekir (1475 sayılı İş Kanunu m.14).",
 "Kıdem tazminatı hesabında hangi ödemeler giydirilmiş ücrete dahil edilir?":
  "Asıl ücrete ek olarak süreklilik arz eden ikramiye, yol, yemek, yakacak gibi "
  "para ve parayla ölçülebilen menfaatler dahil edilir (1475 sayılı İş Kanunu m.14).",
 "Kıdem tazminatı tavanı nedir ve neye göre belirlenir?":
  "En yüksek Devlet memuruna ödenen bir yıllık emeklilik ikramiyesi tutarını "
  "aşamaz (1475 sayılı İş Kanunu m.14).",
 "İhbar önelleri çalışma süresine göre nasıl belirlenir?":
  "6 aya kadar 2 hafta, 6 ay-1,5 yıl 4 hafta, 1,5-3 yıl 6 hafta, 3 yıldan fazla "
  "8 haftadır (4857 sayılı İş Kanunu m.17).",
 "İhbar öneli içinde işçiye iş arama izni verilmesi zorunlu mudur?":
  "Evet, günde en az iki saat iş arama izni verilir (4857 sayılı İş Kanunu m.27).",
 "İşçi istifa ederse kıdem tazminatı alabilir mi?":
  "Kural olarak alamaz; ancak haklı nedenle fesihte alır (1475 sayılı İş Kanunu m.14).",
 "Emeklilik nedeniyle işten ayrılan işçi kıdem tazminatı alabilir mi?":
  "Evet, yaşlılık aylığı almak amacıyla ayrılan işçi kıdem tazminatına hak kazanır "
  "(1475 sayılı İş Kanunu m.14).",
 "Askerlik nedeniyle işten ayrılan işçinin kıdem tazminatı hakkı var mıdır?":
  "Evet, muvazzaf askerlik nedeniyle ayrılan işçi kıdem tazminatı alır "
  "(1475 sayılı İş Kanunu m.14).",
 "Evlilik nedeniyle işten ayrılan kadın işçinin kıdem tazminatı hakkı nedir?":
  "Evlendiği tarihten itibaren bir yıl içinde ayrılırsa kıdem tazminatına hak "
  "kazanır (1475 sayılı İş Kanunu m.14).",
 "İşyeri devrinde işçinin kıdemi nasıl hesaplanır?":
  "Devralan işveren, işçinin devirden önceki hizmet süresinden de sorumludur; "
  "kıdem bütün olarak hesaplanır (4857 sayılı İş Kanunu m.6).",
 "İşveren hangi hallerde haklı nedenle derhal fesih yapabilir?":
  "Sağlık sebepleri, ahlak ve iyiniyet kurallarına uymayan haller ve zorlayıcı "
  "sebeplerde (4857 sayılı İş Kanunu m.25).",
 "İşçi hangi hallerde haklı nedenle derhal fesih yapabilir?":
  "Sağlık sebepleri, ahlak ve iyiniyet kurallarına uymayan haller ve zorlayıcı "
  "sebeplerde (4857 sayılı İş Kanunu m.24).",
 "Haklı nedenle fesih hakkı ne kadar süre içinde kullanılmalıdır?":
  "Öğrenmeden itibaren altı iş günü, her hâlde fiilin gerçekleşmesinden itibaren "
  "bir yıl içinde (4857 sayılı İş Kanunu m.26).",
 "Geçerli sebeple fesih ile haklı sebeple fesih arasındaki fark nedir?":
  "Haklı sebepte derhal fesih yapılır ve ihbar tazminatı doğmaz; geçerli sebepte "
  "ihbar öneli verilir, kıdem tazminatı ödenir (4857 sayılı İş Kanunu m.18).",
 "Fesih bildiriminin yazılı yapılması zorunlu mudur?":
  "İş güvencesi kapsamında fesih yazılı yapılmalı ve sebebi açıkça belirtilmelidir "
  "(4857 sayılı İş Kanunu m.19).",
 "İşçinin savunması alınmadan iş sözleşmesi feshedilebilir mi?":
  "Davranış veya verimden kaynaklanan sebeplerde savunma alınmadan feshedilemez "
  "(4857 sayılı İş Kanunu m.19).",
 "Devamsızlık nedeniyle fesih için kaç gün devamsızlık gerekir?":
  "Ardı ardına iki iş günü, bir ayda iki kez tatil günü ertesi, veya bir ayda üç "
  "iş günü (4857 sayılı İş Kanunu m.25).",
 "İşçinin işverene hakaret etmesi haklı fesih sebebi midir?":
  "Evet, ahlak ve iyiniyet kurallarına uymayan hal sayılır "
  "(4857 sayılı İş Kanunu m.25).",
 "İşe iade davası açabilmek için hangi şartlar aranır?":
  "En az 30 işçi çalıştıran işyerinde, en az 6 aylık kıdemi olan, belirsiz süreli "
  "sözleşmeyle çalışan işçi olmak gerekir (4857 sayılı İş Kanunu m.18).",
 "İşe iade davası ne kadar süre içinde açılmalıdır?":
  "Fesih bildiriminden itibaren bir ay içinde arabulucuya başvurulur "
  "(4857 sayılı İş Kanunu m.20).",
 "İşe iade davası kazanılırsa işçiye hangi haklar doğar?":
  "En çok dört aya kadar boşta geçen süre ücreti ve işe başlatmama hâlinde dört "
  "ila sekiz aylık ücret tutarında tazminat (4857 sayılı İş Kanunu m.21).",
 "İşe iade kararı sonrası işçi kaç gün içinde başvurmalıdır?":
  "Kesinleşen kararın tebliğinden itibaren on iş günü içinde "
  "(4857 sayılı İş Kanunu m.21).",
 "İşveren işe başlatmazsa ödenecek tazminat ne kadardır?":
  "En az dört, en çok sekiz aylık ücreti tutarında tazminat "
  "(4857 sayılı İş Kanunu m.21).",
 "İş güvencesi hükümlerinden yararlanmak için kaç işçi çalışması gerekir?":
  "En az otuz işçi (4857 sayılı İş Kanunu m.18).",
 "Ücret ne zaman ödenmelidir ve gecikirse ne olur?":
  "En geç ayda bir ödenir; yirmi gün geciktirilirse işçi çalışmaktan kaçınabilir "
  "(4857 sayılı İş Kanunu m.32).",
 "Ücreti ödenmeyen işçi çalışmaktan kaçınabilir mi?":
  "Evet, ödeme günü itibarıyla yirmi gün geçerse (4857 sayılı İş Kanunu m.34).",
 "Asgari ücret nasıl belirlenir?":
  "Asgari Ücret Tespit Komisyonunca belirlenir (4857 sayılı İş Kanunu m.39).",
 "Ücretin bankadan ödenmesi zorunlu mudur?":
  "Belirlenen sayıda işçi çalıştıran işverenler için zorunludur "
  "(4857 sayılı İş Kanunu m.32).",
 "İşçinin ücretinden hangi kesintiler yapılabilir?":
  "Kanunen öngörülenler dışında kesinti yapılamaz; ücret kesme cezası ayda iki "
  "gündelikten fazla olamaz (4857 sayılı İş Kanunu m.38).",
 "Ücret alacaklarında zamanaşımı süresi nedir?":
  "Beş yıldır (4857 sayılı İş Kanunu m.32).",
 "Haftalık normal çalışma süresi kaç saattir?":
  "Haftada en çok kırkbeş saattir (4857 sayılı İş Kanunu m.63).",
 "Fazla çalışma ücreti nasıl hesaplanır?":
  "Normal saat ücretinin yüzde elli fazlasıyla ödenir (4857 sayılı İş Kanunu m.41).",
 "Yılda en fazla kaç saat fazla çalışma yaptırılabilir?":
  "Yılda ikiyüzyetmiş saatten fazla olamaz (4857 sayılı İş Kanunu m.41).",
 "Fazla çalışma için işçinin onayı gerekir mi?":
  "Evet, işçinin yazılı onayı gerekir (4857 sayılı İş Kanunu m.41).",
 "Denkleştirme uygulaması nedir ve nasıl yapılır?":
  "İki aylık süre içinde haftalık ortalama çalışma süresi aşılmamak kaydıyla "
  "çalışma süreleri farklı dağıtılabilir (4857 sayılı İş Kanunu m.63).",
 "Gece çalışması en fazla kaç saat olabilir?":
  "Gece çalışması yedi buçuk saati geçemez (4857 sayılı İş Kanunu m.69).",
 "Ara dinlenme süreleri nasıl belirlenir?":
  "Dört saat veya altı için onbeş dakika, dört-yedi buçuk saat için yarım saat, "
  "yedi buçuk saatten fazlası için bir saat (4857 sayılı İş Kanunu m.68).",
 "Hafta tatili ücreti nasıl hesaplanır?":
  "Çalışılmadığı hâlde bir günlük ücret tam olarak ödenir "
  "(4857 sayılı İş Kanunu m.46).",
 "Yıllık ücretli izin süreleri kaç gündür?":
  "1-5 yıl için 14 gün, 5-15 yıl için 20 gün, 15 yıl ve üzeri için 26 günden az "
  "olamaz (4857 sayılı İş Kanunu m.53).",
 "Yıllık izne hak kazanmak için ne kadar çalışmak gerekir?":
  "En az bir yıl çalışmış olmak gerekir (4857 sayılı İş Kanunu m.53).",
 "Kullanılmayan yıllık izin ücreti ne zaman ödenir?":
  "İş sözleşmesinin sona ermesinde son ücret üzerinden ödenir "
  "(4857 sayılı İş Kanunu m.59).",
 "Doğum izni süreleri ne kadardır?":
  "Doğumdan önce sekiz, doğumdan sonra sekiz hafta olmak üzere toplam onaltı "
  "hafta (4857 sayılı İş Kanunu m.74).",
 "Süt izni günde kaç saattir?":
  "Bir yaşından küçük çocuk için günde toplam bir buçuk saat "
  "(4857 sayılı İş Kanunu m.74).",
 "Mazeret izinleri hangi hallerde verilir?":
  "Evlenme, doğum, ölüm ve engelli çocuğun tedavisi hâllerinde "
  "(4857 sayılı İş Kanunu Ek Madde 2).",
 "İş kazası halinde işverenin sorumluluğu nedir?":
  "İşveren iş sağlığı ve güvenliği önlemlerini almakla yükümlüdür; kusuru hâlinde "
  "maddi ve manevi tazminattan sorumludur "
  "(6331 sayılı İş Sağlığı ve Güvenliği Kanunu m.4).",
 "Mobbing iddiasında ispat yükü kimdedir?":
  "İşçi mobbingi kuvvetle muhtemel gösterirse ispat yükü işverene geçer "
  "(6098 sayılı Türk Borçlar Kanunu m.417).",
 "Belirli süreli iş sözleşmesi hangi hallerde yapılabilir?":
  "Belirli süreli işlerde veya belli bir işin tamamlanması gibi objektif "
  "koşullarda (4857 sayılı İş Kanunu m.11).",
 "Deneme süresi en fazla ne kadar olabilir?":
  "En çok iki ay, toplu iş sözleşmesiyle dört aya kadar "
  "(4857 sayılı İş Kanunu m.15).",
 "Rekabet yasağı sözleşmesi hangi şartlarda geçerlidir?":
  "Yazılı olmalı, süre iki yılı aşmamalı, yer ve konu bakımından sınırlı "
  "olmalıdır (6098 sayılı Türk Borçlar Kanunu m.445).",
 "İş davalarında arabuluculuk zorunlu mudur?":
  "İşçilik alacakları ve işe iade taleplerinde dava şartıdır "
  "(7036 sayılı İş Mahkemeleri Kanunu m.3).",
 "Alt işveren (taşeron) ilişkisinde asıl işverenin sorumluluğu nedir?":
  "Asıl işveren, alt işverenin işçilerine karşı o işyeriyle ilgili "
  "yükümlülüklerden alt işverenle birlikte müteselsilen sorumludur "
  "(4857 sayılı İş Kanunu m.2).",
 "İşçilik alacaklarında faiz hangi tarihten itibaren işler?":
  "Kıdem tazminatında fesih tarihinden itibaren mevduata uygulanan en yüksek "
  "faiz işler (1475 sayılı İş Kanunu m.14).",
}
