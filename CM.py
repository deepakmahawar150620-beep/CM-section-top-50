import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium
import os

st.set_page_config(layout="wide")

st.title("🛢️ SCC Risk Assessment Tool")

# =========================
# FILE SELECTION OPTION
# =========================
st.sidebar.header("📂 Data Source")

file_option = st.sidebar.radio(
    "Select Data Input Method:",
    ["Use Default File (CM_Data1.xlsx)", "Upload New File"]
)

# =========================
# LOAD DATA
# =========================
df = None

if file_option == "Use Default File (CM_Data1.xlsx)":
    file_path = "CM_Data1.xlsx"

    if os.path.exists(file_path):
        df = pd.read_excel(file_path, engine="openpyxl")
        st.success("✅ Loaded default file: CM_Data1.xlsx")
    else:
        st.error("❌ Default file not found. Please upload manually.")

elif file_option == "Upload New File":
    uploaded_file = st.file_uploader("📤 Upload Excel File", type=["xlsx"])

    if uploaded_file is not None:
        df = pd.read_excel(uploaded_file, engine="openpyxl")
        st.success("✅ File uploaded successfully")

# =========================
# PROCESS DATA
# =========================
if df is not None:

    df.columns = df.columns.str.strip()

    st.subheader("📄 Data Preview")
    st.dataframe(df.head())

    # =========================
    # CLEANING
    # =========================
    numeric_cols = [
        'OFF PSP (VE V)',
        'Soil Resistivity (Ω-cm)',
        'Distance from Pump(KM)',
        'Operating Pr.',
        'Remaining Thickness(mm)',
        'Hoop stress% of SMYS',
        'Pipe Age',
        'Temperature',
        'Stationing (m)'
    ]

    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    if 'Hoop stress% of SMYS' in df.columns:
        if df['Hoop stress% of SMYS'].max() < 10:
            df['Hoop stress% of SMYS'] *= 100

    df.fillna(method='ffill', inplace=True)

    # =========================
    # SCC SCORING
    # =========================
    df['CP Score'] = np.where(
        (df['OFF PSP (VE V)'] >= 0.85) & (df['OFF PSP (VE V)'] <= 1.12), 1, 10
    )

    df['Stress Score'] = np.where(
        df['Hoop stress% of SMYS'] < 60, 1, 10
    )

    df['Temp Score'] = np.where(
        df['Temperature'] < 40, 1, 10
    )

    # ✅ Your logic (<30 = 10, >30 = 1)
    df['Distance Score'] = np.where(
        df['Distance from Pump(KM)'] < 30, 10, 1
    )

    df['Resistivity Score'] = np.select(
        [
            df['Soil Resistivity (Ω-cm)'] <= 200,
            (df['Soil Resistivity (Ω-cm)'] > 200) & (df['Soil Resistivity (Ω-cm)'] <= 500),
            df['Soil Resistivity (Ω-cm)'] > 500
        ],
        [10, 5, 1]
    )

    df['Age Score'] = np.where(
        df['Pipe Age'] < 10, 1, 10
    )

    df['Total SCC Score'] = (
        df['CP Score'] +
        df['Stress Score'] +
        df['Temp Score'] +
        df['Distance Score'] +
        df['Resistivity Score'] +
        df['Age Score']
    )

    # =========================
    # TOP 50
    # =========================
    df_sorted = df.sort_values(
        by=['Total SCC Score', 'Hoop stress% of SMYS', 'Distance from Pump(KM)'],
        ascending=[False, False, False]
    )

    top50 = df_sorted.head(50)

    st.subheader("🔥 Top 50 SCC Risk Locations")
    st.dataframe(top50[['Stationing (m)', 'Total SCC Score',
                        'Hoop stress% of SMYS', 'Distance from Pump(KM)']])

    # =========================
    # GRAPH
    # =========================
    st.subheader("📊 Graph")

    plot_col = st.selectbox(
        "Select Parameter",
        [
            'Hoop stress% of SMYS',
            'Temperature',
            'Distance from Pump(KM)',
            'Soil Resistivity (Ω-cm)',
            'OFF PSP (VE V)'
        ]
    )

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=df['Stationing (m)'],
        y=df[plot_col],
        mode='lines',
        name=plot_col
    ))

    if plot_col == 'Hoop stress% of SMYS':
        fig.add_hline(y=60, line_dash="dash")

    fig.update_layout(
        title=f"{plot_col} vs Stationing",
        xaxis_title="Stationing (m)",
        yaxis_title=plot_col,
        template='plotly_white',
        height=500
    )

    st.plotly_chart(fig, use_container_width=True)

    # =========================
    # DOWNLOAD
    # =========================
    st.subheader("⬇️ Download")

    st.download_button("Download Full Data", df.to_csv(index=False), "scc_full.csv")
    st.download_button("Download Top 50", top50.to_csv(index=False), "scc_top50.csv")

    # =========================
    # MAP
    # =========================
    if {'LATITUDE', 'LONGITUDE'}.issubset(df.columns):

        st.subheader("🗺️ Pipeline Map")

        m = folium.Map(
            location=[df['LATITUDE'].mean(), df['LONGITUDE'].mean()],
            zoom_start=8
        )

        coords = df[['LATITUDE', 'LONGITUDE']].dropna().values.tolist()

        if len(coords) > 1:
            folium.PolyLine(coords, color="blue").add_to(m)

        cluster = MarkerCluster().add_to(m)

        for _, row in top50.iterrows():
            if pd.notna(row['LATITUDE']) and pd.notna(row['LONGITUDE']):
                folium.Marker(
                    [row['LATITUDE'], row['LONGITUDE']],
                    popup=f"Sta: {row['Stationing (m)']}, Score: {row['Total SCC Score']}",
                    icon=folium.Icon(color='red')
                ).add_to(cluster)

        st_folium(m, width=1000, height=500)

    else:
        st.warning("⚠️ LATITUDE & LONGITUDE not found")
