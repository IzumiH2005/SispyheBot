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

    async def _make_request(self, messages: List[Dict[str, str]], model: str = "mixtral-8x7b-instruct") -> Dict[Any, Any]:
        """Fait une requête à l'API Perplexity avec un modèle plus performant"""
        url = f"{self.base_url}/chat/completions"
        data = {
            "model": model,
            "messages": messages,
            "temperature": 0.7,  # Augmenté pour plus de créativité
            "top_p": 0.9,
            "max_tokens": 1024,  # Augmenté pour des réponses plus détaillées
            "presence_penalty": 0.5,  # Ajouté pour éviter la répétition
            "frequency_penalty": 0.5,
            "return_citations": True,
            "stream": False
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, headers=self.headers, json=data)
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Erreur lors de la requête Perplexity: {e}")
            raise

    async def search(self, query: str, context: Optional[str] = None) -> Dict[str, str]:
        """Effectue une recherche améliorée avec l'API Perplexity"""
        system_prompt = """Tu es Sisyphe, un assistant de recherche philosophique et érudit. Ta mission est de :
        1. Analyser la question en profondeur pour en extraire l'essence
        2. Fournir une réponse structurée, précise et sourcée
        3. Inclure des citations pertinentes
        4. Privilégier les sources académiques et fiables
        5. Traduire la réponse en français si nécessaire
        6. Organiser l'information de manière hiérarchique
        7. Mettre en évidence les concepts clés
        8. Terminer par une synthèse concise

        Format de réponse souhaité :
        1. Introduction (contexte)
        2. Points principaux (avec sources)
        3. Exemples ou illustrations
        4. Conclusion
        5. Sources utilisées
        """

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Recherche approfondie sur : {query}"}
        ]

        if context:
            messages[1]["content"] += f"\nContexte additionnel : {context}"

        try:
            response = await self._make_request(messages)

            content = response["choices"][0]["message"]["content"]
            citations = response.get("citations", [])

            formatted_response = content
            if citations:
                formatted_response += "\n\nSources:\n"
                formatted_response += "\n".join([f"- {citation}" for citation in citations])

            return {"response": formatted_response}

        except Exception as e:
            logger.error(f"Erreur lors de la recherche: {e}")
            return {"error": f"Une erreur est survenue: {str(e)}"}

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