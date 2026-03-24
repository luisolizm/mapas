import streamlit as st
from streamlit_folium import st_folium
import folium
import json
import pandas as pd
import numpy as np
from folium import GeoJsonTooltip
import branca.element
import gdown
import os

# ── Configuración de la página ──
st.set_page_config(
    page_title="Mapa Municipios México",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("Mapa Interactivo de Municipios (datos positivos en verde)")
st.markdown("Municipios en **verde** tienen al menos un valor > 0. Clic para ver detalles con pestañas.")

# ── Carga y procesamiento de datos ──
@st.cache_data
def cargar_y_procesar():
    geojson_path = "georef-mexico-municipality.geojson"
    csv_path = "datos_nacional.csv"

    # Descargar GeoJSON desde Google Drive si no existe localmente
    if not os.path.exists(geojson_path):
        st.info("Descargando archivo GeoJSON grande desde Google Drive... (puede tardar 1-5 minutos la primera vez)")
        url = "https://drive.google.com/uc?id=1u3XLifgF3N257-8tJYvtQPbUxlchdzwU"
        gdown.download(url, geojson_path, quiet=False)
        st.success("GeoJSON descargado correctamente!")

    # Cargar GeoJSON
    with open(geojson_path, encoding='utf-8') as f:
        geojson_full = json.load(f)

    # Cargar y limpiar CSV (asumiendo que está en el repo)
    df = pd.read_csv(csv_path, encoding='latin-1')

    df['sta_code'] = df['sta_code'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip().str.zfill(2)
    df['mun_code'] = df['mun_code'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip().str.zfill(5)
    df['clave_unica'] = df['sta_code'] + df['mun_code'].str[-3:]

    df = df.drop_duplicates(subset='clave_unica', keep='first')

    columnas_datos = [col for col in df.columns if col not in ['sta_name','sta_code','mun_name','mun_code','clave_unica']]
    for col in columnas_datos:
        df[col] = pd.to_numeric(
            df[col].astype(str).str.replace(',', '').str.replace(r'[^\d\.\-]', '', regex=True).str.strip(),
            errors='coerce'
        )

    data_dict = df.set_index('clave_unica')[columnas_datos].to_dict('index')

    # Preparar GeoJSON para el mapa
    geojson_para_mapa = {'type': 'FeatureCollection', 'features': []}
    for feature in geojson_full['features']:
        props = feature['properties'].copy()

        cve_ent_raw = props.get('cve_ent') or props.get('CVE_ENT') or props.get('state_code') or props.get('sta_code') or '0'
        cve_mun_raw = props.get('cve_mun') or props.get('CVE_MUN') or props.get('mun_code') or '0'

        cve_ent = str(cve_ent_raw).replace('.0', '').strip().zfill(2)
        cve_mun = str(cve_mun_raw).replace('.0', '').strip().zfill(5)

        clave = cve_ent + cve_mun[-3:]

        if clave in data_dict:
            props.update(data_dict[clave])

        geojson_para_mapa['features'].append({
            'type': 'Feature',
            'properties': props,
            'geometry': feature['geometry']
        })

    return geojson_para_mapa

geojson_para_mapa = cargar_y_procesar()

# ── Funciones ──
PALABRAS_INSUMOS = ['tractor', 'arados', 'cultivadora', 'desmalezadoras', 'aspersión', 'bombeo', 'fertilizadora', 'maquinarias', 'rastras', 'remolque', 'sembradoras', 'sierra', 'trilladoras', 'motosierra']
PALABRAS_PRODUCTORES = ['productores de']
PALABRAS_SUPERFICIE  = ['superficie sembrada de']
PALABRAS_PRODUCCION  = ['producción de']

ignorar = {
    'mun_name', 'sta_name', 'sta_code', 'mun_code', 'clave_unica',
    'state_code', 'type', 'id', 'geo_point_2d', 'geometry', 'name',
    'state_name', 'cve_ent', 'year'
}

def tiene_datos_relevantes(props):
    for k, v in props.items():
        if k in ignorar:
            continue
        if pd.isna(v) or v is None:
            continue
        if isinstance(v, (int, float)) and v > 0:
            return True
        elif isinstance(v, str):
            try:
                num = float(v.strip().replace(',', ''))
                if num > 0:
                    return True
            except:
                pass
    return False

def decidir_color(props):
    return '#28a745' if tiene_datos_relevantes(props) else '#dc3545'

def decidir_borde(props):
    return '#1e7e34' if tiene_datos_relevantes(props) else '#a71d2a'

# ── Popup con pestañas Bootstrap ──
def crear_popup_html(props):
    mun = props.get('mun_name') or props.get('name') or 'Municipio desconocido'
    edo = props.get('sta_name') or props.get('state_name') or 'Estado desconocido'

    html = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet" integrity="sha384-QWTKZyjpPEjISv5WaRU9OFeRpok6YctnYmDr5pNlyT2bRjXh0JMhjY6hW+ALEwIH" crossorigin="anonymous">
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js" integrity="sha384-YvpcrYf0tY3lHB60NNkmXc5s9fDVZLESaAA55NDzOxhy9GkcIdslK1eN7N6jIeHz" crossorigin="anonymous"></script>
        <style>
            body {{ font-family: Arial, sans-serif; padding: 10px; margin: 0; }}
            .tab-content {{ margin-top: 10px; }}
            table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
            th {{ background: #006400; color: white; padding: 8px; text-align: left; }}
            td {{ border: 1px solid #ddd; padding: 6px; }}
            h4 {{ text-align: center; color: #006400; margin-bottom: 15px; }}
        </style>
    </head>
    <body>
        <h4>{mun}<br><small>{edo}</small></h4>

        <ul class="nav nav-tabs mb-3" id="myTab" role="tablist">
            <li class="nav-item" role="presentation">
                <button class="nav-link active" id="insumos-tab" data-bs-toggle="tab" data-bs-target="#insumos" type="button" role="tab" aria-controls="insumos" aria-selected="true">Insumos</button>
            </li>
            <li class="nav-item" role="presentation">
                <button class="nav-link" id="productores-tab" data-bs-toggle="tab" data-bs-target="#productores" type="button" role="tab" aria-controls="productores" aria-selected="false">Productores</button>
            </li>
            <li class="nav-item" role="presentation">
                <button class="nav-link" id="superficie-tab" data-bs-toggle="tab" data-bs-target="#superficie" type="button" role="tab" aria-controls="superficie" aria-selected="false">Superficie (ha)</button>
            </li>
            <li class="nav-item" role="presentation">
                <button class="nav-link" id="produccion-tab" data-bs-toggle="tab" data-bs-target="#produccion" type="button" role="tab" aria-controls="produccion" aria-selected="false">Producción (ton)</button>
            </li>
        </ul>

        <div class="tab-content" id="myTabContent">
    """

    def agregar_tab(tab_id, palabras, titulo):
        nonlocal html
        active = "show active" if tab_id == "insumos" else ""
        html += f'<div class="tab-pane fade {active}" id="{tab_id}" role="tabpanel" aria-labelledby="{tab_id}-tab">'
        html += f'<table><thead><tr><th>{titulo}</th><th style="text-align:right;">Valor</th></tr></thead><tbody>'

        filas = 0
        for k, v in props.items():
            if any(p.lower() in k.lower() for p in palabras):
                if pd.isna(v) or v == 0:
                    continue
                valor = f"{v:,.1f}" if isinstance(v, (int, float)) else str(v)
                html += f'<tr><td>{k.replace("_"," ").title()}</td><td style="text-align:right;">{valor}</td></tr>'
                filas += 1

        if filas == 0:
            html += '<tr><td colspan="2" style="text-align:center; color:#777; padding:12px;">Sin datos relevantes</td></tr>'
        html += '</tbody></table></div>'

    agregar_tab("insumos", PALABRAS_INSUMOS, "Maquinaria / Equipos")
    agregar_tab("productores", PALABRAS_PRODUCTORES, "Productores")
    agregar_tab("superficie", PALABRAS_SUPERFICIE, "Superficie (ha)")
    agregar_tab("produccion", PALABRAS_PRODUCCION, "Producción (ton)")

    html += """
        </div>
    </body>
    </html>
    """
    return html

# ── Crear el mapa ──
@st.cache_resource
def crear_mapa():
    m = folium.Map(location=[23.6345, -102.5528], zoom_start=6, tiles='CartoDB positron')

    for feature in geojson_para_mapa['features']:
        props = feature['properties']
        single = {'type': 'FeatureCollection', 'features': [feature]}

        popup = None
        if tiene_datos_relevantes(props):
            try:
                html_content = crear_popup_html(props)
                iframe = branca.element.IFrame(html=html_content, width=650, height=550)
                popup = folium.Popup(iframe, max_width=700, parse_html=True)
            except Exception as e:
                popup = folium.Popup(f"Error al generar popup: {str(e)[:100]}", max_width=400)

        folium.GeoJson(
            single,
            style_function=lambda f: {
                'fillColor': decidir_color(f['properties']),
                'color': decidir_borde(f['properties']),
                'weight': 1,
                'fillOpacity': 0.7 if tiene_datos_relevantes(f['properties']) else 0.45
            },
            highlight_function=lambda f: {'weight': 3, 'color': '#3388ff'},
            popup=popup,
            tooltip=GeoJsonTooltip(
                fields=['mun_name', 'sta_name'],
                aliases=['Municipio:', 'Estado:'],
                sticky=True,
                style="background:#fff; border:1px solid #aaa; padding:6px;"
            )
        ).add_to(m)

    return m

m = crear_mapa()

# ── Mostrar mapa en Streamlit ──
st_folium(m, width=1200, height=700, use_container_width=True)

st.caption("Mapa con pestañas Bootstrap en popup | GeoJSON descargado desde Google Drive")