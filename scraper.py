import logging
import httpx
import random
from typing import List, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

class GoogleImageScraper:
    def __init__(self):
        """Initialise le scraper avec l'API Google Custom Search"""
        self.api_keys = [
            "AIzaSyADh3SC8TxrhIXrARFNc_aubO1wxNmf-Cg",
            "AIzaSyBweH1s3Gbyh3CjQhVpWkGmNRNu0MjZbJY"
        ]
        self.search_engine_id = "635349c064b134fbd"
        self.base_url = "https://www.googleapis.com/customsearch/v1"
        self.supported_domains = ['zerochan.net', 'pinterest.com', 'pinimg.com']
        logger.info(f"[DEBUG] Initialisé avec {len(self.api_keys)} clés API")

    def _get_random_api_key(self) -> str:
        """Retourne une clé API au hasard pour la rotation"""
        api_key = random.choice(self.api_keys)
        logger.info(f"[DEBUG] Utilisation de la clé API: {api_key[:10]}...")
        return api_key

    def _is_valid_image_url(self, url: str) -> bool:
        """Vérifie si l'URL est valide et provient des domaines autorisés"""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            logger.debug(f"[DEBUG] Vérification du domaine: {domain}")

            # Vérifier le domaine
            if not any(supported_domain in domain for supported_domain in self.supported_domains):
                logger.debug(f"[DEBUG] Domaine non supporté: {domain}")
                return False

            # Vérifier si c'est une URL d'image
            path_lower = parsed.path.lower()
            image_extensions = ('.jpg', '.jpeg', '.png', '.gif', '.webp')
            is_image = any(path_lower.endswith(ext) for ext in image_extensions)

            if is_image:
                logger.debug(f"[DEBUG] URL d'image valide trouvée: {url}")
            else:
                logger.debug(f"[DEBUG] URL non valide (pas une image): {url}")

            return is_image

        except Exception as e:
            logger.error(f"[DEBUG] Erreur validation URL {url}: {str(e)}")
            return False

    async def search_images(self, query: str, max_results: int = 10) -> List[str]:
        """Recherche des images via l'API Google Custom Search"""
        try:
            logger.info(f"[DEBUG] Recherche d'images pour: {query}")

            # Paramètres de recherche
            params = {
                'key': self._get_random_api_key(),
                'cx': self.search_engine_id,
                'q': query,
                'searchType': 'image',
                'num': min(max_results, 10),  # Maximum 10 résultats par requête
                'safe': 'active'  # Filtre de contenu actif
            }

            logger.debug(f"[DEBUG] Paramètres de recherche: {params}")

            # Faire la requête
            async with httpx.AsyncClient(timeout=30.0) as client:
                logger.info(f"[DEBUG] Envoi de la requête à l'API Google Custom Search: {self.base_url}")
                response = await client.get(self.base_url, params=params)
                response.raise_for_status()
                logger.debug(f"[DEBUG] Réponse reçue avec status code: {response.status_code}")

                data = response.json()
                logger.debug(f"[DEBUG] Réponse API: {data}")

                if 'items' not in data:
                    logger.warning("[DEBUG] Aucun résultat trouvé dans la réponse")
                    if 'error' in data:
                        logger.error(f"[DEBUG] Erreur API: {data['error']}")
                    return []

                # Extraire et filtrer les URLs d'images
                image_urls = []
                for item in data['items']:
                    link = item.get('link')
                    if link and self._is_valid_image_url(link):
                        image_urls.append(link)
                        logger.info(f"[DEBUG] URL d'image valide ajoutée: {link}")
                    else:
                        logger.debug(f"[DEBUG] URL ignorée: {link}")

                    if len(image_urls) >= max_results:
                        break

                logger.info(f"[DEBUG] Nombre total d'URLs trouvées: {len(image_urls)}")
                return image_urls[:max_results]

        except Exception as e:
            logger.error(f"[DEBUG] Erreur lors de la recherche: {str(e)}", exc_info=True)
            return []