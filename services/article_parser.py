import json
import logging
import re
try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

try:
    import anthropic
except ImportError:
    anthropic = None
import requests
from .semantic_search import semantic_search_engine
from .translator import detect_language, translate_to_spanish, translate_points_to_spanish

logger = logging.getLogger(__name__)

class ArticleAnalyzer:
    def analyze(self, text, metadata=None, keywords=None):
        """
        Recibe el texto del artículo (cuerpo sin referencias bibliográficas)
        y devuelve un diccionario con versiones originales y traducidas al español:
        {
            "idioma": "Inglés" | "Español",
            "nombre": "",
            "nombre_es": "",
            "autor": "",
            "año": "",
            "resumen": "",
            "resumen_es": "",
            "puntos_clave": [...],
            "puntos_clave_es": [...],
            "pasajes_semanticos": [...]
        }
        """
        pass

def ensure_spanish_translations(parsed: dict, text: str) -> dict:
    """
    Garantiza que si el documento está en inglés, los campos en español ('nombre_es',
    'resumen_es', 'puntos_clave_es') estén traducidos fielmente y no permanezcan en inglés
    ni se queden como 'No identificado automáticamente' si el campo original sí tiene contenido.
    """
    if not parsed:
        return parsed

    idioma = parsed.get("idioma")
    if not idioma or idioma not in ("Inglés", "Español"):
        idioma = "Inglés" if detect_language(text) == 'en' else "Español"
        parsed["idioma"] = idioma

    if idioma == "Inglés":
        # Título
        nombre = parsed.get("nombre", "")
        nombre_es = parsed.get("nombre_es", "")
        if nombre and nombre != "No identificado automáticamente":
            if not nombre_es or nombre_es == "No identificado automáticamente" or nombre_es == nombre:
                parsed["nombre_es"] = translate_to_spanish(nombre)
        else:
            parsed["nombre_es"] = "No identificado automáticamente"

        # Resumen
        resumen = parsed.get("resumen", "")
        resumen_es = parsed.get("resumen_es", "")
        if resumen and resumen != "No identificado automáticamente":
            if not resumen_es or resumen_es == "No identificado automáticamente" or resumen_es == resumen:
                parsed["resumen_es"] = translate_to_spanish(resumen)
        else:
            parsed["resumen_es"] = "No identificado automáticamente"

        # Puntos clave
        puntos = parsed.get("puntos_clave", [])
        puntos_es = parsed.get("puntos_clave_es", [])
        if puntos and puntos != ["No identificado automáticamente"]:
            if not puntos_es or puntos_es == ["No identificado automáticamente"] or puntos_es == puntos:
                parsed["puntos_clave_es"] = translate_points_to_spanish(puntos)
        else:
            parsed["puntos_clave_es"] = ["No identificado automáticamente"]
    else:
        # En español
        if "nombre_es" not in parsed or not parsed["nombre_es"] or parsed["nombre_es"] == "No identificado automáticamente":
            parsed["nombre_es"] = parsed.get("nombre", "No identificado automáticamente")
        if "resumen_es" not in parsed or not parsed["resumen_es"] or parsed["resumen_es"] == "No identificado automáticamente":
            parsed["resumen_es"] = parsed.get("resumen", "No identificado automáticamente")
        if "puntos_clave_es" not in parsed or not parsed["puntos_clave_es"] or parsed["puntos_clave_es"] == ["No identificado automáticamente"]:
            parsed["puntos_clave_es"] = parsed.get("puntos_clave", ["No identificado automáticamente"])

    return parsed


