import streamlit as st
import ee
import json
from datetime import datetime
import folium
from folium.plugins import Fullscreen, MeasureControl
from streamlit_folium import st_folium
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 1. إعداد الواجهة وثيم المنصة المحترف
st.set_page_config(layout="wide", page_title="نظام مراقبة المد الأحمر العماني")

st.markdown("""
    <div style='background-color: #008080; padding: 25px; border-radius: 12px; margin-bottom: 25px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);'>
        <h1 style='text-align: center; color: white; margin: 0; font-family: sans-serif; font-size: 26px;'>🇴🇲 المنصة الذكية المتقدمة لمراقبة المد الأحمر بسواحل سلطنة عُمان</h1>
        <p style='text-align: center; color: #e0f2f1; margin: 8px 0 0 0; font-size: 15px;'>تحليل مكاني وزمني متكامل باستخدام تقنيات الاستشعار عن بُعد وجوجل إيرث إنجين</p>
    </div>
""", unsafe_allow_html=True)

# 2. دالة الاتصال الآمن بـ Google Earth Engine
@st.cache_resource
def authenticate_gee():
    try:
        if "GEE_KEYS" in st.secrets:
            json_keys = json.loads(st.secrets["GEE_KEYS"])
            if isinstance(json_keys, str):
                json_keys = json.loads(json_keys)
            private_key = json_keys.get("private_key", "")
            if "\\n" in private_key:
                json_keys["private_key"] = private_key.replace("\\n", "\n")
            credentials = ee.ServiceAccountCredentials(json_keys["client_email"], key_data=json.dumps(json_keys))
            ee.Initialize(credentials)
            return True
        else:
            st.error("❌ لم يتم العثور على المتغير GEE_KEYS!")
            return False
    except Exception as e:
        st.error(f"❌ خطأ في الاتصال بـ Google Earth Engine: {str(e)}")
        return False

gee_connected = authenticate_gee()

# 3. اللوحة الجانبية اليسرى (Sidebar) - الفلاتر الأساسية لآدم
st.sidebar.markdown("""
    <div style='background-color: #ffffff; padding: 12px; border-radius: 8px; border: 2px solid #008080; text-align: center; margin-bottom: 15px;'>
        <h4 style='color: #008080; margin: 0 0 3px 0;'>إعداد الطالب الباحث:</h4>
        <h3 style='color: #333; margin: 0 0 5px 0; font-size: 18px;'>آدم العبري</h3>
        <p style='font-size: 12px; color: #666; margin: 0; font-weight: bold;'>تخصص: نظم المعلومات الجغرافية والاستشعار عن بُعد</p>
    </div>
""", unsafe_allow_html=True)

st.sidebar.header("⚙️ إعدادات الفلترة والأقمار")

satellite_source = st.sidebar.selectbox(
    "إختر القمر الصناعي المورد للبيانات:",
    ["MODIS Aqua (ناسا - نطاق واسع تاريخي)", "GCOM-C SGLI (الوكالة الآسيوية - بديل سنتينل المتطور)"]
)

indicator = st.sidebar.selectbox(
    "إختر المؤشر البيئي للمراقبة:",
    ["تركيز الكلوروفيل (Chlorophyll-a)", "درجة حرارة سطح البحر (SST)"]
)

region_choice = st.sidebar.selectbox(
    "نطاق الدراسة المستهدف:",
    ["كامل السواحل العمانية", "سواحل بحر عُمان فقط", "سواحل بحر العرب فقط"]
)

st.sidebar.subheader("📅 الفلاتر الزمنية")
year_mode = st.sidebar.selectbox("طريقة المقارنة بالشارت:", ["سنة واحدة (أشهر متعاقبة)", "مقارنة سنوات متعددة لنفس الشهر"])

current_year = datetime.now().year

if year_mode == "سنة واحدة (أشهر متعاقبة)":
    selected_year = st.sidebar.slider("اختر السنة المعروضة:", 2018, current_year, 2024)
    selected_month = st.sidebar.slider("اختر الشهر المعروض:", 1, 12, 4)
    start_year, end_year = selected_year, selected_year
else:
    selected_month = st.sidebar.slider("اختر الشهر المستهدف (مثلاً 7):", 1, 12, 7)
    start_year, end_year = st.sidebar.slider("نطاق السنوات المقارنة:", 2018, current_year, (2020, 2026))
    selected_year = start_year

month_str = str(selected_month).zfill(2)

# الجانب الأيمن الرئيسي من الواجهة (أدوات التحكم بالليجند)
col_main, col_tools = st.columns([3, 1])

with col_tools:
    st.markdown("### 🎨 تصنيف الخريطة والمفتاح")
    
    if indicator == "تركيز الكلوروفيل (Chlorophyll-a)":
        val_range = st
