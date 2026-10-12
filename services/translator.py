import re
import logging
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

def translate_to_spanish(text: str) -> str:
    """
    Traduce un texto del inglés al español utilizando MyMemoryTranslator (deep-translator).
    Soporta textos largos mediante segmentación por oraciones y cacheo en memoria.
    """
    if not text or not text.strip():
        return text

    clean_text = text.strip()
    if clean_text in _translation_cache:
        return _translation_cache[clean_text]

    try:
        from deep_translator import MyMemoryTranslator
        translator = MyMemoryTranslator(source='english', target='spanish')

        # Si el texto es corto (menor a 450 caracteres), traducir directamente
        if len(clean_text) <= 450:
            translated = translator.translate(clean_text)
            _translation_cache[clean_text] = translated
            return translated

        # Si el texto es largo (ej. resumen), dividirlo en oraciones o párrafos
        sentences = re.split(r'(?<=[.!?])\s+', clean_text)
        translated_parts = []
        current_chunk = ""

        for sent in sentences:
            if len(current_chunk) + len(sent) < 450:
                current_chunk += (" " if current_chunk else "") + sent
            else:
                if current_chunk:
                    part_tr = translator.translate(current_chunk)
                    translated_parts.append(part_tr)
                current_chunk = sent

        if current_chunk:
            part_tr = translator.translate(current_chunk)
            translated_parts.append(part_tr)

        result = " ".join(translated_parts)
        _translation_cache[clean_text] = result
        return result
    except Exception as e:
        logger.warning(f"Error al traducir al español: {e}. Se conservará el texto original.")
        return text

def translate_points_to_spanish(points: List[str]) -> List[str]:
    """
    Traduce una lista de puntos clave o hallazgos semánticos al español,
    preservando prefijos como '[75.2% Relevancia]' o viñetas.
    """
    if not points:
        return []

    translated_points = []
    prefix_pattern = r'^(\s*(?:•|-|\*|\[\d+(?:\.\d+)?%\s*Relevancia\])\s*)(.*)$'

    for p in points:
        match = re.match(prefix_pattern, p)
        if match:
            prefix = match.group(1)
            content = match.group(2)
            content_tr = translate_to_spanish(content)
            translated_points.append(f"{prefix}{content_tr}")
        else:
            translated_points.append(translate_to_spanish(p))

    return translated_points
