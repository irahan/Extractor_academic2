import json
import logging
import re
from openai import OpenAI
import anthropic
import requests

logger = logging.getLogger(__name__)

class ArticleAnalyzer:
    def analyze(self, text, metadata=None, keywords=None):
        """
        Recibe el texto del artículo y devuelve un diccionario con:
        {
            "nombre": "",
            "autor": "",
            "año": "",
            "resumen": "",
            "puntos_clave": ["", "", ""]
        }
        """
        pass

class LLMArticleAnalyzer(ArticleAnalyzer):
    def __init__(self, api_key, base_url=None, model_name="gpt-3.5-turbo-0125"):
        self.model_name = model_name
        
        # Si hay base_url (ej. para DeepSeek, Grok, etc), lo pasamos al cliente de OpenAI
        kwargs = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
            
        self.client = OpenAI(**kwargs)

    def analyze(self, text, metadata=None, keywords=None):
        keywords_instruction = ""
        if keywords:
            keywords_instruction = f"""
        - Localiza toda la información relacionada con las siguientes palabras clave: '{keywords}'.
        - Identifica las secciones donde aparece o se trata el concepto, aunque se use un sinónimo o término relacionado.
        - Incluye cifras, resultados y conclusiones relevantes cuando existan relacionadas a las palabras clave.
        - Si una palabra clave no aparece en el texto, indícalo explícitamente en los puntos clave."""
        else:
            keywords_instruction = """
        - Generar entre 3 y 7 puntos clave extrayéndolos Específicamente de la sección de "Discusión" y/o "Conclusiones" del artículo."""

        prompt = """
        Eres un asistente de investigación experto en análisis de literatura científica.
        Analiza el siguiente texto extraído de un artículo académico y extrae la información requerida en formato JSON estricto.
        
        Instrucciones:
        1. Lee el artículo completo antes de responder.
        2. Extrae únicamente información que esté en el artículo; no inventes datos.
        3. Extrae el nombre (título), autor (separados por ;) y año de publicación (formato YYYY).
        4. Extrae el resumen original. Si no hay resumen explícito, intenta identificar el párrafo inicial que funcione como resumen.
        5. Para generar los "puntos_clave":""" + keywords_instruction + """
        6. Si un dato no está disponible, indica "No identificado automáticamente".
        
        El resultado debe ser estrictamente un JSON válido con la siguiente estructura:
        {
          "nombre": "Título del artículo",
          "autor": "Autor 1; Autor 2",
          "año": "YYYY",
          "resumen": "Texto del resumen...",
          "puntos_clave": [
            "Punto 1...",
            "Punto 2..."
          ]
        }
        
        Texto del artículo (truncado si es muy largo):
        """
        
        # Limitar el texto a los primeros y últimos N caracteres para no exceder el contexto
        max_chars = 15000 
        if len(text) > max_chars:
            text_to_analyze = text[:10000] + "\n\n...[TEXTO OMITIDO]...\n\n" + text[-5000:]
        else:
            text_to_analyze = text

        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant designed to output JSON."},
                    {"role": "user", "content": prompt + text_to_analyze}
                ],
                response_format={ "type": "json_object" }
            )
            
            content = response.choices[0].message.content
            return json.loads(content)
        except Exception as e:
            logger.error(f"Error en LLMArticleAnalyzer: {e}")
            raise

class AnthropicArticleAnalyzer(ArticleAnalyzer):
    def __init__(self, api_key):
        self.client = anthropic.Anthropic(api_key=api_key)

    def analyze(self, text, metadata=None, keywords=None):
        keywords_instruction = ""
        if keywords:
            keywords_instruction = f"""
        - Localiza toda la información relacionada con las siguientes palabras clave: '{keywords}'.
        - Identifica las secciones donde aparece o se trata el concepto, aunque se use un sinónimo o término relacionado.
        - Incluye cifras, resultados y conclusiones relevantes cuando existan relacionadas a las palabras clave.
        - Si una palabra clave no aparece en el texto, indícalo explícitamente en los puntos clave."""
        else:
            keywords_instruction = """
        - Generar entre 3 y 7 puntos clave extrayéndolos Específicamente de la sección de "Discusión" y/o "Conclusiones" del artículo."""

        prompt = """
        Eres un asistente de investigación experto en análisis de literatura científica.
        Analiza el siguiente texto extraído de un artículo académico y extrae la información requerida en formato JSON estricto.
        
        Instrucciones:
        1. Lee el artículo completo antes de responder.
        2. Extrae únicamente información que esté en el artículo; no inventes datos.
        3. Extrae el nombre (título), autor (separados por ;) y año de publicación (formato YYYY).
        4. Extrae el resumen original. Si no hay resumen explícito, intenta identificar el párrafo inicial que funcione como resumen.
        5. Para generar los "puntos_clave":""" + keywords_instruction + """
        6. Si un dato no está disponible, indica "No identificado automáticamente".
        
        El resultado debe ser estrictamente un JSON válido con la siguiente estructura (no agregues nada más antes o después):
        {
          "nombre": "Título del artículo",
          "autor": "Autor 1; Autor 2",
          "año": "YYYY",
          "resumen": "Texto del resumen...",
          "puntos_clave": [
            "Punto 1...",
            "Punto 2..."
          ]
        }
        
        Texto del artículo (truncado si es muy largo):
        """
        
        max_chars = 40000 # Claude soporta ventanas más grandes
        if len(text) > max_chars:
            text_to_analyze = text[:25000] + "\n\n...[TEXTO OMITIDO]...\n\n" + text[-15000:]
        else:
            text_to_analyze = text

        try:
            response = self.client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=2000,
                system="You are a helpful assistant designed to output JSON only.",
                messages=[
                    {"role": "user", "content": prompt + text_to_analyze}
                ]
            )
            
            content = response.content[0].text
            # Limpiar posible markdown
            if content.startswith("```json"):
                content = content[7:-3]
            elif content.startswith("```"):
                content = content[3:-3]
                
            return json.loads(content.strip())
        except Exception as e:
            logger.error(f"Error en AnthropicArticleAnalyzer: {e}")
            raise

