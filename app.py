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
            
            # محاولة قراءة المفتاح الخاص بأمان ومعالجة الرموز المخفية
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

# اختيار المؤشر البيئي
indicator = st.sidebar.selectbox(
    "إختر المؤشر البيئي للمراقبة:",
    ["تركيز الكلوروفيل (Chlorophyll-a)", "درجة حرارة سطح البحر (SST)"]
)

# اختيار السنة والشهر
current_year = datetime.now().year
year = st.sidebar.slider("اختر السنة:", 2000, current_year, 2021) # تم ضبط القيمة الافتراضية على 2021 لضمان تدفق البيانات فوراً
month = st.sidebar.slider("اختر الشهر:", 1, 12, 4)

# تنسيق الشهر والسنة بشكل متوافق مع قاعدة البيانات
month_str = str(month).zfill(2)
start_date = f"{year}-{month_str}-01"
end_date = f"{year}-{month_str}-28"

if gee_connected:
    # تحديد النطاق الجغرافي لسواحل سلطنة عمان
    oman_coasts = ee.Geometry.Rectangle([52.0, 16.0, 60.0, 27.0])
    
    # بناء الخريطة التفاعلية باستخدام Folium المدمج لضمان الاستقرار التام في العرض
    Map = geemap.Map(center=[21.0, 57.0], zoom=6, lite_mode=False)
    
    # 1. جلب بيانات الكلوروفيل من قمر MODIS
    try:
        chl_dataset = (ee.ImageCollection('NASA/OCEANDATA/MODIS-Aqua/L3SMI')
                       .filterDate(start_date, end_date)
                       .filterBounds(oman_coasts)
                       .select('chlor_a'))
        
        if chl_dataset.size().getInfo() > 0:
            chl_image = chl_dataset.median().clip(oman_coasts)
            chl_vis = {'min': 0.01, 'max': 20.0, 'palette': ['blue', 'cyan', 'green', 'yellow', 'red']}
        else:
            chl_image
