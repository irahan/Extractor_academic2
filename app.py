import streamlit as st
import tempfile
import os
from pathlib import Path
from services.text_processor import process_file
from services.excel_generator import generate_excel
from config import Config
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="Extractor de Artículos & Buscador Semántico", 
    page_icon="🔍", 
    layout="wide"
)

st.title("🔍 Extractor de Artículos & Buscador Semántico")
st.markdown("""
Sube tus artículos en formato **PDF** o **DOCX** y realiza búsquedas semánticas sobre el contenido del documento.
- **🛡️ Exclusión de Referencias:** La búsqueda y el análisis se realizan exclusivamente sobre el cuerpo del documento, **omitiendo la bibliografía y citas finales**.
- **🌐 Traducción Automática:** Si el artículo está escrito en **inglés**, se genera automáticamente su **traducción completa al español** en el reporte Excel y en pantalla.
""")

# Configuración
st.subheader("⚙️ Configuración del Buscador y Modelo")
col1, col2 = st.columns([1, 1])

with col1:
    ai_provider = st.selectbox(
        "Modo de Análisis / Proveedor",
        options=["basic", "openai", "anthropic", "deepseek", "grok"],
        format_func=lambda x: {
            "basic": "⚡ Semántico Local + Traductor (Embeddings Neuronales - Sin API)",
            "openai": "🧠 OpenAI (ChatGPT + Semántico + Traductor)",
            "anthropic": "🧠 Claude (Anthropic + Semántico + Traductor)",
            "deepseek": "🧠 DeepSeek (+ Semántico + Traductor)",
            "grok": "🧠 Grok (xAI + Semántico + Traductor)"
        }[x],
        help="El modo Semántico Local utiliza embeddings multilingües y traductor integrado directamente en tu equipo sin costo ni necesidad de API Key."
    )

with col2:
    api_key = st.text_input(
        "API Key (Solo requerida si seleccionas OpenAI, Claude, DeepSeek o Grok)", 
        type="password",
        help="Si usas el modo local, puedes dejar este campo vacío."
    )

st.markdown("---")
st.subheader("🔎 ¿Qué deseas buscar en el documento?")
keywords = st.text_input(
    "Palabras clave a buscar / Consulta semántica en el documento", 
    placeholder="Ej. metodologías de optimización energética, impacto ambiental y costos, algoritmos de clasificación...",
    help="Escribe lo que quieres buscar en el documento PDF. El motor semántico buscará por significado y conceptos en el texto, omitiendo las referencias bibliográficas."
)

# Subida de archivos
col_header, col_limit = st.columns([3, 2])
with col_header:
    st.subheader("📂 Subir Artículos")
with col_limit:
    max_files = st.radio(
        "Límite máximo de artículos:",
        options=Config.MAX_FILES_OPTIONS,
        index=0,
        horizontal=True,
        format_func=lambda x: f"{x} artículos",
        help="Límite máximo de documentos a procesar en esta ejecución (5 o 10 artículos)."
    )

uploaded_files = st.file_uploader(
    f"Selecciona hasta {max_files} archivos PDF o DOCX", 
    type=['pdf', 'docx'], 
    accept_multiple_files=True,
    help=f"Solo se permite procesar hasta un máximo de {max_files} artículos simultáneamente."
)

