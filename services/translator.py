import re
import logging
import requests
from typing import List, Optional

logger = logging.getLogger(__name__)

# Cache en memoria para evitar llamadas redundantes a la traducción
_translation_cache = {}

def detect_language(text: str) -> str:
    """
    Detecta de forma heurística y ultrarrápida si el texto está en inglés ('en') o español ('es').
    """
    if not text or len(text.strip()) < 30:
        return 'es'
        
    words = re.findall(r'\b[a-záéíóúüñ]+\b', text.lower())
    if not words:
        return 'es'
        
    spanish_stop = {
        'de', 'la', 'el', 'en', 'y', 'que', 'los', 'del', 'las', 'por', 'un', 'para', 
        'con', 'no', 'una', 'su', 'al', 'lo', 'como', 'más', 'pero', 'sus', 'este', 
        'entre', 'esta', 'son', 'sobre', 'también', 'se', 'ha', 'fue', 'fueron', 'estos'
    }
    english_stop = {
        'the', 'of', 'and', 'to', 'a', 'in', 'that', 'is', 'was', 'for', 'it', 'with', 
        'as', 'on', 'be', 'at', 'by', 'this', 'have', 'from', 'or', 'had', 'word', 'but', 
        'not', 'what', 'all', 'were', 'we', 'when', 'your', 'can', 'there', 'use', 'an', 
        'each', 'which', 'their', 'has', 'these', 'are', 'paper', 'study', 'results'
    }
    
    # Evaluar sobre una muestra representativa de palabras
    sample_words = words[:1500]
    es_count = sum(1 for w in sample_words if w in spanish_stop)
    en_count = sum(1 for w in sample_words if w in english_stop)
    
    if en_count > es_count:
        return 'en'
    return 'es'


def _translate_google_gtx(text: str) -> Optional[str]:
    """
    Motor 1: Endpoint Google Translate GTX de alta capacidad y velocidad.
    Permite traducir sin límite diario de 5.000 caracteres y maneja hasta 4.500 caracteres por petición.
    """
    url = "https://translate.googleapis.com/translate_a/single"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    data = {
        "client": "gtx",
        "sl": "auto",
        "tl": "es",
        "dt": "t",
        "q": text
    }
    
    resp = requests.post(url, data=data, headers=headers, timeout=12)
    if resp.status_code == 200:
        parsed = resp.json()
        if parsed and isinstance(parsed, list) and len(parsed) > 0 and parsed[0]:
            parts = parsed[0]
            translated = "".join(p[0] for p in parts if p and p[0])
            if translated and translated.strip():
                return translated.strip()
    return None


def _translate_lingva(text: str) -> Optional[str]:
    """
    Motor 2: Fallback mediante instancias públicas de Lingva Translate.
    """
    mirrors = [
        "https://lingva.ml/api/v1/auto/es/",
        "https://translate.plausibility.cloud/api/v1/auto/es/"
    ]
    for base in mirrors:
        try:
            from urllib.parse import quote
            url = f"{base}{quote(text[:1500])}"
            resp = requests.get(url, timeout=8)
            if resp.status_code == 200:
                data = resp.json()
                tr = data.get("translation")
                if tr and tr.strip():
                    return tr.strip()
        except Exception:
            continue
    return None


def _translate_mymemory(text: str) -> Optional[str]:
    """
    Motor 3: Fallback usando MyMemoryTranslator con verificación de cuota.
    """
    try:
        from deep_translator import MyMemoryTranslator
        translator = MyMemoryTranslator(source='english', target='spanish')
        
        # Limitar longitud para MyMemory (máximo 450 caracteres)
        chunk = text[:450].strip()
        result = translator.translate(chunk)
        
        # Verificar si MyMemory agotó cuota
        if result and "MYMEMORY WARNING" not in result.upper():
            return result
    except Exception:
        pass
    return None


