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
st.set_page_config(page_title="Boletín Mensual", layout="wide")

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
def load_data_bis(extract_author=True):
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

    df = pd.DataFrame(rows).drop_duplicates(subset=['Link']) if rows else pd.DataFrame()
    if not df.empty:
        df["Date"] = pd.to_datetime(df["Date"])
        df = df.sort_values("Date", ascending=False)
    return df

@st.cache_data(show_spinner=False)
def load_data_bbk(start_date_str, end_date_str, extract_author=True):
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
            
            author_str = ""
            if extract_author:
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
            
            if extract_author and author_str and titulo: 
                titulo = f"{author_str}: {titulo}"
                
            if fecha_str and titulo: 
                rows.append({"Date": fecha_str, "Title": titulo, "Link": link, "Organismo": "BBk (Alemania)"})
                
        if len(items) < 10: break
        page += 1
        time.sleep(0.3) 
        
    df = pd.DataFrame(rows)
    if not df.empty:
        df["Date"] = pd.to_datetime(df["Date"], format='%d.%m.%Y', errors='coerce')
        df = df.sort_values("Date", ascending=False)
    return df

@st.cache_data(show_spinner=False)
def load_data_bde(start_date_str, end_date_str, extract_author=True):
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
                
                if extract_author:
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
def load_data_fed(anios_num, extract_author=True):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    rows = []
    
    for year in anios_num:
        url = f"https://www.federalreserve.gov/newsevents/{year}-speeches.htm"
        try:
            res = requests.get(url, headers=headers, timeout=12)
            if res.status_code == 404:
                url = "https://www.federalreserve.gov/newsevents/speeches.htm"
                res = requests.get(url, headers=headers, timeout=12)
            
            soup = BeautifulSoup(res.text, 'html.parser')
            
            for a_tag in soup.find_all('a', href=True):
                href = a_tag['href']
                if '/newsevents/speech/' in href and '.htm' in href:
                    link = "https://www.federalreserve.gov" + href if href.startswith('/') else href
                    titulo = a_tag.get_text(strip=True)
                    
                    parent_div = a_tag.find_parent('div', class_='row')
                    if not parent_div:
                        parent_div = a_tag.parent
                    
                    text_content = parent_div.get_text(separator=' | ', strip=True)
                    date_match = re.search(r'(\d{1,2}/\d{1,2}/\d{4}|\w+\s\d{1,2},\s\d{4})', text_content)
                    
                    if date_match:
                        try:
                            parsed_date = parser.parse(date_match.group(1))
                            if parsed_date.year not in anios_num: continue
                            
                            autor = ""
                            if extract_author:
                                partes = text_content.split(' | ')
                                for p in partes:
                                    p_clean = p.strip()
                                    if p_clean and p_clean != titulo and date_match.group(1) not in p_clean and 'Watch Live' not in p_clean:
                                        if any(cargo in p_clean for cargo in ['Chair', 'Governor', 'Vice Chair', 'President']):
                                            autor = p_clean.replace(',', '').replace(':', '').strip()
                                            # Limpiar cargos, "Statement from Federal Reserve..." etc.
                                            autor = re.sub(r'^(?:Statement\s+(?:by|from)\s+)?(?:Federal Reserve\s+)?(?:Former\s+)?(Vice Chair for Supervision|Vice Chair|Chair|Governor|President)\s+', '', autor, flags=re.IGNORECASE)
                                            # Limpiar la inicial intermedia (ej. " W.", " H.")
                                            autor = re.sub(r'\s+[A-Z]\.\s+', ' ', autor)
                                            break
                            
                            final_title = f"{autor}: {titulo}" if autor else titulo
                            rows.append({"Date": parsed_date, "Title": final_title, "Link": link, "Organismo": "Fed (Estados Unidos)"})
                        except: pass
        except: pass
        
    df = pd.DataFrame(rows).drop_duplicates(subset=['Link']) if rows else pd.DataFrame()
    if not df.empty:
        df["Date"] = pd.to_datetime(df["Date"])
        df = df.sort_values("Date", ascending=False)
    return df

@st.cache_data(show_spinner=False)
def load_data_generic(urls, base_domain, org_name, extract_author=True):
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
                grandparent_text = a_tag.parent.parent.get_text(separator=' | ', strip=True) if a_tag.parent and a_tag.parent.parent else ""
                full_context_text = parent_text + " | " + grandparent_text
                
                date_match = re.search(r'(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}|\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4})', full_context_text, re.IGNORECASE)
                
                if date_match:
                    try:
                        parsed_date = parser.parse(date_match.group(1), fuzzy=True)
                        if parsed_date.year > 2000:
                            autor = ""
                            if extract_author:
                                for p in full_context_text.split('|'):
                                    p = p.strip()
                                    if p != title and date_match.group(1) not in p and 4 < len(p) < 45 and not any(c.isdigit() for c in p):
                                        autor = p.replace(',', '').replace(':', '').replace('By ', '').replace('Watch Live', '').strip()
                                        break
                            
                            final_title = f"{autor}: {title}" if autor and extract_author and ":" not in title else title
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

