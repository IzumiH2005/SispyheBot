import os
import logging
import asyncio
from openai import OpenAI
from typing import Dict, Any, List, Optional
import re
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class PerplexityClient:
    def __init__(self):
        """Initialise le client Perplexity avec la clé API"""
        self.api_key = os.getenv('PERPLEXITY_API_KEY')
        if not self.api_key:
            raise ValueError("PERPLEXITY_API_KEY non trouvée dans les variables d'environnement")

        logger.info("Initialisation du client Perplexity")
        self.client = OpenAI(
            api_key=self.api_key,
            base_url="https://api.perplexity.ai"
        )

    async def search(self, query: str) -> Dict[str, Any]:
        """Effectue une recherche avec l'API Perplexity"""
        try:
            clean_query = query.strip()
            if not clean_query:
                return {"error": "La requête ne peut pas être vide"}

            logger.info(f"Recherche pour: {clean_query}")

            # Détecter si c'est une recherche de média
            media_keywords = ['anime', 'série', 'film', 'movie', 'tv show', 'season', 'épisode', 'saison', 'webtoon', 'manga']
            is_media_search = any(keyword in clean_query.lower() for keyword in media_keywords)

            # Configuration du prompt selon le type de recherche
            if is_media_search:
                system_content = """Tu es un assistant de recherche.
                Pour ce contenu média, trouve toutes les informations suivantes :
                - Titre complet et titre original
                - Type exact (anime, film, série TV, etc.)
                - Créateur(s) et équipe de production
                - Studio/Production
                - Année et période de diffusion
                - Genres
                - Nombre d'épisodes/durée
                - Description de l'univers
                - Synopsis complet
                - Personnages principaux
                - Thèmes majeurs
                - Adaptations et œuvres dérivées

                Fournis toutes les informations brutes sans les formater.
                Donne le maximum de détails possibles."""
            else:
                system_content = """Tu es un assistant de recherche.
                Fais une recherche approfondie et fournis :
                - Les informations principales
                - Les détails importants
                - Une analyse si pertinent

                Organise les informations de façon claire avec des paragraphes.
                Ajoute une ligne "Sources :" à la fin suivie des liens."""

            messages = [
                {
                    "role": "system",
                    "content": system_content
                },
                {
                    "role": "user",
                    "content": clean_query
                }
            ]

            logger.info("Envoi de la requête à l'API Perplexity...")
            response = await asyncio.to_thread(
                self.client.chat.completions.create,
                model="sonar-pro",
                messages=messages,
                temperature=0.2,
                top_p=0.9,
                stream=False
            )

            logger.info(f"Réponse reçue du modèle: {response.model}")
            logger.info(f"ID de la réponse: {response.id}")

            content = response.choices[0].message.content
            citations = []

            if hasattr(response, 'citations'):
                logger.info("Citations trouvées dans l'objet response")
                citations = response.citations
            else:
                logger.info("Extraction des URLs depuis le contenu")
                urls = re.findall(r'https?://[^\s<>"]+|www\.[^\s<>"]+', content)
                citations = [url for url in urls if url.startswith('http')]
                logger.info(f"Nombre d'URLs extraites: {len(citations)}")

            return {
                "response": content,
                "sources": citations,
                "is_media": is_media_search
            }

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Erreur dans la méthode search: {error_msg}")
            logger.exception("Détails complets de l'erreur:")

            if "quota" in error_msg.lower():
                return {"error": "Limite de requêtes atteinte"}
            elif "unauthorized" in error_msg.lower():
                return {"error": "Erreur d'authentification avec l'API"}
            elif "timeout" in error_msg.lower():
                return {"error": "La requête a pris trop de temps"}

            return {"error": f"Une erreur est survenue: {error_msg}"}