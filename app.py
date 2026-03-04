import streamlit as st
import requests
import pandas as pd
import html
from io import BytesIO
import datetime
import docx
from docx import Document

# Configuración inicial de la página
st.set_page_config(page_title="BIS Central Bank Speeches", layout="wide")

st.title("BIS Central Bank Speeches Extractor")
st.markdown("Extrae y descarga los discursos de los bancos centrales desde el BIS.")

# 1. Filtros en la pantalla principal
st.subheader("1. Selecciona el rango de fechas")

hoy = datetime.date.today()
hace_un_mes = hoy - datetime.timedelta(days=30)

col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("Fecha de inicio", hace_un_mes)
with col2:
    end_date = st.date_input("Fecha de fin", hoy)

buscar = st.button("🔍 Buscar Discursos", type="primary")

# 2. Función para descargar los datos del BIS
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

# Función auxiliar mágica para inyectar hipervínculos en Word
def add_hyperlink(paragraph, text, url):
    # Obtener acceso a las relaciones del documento
    part = paragraph.part
    r_id = part.relate_to(url, docx.opc.constants.RELATIONSHIP_TYPE.HYPERLINK, is_external=True)

    # Crear la etiqueta de hipervínculo en XML
    hyperlink = docx.oxml.shared.OxmlElement('w:hyperlink')
    hyperlink.set(docx.oxml.shared.qn('r:id'), r_id)

    # Crear la corrida de texto (Run)
    new_run = docx.oxml.shared.OxmlElement('w:r')
    rPr = docx.oxml.shared.OxmlElement('w:rPr')

    # Darle color azul al enlace
    c = docx.oxml.shared.OxmlElement('w:color')
    c.set(docx.oxml.shared.qn('w:val'), '0000EE')
    rPr.append(c)

    # Añadir el subrayado
    u = docx.oxml.shared.OxmlElement('w:u')
    u.set(docx.oxml.shared.qn('w:val'), 'single')
    rPr.append(u)

    # Añadir el texto
    t = docx.oxml.shared.OxmlElement('w:t')
    t.text = text
    new_run.append(rPr)
    new_run.append(t)
    
    # Unir todo al párrafo
    hyperlink.append(new_run)
    paragraph._p.append(hyperlink)
    return hyperlink

# 3. Función para generar el documento de Word CON enlaces
def generate_word(dataframe):
    doc = Document()
    doc.add_heading('BIS Central Bank Speeches', 0)

    # Crear una tabla con solo 2 columnas (Fecha y Título)
    table = doc.add_table(rows=1, cols=2)
    table.style = 'Table Grid'
    
    # Escribir los encabezados
    hdr_cells = table.rows[0].cells
    hdr_cells[0].text = 'Date'
    hdr_cells[1].text = 'Title'

    # Llenar la tabla
    for index, row in dataframe.iterrows():
        row_cells = table.add_row().cells
        
        # Columna 1: Fecha
        if pd.api.types.is_datetime64_any_dtype(row['Date']):
            date_str = row['Date'].strftime('%Y-%m-%d')
        else:
            date_str = str(row['Date'])
        row_cells[0].text = date_str
        
        # Columna 2: Título como Hipervínculo
        # Borramos cualquier texto por defecto de la celda
        p = row_cells[1].paragraphs[0]
        # Inyectamos el texto del título y su URL
        add_hyperlink(p, str(row['Title']), str(row['Link']))

    output = BytesIO()
    doc.save(output)
    output.seek(0)
    return output

st.markdown("---")

# 4. Lógica de ejecución de la app
if buscar or "df_filtrado" in st.session_state:
    
    df = load_data()
    
    mask = (df["Date"].dt.date >= start_date) & (df["Date"].dt.date <= end_date)
    filtered_df = df[mask]
    
    st.session_state["df_filtrado"] = filtered_df

    st.subheader("2. Resultados de la búsqueda")
    
    if len(filtered_df) > 0:
        st.success(f"Se encontraron **{len(filtered_df)}** discursos entre {start_date} y {end_date}.")
        
        filtered_df_display = filtered_df.copy()
        filtered_df_display["Date"] = filtered_df_display["Date"].dt.strftime('%Y-%m-%d')
        filtered_df_display["Title"] = filtered_df_display.apply(
            lambda x: f"[{x['Title']}]({x['Link']})", axis=1
        )

        st.markdown(
            filtered_df_display[["Date", "Title"]].to_markdown(index=False),
            unsafe_allow_html=True
        )

        st.markdown("---")
        st.subheader("3. Exportar Datos")
        
        word_file = generate_word(filtered_df)
        st.download_button(
            label="📄 Descargar en Word",
            data=word_file,
            file_name=f"bis_speeches_{start_date}_to_{end_date}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
    else:
        st.warning("No hay discursos del BIS en el rango de fechas seleccionado. Intenta ampliar tu búsqueda.")
else:
    st.info("👆 Selecciona las fechas arriba y presiona **'Buscar Discursos'**.")