def translate_to_spanish(text: str) -> str:
    """
    Traduce un texto del inglés al español utilizando un sistema resiliente en cascada:
    1. Google Translate GTX (alta velocidad, sin cuota diaria restrictiva de 5000 caracteres)
    2. Lingva Translate (fallback)
    3. MyMemoryTranslator (fallback)
    
    Soporta textos largos mediante segmentación inteligente y almacenamiento en caché.
    """
    if not text or not text.strip():
        return text

    clean_text = text.strip()
    if clean_text in _translation_cache:
        return _translation_cache[clean_text]

    # Si el texto es de longitud moderada (hasta 3500 caracteres), traducir directamente
    if len(clean_text) <= 3500:
        # Intentar Motor 1 (Google GTX)
        try:
            res = _translate_google_gtx(clean_text)
            if res:
                _translation_cache[clean_text] = res
                return res
        except Exception as e:
            logger.warning(f"Fallo en Motor Google GTX: {e}. Intentando motor alternativo...")

        # Intentar Motor 2 (Lingva)
        res_lingva = _translate_lingva(clean_text)
        if res_lingva:
            _translation_cache[clean_text] = res_lingva
            return res_lingva

        # Intentar Motor 3 (MyMemory)
        res_mymemory = _translate_mymemory(clean_text)
        if res_mymemory:
            _translation_cache[clean_text] = res_mymemory
            return res_mymemory

        # Si todo falla, devolver original
        logger.warning("No se pudo traducir el texto con ningún motor disponible. Se conservará el original.")
        return text

    # Si el texto es muy largo (> 3500 caracteres), dividir por oraciones/párrafos
    sentences = re.split(r'(?<=[.!?])\s+', clean_text)
    translated_parts = []
    current_chunk = ""

    for sent in sentences:
        if len(current_chunk) + len(sent) < 3000:
            current_chunk += (" " if current_chunk else "") + sent
        else:
            if current_chunk:
                translated_chunk = translate_to_spanish(current_chunk)
                translated_parts.append(translated_chunk)
            current_chunk = sent

    if current_chunk:
        translated_chunk = translate_to_spanish(current_chunk)
        translated_parts.append(translated_chunk)

    result = " ".join(translated_parts)
    _translation_cache[clean_text] = result
    return result


def translate_points_to_spanish(points: List[str]) -> List[str]:
    """
    Traduce una lista de puntos clave o hallazgos semánticos al español de forma eficiente en bloque,
    preservando prefijos como '[75.2% Relevancia]' o viñetas sin realizar múltiples peticiones redundantes.
    """
    if not points:
        return []

    if isinstance(points, str):
        points = [p.strip() for p in points.split("\n") if p.strip()]

    prefix_pattern = r'^(\s*(?:•|-|\*|\[\d+(?:\.\d+)?%\s*Relevancia\])\s*)(.*)$'
    prefixes = []
    contents = []

    for p in points:
        match = re.match(prefix_pattern, p)
        if match:
            prefixes.append(match.group(1))
            contents.append(match.group(2))
        else:
            prefixes.append("")
            contents.append(p)

    # Si hay varios puntos, agruparlos con un delimitador para traducirlos en UNA SOLA llamada
    if len(contents) > 1:
        delimiter = "\n<<<SEP>>>\n"
        combined_text = delimiter.join(contents)
        
        try:
            translated_combined = translate_to_spanish(combined_text)
            translated_contents = [c.strip() for c in re.split(r'\s*<<<SEP>>>\s*', translated_combined)]
            
            if len(translated_contents) == len(contents):
                translated_points = []
                for pref, trans in zip(prefixes, translated_contents):
                    translated_points.append(f"{pref}{trans}")
                return translated_points
        except Exception as e:
            logger.warning(f"Traducción en bloque de puntos falló ({e}). Procediendo con traducción individual...")

    # Fallback: traducción individual de cada punto
    translated_points = []
    for pref, cont in zip(prefixes, contents):
        content_tr = translate_to_spanish(cont)
        translated_points.append(f"{pref}{content_tr}" if pref else content_tr)

    return translated_points


def clear_translation_cache():
    """Limpia el caché de traducciones en memoria."""
    global _translation_cache
    _translation_cache.clear()
