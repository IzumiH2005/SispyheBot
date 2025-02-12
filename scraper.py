import logging
import httpx
import re
from bs4 import BeautifulSoup
from typing import List, Optional
from urllib.parse import urljoin, urlparse

logger = logging.getLogger(__name__)

class StartpageImageScraper:
    def __init__(self):
        self.base_url = "https://www.startpage.com"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

    async def search_images(self, query: str, max_results: int = 5) -> List[str]:
        """
        Recherche des images sur Startpage et retourne leurs URLs
        """
        try:
            search_url = f"{self.base_url}/images"
            params = {
                'q': query,
                't': 'images',
                'language': 'fr'
            }

            async with httpx.AsyncClient(headers=self.headers, follow_redirects=True) as client:
                # Faire la requête initiale
                response = await client.get(search_url, params=params, timeout=30.0)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, 'html.parser')

                # Extraire les URLs des images
                image_urls = []
                image_elements = soup.select('.image')  # Sélecteur CSS pour les images

                for element in image_elements:
                    if len(image_urls) >= max_results:
                        break

                    try:
                        # Chercher l'URL de l'image dans différents attributs possibles
                        img_src = element.get('data-src') or element.get('src')
                        if img_src:
                            clean_url = self._clean_image_url(img_src)
                            if clean_url and self._is_valid_image_url(clean_url):
                                image_urls.append(clean_url)
                                logger.info(f"Image URL trouvée : {clean_url}")

                        # Chercher aussi dans les balises img imbriquées
                        img_tags = element.select('img')
                        for img in img_tags:
                            img_src = img.get('data-src') or img.get('src')
                            if img_src:
                                clean_url = self._clean_image_url(img_src)
                                if clean_url and self._is_valid_image_url(clean_url) and clean_url not in image_urls:
                                    image_urls.append(clean_url)
                                    logger.info(f"Image URL trouvée dans img tag : {clean_url}")

                    except Exception as e:
                        logger.warning(f"Erreur lors de l'extraction d'une image: {e}")
                        continue

                if not image_urls:
                    # Essayer des sélecteurs alternatifs
                    for selector in ['.image-result', 'img.thumbnail', '.thumbnail img']:
                        elements = soup.select(selector)
                        logger.info(f"Tentative avec le sélecteur {selector}: {len(elements)} éléments trouvés")
                        for element in elements:
                            if len(image_urls) >= max_results:
                                break
                            try:
                                img_src = element.get('data-src') or element.get('src')
                                if img_src:
                                    clean_url = self._clean_image_url(img_src)
                                    if clean_url and self._is_valid_image_url(clean_url) and clean_url not in image_urls:
                                        image_urls.append(clean_url)
                                        logger.info(f"Image URL trouvée avec sélecteur alternatif : {clean_url}")
                            except Exception as e:
                                logger.warning(f"Erreur avec sélecteur alternatif: {e}")
                                continue

                logger.info(f"Nombre total d'images trouvées : {len(image_urls)}")
                return image_urls

        except Exception as e:
            logger.error(f"Erreur lors de la recherche d'images sur Startpage: {e}")
            logger.exception("Détails de l'erreur:")
            return []

    def _is_valid_image_url(self, url: str) -> bool:
        """Vérifie si l'URL est valide et pointe vers une image"""
        if not isinstance(url, str):
            return False

        try:
            result = urlparse(url)
            if not all([result.scheme, result.netloc]):
                return False
        except Exception as e:
            logger.warning(f"URL invalide: {url}, erreur: {e}")
            return False

        # Vérifier l'extension
        valid_extensions = ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp')
        has_valid_extension = any(url.lower().endswith(ext) for ext in valid_extensions)

        if not has_valid_extension:
            # Vérifier si l'URL contient des paramètres d'image
            image_patterns = ['/image/', '/images/', 'img=', 'image=']
            if not any(pattern in url.lower() for pattern in image_patterns):
                return False

        return True

    def _clean_image_url(self, url: str) -> Optional[str]:
        """Nettoie et normalise l'URL de l'image"""
        if not isinstance(url, str):
            return None

        try:
            # Supprimer les paramètres de requête inutiles
            url = re.sub(r'\?.*$', '', url)

            # Assurer que l'URL commence par http ou https
            if not url.startswith(('http://', 'https://')):
                if url.startswith('//'):
                    url = 'https:' + url
                else:
                    url = 'https://' + url.lstrip('/')

            return url
        except Exception as e:
            logger.warning(f"Erreur lors du nettoyage de l'URL {url}: {e}")
            return None