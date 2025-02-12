import logging
import httpx
import re
from bs4 import BeautifulSoup
from typing import List, Optional
from urllib.parse import urljoin, urlparse, unquote

logger = logging.getLogger(__name__)

class StartpageImageScraper:
    def __init__(self):
        """Initialise le scraper avec des paramètres optimisés"""
        self.base_url = "https://www.startpage.com"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9,fr;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0'
        }
        self.supported_extensions = ('.jpg', '.jpeg', '.png', '.gif', '.webp')

    def _is_valid_image_url(self, url: str) -> bool:
        """Vérifie si l'URL est valide et pointe vers une image supportée"""
        try:
            parsed = urlparse(url)
            if not all([parsed.scheme, parsed.netloc]):
                return False

            # Vérifier l'extension
            path_lower = parsed.path.lower()
            if any(path_lower.endswith(ext) for ext in self.supported_extensions):
                return True

            # Vérifier les motifs d'URL d'images courants
            image_patterns = ['/image/', '/images/', '/img/', '/photo/']
            return any(pattern in url.lower() for pattern in image_patterns)

        except Exception as e:
            logger.error(f"[DEBUG] Erreur validation URL {url}: {str(e)}")
            return False

    def _clean_image_url(self, url: str) -> Optional[str]:
        """Nettoie et normalise l'URL de l'image"""
        try:
            if not url or not isinstance(url, str):
                return None

            # Supprimer les espaces et caractères non désirés
            url = url.strip()
            url = re.sub(r'[\n\r\t]', '', url)

            # Décoder l'URL
            url = unquote(url)

            # Vérifier et corriger le protocole
            if not url.startswith(('http://', 'https://')):
                if url.startswith('//'):
                    url = 'https:' + url
                elif not url.startswith('/'):
                    url = 'https://' + url
                else:
                    return None

            # Vérifier si c'est une URL d'image valide
            if self._is_valid_image_url(url):
                return url

            return None

        except Exception as e:
            logger.error(f"[DEBUG] Erreur nettoyage URL {url}: {str(e)}")
            return None

    async def search_images(self, query: str, max_results: int = 3) -> List[str]:
        """Recherche des images sur Startpage"""
        try:
            logger.info(f"[DEBUG] Recherche d'images pour: {query}")

            # Paramètres de recherche
            params = {
                'q': query,
                't': 'images',
                'cat': 'pics',
                'language': 'english'
            }

            # Faire la requête avec gestion des redirections
            async with httpx.AsyncClient(headers=self.headers, follow_redirects=True, timeout=30.0) as client:
                # Première requête pour obtenir les cookies
                logger.info("[DEBUG] Envoi de la requête initiale à Startpage")
                response = await client.get(self.base_url)
                response.raise_for_status()

                # Requête de recherche d'images
                logger.info("[DEBUG] Envoi de la requête de recherche d'images")
                response = await client.get(f"{self.base_url}/sp/search", params=params)
                response.raise_for_status()

                logger.info(f"[DEBUG] Statut réponse: {response.status_code}")
                logger.info(f"[DEBUG] URL finale: {response.url}")

                # Parser le HTML
                soup = BeautifulSoup(response.text, 'html.parser')

                # Trouver toutes les images avec différents sélecteurs
                image_urls = set()
                selectors = [
                    'img[src]',
                    'img[data-src]',
                    '.image-result img',
                    '.image img',
                    '.thumbnail img'
                ]

                for selector in selectors:
                    for img in soup.select(selector):
                        for attr in ['src', 'data-src', 'data-original']:
                            if img.get(attr):
                                url = img[attr]
                                clean_url = self._clean_image_url(url)
                                if clean_url:
                                    logger.info(f"[DEBUG] URL trouvée: {clean_url}")
                                    image_urls.add(clean_url)
                                    if len(image_urls) >= max_results:
                                        break

                # Chercher aussi dans les liens qui pourraient contenir des images
                for link in soup.find_all('a', href=True):
                    href = link['href']
                    if self._is_valid_image_url(href):
                        clean_url = self._clean_image_url(href)
                        if clean_url:
                            logger.info(f"[DEBUG] URL trouvée dans lien: {clean_url}")
                            image_urls.add(clean_url)
                            if len(image_urls) >= max_results:
                                break

                logger.info(f"[DEBUG] Nombre d'URLs trouvées: {len(image_urls)}")
                return list(image_urls)[:max_results]

        except Exception as e:
            logger.error(f"[DEBUG] Erreur recherche: {str(e)}")
            return []