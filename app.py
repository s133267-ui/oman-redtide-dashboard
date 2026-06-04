import datetime
import json
import ee
import geemap.foliumap as geemap
import streamlit as st

# 1. إعدادات واجهة المستخدم للداشبورد
st.set_page_config(layout="wide", page_title="داشبورد مراقبة المد الأحمر - سلطنة عمان")

# تصميم العنوان باللغة العربية
st.markdown(
    "<h1 style='text-align: center; color: #008080;'>🛸 نظام مراقبة المد الأحمر المؤتمت لسواحل سلطنة عُمان</h1>",
    unsafe_allow_html=True,
)
st.markdown(
    "<p style='text-align: center;'>تحليل مستمر لبيانات الكلوروفيل، درجة حرارة سطح البحر (SST)، وأعماق المياه</p>",
    unsafe_allow_html=True,
)

# 2. تفعيل الاتصال الآمن بجوجل إيرث إنجين باستخدام الرموز السرية (Secrets)
@st.cache_resource
def authenticate_gee():
    try:
        # قراءة المفتاح السري الذي سنضعه في إعدادات السيرفر في المرحلة الرابعة
        credentials_dict = json.loads(st.secrets["GEE_KEYS"])
        credentials = ee.ServiceAccountCredentials(
            credentials_dict["client_email"], key_data=credentials_dict["private_key"]
        )
        ee.Initialize(credentials, project=credentials_dict["project_id"])
    except Exception as e:
        st.error(f"خطأ في الاتصال بسيرفر Google Earth Engine: {e}")

authenticate_gee()

# 3. تحديد الحدود الجغرافية لسواحل سلطنة عمان (من مسندم إلى ظفار)
oman_coasts = ee.Geometry.Rectangle([52.0, 16.0, 60.0, 27.0])

# 4. شريط التحكم الجانبي في الموقع (Sidebar)
st.sidebar.image(
    "https://cdn-icons-png.flaticon.com/512/4144/4144426.png", width=100
)
st.sidebar.header("🎛️ لوحة الفلترة والتحكم")

indicator = st.sidebar.selectbox(
    "اختر المؤشر البيئي للمراقبة:",
    ("تركيز الكلوروفيل (Chlorophyll-a)", "درجة حرارة سطح البحر (SST)"),
)

# تحديد السنوات ديناميكياً حتى السنة الحالية 2026
current_year = datetime.date.today().year
year = st.sidebar.slider("اختر السنة:", 2002, current_year, current_year)
month = st.sidebar.slider("اختر الشهر:", 1, 12, datetime.date.today().month)

# تحضير تواريخ الفلترة بناءً على اختيار المستخدم
start_date = f"{year}-{month:02d}-01"
if month == 12:
    end_date = f"{year+1}-01-01"
else:
    end_date = f"{year}-{month+1:02d}-01"

# 5. جلب البيانات الجغرافية من سيرفرات جوجل
# أ) بيانات أعماق المياه (ثابتة وقوية)
bathymetry = ee.Image("GEBCO/v2022").select("elevation").clip(oman_coasts)

# ب) بيانات قمر ناسا (MODIS Aqua) للبحار
modis = (
    ee.ImageCollection("NASA/OCEANCOLOR/MODISA/L3SMI")
    .filterDate(start_date, end_date)
    .filterBounds(oman_coasts)
    .mean()
)

# 6. بناء الخريطة التفاعلية
Map = geemap.Map(center=[21.0, 57.0], zoom=6)

# إضافة طبقة الأعماق كخلفية مائية مجانية
bathymetry_vis = {
    "min": -4000,
    "max": 0,
    "palette": ["#000011", "#001144", "#0033aa", "#aaeeff"],
}
Map.addLayer(bathymetry, bathymetry_vis, "أعماق المياه (GEBCO)", True, 0.4)

# إضافة مؤشر المراقبة المختار
if indicator == "تركيز الكلوروفيل (Chlorophyll-a)":
    chl_image = modis.select("chlor_a").clip(oman_coasts)
    # تدرج ألوان: الأزرق (سليم)، الأخضر (متوسط)، الأحمر (كثافة طحالب عالية - خطر مد أحمر)
    chl_vis = {
        "min": 0.01,
        "max": 15,
        "palette": ["blue", "cyan", "green", "yellow", "red"],
    }
    Map.addLayer(chl_image, chl_vis, f"تركيز الكلوروفيل ({month}-{year})")
    st.sidebar.success(f"📊 يعرض الآن: الكلوروفيل لشهر {month} لعام {year}")
else:
    sst_image = modis.select("sst").clip(oman_coasts)
    sst_vis = {
        "min": 18,
        "max": 34,
        "palette": ["blue", "green", "yellow", "orange", "red"],
    }
    Map.addLayer(sst_image, sst_vis, f"درجة حرارة السطح ({month}-{year})")
    st.sidebar.success(f"🌡️ يعرض الآن: درجة حرارة البحر لشهر {month} لعام {year}")

# 7. عرض الخريطة داخل الداشبورد
Map.to_streamlit(height=650)

# 8. أسفل الصفحة معلومات توضيحية
st.markdown("---")
st.caption(
    "💡 هذا النظام يعمل بصفر تكلفة استضافة ويقوم بتحديث بياناته تلقائياً فور صدورها من وكالات الفضاء العالمية."
)