class LLMArticleAnalyzer(ArticleAnalyzer):
    def __init__(self, api_key, base_url=None, model_name="gpt-3.5-turbo-0125"):
        self.model_name = model_name
        kwargs = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
            
        if OpenAI is None:
            raise ImportError("El módulo 'openai' no está instalado. Ejecute 'pip install openai' para usar este modelo.")
        self.client = OpenAI(**kwargs)

    def analyze(self, text, metadata=None, keywords=None):
        semantic_matches = []
        if keywords:
            semantic_matches = semantic_search_engine.search(text, keywords, top_k=6)
            passages_context = "\n\n".join([
                f"[Pasaje {i+1} | Relevancia semántica: {m['relevance_pct']:.1f}%]:\n{m['text']}" 
                for i, m in enumerate(semantic_matches)
            ])
            keywords_instruction = f"""
        - El usuario realizó la siguiente consulta de BÚSQUEDA SEMÁNTICA en el documento: '{keywords}'.
        - A continuación se presentan los pasajes más relevantes identificados en el texto del documento:
{passages_context}
        - Extrae y sintetiza de 3 a 7 puntos clave que respondan directamente a la consulta del usuario, basándote en los pasajes anteriores y en el contenido del documento.
        - Incluye cifras, hallazgos empíricos, métricas y metodologías relevantes.
        - NO incluyas referencias bibliográficas ni citas de libros/artículos en la lista de autores.
        - Si el concepto no está presente en el documento, indícalo expresamente.
            """
        else:
            keywords_instruction = """
        - Generar entre 3 y 7 puntos clave extrayéndolos específicamente de la sección de "Discusión" y/o "Conclusiones" del artículo."""

        prompt = """
        Eres un asistente de investigación experto en análisis de literatura científica, búsqueda semántica y traducción académica.
        Analiza el siguiente texto extraído de un artículo académico (del cual ya se han excluido las referencias bibliográficas)
        y extrae la información requerida en formato JSON estricto.
        
        Instrucciones:
        1. Lee el contenido provisto antes de responder.
        2. Detecta el idioma en que está escrito el documento ("Inglés" o "Español").
        3. Si el artículo está en inglés, proporciona tanto los textos en su idioma original como su traducción fiel al español en los campos con sufijo '_es'. Si el artículo ya está en español, los campos con sufijo '_es' tendrán el mismo texto en español.
        4. Extrae únicamente información presente en el artículo; no inventes datos.
        5. Extrae el nombre (título), autor (separados por ;) y año de publicación (formato YYYY).
        6. Extrae el resumen original y su traducción al español.
        7. Para generar los "puntos_clave":""" + keywords_instruction + """
        8. Si un dato no está disponible, indica "No identificado automáticamente".
        
        El resultado debe ser estrictamente un JSON válido con la siguiente estructura:
        {
          "idioma": "Inglés" o "Español",
          "nombre": "Título original del artículo",
          "nombre_es": "Título traducido al español",
          "autor": "Autor 1; Autor 2",
          "año": "YYYY",
          "resumen": "Texto del resumen original...",
          "resumen_es": "Texto del resumen traducido al español...",
          "puntos_clave": [
            "Punto 1 en idioma original...",
            "Punto 2..."
          ],
          "puntos_clave_es": [
            "Punto 1 traducido al español...",
            "Punto 2 traducido al español..."
          ]
        }
        
        Texto del artículo:
        """
        
        max_chars = 18000 
        if len(text) > max_chars:
            text_to_analyze = text[:11000] + "\n\n...[SECCIONES INTERMEDIAS RESUMIDAS]...\n\n" + text[-7000:]
        else:
            text_to_analyze = text

        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You are a helpful academic research and translation assistant designed to output JSON."},
                    {"role": "user", "content": prompt + text_to_analyze}
                ],
                response_format={ "type": "json_object" }
            )
            
            content = response.choices[0].message.content
            parsed = json.loads(content)
            parsed["pasajes_semanticos"] = semantic_matches
            
            return ensure_spanish_translations(parsed, text)
        except Exception as e:
            logger.error(f"Error en LLMArticleAnalyzer: {e}")
            raise

