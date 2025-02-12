import httpx
import logging
import os
import re
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

class PerplexityClient:
    def __init__(self):
        """Initialise le client Perplexity avec la clé API"""
        self.api_key = os.getenv('PERPLEXITY_API_KEY')
        if not self.api_key:
            raise ValueError("PERPLEXITY_API_KEY non trouvée dans les variables d'environnement")

        self.base_url = "https://api.perplexity.ai"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    async def _make_request(self, messages: list, model: str = "sonar-medium-online") -> Dict[Any, Any]:
        """Fait une requête optimisée à l'API Perplexity"""
        url = f"{self.base_url}/chat/completions"

        data = {
            "model": model,
            "messages": messages,
            "max_tokens": 1024,
            "temperature": 0.7,
            "top_p": 0.9,
            "stream": False,
            "presence_penalty": 0.0,
            "frequency_penalty": 0.0
        }

        try:
            logger.info(f"Envoi de la requête à Perplexity avec le modèle {model}")
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, headers=self.headers, json=data)

                if response.status_code == 400:
                    error_text = response.text
                    logger.error(f"Erreur 400 de l'API Perplexity: {error_text}")
                    return {"error": "La recherche n'a pas pu aboutir, essayez de reformuler votre question"}

                if response.status_code != 200:
                    logger.error(f"Erreur {response.status_code} de l'API: {response.text}")
                    return {"error": "Un problème est survenu avec le service de recherche"}

                response.raise_for_status()
                return response.json()

        except httpx.TimeoutException:
            logger.error("Timeout de la requête Perplexity")
            return {"error": "La recherche a pris trop de temps, veuillez réessayer"}
        except Exception as e:
            logger.error(f"Erreur lors de la requête Perplexity: {e}")
            if "quota" in str(e).lower():
                return {"error": "Limite de requêtes atteinte, veuillez réessayer plus tard"}
            return {"error": "Une erreur est survenue lors de la recherche"}

    async def search(self, query: str) -> Dict[str, str]:
        """Effectue une recherche avec l'API Perplexity"""
        try:
            # Nettoyer et formater la requête
            clean_query = query.strip()
            if not clean_query:
                return {"error": "La requête ne peut pas être vide"}

            system_prompt = """Tu es un assistant de recherche expert qui :
1. Répond de manière factuelle et directe
2. Se concentre sur les informations vérifiées et pertinentes
3. Structure la réponse de manière claire et concise
4. Cite ses sources quand c'est possible
5. Traduit toujours la réponse en français

Pour une recherche sur une personne :
- Commence par les informations essentielles (dates, nationalité, domaine)
- Mentionne les réalisations principales
- Ajoute un fait intéressant ou une citation notable

Format de réponse :
1. Présentation en 2-3 phrases
2. Points clés si nécessaire (max 3)
3. Sources en fin de réponse

Reste factuel et précis."""

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Recherche détaillée sur : {clean_query}"}
            ]

            logger.info(f"Démarrage de la recherche pour: {clean_query}")
            response = await self._make_request(messages)

            if "error" in response:
                logger.warning(f"Erreur retournée: {response['error']}")
                return response

            if "choices" not in response or not response["choices"]:
                logger.error("Réponse invalide de l'API Perplexity")
                return {"error": "Format de réponse invalide"}

            formatted_response = response["choices"][0]["message"]["content"].strip()

            # Vérifier que la réponse n'est pas vide
            if not formatted_response:
                return {"error": "Aucune information trouvée"}

            logger.info("Recherche terminée avec succès")
            return {"response": formatted_response}

        except Exception as e:
            logger.error(f"Erreur lors de la recherche: {e}")
            return {"error": "Une erreur inattendue est survenue"}

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