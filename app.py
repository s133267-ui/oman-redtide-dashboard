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
        val_range = st.slider("مدى تركيز الكلوروفيل المستهدف (mg/m³):", 0.0, 30.0, (0.3, 15.0), step=0.1)
    else:
        val_range = st.slider("مدى درجات الحرارة المستهدفة (°C):", 15.0, 38.0, (20.0, 32.0), step=0.5)

    classes_num = st.slider("عدد فئات التصنيف (Classes):", 3, 7, 5)
    palette_style = st.selectbox("نمط التدرج اللوني لليجند:", ["قوس قزح التفاعلي", "تدرج بيئي مخصص", "أحمر تنبيهي"])
    sync_charts = st.checkbox("🔄 ربط تفاعلي: تحديث الشارت ديناميكيًا حسب زووم الخريطة", value=False)

if gee_connected:
    # 4. مضلعات سواحل سلطنة عُمان
    poly_gulf_of_oman = ee.Geometry.Polygon([[
        [56.3, 26.4], [56.9, 26.0], [59.7, 22.5], [59.4, 22.4], [56.5, 23.6], [56.3, 26.4]
    ]])
    poly_arabian_sea = ee.Geometry.Polygon([[
        [59.4, 22.4], [59.7, 22.5], [58.1, 19.1], [53.1, 16.1], [52.1, 16.6], [54.1, 17.6], [59.4, 22.4]
    ]])
    
    if region_choice == "سواحل بحر عُمان فقط":
        target_aoi = poly_gulf_of_oman
    elif region_choice == "سواحل بحر العرب فقط":
        target_aoi = poly_arabian_sea
    else:
        target_aoi = ee.Geometry.MultiPolygon([poly_gulf_of_oman, poly_arabian_sea])

    image_to_show = None
    start_date = f"{selected_year}-{month_str}-01"
    end_date = f"{selected_year}-{month_str}-28"

    # 5. معالجة وتصفية الصور لكلا القمرين لضمان إخراج دقيق
    try:
        if satellite_source.startswith("MODIS"):
            collection_name = 'NASA/OCEANDATA/MODIS-Aqua/L3SMI'
            band_name = 'chlor_a' if indicator == "تركيز الكلوروفيل (Chlorophyll-a)" else 'sst'
            dataset = ee.ImageCollection(collection_name).filterDate(start_date, end_date).filterBounds(target_aoi).select(band_name)
            if dataset.size().getInfo() > 0:
                raw_img = dataset.median().clip(target_aoi)
                image_to_show = raw_img.updateMask(raw_img.gte(val_range[0]).And(raw_img.lte(val_range[1])))
        else:
            # معالجة القمر الآسيوي GCOM-C
            if indicator == "تركيز الكلوروفيل (Chlorophyll-a)":
                dataset = ee.ImageCollection('JAXA/GCOM-C/L3/OCEAN/CHLA/V3').filterDate(start_date, end_date).filterBounds(target_aoi).select('CHLA_AVE')
                if dataset.size().getInfo() > 0:
                    raw_img = dataset.median().clip(target_aoi).multiply(0.001)
                    image_to_show = raw_img.updateMask(raw_img.gte(val_range[0]).And(raw_img.lte(val_range[1])))
            else:
                dataset = ee.ImageCollection('JAXA/GCOM-C/L3/OCEAN/SST/V3').filterDate(start_date, end_date).filterBounds(target_aoi).select('SST_AVE')
                if dataset.size().getInfo() > 0:
                    raw_img = dataset.median().clip(target_aoi).multiply(0.02).subtract(273.15)
                    image_to_show = raw_img.updateMask(raw_img.gte(val_range[0]).And(raw_img.lte(val_range[1])))
    except Exception as e:
        pass

    # إعداد لوحة الألوان المخصصة
    palette_dict = {
        "قوس قزح التفاعلي": ['blue', 'cyan', 'green', 'yellow', 'red'],
        "تدرج بيئي مخصص": ['#0044ff', '#00ffcc', '#ffff00', '#ff0000'],
        "أحمر تنبيهي": ['#ffebee', '#ffb74d', '#b71c1c']
    }
    selected_palette = palette_dict[palette_style][:classes_num]
    vis_params = {'min': val_range[0], 'max': val_range[1], 'palette': selected_palette}

    with col_main:
        # صياغة الـ Key الديناميكي لضمان التحديث التفاعلي اللحظي فور تغيير الفلاتر
        map_key = f"map_render_{satellite_source}_{indicator}_{region_choice}_{selected_year}_{selected_month}_{val_range[0]}_{val_range[1]}_{palette_style}_{classes_num}"
        
        m = folium.Map(location=[21.0, 57.0], zoom_start=6, tiles="OpenStreetMap")
        folium.TileLayer(
            tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
            attr='Esri World Imagery', name='خلفية القمر الصناعي (