def generate_word(dataframe, title="Boletín Mensual", subtitle=""):
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
        
        for i, col_name in enumerate(display_cols):
            p = row_cells[i].paragraphs[0]
            
            if col_name == 'Title':
                add_hyperlink(p, str(row['Title']), str(row['Link']))
            elif col_name == 'Date':
                date_str = str(row['Date'])[:10]
                run = p.add_run(date_str)
                run.font.name = 'Calibri'
                run.font.size = Pt(12)
            else:
                run = p.add_run(str(row[col_name]))
                run.font.name = 'Calibri'
                run.font.size = Pt(12)

    output = BytesIO()
    doc.save(output)
    output.seek(0)
    return output

# ==========================================
# INTERFAZ DE USUARIO Y NAVEGACIÓN
# ==========================================

try:
    st.sidebar.image("logo_banxico.png", use_column_width=True)
except:
    st.sidebar.markdown("### 🏦 BANCO DE MÉXICO")

st.sidebar.markdown("---")
st.sidebar.header("Menú de Navegación")

modo_app = st.sidebar.radio(
    "",
    ["Boletín", "Categorías"]
)
st.sidebar.markdown("---")

tipo_doc = ""
organismo_seleccionado = ""

if modo_app == "Categorías":
    tipo_doc = st.sidebar.selectbox(
        "Selecciona el Tipo de Documento",
        ["Reportes", "Publicaciones Institucionales", "Investigación", "Discursos"]
    )

    if tipo_doc == "Discursos":
        organismos = ["Todos", "BBk (Alemania)", "BdE (España)", "BdF (Francia)", "BM", "BoC (Canadá)", "BoE (Inglaterra)", "BoJ (Japón)", "BPI", "CEF", "ECB (Europa)", "Fed (Estados Unidos)", "FMI", "PBoC (China)"]
    elif tipo_doc == "Reportes":
        organismos = ["Todos", "BID", "BM", "BPI", "CEF", "FEM", "OCDE"]
    elif tipo_doc == "Investigación":
        organismos = ["Todos", "BID", "BM", "BPI", "CEMLA", "FMI", "OCDE"]
    elif tipo_doc == "Publicaciones Institucionales":
        organismos = ["Todos", "BM", "BPI", "CEF", "CEMLA", "FMI", "G20", "OCDE", "OEI"]

    organismo_seleccionado = st.sidebar.selectbox("Selecciona el Organismo", organismos)

st.sidebar.info("Herramienta de extracción automatizada para la elaboración del boletín mensual.")

mapeo_discursos = {
    "BdF (Francia)": (["https://www.banque-france.fr/en/governor-interventions?category%5B7052%5D=7052"], "https://www.banque-france.fr"),
    "BM": (["https://openknowledge.worldbank.org/communities/b6a50016-276d-56d3-bbe5-891c8d18db24?spc.sf=dc.date.issued&spc.sd=DESC"], "https://openknowledge.worldbank.org"),
    "BoC (Canadá)": (["https://www.bankofcanada.ca/press/speeches/"], "https://www.bankofcanada.ca"),
    "BoE (Inglaterra)": (["https://www.bankofengland.co.uk/news/speeches"], "https://www.bankofengland.co.uk"),
    "BoJ (Japón)": (["https://www.boj.or.jp/en/about/press/index.htm"], "https://www.boj.or.jp"),
    "CEF": (["https://www.fsb.org/press/speeches-and-statements/"], "https://www.fsb.org"),
    "ECB (Europa)": (["https://www.ecb.europa.eu/press/pubbydate/html/index.en.html?name_of_publication=Speech"], "https://www.ecb.europa.eu"),
    "FMI": (["https://www.imf.org/en/news/searchnews#sortCriteria=%40imfdate%20descending&cf-type=SPEECHES", "https://www.imf.org/en/news/searchnews#sortCriteria=%40imfdate%20descending&cf-type=TRANSCRIPTS"], "https://www.imf.org"),
    "PBoC (China)": (["https://www.pbc.gov.cn/en/3688110/3688175/index.html"], "https://www.pbc.gov.cn")
}

anios_str = ["2026", "2025", "2024", "2023", "2022", "2021", "2020"]
meses_dict = {"Enero": 1, "Febrero": 2, "Marzo": 3, "Abril": 4, "Mayo": 5, "Junio": 6, "Julio": 7, "Agosto": 8, "Septiembre": 9, "Octubre": 10, "Noviembre": 11, "Diciembre": 12}

