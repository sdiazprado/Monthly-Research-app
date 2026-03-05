import streamlit as st
import requests
import pandas as pd
import html
from io import BytesIO
import datetime
import docx
from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
from bs4 import BeautifulSoup
import calendar
import time
import re
from dateutil import parser

# ==========================================
# CONFIGURACIÓN INICIAL Y ESTILOS
# ==========================================
st.set_page_config(page_title="Boletín Mensual - Banxico", layout="wide")

st.markdown("""
    <style>
    div.stButton > button, div.stDownloadButton > button {
        background-color: #00205B !important;
        color: white !important;
        border: none !important;
    }
    div.stButton > button:hover, div.stDownloadButton > button:hover {
        background-color: #00153D !important;
        color: white !important;
    }
    span[data-baseweb="tag"] {
        background-color: #00205B !important;
        color: white !important;
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# FUNCIONES DE EXTRACCIÓN (BACKEND)
# ==========================================

@st.cache_data(show_spinner=False)
def load_data_bis():
    urls = [
        "https://www.bis.org/api/document_lists/cbspeeches.json",
        "https://www.bis.org/api/document_lists/bcbs_speeches.json",
        "https://www.bis.org/api/document_lists/mgmtspeeches.json"
    ]
    headers = {'User-Agent': 'Mozilla/5.0'}
    rows = []
    
    for url in urls:
        try:
            response = requests.get(url, headers=headers, timeout=10)
            data = response.json()
            for path, speech in data.get("list", {}).items():
                title = html.unescape(speech.get("short_title", ""))
                date_str = speech.get("publication_start_date", "")
                link = "https://www.bis.org" + path + (".htm" if not path.endswith(".htm") else "")
                rows.append({"Date": date_str, "Title": title, "Link": link, "Organismo": "BPI"})
        except:
            continue

    df = pd.DataFrame(rows).drop_duplicates(subset=['Link'])
    if not df.empty:
        df["Date"] = pd.to_datetime(df["Date"])
        df = df.sort_values("Date", ascending=False)
    return df

@st.cache_data(show_spinner=False)
def load_data_bbk(start_date_str, end_date_str):
    base_url = "https://www.bundesbank.de/action/en/730564/bbksearch"
    headers = {'User-Agent': 'Mozilla/5.0'}
    rows = []
    page = 0
    
    while True:
        params = {'sort': 'bbksortdate desc', 'dateFrom': start_date_str, 'dateTo': end_date_str, 'pageNumString': str(page)}
        try:
            response = requests.get(base_url, headers=headers, params=params, timeout=10)
        except:
            break 
            
        soup = BeautifulSoup(response.text, 'html.parser')
        items = soup.find_all('li', class_='resultlist__item')
        if not items: break 
            
        for item in items:
            fecha_tag = item.find('span', class_='metadata__date')
            fecha_str = fecha_tag.text.strip() if fecha_tag else ""
            
            author_tag = item.find('span', class_='metadata__authors')
            author_str = author_tag.text.strip() if author_tag else ""
            if author_str:
                author_str = re.sub(r'([a-z])([A-Z])', r'\1 \2', author_str)
            
            data_div = item.find('div', class_='teasable__data')
            link, titulo = "", ""
            if data_div and data_div.find('a'):
                a_tag = data_div.find('a')
                link = "https://www.bundesbank.de" + a_tag.get('href', '') if a_tag.get('href', '').startswith('/') else a_tag.get('href', '')
                if a_tag.find('span', class_='link__label'):
                    titulo = a_tag.find('span', class_='link__label').text.strip()
            
            if author_str and titulo: titulo = f"{author_str}: {titulo}"
            if fecha_str and titulo: rows.append({"Date": fecha_str, "Title": titulo, "Link": link, "Organismo": "BBk (Alemania)"})
                
        if len(items) < 10: break
        page += 1
        time.sleep(0.3) 
        
    df = pd.DataFrame(rows)
    if not df.empty:
        df["Date"] = pd.to_datetime(df["Date"], format='%d.%m.%Y', errors='coerce')
        df = df.sort_values("Date", ascending=False)
    return df

@st.cache_data(show_spinner=False)
def load_data_bde(start_date_str, end_date_str):
    base_url = "https://www.bde.es/wbe/es/noticias-eventos/actualidad-banco-espana/intervenciones-publicas/"
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    try: start_date = datetime.datetime.strptime(start_date_str, '%d.%m.%Y')
    except: start_date = datetime.datetime(2000, 1, 1)
        
    rows = []
    page = 1
    while True:
        try:
            response = requests.get(base_url, headers=headers, params={'page': page, 'role': ' ', 'sort': 'DESC', 'limit': 10}, timeout=10)
        except: break 
            
        soup = BeautifulSoup(response.text, 'html.parser')
        date_pattern = re.compile(r'\b(\d{2}/\d{2}/\d{4})\b')
        items = soup.find_all(string=date_pattern)
        items_found = 0
        
        for date_node in items:
            fecha_str = date_pattern.search(date_node).group(1)
            parent = date_node.parent
            a_tag = None
            
            for _ in range(6):
                if parent is None: break
                a_tags = parent.find_all('a')
                a_tag = next((a for a in a_tags if 'compartir' not in a.text.lower() and 'share' not in a.text.lower()), None)
                if a_tag: break
                parent = parent.parent
                
            if a_tag and parent:
                link = "https://www.bde.es" + a_tag.get('href', '') if a_tag.get('href', '').startswith('/') else a_tag.get('href', '')
                partes = [p.strip() for p in parent.get_text(separator=" | ", strip=True).split('|') if p.strip()]
                titulo_final = a_tag.text.strip()
                autor = ""
                
                try:
                    idx_fecha = partes.index(fecha_str)
                    if len(partes) > idx_fecha + 1:
                        posible_autor = partes[idx_fecha + 1]
                        if posible_autor != titulo_final and len(posible_autor) < 50:
                            autor = posible_autor.replace('.', '').replace(',', '').replace(':', '').strip()
                except: pass
                
                if autor: titulo_final = f"{autor}: {titulo_final}"
                
                if not any(r['Link'] == link for r in rows):
                    rows.append({"Date": fecha_str, "Title": titulo_final, "Link": link, "Organismo": "BdE (España)"})
                    items_found += 1
                    
        should_break = False
        if rows:
            try:
                if datetime.datetime.strptime(rows[-1]['Date'], '%d/%m/%Y') < start_date: should_break = True
            except: pass
                
        if items_found == 0 or should_break: break
        page += 1
        time.sleep(0.3) 
        
    df = pd.DataFrame(rows)
    if not df.empty:
        df["Date"] = pd.to_datetime(df["Date"], format='%d/%m/%Y', errors='coerce')
        df = df.sort_values("Date", ascending=False)
    return df

@st.cache_data(show_spinner=False)
def load_data_generic(urls, base_domain, org_name):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    rows = []
    
    for url in urls:
        try:
            response = requests.get(url, headers=headers, timeout=12)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            for a_tag in soup.find_all('a', href=True):
                link = a_tag['href']
                if link.startswith('/'): link = base_domain + link
                if base_domain not in link: continue
                    
                title = re.sub(r'\s+', ' ', a_tag.get_text(separator=" ", strip=True))
                if len(title) < 15 or "read more" in title.lower() or "download" in title.lower(): continue
                    
                parent_text = a_tag.parent.get_text(separator=' | ', strip=True) if a_tag.parent else ""
                
                date_match = re.search(r'(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}|\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4})', parent_text, re.IGNORECASE)
                
                if date_match:
                    try:
                        parsed_date = parser.parse(date_match.group(1), fuzzy=True)
                        if parsed_date.year > 2000:
                            autor = ""
                            for p in parent_text.split('|'):
                                p = p.strip()
                                if p != title and date_match.group(1) not in p and 4 < len(p) < 35 and not any(c.isdigit() for c in p):
                                    autor = p.replace(',', '').replace(':', '').strip()
                                    break
                            
                            final_title = f"{autor}: {title}" if autor and ":" not in title else title
                            rows.append({"Date": parsed_date, "Title": final_title, "Link": link, "Organismo": org_name})
                    except: pass
        except: continue
            
    df = pd.DataFrame(rows).drop_duplicates(subset=['Link']) if rows else pd.DataFrame()
    if not df.empty:
        df["Date"] = pd.to_datetime(df["Date"])
        df = df.sort_values("Date", ascending=False)
    return df

# ==========================================
# FUNCIONES DE EXPORTACIÓN A WORD
# ==========================================
def add_hyperlink(paragraph, text, url):
    part = paragraph.part
    r_id = part.relate_to(url, docx.opc.constants.RELATIONSHIP_TYPE.HYPERLINK, is_external=True)
    hyperlink = docx.oxml.shared.OxmlElement('w:hyperlink')
    hyperlink.set(docx.oxml.shared.qn('r:id'), r_id)
    new_run = docx.oxml.shared.OxmlElement('w:r')
    rPr = docx.oxml.shared.OxmlElement('w:rPr')
    c = docx.oxml.shared.OxmlElement('w:color')
    c.set(docx.oxml.shared.qn('w:val'), '0000EE')
    rPr.append(c)
    u = docx.oxml.shared.OxmlElement('w:u')
    u.set(docx.oxml.shared.qn('w:val'), 'single')
    rPr.append(u)
    sz = docx.oxml.shared.OxmlElement('w:sz')
    sz.set(docx.oxml.shared.qn('w:val'), '24')
    rPr.append(sz)
    szCs = docx.oxml.shared.OxmlElement('w:szCs')
    szCs.set(docx.oxml.shared.qn('w:val'), '24')
    rPr.append(szCs)
    rFonts = docx.oxml.shared.OxmlElement('w:rFonts')
    rFonts.set(docx.oxml.shared.qn('w:ascii'), 'Calibri')
    rFonts.set(docx.oxml.shared.qn('w:hAnsi'), 'Calibri')
    rPr.append(rFonts)
    t = docx.oxml.shared.OxmlElement('w:t')
    t.text = text
    new_run.append(rPr)
    new_run.append(t)
    hyperlink.append(new_run)
    paragraph._p.append(hyperlink)
    return hyperlink

def generate_word(dataframe, title="Discursos", subtitle=""):
    doc = Document()
    heading = doc.add_heading(title, 0)
    heading.alignment = WD_ALIGN_PARAGRAPH.CENTER
    if subtitle:
        p_sub = doc.add_paragraph()
        p_sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run_sub = p_sub.add_run(subtitle)
        run_sub.font.name = 'Calibri'
        run_sub.font.size = Pt(12)
    doc.add_paragraph()

    display_cols = [c for c in dataframe.columns if c != 'Link']
    table = doc.add_table(rows=1, cols=len(display_cols))
    
    hdr_cells = table.rows[0].cells
    for idx, header_text in enumerate(display_cols):
        p = hdr_cells[idx].paragraphs[0]
        run = p.add_run(header_text)
        run.font.name = 'Calibri'
        run.font.size = Pt(12)
        run.bold = True 

    for index, row in dataframe.iterrows():
        row_cells = table.add_row().cells
        date_str = str(row['Date'])[:10]
        p_date = row_cells[0].paragraphs[0]
        run_date = p_date.add_run(date_str)
        run_date.font.name = 'Calibri'
        run_date.font.size = Pt(12)
        
        if 'Organismo' in display_cols:
            p_org = row_cells[1].paragraphs[0]
            run_org = p_org.add_run(str(row['Organismo']))
            run_org.font.name = 'Calibri'
            run_org.font.size = Pt(12)
            p_title = row_cells[2].paragraphs[0]
            add_hyperlink(p_title, str(row['Title']), str(row['Link']))
        else:
            p_title = row_cells[1].paragraphs[0]
            add_hyperlink(p_title, str(row['Title']), str(row['Link']))

    output = BytesIO()
    doc.save(output)
    output.seek(0)
    return output

# ==========================================
# INTERFAZ DE USUARIO (SIDEBAR Y NAVEGACIÓN)
# ==========================================

try:
    st.sidebar.image("logo_banxico.png", use_column_width=True)
except:
    st.sidebar.markdown("### 🏦 BANCO DE MÉXICO")

st.sidebar.markdown("---")
st.sidebar.header("Menú de Navegación")

tipo_doc = st.sidebar.selectbox(
    "Selecciona el Tipo de Documento",
    ["Reportes", "Publicaciones Institucionales", "Investigación", "Discursos"]
)

mapeo_generico = {
    "BdF (Francia)": (["https://www.banque-france.fr/en/governor-interventions?category%5B7052%5D=7052"], "https://www.banque-france.fr"),
    "BM": (["https://openknowledge.worldbank.org/communities/b6a50016-276d-56d3-bbe5-891c8d18db24?spc.sf=dc.date.issued&spc.sd=DESC"], "https://openknowledge.worldbank.org"),
    "BoC (Canadá)": (["https://www.bankofcanada.ca/press/speeches/"], "https://www.bankofcanada.ca"),
    "BoE (Inglaterra)": (["https://www.bankofengland.co.uk/news/speeches"], "https://www.bankofengland.co.uk"),
    "BoJ (Japón)": (["https://www.boj.or.jp/en/about/press/index.htm"], "https://www.boj.or.jp"),
    "CEF": (["https://www.fsb.org/press/speeches-and-statements/"], "https://www.fsb.org"),
    "ECB (Europa)": (["https://www.ecb.europa.eu/press/pubbydate/html/index.en.html?name_of_publication=Speech"], "https://www.ecb.europa.eu"),
    "Fed (Estados Unidos)": (["https://www.federalreserve.gov/newsevents/speeches-testimony.htm"], "https://www.federalreserve.gov"),
    "FMI": (["https://www.imf.org/en/news/searchnews#sortCriteria=%40imfdate%20descending&cf-type=SPEECHES", "https://www.imf.org/en/news/searchnews#sortCriteria=%40imfdate%20descending&cf-type=TRANSCRIPTS"], "https://www.imf.org"),
    "PBoC (China)": (["https://www.pbc.gov.cn/en/3688110/3688175/index.html"], "https://www.pbc.gov.cn")
}

if tipo_doc == "Discursos":
    organismos = ["Todos", "BBk (Alemania)", "BdE (España)", "BdF (Francia)", "BM", "BoC (Canadá)", "BoE (Inglaterra)", "BoJ (Japón)", "BPI", "CEF", "ECB (Europa)", "Fed (Estados Unidos)", "FMI", "PBoC (China)"]
elif tipo_doc == "Reportes":
    organismos = ["BID", "BM", "BPI", "CEF", "FEM", "OCDE"]
elif tipo_doc == "Investigación":
    organismos = ["BID", "BM", "BPI", "CEMLA", "FMI", "OCDE"]
elif tipo_doc == "Publicaciones Institucionales":
    organismos = ["BM", "BPI", "CEF", "CEMLA", "FMI", "G20", "OCDE", "OEI"]

organismo_seleccionado = st.sidebar.selectbox("Selecciona el Organismo", organismos)

st.sidebar.markdown("---")
st.sidebar.info("Herramienta de extracción automatizada para la elaboración del boletín mensual.")

# ==========================================
# LÓGICA DE CONTROLADORES
# ==========================================

st.title("Boletín Mensual de Organismos Internacionales")
st.markdown(f"**Explorador de {tipo_doc} - {organismo_seleccionado}**")
st.markdown("---")

if tipo_doc == "Discursos":
    st.subheader("1. Selecciona el Mes y Año")
    anios_str = ["2026", "2025", "2024", "2023", "2022", "2021", "2020"]
    meses_dict = {"Enero": 1, "Febrero": 2, "Marzo": 3, "Abril": 4, "Mayo": 5, "Junio": 6, "Julio": 7, "Agosto": 8, "Septiembre": 9, "Octubre": 10, "Noviembre": 11, "Diciembre": 12}

    col1, col2 = st.columns(2)
    with col1: meses_seleccionados = st.multiselect("Mes(es)", options=list(meses_dict.keys()), default=[])
    with col2: anios_seleccionados = st.multiselect("Año(s)", options=anios_str, default=["2026"])

    buscar = st.button("🔍 Buscar", type="primary")

    if buscar or "discursos_df_filtrado" in st.session_state:
        if not meses_seleccionados or not anios_seleccionados:
            st.warning("⚠️ Por favor, selecciona al menos un mes y un año.")
        else:
            meses_num = [meses_dict[m] for m in meses_seleccionados]
            anios_num = [int(a) for a in anios_seleccionados]
            
            min_month, max_month = min(meses_num), max(meses_num)
            min_year, max_year = min(anios_num), max(anios_num)
            start_date_str = f"01.{min_month:02d}.{min_year}"
            last_day = calendar.monthrange(max_year, max_month)[1]
            end_date_str = f"{last_day:02d}.{max_month:02d}.{max_year}"

            lista_organismos_a_procesar = organismos[1:] if organismo_seleccionado == "Todos" else [organismo_seleccionado]
            dfs_combinados = []
            
            progreso = st.progress(0)
            status_text = st.empty()
            
            for i, org in enumerate(lista_organismos_a_procesar):
                status_text.text(f"Extrayendo datos de: {org}...")
                df_org = pd.DataFrame()
                
                if org == "BPI":
                    df_org = load_data_bis()
                elif org == "BBk (Alemania)":
                    df_org = load_data_bbk(start_date_str, end_date_str)
                elif org == "BdE (España)":
                    df_org = load_data_bde(start_date_str, end_date_str)
                elif org in mapeo_generico:
                    urls, base = mapeo_generico[org]
                    df_org = load_data_generic(urls, base, org)
                
                if not df_org.empty:
                    mask = (df_org["Date"].dt.year.isin(anios_num)) & (df_org["Date"].dt.month.isin(meses_num))
                    df_org_fil = df_org[mask].copy()
                    if not df_org_fil.empty:
                        if 'Organismo' not in df_org_fil.columns:
                            df_org_fil['Organismo'] = org
                        dfs_combinados.append(df_org_fil)
                        
                progreso.progress((i + 1) / len(lista_organismos_a_procesar))
            
            status_text.empty() 
            progreso.empty()
            
            if dfs_combinados:
                final_df = pd.concat(dfs_combinados, ignore_index=True)
                
                # --- LA CEREZA DEL PASTEL: Ordenar alfabéticamente por Autor (Título) y luego por Fecha ---
                final_df = final_df.sort_values(by=["Title", "Date"], ascending=[True, False])
                
                if organismo_seleccionado != "Todos":
                    final_df = final_df[['Date', 'Title', 'Link']]
                else:
                    final_df = final_df[['Date', 'Organismo', 'Title', 'Link']]
            else:
                final_df = pd.DataFrame()
            
            st.session_state["discursos_df_filtrado"] = final_df

            if len(final_df) > 0:
                st.subheader("2. Resultados de la búsqueda")
                col_mensaje, col_boton = st.columns([3, 1])
                str_meses, str_anios = ", ".join(meses_seleccionados), ", ".join(anios_seleccionados)
                
                with col_mensaje:
                    st.success(f"Se encontraron **{len(final_df)}** discursos en **{str_meses} {str_anios}**.")
                with col_boton:
                    subtitulo = f"{str_meses} {str_anios}"
                    titulo_doc = "Boletín Consolidado" if organismo_seleccionado == "Todos" else f"{organismo_seleccionado} Speeches"
                    word_file = generate_word(final_df, title=titulo_doc, subtitle=subtitulo)
                    st.download_button(label="📄 Descargar en Word", data=word_file, file_name=f"discursos_{organismo_seleccionado}_{'_'.join(meses_seleccionados)}.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", use_container_width=True)
                
                display_df = final_df.copy()
                display_df["Date"] = display_df["Date"].dt.strftime('%Y-%m-%d')
                display_df["Title"] = display_df.apply(lambda x: f"[{x['Title']}]({x['Link']})", axis=1)
                
                if organismo_seleccionado == "Todos":
                    st.markdown(display_df[["Date", "Organismo", "Title"]].to_markdown(index=False), unsafe_allow_html=True)
                else:
                    st.markdown(display_df[["Date", "Title"]].to_markdown(index=False), unsafe_allow_html=True)
            else:
                st.warning(f"No se encontraron discursos para las fechas seleccionadas.")

else:
    st.info(f"El extractor de **{tipo_doc}** para **{organismo_seleccionado}** está en construcción.")
    st.write("Próximamente podrás extraer estos documentos de forma automatizada.")
