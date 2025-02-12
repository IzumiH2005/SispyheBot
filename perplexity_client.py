import os
import httpx
import logging
import re
from typing import List, Optional, Dict, Any
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

class PerplexityClient:
    def __init__(self):
        self.api_key = os.getenv('PERPLEXITY_API_KEY')
        if not self.api_key:
            raise ValueError("PERPLEXITY_API_KEY non trouvée dans les variables d'environnement")

        self.base_url = "https://api.perplexity.ai"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    async def _make_request(self, messages: List[Dict[str, str]], model: str = "llama-3.1-sonar-small-128k-online") -> Dict[Any, Any]:
        """Fait une requête à l'API Perplexity avec une meilleure gestion des erreurs"""
        url = f"{self.base_url}/search"

        # Extraire la requête du dernier message utilisateur
        query = next((msg["content"] for msg in reversed(messages) if msg["role"] == "user"), "")
        logger.info(f"Requête à envoyer: {query}")

        data = {
            "query": query,
            "follow_up": True,
            "temperature": 0.7,
            "max_tokens": 2048,
            "focus": ["news", "wiki", "arxiv", "web"],
            "search_depth": "advanced",
            "context_level": "detailed"
        }

        logger.info(f"Envoi de la requête à {url} avec les données: {data}")

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                logger.debug(f"Headers utilisés: {self.headers}")
                response = await client.post(url, headers=self.headers, json=data)
                logger.info(f"Code de statut de la réponse: {response.status_code}")

                response_text = response.text
                logger.info(f"Réponse brute reçue: {response_text[:500]}...")  # Log premiers 500 caractères

                response.raise_for_status()
                response_json = response.json()
                logger.info(f"Structure de la réponse JSON: {list(response_json.keys())}")
                return response_json

        except httpx.HTTPStatusError as e:
            logger.error(f"Erreur HTTP lors de la requête Perplexity: {e.response.status_code}")
            if e.response.status_code == 400:
                logger.error(f"Détails de l'erreur 400: {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Erreur lors de la requête Perplexity: {e}")
            raise

    async def search(self, query: str, context: Optional[str] = None) -> Dict[str, str]:
        """Effectue une recherche améliorée avec l'API Perplexity"""
        system_prompt = """Tu es Sisyphe, un assistant de recherche érudit. Ta mission est de :

1. Pour TOUTE recherche :
   - Analyser en profondeur et fournir une réponse détaillée
   - Reformuler la requête si nécessaire pour plus d'informations
   - Traduire en français tout contenu en anglais
   - Citer les sources utilisées
   - Ne jamais dire qu'aucun résultat n'a été trouvé, chercher plus largement"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query}
        ]

        if context:
            messages[1]["content"] += f"\nContexte additionnel : {context}"

        try:
            logger.info(f"Démarrage de la recherche pour la requête: {query}")
            response = await self._make_request(messages)

            if not response:
                logger.error("Réponse vide de l'API Perplexity")
                return {"error": "Réponse vide de l'API"}

            logger.info(f"Clés disponibles dans la réponse: {list(response.keys())}")

            # Vérifier la structure de la réponse
            if "text" in response:
                formatted_response = response["text"]
                logger.info("Utilisation de la clé 'text' pour la réponse")
            elif "answer" in response:
                formatted_response = response["answer"]
                logger.info("Utilisation de la clé 'answer' pour la réponse")
            elif "choices" in response and response["choices"]:
                formatted_response = response["choices"][0].get("message", {}).get("content", "")
                logger.info("Utilisation de la structure choices/message/content pour la réponse")
            else:
                logger.error(f"Structure de réponse inattendue: {response}")
                return {"error": "Format de réponse inattendu"}

            # Traitement des sources
            if "sources" in response and response["sources"]:
                logger.info(f"Sources trouvées: {len(response['sources'])}")
                formatted_response += "\n\nSources :\n"
                formatted_response += "\n".join([
                    f"- {source.get('title', 'Source')} : {source.get('url', '#')}"
                    for source in response["sources"]
                ])
            elif "citations" in response:
                logger.info(f"Citations trouvées: {len(response['citations'])}")
                formatted_response += "\n\nSources :\n"
                formatted_response += "\n".join([f"- {citation}" for citation in response["citations"]])

            logger.info("Réponse formatée avec succès")
            return {"response": formatted_response}

        except Exception as e:
            logger.error(f"Erreur lors de la recherche: {e}")
            logger.exception("Détails de l'erreur:")
            return {"error": "Une erreur est survenue lors de la recherche. Veuillez réessayer."}

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
            content = response["choices"][0]["message"]["content"]

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
            content = response["choices"][0]["message"]["content"]

            videos = []
            for line in content.split('\n'):
                if '|' in line:
                    parts = line.split('|')
                    if len(parts) >= 2:
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
            logger.error(f"Erreur lors de la recherche YouTube: {e}")
            return []