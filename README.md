# Boletín de Organismos Internacionales 

Este ecosistema automatizado, desarrollado en **Python 3.12**, permite la extracción, filtrado y consolidación de información estratégica (discursos, reportes y working papers) de las principales instituciones financieras globales. El objetivo es estandarizar la vigilancia macroeconómica y reducir casi en su totalidad el tiempo de recolección manual de datos.

---

## Capacidades Principales

* **Extracción Multi-Fuente:** Conexión directa con las bases de datos de:
    * **FMI:** Uso de *Coveo API* para búsqueda unificada.
    * **BPI (BIS):** Triple validación de discursos (JSON + HTML Meta-tags).
    * **FEM (World Economic Forum):** Integración con *Apollo API*.
    * **Bancos Centrales:** Scraping dinámico de intervenciones (Fed, ECB, PBoC, BoJ, etc.).
* **Filtros de Precisión:** Sistema de validación de fechas por metadatos de descripción para evitar "rezagados" de meses anteriores.
* **Exportación Institucional:** Generación automática de documentos **.docx** con estilos, jerarquías y formatos listos para distribución oficial.

---

## Arquitectura del Proyecto

El proyecto sigue una estructura modular para facilitar el mantenimiento de los scrapers individuales:

```text
├── app1.py              # Interfaz web principal (Streamlit)
├── core_logic.py        # Orquestación de datos y manejo de fechas
├── scrapers/            # Módulos de extracción por organismo
│   ├── fmi_coveo.py     # Integración API FMI
│   ├── bis_logic.py     # Filtros avanzados para el BPI
│   └── bank_scrapers.py # Scraping de Bancos Centrales
├── utils/
│   ├── gen_reporte.py   # Motor de formateo python-docx
│   └── formats.py       # Estilos del documento final
├── requirements.txt     # Dependencias del proyecto
└── README.md            # Documentación técnica