# ==========================================
# LÓGICA PRINCIPAL DE LA APP
# ==========================================

if modo_app == "Boletín":
    st.title("Generador de Boletín Mensual")
    st.markdown("**Extrae y unifica documentos de todas las categorías y organismos por mes.**")
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    with col1: meses_seleccionados = st.multiselect("Mes(es)", options=list(meses_dict.keys()), default=[])
    with col2: anios_seleccionados = st.multiselect("Año(s)", options=anios_str, default=["2026"])
    
    buscar_boletin = st.button("📄 Generar Boletín Mensual", type="primary")
    
    if buscar_boletin or "boletin_df_filtrado" in st.session_state:
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
            
            dfs_boletin = []
            progreso = st.progress(0)
            status_text = st.empty()
            
            # --- EXTRACCIÓN DE DISCURSOS ---
            orgs_discursos = ["BBk (Alemania)", "BdE (España)", "BdF (Francia)", "BM", "BoC (Canadá)", "BoE (Inglaterra)", "BoJ (Japón)", "BPI", "CEF", "ECB (Europa)", "Fed (Estados Unidos)", "FMI", "PBoC (China)"]
            total_pasos = len(orgs_discursos)
            
            for i, org in enumerate(orgs_discursos):
                status_text.text(f"Procesando Discursos: {org}...")
                df_org = pd.DataFrame()
                
                if org == "BPI":
                    df_org = load_data_bis(extract_author=True)
                elif org == "BBk (Alemania)":
                    df_org = load_data_bbk(start_date_str, end_date_str, extract_author=True)
                elif org == "BdE (España)":
                    df_org = load_data_bde(start_date_str, end_date_str, extract_author=True)
                elif org == "Fed (Estados Unidos)":
                    df_org = load_data_fed(anios_num, extract_author=True)
                elif org in mapeo_discursos:
                    urls, base = mapeo_discursos[org]
                    df_org = load_data_generic(urls, base, org, extract_author=True)
                    
                if not df_org.empty:
                    mask = (df_org["Date"].dt.year.isin(anios_num)) & (df_org["Date"].dt.month.isin(meses_num))
                    df_org_fil = df_org[mask].copy()
                    if not df_org_fil.empty:
                        if 'Organismo' not in df_org_fil.columns:
                            df_org_fil['Organismo'] = org
                        df_org_fil['Categoría'] = "Discursos"
                        dfs_boletin.append(df_org_fil)
                
                progreso.progress((i + 1) / total_pasos)
                
            status_text.empty()
            progreso.empty()
            
            if dfs_boletin:
                final_df = pd.concat(dfs_boletin, ignore_index=True)
                final_df = final_df.sort_values(by=["Categoría", "Organismo", "Title", "Date"], ascending=[True, True, True, False])
                final_df = final_df[['Date', 'Categoría', 'Organismo', 'Title', 'Link']]
            else:
                final_df = pd.DataFrame()
                
            st.session_state["boletin_df_filtrado"] = final_df

            if len(final_df) > 0:
                str_meses, str_anios = ", ".join(meses_seleccionados), ", ".join(anios_seleccionados)
                st.markdown(f"**Resultados del Boletín: {str_meses} {str_anios}**")
                
                col_msg, col_btn = st.columns([3, 1])
                with col_msg:
                    st.success(f"Se consolidaron **{len(final_df)}** documentos.")
                with col_btn:
                    subtitulo = f"{str_meses} {str_anios}"
                    word_file = generate_word(final_df, title="Boletín Mensual", subtitle=subtitulo)
                    st.download_button(label="📄 Descargar Boletín", data=word_file, file_name=f"Boletin_Consolidado_{'_'.join(meses_seleccionados)}.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", use_container_width=True)
                
                display_df = final_df.copy()
                display_df["Date"] = display_df["Date"].dt.strftime('%Y-%m-%d')
                display_df["Title"] = display_df.apply(lambda x: f"[{x['Title']}]({x['Link']})", axis=1)
                st.markdown(display_df[["Date", "Categoría", "Organismo", "Title"]].to_markdown(index=False), unsafe_allow_html=True)
            else:
                st.warning("No se encontraron documentos para las fechas seleccionadas.")

