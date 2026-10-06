import os
import logging
from .pdf_reader import extract_text_from_pdf
from .docx_reader import extract_text_from_docx
from .article_parser import LLMArticleAnalyzer, LocalArticleAnalyzer, RuleBasedArticleAnalyzer, AnthropicArticleAnalyzer
from config import Config

logger = logging.getLogger(__name__)

def get_analyzer(provider=None, api_key=None):
    # Si hay clave desde la UI, tiene prioridad sobre .env
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
            
    # Si no hay UI, usamos .env
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
        # Fallback a Local o RuleBased
        try:
            # Intento simple de ver si la URL local responde
            import requests
            # Para Ollama es solo la base
            base_url = Config.LOCAL_LLM_URL.replace("/api/generate", "")
            response = requests.get(base_url, timeout=2)
            if response.status_code == 200:
                logger.info("Usando LocalArticleAnalyzer (Ollama)")
                return LocalArticleAnalyzer(url=Config.LOCAL_LLM_URL, model=Config.LOCAL_LLM_MODEL)
        except Exception:
            pass
            
        logger.info("Usando RuleBasedArticleAnalyzer (Fallback)")
        return RuleBasedArticleAnalyzer()

def process_file(file_path, original_filename, provider=None, api_key=None, keywords=None):
    """
    Procesa un único archivo y devuelve los datos estructurados.
    """
    ext = os.path.splitext(file_path)[1].lower()
    text = None
    metadata = {}
    
    if ext == '.pdf':
        text, metadata = extract_text_from_pdf(file_path)
    elif ext == '.docx':
        text, metadata = extract_text_from_docx(file_path)
    else:
        raise ValueError(f"Extensión no soportada: {ext}")
        
    if not text:
        raise ValueError("No se pudo extraer texto del documento.")
        
    analyzer = get_analyzer(provider=provider, api_key=api_key)
    data = analyzer.analyze(text, metadata, keywords=keywords)
    
    # Asegurar la estructura correcta
    resultado = {
        "Artículo": original_filename,
        "Nombre": data.get("nombre", "No identificado automáticamente"),
        "Autor": data.get("autor", "No identificado automáticamente"),
        "Año": data.get("año", "No identificado automáticamente"),
        "Resumen": data.get("resumen", "No identificado automáticamente"),
    }
    
    puntos_clave = data.get("puntos_clave", [])
    if isinstance(puntos_clave, list) and puntos_clave:
        puntos_format = "\n".join([f"• {p}" for p in puntos_clave])
        resultado["Punto clave más relevantes"] = puntos_format
    else:
        resultado["Punto clave más relevantes"] = "No identificado automáticamente"
        
    return resultado