class AnthropicArticleAnalyzer(ArticleAnalyzer):
    def __init__(self, api_key):
        if anthropic is None:
            raise ImportError("El módulo 'anthropic' no está instalado. Ejecute 'pip install anthropic' para usar este modelo.")
        self.client = anthropic.Anthropic(api_key=api_key)

    def analyze(self, text, metadata=None, keywords=None):
        semantic_matches = []
        if keywords:
            semantic_matches = semantic_search_engine.search(text, keywords, top_k=6)
            passages_context = "\n\n".join([
                f"[Pasaje {i+1} | Relevancia semántica: {m['relevance_pct']:.1f}%]:\n{m['text']}" 
                for i, m in enumerate(semantic_matches)
            ])
            keywords_instruction = f"""
        - El usuario realizó la siguiente consulta de BÚSQUEDA SEMÁNTICA en el documento: '{keywords}'.
        - A continuación se presentan los pasajes más relevantes identificados en el texto del documento:
{passages_context}
        - Extrae y sintetiza de 3 a 7 puntos clave que respondan directamente a la consulta del usuario, basándote en los pasajes anteriores y en el contenido del documento.
        - Incluye cifras, hallazgos empíricos, métricas y metodologías relevantes.
        - NO incluyas referencias bibliográficas ni citas de libros/artículos en la lista de autores.
        - Si el concepto no está presente en el documento, indícalo expresamente.
            """
        else:
            keywords_instruction = """
        - Generar entre 3 y 7 puntos clave extrayéndolos específicamente de la sección de "Discusión" y/o "Conclusiones" del artículo."""

        prompt = """
        Eres un asistente de investigación experto en análisis de literatura científica y traducción académica.
        Analiza el siguiente texto extraído de un artículo académico (del cual ya se han excluido las referencias bibliográficas)
        y extrae la información requerida en formato JSON estricto.
        
        Instrucciones:
        1. Lee el contenido provisto antes de responder.
        2. Detecta el idioma del documento ("Inglés" o "Español").
        3. Si está en inglés, traduce al español en los campos con sufijo '_es'. Si ya está en español, copia el texto en dichos campos.
        4. Extrae únicamente información presente en el artículo; no inventes datos.
        5. Extrae el nombre (título), autor (separados por ;) y año de publicación (formato YYYY).
        6. Extrae el resumen original y su traducción al español.
        7. Para generar los "puntos_clave":""" + keywords_instruction + """
        8. Si un dato no está disponible, indica "No identificado automáticamente".
        
        El resultado debe ser estrictamente un JSON válido con la siguiente estructura:
        {
          "idioma": "Inglés" o "Español",
          "nombre": "Título original",
          "nombre_es": "Título traducido al español",
          "autor": "Autor 1; Autor 2",
          "año": "YYYY",
          "resumen": "Resumen original...",
          "resumen_es": "Resumen traducido al español...",
          "puntos_clave": [
            "Punto 1 original...",
            "Punto 2..."
          ],
          "puntos_clave_es": [
            "Punto 1 traducido al español...",
            "Punto 2 traducido al español..."
          ]
        }
        
        Texto del artículo:
        """
        
        max_chars = 40000
        if len(text) > max_chars:
            text_to_analyze = text[:25000] + "\n\n...[SECCIONES INTERMEDIAS RESUMIDAS]...\n\n" + text[-15000:]
        else:
            text_to_analyze = text

        try:
            response = self.client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=2500,
                system="You are a helpful academic research and translation assistant designed to output JSON only.",
                messages=[
                    {"role": "user", "content": prompt + text_to_analyze}
                ]
            )
            
            content = response.content[0].text
            if content.startswith("```json"):
                content = content[7:-3]
            elif content.startswith("```"):
                content = content[3:-3]
                
            parsed = json.loads(content.strip())
            parsed["pasajes_semanticos"] = semantic_matches
            
            return ensure_spanish_translations(parsed, text)
        except Exception as e:
            logger.error(f"Error en AnthropicArticleAnalyzer: {e}")
            raise

class LocalArticleAnalyzer(ArticleAnalyzer):
    def __init__(self, url="http://localhost:11434/api/generate", model="llama3"):
        self.url = url
        self.model = model

    def analyze(self, text, metadata=None, keywords=None):
        semantic_matches = []
        if keywords:
            semantic_matches = semantic_search_engine.search(text, keywords, top_k=5)
            passages_context = "\n\n".join([
                f"[Pasaje {i+1} | Relevancia: {m['relevance_pct']:.1f}%]:\n{m['text']}" 
                for i, m in enumerate(semantic_matches)
            ])
            keywords_instruction = f"""
        - BÚSQUEDA SEMÁNTICA: '{keywords}'.
        - Pasajes relevantes del documento:
{passages_context}
        - Extrae de 3 a 5 puntos clave respondiendo a la búsqueda a partir de los pasajes. NO incluyas referencias bibliográficas."""
        else:
            keywords_instruction = """
        - Generar entre 3 y 5 puntos clave de las Conclusiones o Discusión."""

        prompt = f"""
        Eres un asistente experto en análisis científico. Extrae la información en formato JSON estricto incluyendo traducción a español:
        {keywords_instruction}
        Estructura requerida:
        {{
          "idioma": "Inglés" o "Español",
          "nombre": "Título original",
          "nombre_es": "Título en español",
          "autor": "Autor",
          "año": "YYYY",
          "resumen": "Resumen original",
          "resumen_es": "Resumen en español",
          "puntos_clave": ["Punto 1", "Punto 2"],
          "puntos_clave_es": ["Punto 1 en español", "Punto 2 en español"]
        }}
        Texto:
        """
        max_chars = 12000
        text_to_analyze = text[:max_chars]
        
        payload = {
            "model": self.model,
            "prompt": prompt + text_to_analyze,
            "stream": False,
            "format": "json"
        }
        
        try:
            response = requests.post(self.url, json=payload, timeout=60)
            response.raise_for_status()
            data = response.json()
            parsed = json.loads(data.get("response", "{}"))
            parsed["pasajes_semanticos"] = semantic_matches
            
            return ensure_spanish_translations(parsed, text)
        except Exception as e:
            logger.error(f"Error en LocalArticleAnalyzer: {e}")
            raise

