import fitz  # PyMuPDF
import logging
import re

logger = logging.getLogger(__name__)

def extract_text_from_pdf(file_path):
    """
    Extrae el texto estructurado de un archivo PDF usando PyMuPDF,
    preservando párrafos, encabezados y secciones limpias sin fusionar títulos.
    """
    text_blocks_all = []
    metadata = {}
    try:
        doc = fitz.open(file_path)
        metadata = doc.metadata or {}
        
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            blocks = page.get_text("blocks")
            
            for b in blocks:
                # b[6] == 0 indica bloque de texto (no imagen)
                if len(b) >= 5 and b[6] == 0:
                    raw_block_text = b[4]
                    if not raw_block_text or not raw_block_text.strip():
                        continue
                        
                    # Reensamblar palabras separadas por guión al final de línea (ej. carac-\nterísticas -> características)
                    block_clean = re.sub(r'(\w+)-\s*\n\s*(\w+)', r'\1\2', raw_block_text)
                    
                    # Unir líneas dentro del bloque respetando encabezados y oraciones
                    lines = [line.strip() for line in block_clean.split('\n') if line.strip()]
                    if not lines:
                        continue
                        
                    current_sub_block = []
                    for line in lines:
                        # Detectar si la línea es un encabezado evidente o inicio de cita bibliográfica
                        is_heading = bool(re.match(
                            r'^(?:(?:\d+(?:\.\d+)*|[ivxlcdm]+)[\.\)]\s*)?(?:referencias|references|bibliograf[ií]a|conclusiones|conclusions|discusi[oó]n|discussion|resultados|results|metodolog[ií]a|methodology|introducci[oó]n|introduction|resumen|abstract)\b', 
                            line, 
                            re.I
                        )) and len(line) < 70
                        is_citation_start = bool(re.match(r'^(?:\[\d+\]|\d+\.\s+[A-Z])', line))
                        
                        if (is_heading or is_citation_start) and current_sub_block:
                            text_blocks_all.append(" ".join(current_sub_block))
                            current_sub_block = [line]
                        else:
                            current_sub_block.append(line)
                            
                    if current_sub_block:
                        if len(current_sub_block) == 1:
                            text_blocks_all.append(current_sub_block[0])
                        else:
                            text_blocks_all.append(" ".join(current_sub_block))
                        
        doc.close()
        
        full_text = "\n\n".join(text_blocks_all).strip()
        
        if not full_text:
            logger.warning(f"El archivo {file_path} parece no tener texto extraíble (posiblemente escaneado).")
            return None, metadata
            
        return full_text, metadata
    except Exception as e:
        logger.error(f"Error al leer PDF {file_path}: {e}")
        raise