elif modo_app == "Categorías":
    st.title("Documentos de Organismos Internacionales")
    st.markdown(f"**Explorador de {tipo_doc} - {organismo_seleccionado}**")
    st.markdown("---")

    if tipo_doc == "Discursos" or (tipo_doc in ["Reportes", "Investigación", "Publicaciones Institucionales"] and organismo_seleccionado == "Todos"):
        st.markdown("**1. Selecciona el Mes y Año**")

        col1, col2 = st.columns(2)
        with col1: meses_seleccionados = st.multiselect("Mes(es)", options=list(meses_dict.keys()), default=[])
        with col2: anios_seleccionados = st.multiselect("Año(s)", options=anios_str, default=["2026"])

        buscar = st.button("🔍 Buscar", type="primary")
        
        debe_extraer_autor = True if tipo_doc == "Discursos" else False

        if buscar or "explorador_df_filtrado" in st.session_state:
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

                if organismo_seleccionado == "Todos" and tipo_doc != "Discursos":
                    st.info(f"La extracción consolidada para {tipo_doc} está en construcción.")
                    st.stop()
                
                lista_orgs = organismos[1:] if organismo_seleccionado == "Todos" else [organismo_seleccionado]
                dfs_combinados = []
                
                progreso = st.progress(0)
                status_text = st.empty()
                
                for i, org in enumerate(lista_orgs):
                    status_text.text(f"Extrayendo {tipo_doc} de: {org}...")
                    df_org = pd.DataFrame()
                    
                    if org == "BPI":
                        df_org = load_data_bis(extract_author=debe_extraer_autor)
                    elif org == "BBk (Alemania)":
                        df_org = load_data_bbk(start_date_str, end_date_str, extract_author=debe_extraer_autor)
                    elif org == "BdE (España)":
                        df_org = load_data_bde(start_date_str, end_date_str, extract_author=debe_extraer_autor)
                    elif org == "Fed (Estados Unidos)":
                        df_org = load_data_fed(anios_num, extract_author=debe_extraer_autor)
                    elif org in mapeo_discursos and tipo_doc == "Discursos":
                        urls, base = mapeo_discursos[org]
                        df_org = load_data_generic(urls, base, org, extract_author=debe_extraer_autor)
                    
                    if not df_org.empty:
                        mask = (df_org["Date"].dt.year.isin(anios_num)) & (df_org["Date"].dt.month.isin(meses_num))
                        df_org_fil = df_org[mask].copy()
                        if not df_org_fil.empty:
                            if 'Organismo' not in df_org_fil.columns:
                                df_org_fil['Organismo'] = org
                            dfs_combinados.append(df_org_fil)
                            
                    progreso.progress((i + 1) / len(lista_orgs))
                
                status_text.empty() 
                progreso.empty()
                
                if dfs_combinados:
                    final_df = pd.concat(dfs_combinados, ignore_index=True)
                    final_df = final_df.sort_values(by=["Title", "Date"], ascending=[True, False])
                    
                    if organismo_seleccionado != "Todos":
                        final_df = final_df[['Date', 'Title', 'Link']]
                    else:
                        final_df = final_df[['Date', 'Organismo', 'Title', 'Link']]
                else:
                    final_df = pd.DataFrame()
                
                st.session_state["explorador_df_filtrado"] = final_df

                if len(final_df) > 0:
                    st.markdown("**2. Resultados de la búsqueda**")
                    col_mensaje, col_boton = st.columns([3, 1])
                    str_meses, str_anios = ", ".join(meses_seleccionados), ", ".join(anios_seleccionados)
                    
                    with col_mensaje:
                        st.success(f"Se encontraron **{len(final_df)}** documentos en **{str_meses} {str_anios}**.")
                    with col_boton:
                        subtitulo = f"{str_meses} {str_anios}"
                        titulo_doc = "Boletín Mensual" if organismo_seleccionado == "Todos" else f"{organismo_seleccionado} {tipo_doc}"
                        word_file = generate_word(final_df, title=titulo_doc, subtitle=subtitulo)
                        st.download_button(label="📄 Descargar en Word", data=word_file, file_name=f"{tipo_doc}_{organismo_seleccionado}_{'_'.join(meses_seleccionados)}.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", use_container_width=True)
                    
                    display_df = final_df.copy()
                    display_df["Date"] = display_df["Date"].dt.strftime('%Y-%m-%d')
                    display_df["Title"] = display_df.apply(lambda x: f"[{x['Title']}]({x['Link']})", axis=1)
                    
                    if organismo_seleccionado == "Todos":
                        st.markdown(display_df[["Date", "Organismo", "Title"]].to_markdown(index=False), unsafe_allow_html=True)
                    else:
                        st.markdown(display_df[["Date", "Title"]].to_markdown(index=False), unsafe_allow_html=True)
                else:
                    st.warning(f"No se encontraron documentos para las fechas seleccionadas.")

    else:
        st.info(f"El extractor de **{tipo_doc}** para **{organismo_seleccionado}** está en construcción.")
