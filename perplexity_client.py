import os
import logging
from openai import OpenAI
from typing import Dict, Any, List, Optional
import httpx
import re

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

    async def _make_request(self, messages: list) -> Dict[Any, Any]:
        """Fait une requête optimisée à l'API Perplexity"""
        try:
            logger.info(f"Envoi de la requête à Perplexity avec les messages : {messages}")

            response = self.client.chat.completions.create(
                model="sonar-pro",
                messages=messages,
                temperature=0.1,  # Réduit pour des réponses plus précises
                presence_penalty=0.0,
                frequency_penalty=0.0,
                top_p=0.9
            )

            # Log detailed response information
            logger.debug(f"Réponse brute de l'API: {response}")
            logger.info(f"Modèle utilisé: {response.model}")
            logger.info(f"Nombre de choix: {len(response.choices)}")

            # Vérifier si la réponse est valide
            if not response or not response.choices:
                logger.error("Réponse invalide: pas de choices dans la réponse")
                raise ValueError("Réponse invalide de l'API")

            logger.info("Réponse valide reçue de l'API")
            return {
                "content": response.choices[0].message.content.strip()
            }

        except Exception as e:
            logger.error(f"Erreur détaillée lors de la requête Perplexity: {str(e)}")
            error_type = type(e).__name__
            error_msg = str(e).lower()

            if "quota" in error_msg:
                logger.error("Erreur de quota détectée")
                return {"error": "Limite de requêtes atteinte"}
            elif "unauthorized" in error_msg or "authentication" in error_msg:
                logger.error("Erreur d'authentification détectée")
                return {"error": "Erreur d'authentification avec l'API"}
            elif "invalid" in error_msg:
                logger.error(f"Requête invalide détectée: {str(e)}")
                return {"error": "Requête invalide"}

            logger.error(f"Erreur non catégorisée ({error_type}): {str(e)}")
            return {"error": "Erreur du service de recherche"}

    def _prepare_search_query(self, query: str) -> List[Dict[str, str]]:
        """Prépare la requête de recherche avec un prompt système approprié"""
        system_prompt = """Tu es un assistant de recherche expert qui doit :
1. Effectuer une recherche approfondie basée sur les mots-clés ou la phrase fournie
2. Analyser intelligemment l'intention de la recherche, qu'elle soit générale ou spécifique
3. Fournir des informations précises et vérifiées en français
4. Ne jamais demander de reformulation, mais plutôt extraire l'essentiel de la requête
5. Adapter la réponse au type de recherche :
   - Pour une personne : biographie et impact
   - Pour un concept : définition et contexte
   - Pour un sujet d'actualité : derniers développements
   - Pour une recherche générale : vue d'ensemble
6. Citer les sources pertinentes"""

        # Simplifier la requête pour l'API
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query}  # Envoi direct de la requête sans préfixe
        ]

        logger.info(f"Messages préparés pour la recherche: {messages}")
        return messages

    async def search(self, query: str) -> Dict[str, str]:
        """Effectue une recherche avec l'API Perplexity"""
        try:
            # Nettoyer la requête
            clean_query = query.strip()
            if not clean_query:
                logger.warning("Requête vide reçue")
                return {"error": "La requête ne peut pas être vide"}

            # Préparer et envoyer la requête
            messages = self._prepare_search_query(clean_query)
            logger.info(f"Démarrage de la recherche pour: {clean_query}")

            response = await self._make_request(messages)
            logger.debug(f"Réponse reçue: {response}")

            if "error" in response:
                logger.warning(f"Erreur retournée: {response['error']}")
                return response

            content = response.get("content")
            if not content:
                logger.error("Contenu de la réponse vide")
                return {"error": "Aucune information trouvée"}

            logger.info("Recherche terminée avec succès")
            return {"response": content}

        except Exception as e:
            logger.error(f"Erreur inattendue lors de la recherche: {str(e)}")
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