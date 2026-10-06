import fitz  # PyMuPDF
import logging

logger = logging.getLogger(__name__)

def extract_text_from_pdf(file_path):
    """
    Extrae el texto de un archivo PDF usando PyMuPDF.
    """
    text = ""
    try:
        doc = fitz.open(file_path)
        metadata = doc.metadata
        
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            page_text = page.get_text("text")
            
            # Limpiar espacios excesivos y mantener saltos de párrafo razonables
            lines = page_text.split('\n')
            cleaned_lines = [line.strip() for line in lines if line.strip()]
            
            # Unir líneas, intentando mantener párrafos
            page_text_clean = " ".join(cleaned_lines)
            
            text += page_text_clean + "\n\n"
            
        doc.close()
        
        if not text.strip():
            logger.warning(f"El archivo {file_path} parece no tener texto extraíble (posiblemente escaneado).")
            return None, metadata
            
        return text, metadata
    except Exception as e:
        logger.error(f"Error al leer PDF {file_path}: {e}")
        raise