class RuleBasedArticleAnalyzer(ArticleAnalyzer):
    """
    Analizador semántico y heurístico local con detección de idioma y traducción automática al español.
    """
    def analyze(self, text, metadata=None, keywords=None):
        data = {
            "idioma": "Español",
            "nombre": "No identificado automáticamente",
            "nombre_es": "No identificado automáticamente",
            "autor": "No identificado automáticamente",
            "año": "No identificado automáticamente",
            "resumen": "No identificado automáticamente",
            "resumen_es": "No identificado automáticamente",
            "puntos_clave": ["No identificado automáticamente"],
            "puntos_clave_es": ["No identificado automáticamente"],
            "pasajes_semanticos": []
        }
        
        lang = detect_language(text)
        data["idioma"] = "Inglés" if lang == 'en' else "Español"
        
        # 1. Metadatos del documento
        if metadata:
            if metadata.get('title'):
                data['nombre'] = metadata.get('title').strip()
            if metadata.get('author'):
                data['autor'] = metadata.get('author').strip()
        
        # 2. Extracción heurística de título y autor si no estaban en metadatos
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        if lines:
            if data['nombre'] == "No identificado automáticamente":
                for line in lines[:8]:
                    if len(line) > 15 and not re.match(r'^(?:vol|issn|isbn|doi|http|www|page|página)\b', line, re.I):
                        data["nombre"] = line[:200]
                        break
            
            if data['autor'] == "No identificado automáticamente" and data["nombre"] != "No identificado automáticamente":
                try:
                    title_index = lines.index(data["nombre"])
                    for i in range(title_index + 1, min(title_index + 6, len(lines))):
                        line_cand = lines[i]
                        if 5 < len(line_cand) < 150 and not re.match(r'^(?:abstract|resumen|introducción|introduction)\b', line_cand, re.I):
                            data["autor"] = line_cand
                            break
                except ValueError:
                    pass

        # 3. Extracción de año
        year_match = re.search(r'\b(19|20)\d{2}\b', text[:3000])
        if year_match:
            data["año"] = year_match.group(0)
            
        # 4. Extracción de resumen
        abstract_match = re.search(r'(?i)(?:abstract|resumen)\s*[:\.]?\s*(.*?)(?:\n\s*(?:introduction|introducción|keywords|palabras clave|\d+\.\s+Introducción)|\Z)', text[:6000], re.DOTALL)
        if abstract_match:
            resumen = abstract_match.group(1).strip()
            data["resumen"] = re.sub(r'\s+', ' ', resumen)[:1200]
        else:
            for p in text.split('\n\n')[:6]:
                p_clean = " ".join(p.split())
                if len(p_clean) > 120 and not p_clean.startswith(('http', 'doi', 'ISSN')):
                    data["resumen"] = p_clean[:1000]
                    break

        # 5. Búsqueda semántica / Puntos clave
        if keywords:
            semantic_results = semantic_search_engine.search(text, keywords, top_k=5)
            data["pasajes_semanticos"] = semantic_results
            
            if semantic_results:
                data["puntos_clave"] = semantic_search_engine.format_results_as_points(semantic_results)
            else:
                data["puntos_clave"] = [f"No se encontraron coincidencias semánticas relevantes para: '{keywords}'"]
        else:
            pattern = r'(?im)(?:^|\n)\s*(?:\d+\.?\s*)?(?:discussion and conclusions?|conclusions?|conclusiones|discusión|discussion)\s*(?::|\n)(.*?)(?:\n\s*(?:\d+\.?\s*)?(?:acknowledgements?|agradecimientos|anexos?|apéndice)\b|\Z)'
            conclusion_match = re.search(pattern, text[-30000:], re.DOTALL)
            
            target_text = conclusion_match.group(1).strip() if conclusion_match else text[-6000:]
            sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', target_text.replace('\n', ' ')) if len(s.strip()) > 45]
            
            if sentences:
                data["puntos_clave"] = sentences[:5]
            else:
                data["puntos_clave"] = ["No identificado automáticamente"]

        return ensure_spanish_translations(data, text)
