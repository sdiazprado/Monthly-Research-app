import streamlit as st
import requests
import pandas as pd
import html
from io import BytesIO
import datetime

st.set_page_config(page_title="BIS Central Bank Speeches", layout="wide")

st.title("BIS Central Bank Speeches Extractor")

# 1. Configurar barra lateral y pedir fechas primero
st.sidebar.header("Filtros de Búsqueda")

# Fechas por defecto: del último mes al día de hoy
hoy = datetime.date.today()
hace_un_mes = hoy - datetime.timedelta(days=30)

start_date = st.sidebar.date_input("Fecha de inicio", hace_un_mes)
end_date = st.sidebar.date_input("Fecha de fin", hoy)

# Botón para iniciar la búsqueda
buscar = st.sidebar.button("Buscar Discursos")

# 2. Función de carga de datos (Mantenemos el caché para no saturar al BIS si buscas varias veces)
@st.cache_data(show_spinner="Descargando y procesando datos del BIS...")
def load_data():
    url = "https://www.bis.org/api/document_lists/cbspeeches.json"
    response = requests.get(url)
    response.raise_for_status()
    data = response.json()

    speeches_dict = data.get("list", {})
    rows = []

    for path, speech in speeches_dict.items():
        title = html.unescape(speech.get("short_title", ""))
        date_str = speech.get("publication_start_date", "")

        if not path.endswith(".htm"):
            link = "https://www.bis.org" + path + ".htm"
        else:
            link = "https://www.bis.org" + path

        rows.append({
            "Date": date_str,
            "Title": title,
            "Link": link
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        df["Date"] = pd.to_datetime(df["Date"])
        df = df.sort_values("Date", ascending=False)
    
    return df

# Función para generar el Excel
def generate_excel(dataframe):
    output = BytesIO()
    dataframe_to_export = dataframe.copy()
    
    dataframe_to_export["Title"] = dataframe_to_export.apply(
        lambda x: f'=HYPERLINK("{x["Link"]}","{x["Title"]}")',
        axis=1
    )
    
    dataframe_to_export = dataframe_to_export.drop(columns=["Link"])
    
    # Especificamos el motor openpyxl explícitamente
    dataframe_to_export.to_excel(output, index=False, engine='openpyxl')
    output.seek(0)
    return output

# 3. Lógica principal: Solo se ejecuta si se presionó "Buscar" o si ya hay una búsqueda activa
if buscar or "df_filtrado" in st.session_state:
    
    # Cargar todos los datos en memoria (rápido gracias al caché)
    df = load_data()
    
    # Filtrar el dataframe con las fechas seleccionadas
    mask = (df["Date"].dt.date >= start_date) & (df["Date"].dt.date <= end_date)
    filtered_df = df[mask]
    
    # Guardar en session_state para que el botón de descarga no reinicie la app
    st.session_state["df_filtrado"] = filtered_df

    st.subheader("Resultados de la búsqueda")
    st.write(f"Se encontraron **{len(filtered_df)}** discursos entre {start_date} y {end_date}.")

    if len(filtered_df) > 0:
        # Preparar tabla para mostrar con links
        filtered_df_display = filtered_df.copy()
        # Formatear la fecha para que se vea más limpia en la pantalla
        filtered_df_display["Date"] = filtered_df_display["Date"].dt.strftime('%Y-%m-%d')
        filtered_df_display["Title"] = filtered_df_display.apply(
            lambda x: f"[{x['Title']}]({x['Link']})", axis=1
        )

        # Mostrar tabla
        st.markdown(
            filtered_df_display[["Date", "Title"]].to_markdown(index=False),
            unsafe_allow_html=True
        )

        # Botón para descargar Excel
        excel_file = generate_excel(filtered_df)
        st.download_button(
            label="📥 Descargar Excel",
            data=excel_file,
            file_name=f"bis_speeches_{start_date}_to_{end_date}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.warning("No hay discursos del BIS en el rango de fechas seleccionado. Intenta ampliar tu búsqueda.")
else:
    # Mensaje inicial cuando la app carga por primera vez
    st.info("👈 Selecciona un rango de fechas en el menú lateral y presiona **'Buscar Discursos'** para comenzar.")