class LocalArticleAnalyzer(ArticleAnalyzer):
    def __init__(self, url="http://localhost:11434/api/generate", model="llama3"):
        self.url = url
        self.model = model

    def analyze(self, text, metadata=None, keywords=None):
        keywords_instruction = ""
        if keywords:
            keywords_instruction = f"""
        - Localiza toda la información relacionada con las siguientes palabras clave: '{keywords}'.
        - Identifica las secciones donde aparece o se trata el concepto, aunque se use un sinónimo o término relacionado.
        - Incluye cifras, resultados y conclusiones relevantes cuando existan.
        - Si una palabra clave no aparece, indícalo explícitamente."""
        else:
            keywords_instruction = """
        - Generar entre 3 y 7 puntos clave extrayéndolos Específicamente de la sección de "Discusión" y/o "Conclusiones" del artículo."""

        prompt = """
        Eres un asistente de investigación experto en análisis de literatura científica.
        Analiza el siguiente texto extraído de un artículo académico y extrae la información requerida en formato JSON estricto.
        
        Instrucciones:
        1. Lee el artículo completo antes de responder.
        2. Extrae únicamente información que esté en el artículo; no inventes datos.
        3. Extrae el "nombre" (título), "autor" (separados por ;), "año" (YYYY) y "resumen".
        4. Para generar los "puntos_clave":""" + keywords_instruction + """
        5. Si no encuentras algo, pon "No identificado automáticamente". Solo responde con el JSON.
        
        Texto:
        """
        max_chars = 10000
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
            return json.loads(data.get("response", "{}"))
        except Exception as e:
            logger.error(f"Error en LocalArticleAnalyzer: {e}")
            raise

class RuleBasedArticleAnalyzer(ArticleAnalyzer):
    """
    Fallback usando expresiones regulares cuando no hay API configurada.
    """
    def analyze(self, text, metadata=None, keywords=None):
        data = {
            "nombre": "No identificado automáticamente",
            "autor": "No identificado automáticamente",
            "año": "No identificado automáticamente",
            "resumen": "No identificado automáticamente",
            "puntos_clave": ["No identificado automáticamente"]
        }
        
        # Usar metadata si está disponible
        if metadata:
            if metadata.get('title'):
                data['nombre'] = metadata.get('title').strip()
            if metadata.get('author'):
                data['autor'] = metadata.get('author').strip()
        
        # Intento básico de extraer nombre (título) y autor si no están en metadata
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        if lines:
            if data['nombre'] == "No identificado automáticamente":
                for line in lines[:5]:
                    if len(line) > 15:
                        data["nombre"] = line[:200]
                        break
            
            if data['autor'] == "No identificado automáticamente" and data["nombre"] != "No identificado automáticamente":
                try:
                    title_index = lines.index(data["nombre"])
                    for i in range(title_index + 1, min(title_index + 5, len(lines))):
                        if 5 < len(lines[i]) < 150:
                            data["autor"] = lines[i]
                            break
                except ValueError:
                    pass

        # Intento básico de extraer año
        year_match = re.search(r'\b(19|20)\d{2}\b', text[:2000])
        if year_match:
            data["año"] = year_match.group(0)
            
        # Intento básico de extraer resumen
        abstract_match = re.search(r'(?i)(?:abstract|resumen)(.*?)(?:introduction|introducción|keywords|palabras clave)', text[:5000], re.DOTALL)
        if abstract_match:
            resumen = abstract_match.group(1).strip()
            # Limpiar saltos de línea
            data["resumen"] = re.sub(r'\s+', ' ', resumen)[:1000]
            
        # Intento de extraer puntos clave de las conclusiones o discusión
        pattern = r'(?i)\n\s*(?:\d+\.?\s*)?(?:discussion and conclusions?|conclusions?|conclusiones|discusión|discussion)\s*\n(.*?)(?:\n\s*(?:\d+\.?\s*)?(?:acknowledgements?|agradecimientos|references|referencias|bibliography)\s*\n)'
        conclusion_match = re.search(pattern, text[-25000:], re.DOTALL)
        
        if keywords:
            # Dividir TODO el texto por puntos y tomar las oraciones
            # Limpiamos los saltos de línea para que las oraciones no estén cortadas
            clean_text = text.replace('\n', ' ')
            sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', clean_text) if len(s.strip()) > 40]
            
            # Filtrar oraciones que contengan alguna de las palabras clave (ignorando mayúsculas)
            kw_list = [k.strip().lower() for k in keywords.split(',')]
            filtered_sentences = []
            
            # Usamos un conjunto (set) para no repetir oraciones exactamente iguales
            seen = set()
            for s in sentences:
                if s not in seen:
                    s_lower = s.lower()
                    if any(kw in s_lower for kw in kw_list):
                        filtered_sentences.append(s)
                        seen.add(s)
            
            if filtered_sentences:
                data["puntos_clave"] = filtered_sentences[:5]
            else:
                data["puntos_clave"] = [f"La palabra clave no aparece."]
        else:
            if conclusion_match:
                conclusion_text = conclusion_match.group(1).strip()
                sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', conclusion_text) if len(s.strip()) > 40]
                if sentences:
                    data["puntos_clave"] = sentences[:5]  # Tomar hasta 5 oraciones clave largas
                else:
                    data["puntos_clave"] = ["No identificado automáticamente"]
            else:
                data["puntos_clave"] = ["No identificado automáticamente"]
            
        return data
