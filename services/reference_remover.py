import re
import logging

logger = logging.getLogger(__name__)

def separate_references(text: str) -> tuple[str, str, bool]:
    """
    Detecta y separa la sección de referencias bibliográficas de un documento académico.
    Retorna: (body_text, references_text, has_references_removed)
    
    Garantiza que la búsqueda semántica y el análisis se realicen ÚNICAMENTE sobre el
    cuerpo del documento y no sobre las fuentes bibliográficas.
    """
    if not text or len(text.strip()) < 200:
        return text, "", False

    total_len = len(text)
    # Las referencias en un artículo científico se ubican en la segunda mitad del documento.
    # Buscamos a partir del 30% del texto para evitar falsos positivos al inicio.
    search_start = int(total_len * 0.30)
    candidate_text = text[search_start:]

    # Patrones para identificar encabezados de bibliografía en español e inglés
    header_patterns = [
        # Encabezado en línea separada o seguido de salto de línea, dos puntos, o inicio de citas
        r'(?im)(?:^|\n)\s*(?:(?:\d+(?:\.\d+)*|[ivxlcdm]+)[\.\)]\s*)?(?:referencias\s+bibliogr[aá]ficas|referencias|bibliograf[ií]a|fuentes\s+bibliogr[aá]ficas|fuentes\s+consultadas|obras\s+citadas|literatura\s+citada|references\s+and\s+notes|references|bibliography|works\s+cited|literature\s+cited|reference\s+list)\b(?:\s*[:\n\r]|\s+\[|\s+\d+\.|\s{2,}|\s*$|\s+(?=[A-Z]))',
        # Encabezado en mayúsculas sostenidas
        r'(?:^|\n)\s*(?:(?:\d+(?:\.\d+)*|[IVXLCDM]+)[\.\)]\s*)?(?:REFERENCIAS\s+BIBLIOGR[AÁ]FICAS|REFERENCIAS|BIBLIOGRAF[IÍ]A|REFERENCES|BIBLIOGRAPHY|WORKS\s+CITED)\b(?:\s*[:\n\r]|\s+\[|\s+\d+\.|\s{2,}|\s*$|\s+(?=[A-Z]))',
    ]

    best_match_start = -1
    best_match_header = ""

    for pattern in header_patterns:
        for match in re.finditer(pattern, candidate_text):
            matched_header = match.group(0).strip()
            abs_start = search_start + match.start()
            
            # Verificamos el contenido que sigue al encabezado
            following_snippet = text[abs_start: abs_start + 3000]
            
            # 1. Años entre paréntesis, corchetes o numeración de citas: (2020), [1], 1., 2021
            years_count = len(re.findall(r'(?:\((?:19|20)\d{2}[a-z]?\)|\[\d+\]|(?<!\w)(?:19|20)\d{2}(?!\w))', following_snippet))
            # 2. Indicadores típicos de publicaciones académicas
            citation_cues = len(re.findall(r'(?i)\b(?:doi|vol|no|pp|pages|et\s+al|journal|revista|proceedings|springer|elsevier|ieee|wiley|press|university|universidad|editorial|http|https|isbn|issn)\b', following_snippet))
            
            # Es una sección bibliográfica válida si contiene citas o si está en el último tercio con indicios
            is_valid = (years_count >= 1 or citation_cues >= 1 or abs_start > total_len * 0.65)
            
            if is_valid:
                best_match_start = abs_start
                best_match_header = matched_header
                break
        if best_match_start != -1:
            break

    if best_match_start != -1:
        # Verificar si después de las referencias hay secciones de Apéndices o Anexos
        ref_portion = text[best_match_start:]
        appendix_pattern = r'(?im)(?:^|\n)\s*(?:(?:\d+|[ivxlcdm]+)[\.\)]\s*)?(?:ap[eé]ndices?|anexos?|appendix|appendices|sobre\s+los\s+autores|about\s+the\s+authors?)\b'
        appendix_match = re.search(appendix_pattern, ref_portion[60:])
        
        if appendix_match:
            appendix_start = best_match_start + 60 + appendix_match.start()
            references_text = text[best_match_start:appendix_start].strip()
            body_text = text[:best_match_start].strip() + "\n\n" + text[appendix_start:].strip()
        else:
            references_text = text[best_match_start:].strip()
            body_text = text[:best_match_start].strip()
            
        logger.info(f"Sección de referencias detectada y excluida ({len(references_text)} caracteres excluidos). Encabezado: '{best_match_header}'")
        return body_text, references_text, True

    logger.info("No se detectó una sección de referencias explícita al final del documento.")
    return text.strip(), "", False


def strip_references(text: str) -> str:
    """
    Función de conveniencia que devuelve únicamente el cuerpo del texto sin referencias.
    """
    body, _, _ = separate_references(text)
    return body
