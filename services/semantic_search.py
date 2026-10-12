import re
import logging
from typing import List, Dict, Any, Optional
import numpy as np

logger = logging.getLogger(__name__)

class SemanticSearchEngine:
    _instance = None
    _model = None
    _model_failed = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SemanticSearchEngine, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if self._model is None and not self._model_failed:
            self._load_model()

    def _load_model(self):
        try:
            from sentence_transformers import SentenceTransformer
            logger.info("Cargando modelo de embeddings semánticos paraphrase-multilingual-MiniLM-L12-v2...")
            self._model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
            logger.info("Modelo de embeddings semánticos cargado con éxito.")
        except Exception as e:
            logger.warning(f"No se pudo cargar el modelo SentenceTransformer: {e}. Se utilizará TF-IDF + Similitud Coseno como motor semántico de respaldo.")
            self._model_failed = True
            self._model = None

    def chunk_text(self, text: str, max_words: int = 140, min_words: int = 15) -> List[str]:
        """
        Divide el cuerpo del texto en pasajes y oraciones coherentes para búsqueda semántica.
        """
        if not text:
            return []

        # Normalizar saltos de línea
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        
        # Primero intentar dividir por párrafos dobles
        raw_paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        chunks = []

        for para in raw_paragraphs:
            words = para.split()
            if len(words) <= max_words and len(words) >= min_words:
                chunks.append(para)
            elif len(words) > max_words:
                # Si el párrafo es muy largo, dividirlo en oraciones
                sentences = re.split(r'(?<=[.!?])\s+', para)
                current_chunk = []
                current_len = 0
                for sent in sentences:
                    sent = sent.strip()
                    if not sent:
                        continue
                    sent_words = len(sent.split())
                    if current_len + sent_words > max_words and current_chunk:
                        chunk_str = " ".join(current_chunk)
                        if len(chunk_str.split()) >= min_words:
                            chunks.append(chunk_str)
                        current_chunk = [sent]
                        current_len = sent_words
                    else:
                        current_chunk.append(sent)
                        current_len += sent_words
                if current_chunk:
                    chunk_str = " ".join(current_chunk)
                    if len(chunk_str.split()) >= min_words:
                        chunks.append(chunk_str)
            else:
                # Párrafo corto: solo agregar si tiene cierta sustancia
                if len(words) >= 8:
                    chunks.append(para)

        # Si por alguna razón no salieron suficientes chunks, dividir por oraciones generales
        if len(chunks) < 3:
            sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text.replace('\n', ' ')) if len(s.strip()) > 35]
            chunks = sentences

        return chunks

    def search(self, text: str, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Ejecuta la búsqueda semántica de la consulta en el texto del documento.
        Retorna una lista ordenada de los pasajes más relevantes con su puntuación de similitud.
        """
        if not text or not query or not query.strip():
            return []

        chunks = self.chunk_text(text)
        if not chunks:
            return []

        # Intentar búsqueda neuronal con SentenceTransformer
        if self._model is not None:
            try:
                from sentence_transformers import util
                query_emb = self._model.encode(query.strip(), convert_to_tensor=True)
                chunk_embs = self._model.encode(chunks, convert_to_tensor=True)
                scores = util.cos_sim(query_emb, chunk_embs)[0].cpu().numpy()

                results = []
                for idx, score in enumerate(scores):
                    # Solo considerar resultados con similitud positiva relevante
                    results.append({
                        "text": chunks[idx],
                        "score": float(score),
                        "relevance_pct": max(0.0, min(100.0, float(score) * 100))
                    })

                results.sort(key=lambda x: x["score"], reverse=True)
                return results[:top_k]
            except Exception as e:
                logger.error(f"Error en inferencia de SentenceTransformer: {e}. Usando fallback TF-IDF.")

        # Fallback de alta precisión con TF-IDF + Similitud Coseno N-Gram
        return self._search_tfidf(chunks, query, top_k)

    def _search_tfidf(self, chunks: List[str], query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.metrics.pairwise import cosine_similarity

            # Vectorizador con n-gramas para capturar contexto semántico de frases
            vectorizer = TfidfVectorizer(
                ngram_range=(1, 3),
                sublinear_tf=True,
                lowercase=True
            )
            all_texts = [query.strip()] + chunks
            tfidf_matrix = vectorizer.fit_transform(all_texts)
            
            sim_scores = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:])[0]
            
            results = []
            for idx, score in enumerate(sim_scores):
                results.append({
                    "text": chunks[idx],
                    "score": float(score),
                    "relevance_pct": max(0.0, min(100.0, float(score) * 100))
                })
                
            results.sort(key=lambda x: x["score"], reverse=True)
            return results[:top_k]
        except Exception as e:
            logger.error(f"Error en búsqueda semántica TF-IDF: {e}")
            return []

    def format_results_as_points(self, results: List[Dict[str, Any]], min_score: float = 0.15) -> List[str]:
        """
        Formatea los resultados semánticos en puntos clave legibles para el reporte.
        """
        if not results:
            return ["No se encontraron pasajes relevantes para la búsqueda en el contenido del documento."]

        points = []
        for res in results:
            score = res.get("score", 0.0)
            text = res.get("text", "").strip()
            # Limpiar saltos de línea internos
            clean_text = " ".join(text.split())
            if score >= min_score or len(points) == 0:
                pct = res.get("relevance_pct", score * 100)
                points.append(f"[{pct:.1f}% Relevancia] {clean_text}")

        if not points:
            return ["No se identificaron coincidencias conceptuales con suficiente relevancia en el texto."]

        return points

# Instancia global reutilizable
semantic_search_engine = SemanticSearchEngine()
