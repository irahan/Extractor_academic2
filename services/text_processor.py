import os
import logging
from .pdf_reader import extract_text_from_pdf
from .docx_reader import extract_text_from_docx
from .article_parser import LLMArticleAnalyzer, LocalArticleAnalyzer, RuleBasedArticleAnalyzer, AnthropicArticleAnalyzer
from .reference_remover import separate_references
from config import Config

logger = logging.getLogger(__name__)

def get_analyzer(provider=None, api_key=None):
    if api_key and provider != 'basic':
        if provider == 'openai':
            logger.info("Usando LLMArticleAnalyzer (OpenAI) desde UI")
            return LLMArticleAnalyzer(api_key=api_key)
        elif provider == 'anthropic':
            logger.info("Usando AnthropicArticleAnalyzer (Claude) desde UI")
            return AnthropicArticleAnalyzer(api_key=api_key)
        elif provider == 'deepseek':
            logger.info("Usando LLMArticleAnalyzer (DeepSeek) desde UI")
            return LLMArticleAnalyzer(api_key=api_key, base_url="https://api.deepseek.com/v1", model_name="deepseek-chat")
        elif provider == 'grok':
            logger.info("Usando LLMArticleAnalyzer (Grok) desde UI")
            return LLMArticleAnalyzer(api_key=api_key, base_url="https://api.x.ai/v1", model_name="grok-beta")
            
    if Config.ANTHROPIC_API_KEY:
        logger.info("Usando AnthropicArticleAnalyzer (Claude)")
        return AnthropicArticleAnalyzer(api_key=Config.ANTHROPIC_API_KEY)
    elif Config.OPENAI_API_KEY:
        logger.info(f"Usando LLMArticleAnalyzer (OpenAI/Compatible) - Modelo: {Config.OPENAI_MODEL_NAME}")
        return LLMArticleAnalyzer(
            api_key=Config.OPENAI_API_KEY, 
            base_url=Config.OPENAI_API_BASE, 
            model_name=Config.OPENAI_MODEL_NAME
        )
    else:
        try:
            import requests
            base_url = Config.LOCAL_LLM_URL.replace("/api/generate", "")
            response = requests.get(base_url, timeout=2)
            if response.status_code == 200:
                logger.info("Usando LocalArticleAnalyzer (Ollama)")
                return LocalArticleAnalyzer(url=Config.LOCAL_LLM_URL, model=Config.LOCAL_LLM_MODEL)
        except Exception:
            pass
            
        logger.info("Usando RuleBasedArticleAnalyzer con motor semántico y traducción")
        return RuleBasedArticleAnalyzer()

def process_file(file_path, original_filename, provider=None, api_key=None, keywords=None):
    """
    Procesa un único archivo, excluye la sección de referencias bibliográficas,
    ejecuta la búsqueda semántica y genera la traducción a español si está en inglés.
    """
    ext = os.path.splitext(file_path)[1].lower()
    raw_text = None
    metadata = {}
    
    if ext == '.pdf':
        raw_text, metadata = extract_text_from_pdf(file_path)
    elif ext == '.docx':
        raw_text, metadata = extract_text_from_docx(file_path)
    else:
        raise ValueError(f"Extensión no soportada: {ext}")
        
    if not raw_text:
        raise ValueError("No se pudo extraer texto del documento.")
        
    # EXCLUSIÓN CRÍTICA DE REFERENCIAS BIBLIOGRÁFICAS
    body_text, references_text, refs_removed = separate_references(raw_text)
    
    logger.info(f"[{original_filename}] Tamaño total: {len(raw_text)} chars | Cuerpo: {len(body_text)} chars | Referencias excluidas: {len(references_text)} chars ({'Sí' if refs_removed else 'No detectadas'}).")
    
    # Análisis, búsqueda semántica y traducción
    analyzer = get_analyzer(provider=provider, api_key=api_key)
    data = analyzer.analyze(body_text, metadata, keywords=keywords)
    
    # Formateo de puntos clave originales
    puntos_clave = data.get("puntos_clave", [])
    if isinstance(puntos_clave, list) and puntos_clave:
        puntos_format = "\n".join([f"• {p}" for p in puntos_clave])
    else:
        puntos_format = str(puntos_clave) if puntos_clave else "No identificado automáticamente"
        
    # Formateo de puntos clave en español
    puntos_clave_es = data.get("puntos_clave_es", [])
    if isinstance(puntos_clave_es, list) and puntos_clave_es:
        puntos_es_format = "\n".join([f"• {p}" for p in puntos_clave_es])
    else:
        puntos_es_format = puntos_format

    resultado = {
        "Artículo": original_filename,
        "Idioma": data.get("idioma", "Español"),
        "Nombre": data.get("nombre", "No identificado automáticamente"),
        "Nombre_ES": data.get("nombre_es", data.get("nombre", "No identificado automáticamente")),
        "Autor": data.get("autor", "No identificado automáticamente"),
        "Año": data.get("año", "No identificado automáticamente"),
        "Resumen": data.get("resumen", "No identificado automáticamente"),
        "Resumen_ES": data.get("resumen_es", data.get("resumen", "No identificado automáticamente")),
        "Punto clave más relevantes": puntos_format,
        "Puntos_Clave_ES": puntos_es_format,
        "Referencias_Excluidas": refs_removed,
        "Caracteres_Referencias_Excluidos": len(references_text),
        "Pasajes_Semanticos": data.get("pasajes_semanticos", []),
        "Consulta_Semantica": keywords if keywords else "N/A"
    }
        
    return resultado
