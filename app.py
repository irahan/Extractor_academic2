import streamlit as st
import tempfile
import os
from pathlib import Path
from services.text_processor import process_file
from services.excel_generator import generate_excel
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="Extractor de Artículos", page_icon="📄", layout="centered")

st.title("📄 Extracción Automatizada de Artículos")
st.markdown("Sube tus artículos en formato PDF o DOCX y genera automáticamente una tabla estructurada de Excel con la información clave.")

# Configuración
st.subheader("⚙️ Configuración de IA")
col1, col2 = st.columns(2)

with col1:
    ai_provider = st.selectbox(
        "Proveedor de IA",
        options=["openai", "anthropic", "deepseek", "grok", "basic"],
        format_func=lambda x: {
            "openai": "ChatGPT (OpenAI)",
            "anthropic": "Claude (Anthropic)",
            "deepseek": "DeepSeek",
            "grok": "Grok (xAI)",
            "basic": "Básico (Sin IA)"
        }[x]
    )

with col2:
    api_key = st.text_input("API Key (Opcional, sobrescribe el .env)", type="password")

keywords = st.text_input("Palabras clave a buscar (Opcional, separadas por coma)", placeholder="Ej. eficiencia, impacto ambiental, costo")

# Subida de archivos
st.subheader("📂 Subir Archivos")
uploaded_files = st.file_uploader("Selecciona archivos PDF o DOCX", type=['pdf', 'docx'], accept_multiple_files=True)

if uploaded_files:
    st.write(f"Has seleccionado {len(uploaded_files)} archivo(s).")
    
    if st.button("Procesar Artículos", type="primary"):
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        results = []
        errors = 0
        
        # Crear un directorio temporal para guardar los archivos subidos
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            for i, file in enumerate(uploaded_files):
                status_text.text(f"Procesando ({i+1}/{len(uploaded_files)}): {file.name}...")
                
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
                        keywords=keywords if keywords else None
                    )
                    results.append(resultado)
                except Exception as e:
                    st.error(f"Error al procesar {file.name}: {e}")
                    errors += 1
                
                # Actualizar progreso
                progress_bar.progress((i + 1) / len(uploaded_files))
            
            status_text.text("Generando archivo Excel...")
            
            # Generar Excel
            if results:
                excel_path = temp_path / "resultados.xlsx"
                stats = {
                    "total": len(uploaded_files),
                    "procesados": len(results),
                    "errores": errors,
                    "modelo": ai_provider
                }
                
                try:
                    generate_excel(results, str(excel_path), stats)
                    status_text.text("¡Proceso completado exitosamente!")
                    
                    with open(excel_path, "rb") as f:
                        excel_data = f.read()
                        
                    st.success("✅ Excel generado correctamente.")
                    st.download_button(
                        label="⬇️ Descargar Resultados en Excel",
                        data=excel_data,
                        file_name="articulos_procesados.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                except Exception as e:
                    st.error(f"Error al generar el Excel: {e}")
            else:
                st.warning("No se pudo procesar exitosamente ningún archivo.")
