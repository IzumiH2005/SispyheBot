import os
import logging
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

    def _detect_time_filter(self, query: str) -> Optional[str]:
        """Détecte si la requête contient des indicateurs temporels"""
        # Mots-clés indiquant une recherche d'actualité
        recency_keywords = {
            # Actualités très récentes (24h)
            'recent': 'day',
            'récent': 'day',
            'dernière': 'day',
            'dernières': 'day',
            'actuel': 'day',
            'actuelles': 'day',
            "aujourd'hui": 'day',
            'dernier': 'day',
            'derniers': 'day',
            'récente': 'day',
            'récentes': 'day',
            'actualité': 'day',
            'actualités': 'day',
            'news': 'day',

            # Par semaine
            'cette semaine': 'week',
            'semaine dernière': 'week',
            'hebdomadaire': 'week',

            # Par mois
            'ce mois': 'month',
            'mois dernier': 'month',
            'mensuel': 'month',
            'mensuelle': 'month',

            # Par année
            'cette année': 'year',
            'année en cours': 'year',
            'annuel': 'year',
            'annuelle': 'year',
            '2025': 'year',  # année courante
            '2024': 'custom'  # année précédente
        }

        query_lower = query.lower()

        # Vérifier les mots-clés de récence
        for keyword, period in recency_keywords.items():
            if keyword in query_lower:
                logger.info(f"Filtre temporel trouvé: {period} pour le mot-clé: {keyword}")
                return period

        # Recherche de dates spécifiques (format: YYYY, MM/YYYY, DD/MM/YYYY)
        date_patterns = [
            r'\b\d{4}\b',  # YYYY
            r'\b\d{1,2}/\d{4}\b',  # MM/YYYY
            r'\b\d{1,2}/\d{1,2}/\d{4}\b'  # DD/MM/YYYY
        ]

        for pattern in date_patterns:
            if re.search(pattern, query):
                logger.info(f"Date spécifique trouvée dans la requête: {re.search(pattern, query).group()}")
                return 'custom'

        logger.info("Aucun filtre temporel détecté dans la requête")
        return None

    async def _make_request(self, messages: list, time_filter: Optional[str] = None) -> Dict[Any, Any]:
        """Fait une requête à l'API Perplexity avec gestion du temps et des sources"""
        try:
            logger.info("Structure complète de la requête:")
            logger.info(f"API Key présente: {'Oui' if self.api_key else 'Non'}")
            logger.info(f"Filtre temporel: {time_filter if time_filter else 'Aucun'}")

            # Configuration de base suivant exactement le blueprint
            request_kwargs = {
                "model": "sonar-pro",  # Utilisation cohérente du modèle
                "messages": messages,
                "temperature": 0.2,
                "top_p": 0.9
            }

            logger.info(f"Paramètres de la requête: {request_kwargs}")

            try:
                response = self.client.chat.completions.create(**request_kwargs)
                logger.info(f"Réponse reçue du modèle: {response.model}")
                logger.info(f"ID de la réponse: {response.id}")
            except Exception as e:
                logger.error(f"Erreur lors de l'appel API: {str(e)}")
                logger.error(f"Paramètres utilisés: {request_kwargs}")
                raise

            if not response.choices:
                logger.error("Pas de choix dans la réponse")
                raise ValueError("Réponse invalide: pas de choix disponible")

            content = response.choices[0].message.content
            # Extraire les citations si disponibles
            citations = []
            if hasattr(response, 'citations'):
                citations = response.citations

            return {
                "response": content,
                "sources": citations
            }

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Erreur lors de la requête Perplexity: {error_msg}")

            if "quota" in error_msg.lower():
                return {"error": "Limite de requêtes atteinte"}
            elif "unauthorized" in error_msg.lower() or "authentication" in error_msg.lower():
                return {"error": "Erreur d'authentification avec l'API"}
            elif "invalid" in error_msg.lower():
                return {"error": f"Requête invalide: {error_msg}"}

            return {"error": f"Erreur du service: {error_msg}"}

    def _prepare_search_query(self, query: str, time_filter: Optional[str] = None) -> List[Dict[str, str]]:
        """Prépare la requête de recherche avec un prompt système sophistiqué incluant le filtre temporel"""
        system_content = """Tu es un assistant qui donne des réponses précises et factuelles en français.

Je veux que tu effectues une recherche approfondie """

        # Ajouter des instructions temporelles si un filtre est spécifié
        if time_filter:
            if time_filter == 'day':
                system_content += "en te concentrant uniquement sur les informations des dernières 24 heures. "
            elif time_filter == 'week':
                system_content += "en te limitant aux informations de la semaine dernière. "
            elif time_filter == 'month':
                system_content += "en te limitant aux informations du mois dernier. "
            elif time_filter == 'year':
                system_content += "en te limitant aux informations de l'année en cours. "
            elif time_filter == 'custom':
                system_content += "en te concentrant sur la période spécifique mentionnée dans la requête. "

        system_content += """

Ton rôle est de :
1. Comprendre la requête et identifier les points clés
2. Effectuer une recherche approfondie sur ces points
3. Fournir une réponse factuelle et sourcée
4. Citer systématiquement tes sources

Format de réponse souhaité :
- Information principale
- Détails pertinents
- Sources utilisées (avec URLs)"""

        messages = [
            {
                "role": "system",
                "content": system_content
            },
            {
                "role": "user",
                "content": query
            }
        ]
        return messages

    async def search(self, query: str) -> Dict[str, Any]:
        """Effectue une recherche avec l'API Perplexity avec gestion du temps"""
        try:
            clean_query = query.strip()
            if not clean_query:
                return {"error": "La requête ne peut pas être vide"}

            # Détecter si un filtre temporel est nécessaire
            time_filter = self._detect_time_filter(clean_query)
            logger.info(f"Filtre temporel détecté: {time_filter}")

            messages = self._prepare_search_query(clean_query, time_filter)
            logger.info(f"Recherche pour: {clean_query}")

            result = await self._make_request(messages)

            if "error" in result:
                return result

            return {
                "response": result["response"],
                "sources": result["sources"]
            }

        except Exception as e:
            logger.error(f"Erreur dans la méthode search: {e}")
            return {"error": "Une erreur inattendue est survenue"}

    async def _make_request_with_retries(self, messages: list, max_retries: int = 2) -> Dict[Any, Any]:
        """Fait une requête avec tentatives de réessai"""
        for attempt in range(max_retries + 1):
            try:
                return await self._make_request(messages)
            except Exception as e:
                if attempt == max_retries:
                    raise
                logger.warning(f"Tentative {attempt + 1} échouée: {str(e)}")
                continue

    async def search_images(self, query: str, site: str) -> List[str]:
        """Recherche améliorée d'images sur différentes plateformes"""
        system_prompt = f"""Assistant de recherche d'images, votre tâche est de :
        1. Analyser la requête : "{query}" pour comprendre le type d'image recherché
        2. Rechercher sur {site} des images correspondant aux critères suivants :
           - Haute qualité visuelle
           - Pertinence par rapport à la requête
           - Diversité des résultats
        3. Fournir à la fois :
           - Les URLs directes des images (commençant par http/https)
           - Les URLs des pages contenant ces images
        4. Pour chaque image, décrire brièvement son contenu

        Format de réponse :
        [URL_IMAGE]|[URL_PAGE]|[DESCRIPTION]
        (une ligne par image)
        """

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Rechercher des images pour : {query}"}
        ]

        try:
            response = await self._make_request(messages)
            content = response.get("content", "")

            # Extraire les URLs avec regex amélioré
            urls = []
            for line in content.split('\n'):
                if '|' in line:
                    parts = line.split('|')
                    if len(parts) >= 2:
                        url = parts[0].strip()
                        if self._is_valid_image_url(url):
                            urls.append(url)

            # Backup : rechercher des URLs dans le texte si le format n'est pas respecté
            if not urls:
                urls = re.findall(r'https?://[^\s<>"]+?(?:jpg|jpeg|png|gif|webp)(?:[^\s<>"]*)', content, re.I)

            # Filtrer et nettoyer les URLs
            valid_urls = []
            for url in urls:
                cleaned_url = self._clean_image_url(url)
                if cleaned_url and self._is_valid_image_url(cleaned_url):
                    valid_urls.append(cleaned_url)

            logger.info(f"Trouvé {len(valid_urls)} images sur {site} pour la requête '{query}'")
            return valid_urls[:5]  # Retourner les 5 meilleures images

        except Exception as e:
            logger.error(f"Erreur lors de la recherche d'images sur {site}: {e}")
            return []

    def _is_valid_image_url(self, url: str) -> bool:
        """Vérifie si l'URL est une image valide avec une validation améliorée"""
        if not url:
            return False

        # Vérifier le format de l'URL
        url_pattern = re.compile(
            r'^https?://'  # http:// ou https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domaine
            r'localhost|'  # localhost
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # IPv4
            r'(?::\d+)?'  # port optionnel
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)

        if not url_pattern.match(url):
            return False

        # Vérifier l'extension
        image_extensions = ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp')
        if not any(url.lower().endswith(ext) for ext in image_extensions):
            return False

        # Vérifier les domaines connus
        allowed_domains = ('pinterest', 'zerochan', 'imgur', 'flickr', 'deviantart')
        if not any(domain in url.lower() for domain in allowed_domains):
            return False

        return True

    def _clean_image_url(self, url: str) -> Optional[str]:
        """Nettoie et normalise l'URL de l'image"""
        try:
            # Supprimer les paramètres de requête inutiles
            url = re.sub(r'\?.*$', '', url)

            # Assurer que l'URL commence par http ou https
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url

            return url
        except Exception:
            return None

    async def search_youtube(self, query: str) -> List[Dict[str, str]]:
        """Recherche améliorée de vidéos YouTube via Perplexity"""
        system_prompt = """Assistant de recherche YouTube expert, votre mission est de :
        1. Comprendre l'intention derrière la recherche
        2. Trouver les vidéos les plus pertinentes en considérant :
           - La qualité du contenu
           - La pertinence par rapport à la requête
           - La popularité et les avis
           - La durée appropriée
        3. Retourner les informations au format suivant pour chaque vidéo :
           [TITRE]|[URL]|[DURÉE]|[DESCRIPTION]
        """

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Rechercher les meilleures vidéos YouTube pour : {query}"}
        ]

        try:
            response = await self._make_request(messages)
            content = response.get("content", "")

            videos = []
            for line in content.split('\n'):
                if '|' in line:
                    parts = line.split('|')
                    if len(parts) >= 4: # Ensure enough parts for title, url, duration, description.
                        title = parts[0].strip()
                        url = parts[1].strip()

                        # Vérifier et nettoyer l'URL YouTube
                        if 'youtube.com/watch?v=' in url or 'youtu.be/' in url:
                            # Extraire l'ID de la vidéo
                            video_id = None
                            if 'youtube.com/watch?v=' in url:
                                video_id = url.split('watch?v=')[1].split('&')[0]
                            elif 'youtu.be/' in url:
                                video_id = url.split('youtu.be/')[1].split('?')[0]

                            if video_id:
                                clean_url = f"https://www.youtube.com/watch?v={video_id}"
                                videos.append({"title": title, "url": clean_url})

            logger.info(f"Trouvé {len(videos)} vidéos YouTube pour la requête '{query}'")
            return videos[:5]  # Retourner les 5 meilleures vidéos

        except Exception as e:
            logger.error(f"Erreur lors de la recherche YouTube: {str(e)}")
            return []

import httpx
import re