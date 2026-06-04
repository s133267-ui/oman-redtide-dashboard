import streamlit as st
import ee
import geemap
import json
from datetime import datetime

# إعداد واجهة المستخدم والعناوين
st.set_page_config(layout="wide", page_title="نظام مراقبة المد الأحمر")
st.markdown("<h1 style='text-align: center; color: #008080;'>🛸 نظام مراقبة المد الأحمر المؤتمت لسواحل سلطنة عُمان</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #666;'>تحليل مستمر لبيانات الكلوروفيل ودرجة حرارة سطح البحر (SST)</p>", unsafe_allow_html=True)

# دالة الاتصال بجوجل إيرث إنجين باستخدام المفاتيح السرية
@st.cache_resource
def authenticate_gee():
    try:
        if "GEE_KEYS" in st.secrets:
            json_keys = json.loads(st.secrets["GEE_KEYS"])
            if isinstance(json_keys, str):
                json_keys = json.loads(json_keys)
            
            # معالجة الرموز المخفية للمفتاح الخاص
            private_key = json_keys.get("private_key", "")
            if "\\n" in private_key:
                json_keys["private_key"] = private_key.replace("\\n", "\n")
                
            credentials = ee.ServiceAccountCredentials(json_keys["client_email"], key_data=json.dumps(json_keys))
            ee.Initialize(credentials)
            return True
        else:
            st.error("❌ لم يتم العثور على المتغير GEE_KEYS في إعدادات Secrets!")
            return False
    except Exception as e:
        st.error(f"❌ خطأ في الاتصال بسيرفر Google Earth Engine: {str(e)}")
        return False

# تشغيل الاتصال
gee_connected = authenticate_gee()

# لوحة التحكم الجانبية (Sidebar)
st.sidebar.header("🗺️ لوحة الفلترة والتحكم")

indicator = st.sidebar.selectbox(
    "إختر المؤشر البيئي للمراقبة:",
    ["تركيز الكلوروفيل (Chlorophyll-a)", "درجة حرارة سطح البحر (SST)"]
)

current_year = datetime.now().year
year = st.sidebar.slider("اختر السنة:", 2000, current_year, 2021)
month = st.sidebar.slider("اختر الشهر:", 1, 12, 4)

month_str = str(month).zfill(2)
start_date = f"{year}-{month_str}-01"
end_date = f"{year}-{month_str}-28"

if gee_connected:
    # تحديد النطاق الجغرافي لسواحل سلطنة عمان
    oman_coasts = ee.Geometry.Rectangle([52.0, 16.0, 60.0, 27.0])
    
    # إنشاء الخريطة باستخدام المكون التفاعلي الأساسي والمستقر
    Map = geemap.Map(center=[21.0, 57.0], zoom=6)
    
    chl_image = None
    sst_image = None

    # 1. جلب بيانات الكلوروفيل
    try:
        chl_dataset = (ee.ImageCollection('NASA/OCEANDATA/MODIS-Aqua/L3SMI')
                       .filterDate(start_date, end_date)
                       .filterBounds(oman_coasts)
                       .select('chlor_a'))
        if chl_dataset.size().getInfo() > 0:
            chl_image = chl_dataset.median().clip(oman_coasts)
    except Exception:
        pass

    # 2. جلب بيانات درجة حرارة سطح البحر
    try:
        sst_dataset = (ee.ImageCollection('NASA/OCEANDATA/MODIS-Aqua/L3SMI')
                       .filterDate(start_date, end_date)
                       .filterBounds(oman_coasts)
                       .select('sst'))
        if sst_dataset.size().getInfo() > 0:
            sst_image = sst_dataset.median().clip(oman_coasts)
    except Exception:
        pass

    # عرض الطبقات البيئية فوق الخريطة
    if indicator == "تركيز الكلوروفيل (Chlorophyll-a)":
        if chl_image is not None:
            chl_vis = {'min': 0.01, 'max': 20.0, 'palette': ['blue', 'cyan', 'green', 'yellow', 'red']}
            Map.addLayer(chl_image, chl_vis, f"Chlorophyll-a ({month_str}-{year})")
            st.success(f"✅ تم عرض بيانات الكلوروفيل لشهر {month_str} عام {year} بنجاح.")
        else:
            st.warning(f"⚠️ بيانات الكلوروفيل غير متوفرة لشهر {month_str} عام {year}.")
            
    elif indicator == "درجة حرارة سطح البحر (SST)":
        if sst_image is not None:
            sst_vis = {'min': 15.0, 'max': 35.0, 'palette': ['blue', 'purple', 'green', 'yellow', 'red']}
            Map.addLayer(sst_image, sst_vis, f"SST ({month_str}-{year})")
            st.success(f"✅ تم عرض بيانات حرارة السطح (SST) لشهر {month_str} عام {year} بنجاح.")
        else:
            st.warning(f"⚠️ بيانات درجة حرارة سطح البحر غير متوفرة لشهر {month_str} عام {year}.")

    # التعديل الذهبي: عرض الخريطة بالدالة الأصلية المدعومة بملء الشاشة ومساحة عمودية واضحة لمنع الاختفاء
    Map.to_streamlit(height=650)

else:
    st.info("ℹ️ يرجى إعداد الصلاحيات وربط المفتاح السري بشكل صحيح.")