if uploaded_files:
    num_files = len(uploaded_files)
    files_to_process = None
    
    if num_files > max_files:
        st.error(
            f"🚫 **Límite superado:** Has seleccionado **{num_files}** archivo(s), "
            f"pero el límite configurado es de **{max_files} artículos**."
        )
        if max_files < 10 and num_files <= 10:
            st.info("💡 **Sugerencia:** Puedes cambiar el selector de arriba a **10 artículos** para procesar todos los archivos seleccionados.")
            
        st.warning(
            f"⚠️ Por favor, elimina al menos **{num_files - max_files}** archivo(s) usando la **✖** en la lista de arriba, "
            f"o utiliza el botón a continuación para procesar solo los primeros {max_files}."
        )
        
        col_btn1, col_btn2 = st.columns([1, 1])
        with col_btn1:
            st.button("🚀 Iniciar Búsqueda Semántica y Procesamiento", type="primary", disabled=True, help=f"Deshabilitado: excede el límite de {max_files} artículos.")
        with col_btn2:
            if st.button(f"✂️ Procesar solo los primeros {max_files} artículos"):
                files_to_process = uploaded_files[:max_files]
    else:
        st.info(f"📁 Has seleccionado {num_files} de máximo {max_files} archivo(s) permitido(s).")
        if st.button("🚀 Iniciar Búsqueda Semántica y Procesamiento", type="primary"):
            files_to_process = uploaded_files
    
    if files_to_process:
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        results = []
        errors = 0
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            for i, file in enumerate(files_to_process):
                status_text.text(f"⏳ Procesando ({i+1}/{len(files_to_process)}): {file.name} (excluyendo referencias y traduciendo si aplica)...")
                
                # Guardar el archivo temporalmente
                file_path = temp_path / file.name
                with open(file_path, "wb") as f:
                    f.write(file.getbuffer())
                
                # Procesar
                try:
                    resultado = process_file(
                        str(file_path), 
                        file.name, 
                        provider=ai_provider, 
                        api_key=api_key if api_key else None, 
                        keywords=keywords if keywords.strip() else None
                    )
                    results.append(resultado)
                except Exception as e:
                    st.error(f"❌ Error al procesar {file.name}: {e}")
                    errors += 1
                
                # Actualizar barra de progreso
                progress_bar.progress((i + 1) / len(files_to_process))
            
            status_text.text("📊 Generando archivo Excel con los resultados y traducciones...")
            
            # Generar Excel y mostrar resultados
            if results:
                excel_path = temp_path / "articulos_busqueda_semantica.xlsx"
                stats = {
                    "total": len(files_to_process),
                    "procesados": len(results),
                    "errores": errors,
                    "modelo": ai_provider,
                    "consulta": keywords if keywords.strip() else "Puntos clave generales"
                }
                
                try:
                    generate_excel(results, str(excel_path), stats)
                    status_text.text("✅ ¡Búsqueda semántica, extracción y traducciones completadas con éxito!")
                    
                    with open(excel_path, "rb") as f:
                        excel_data = f.read()
                        
                    st.success("✅ Procesamiento finalizado. Los resultados y traducciones están listos en el Excel.")
                    
                    col_dl, _ = st.columns([1, 2])
                    with col_dl:
                        st.download_button(
                            label="⬇️ Descargar Resultados en Excel (Con Traducción)",
                            data=excel_data,
                            file_name="articulos_busqueda_semantica.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
                    
                    # Vista previa interactiva de los resultados en pantalla
                    st.markdown("### 📋 Vista Previa de Resultados")
                    for res in results:
                        idioma = res.get("Idioma", "Español")
                        is_english = (idioma == "Inglés")
                        flag = "🇬🇧 Inglés" if is_english else "🇪🇸 Español"
                        
                        refs_badge = "🛡️ **Referencias excluidas:** Sí" if res.get("Referencias_Excluidas") else "ℹ️ **Referencias:** No detectadas"
                        chars_excl = res.get("Caracteres_Referencias_Excluidos", 0)
                        if chars_excl > 0:
                            refs_badge += f" ({chars_excl:,} caracteres omitidos)"

                        titulo_card = res.get('Nombre_ES') if is_english else res.get('Nombre')
                        with st.expander(f"📄 {res.get('Artículo')} — **{titulo_card}** ({res.get('Año')})", expanded=True):
                            st.caption(f"**Idioma original:** {flag} | **Autores:** {res.get('Autor')} | {refs_badge}")
                            
                            if is_english:
                                tab_es, tab_orig = st.tabs(["🇪🇸 Versión en Español (Traducida)", "🇬🇧 Versión Original (Inglés)"])
                                
                                with tab_es:
                                    st.markdown(f"**Título traducido:** {res.get('Nombre_ES')}")
                                    st.markdown("**Resumen traducido:**")
                                    st.write(res.get("Resumen_ES"))
                                    st.markdown(f"**🎯 Hallazgos Semánticos ({'Consulta: ' + keywords if keywords.strip() else 'Puntos Clave'}):**")
                                    st.markdown(res.get("Puntos_Clave_ES", ""))
                                    
                                with tab_orig:
                                    st.markdown(f"**Original Title:** {res.get('Nombre')}")
                                    st.markdown("**Original Abstract:**")
                                    st.write(res.get("Resumen"))
                                    st.markdown(f"**🎯 Semantic Findings ({'Query: ' + keywords if keywords.strip() else 'Key Points'}):**")
                                    st.markdown(res.get("Punto clave más relevantes", ""))
                            else:
                                st.markdown("**Resumen:**")
                                st.write(res.get("Resumen"))
                                st.markdown(f"**🎯 Hallazgos de Búsqueda Semántica ({'Consulta: ' + keywords if keywords.strip() else 'Puntos Clave'}):**")
                                st.markdown(res.get("Punto clave más relevantes", ""))
                            
                except Exception as e:
                    st.error(f"❌ Error al generar el Excel: {e}")
            else:
                st.warning("⚠️ No se pudo procesar exitosamente ningún archivo.")
