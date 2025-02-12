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
            'Accept-Language': 'fr,fr-FR;q=0.8,en-US;q=0.5,en;q=0.3',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        # Patterns pour trouver des images dans différents formats de HTML
        self.fallback_patterns = [
            'data-src="([^"]+)"',
            'src="([^"]+)"',
            'background-image:\s*url\([\'"]?([^\'"\\)]+)[\'"]?\)',
            'data-original="([^"]+)"',
            'data-lazy-src="([^"]+)"',
            'data-image="([^"]+)"',
            'data-img="([^"]+)"',
            'data-poster="([^"]+)"'
        ]

    async def search_images(self, query: str, max_results: int = 5) -> List[str]:
        """Recherche des images sur Startpage avec une extraction améliorée"""
        try:
            search_url = f"{self.base_url}/images"
            params = {
                'q': query,
                't': 'images',
                'language': 'fr',
                'cat': 'pics',
                'sc': '2Ck1x9nGRgYT20'
            }

            async with httpx.AsyncClient(headers=self.headers, follow_redirects=True, timeout=30.0) as client:
                logger.info(f"Recherche d'images pour: {query}")
                response = await client.get(search_url, params=params)
                response.raise_for_status()

                soup = BeautifulSoup(response.text, 'html.parser')
                image_urls = set()  # Utiliser un set pour éviter les doublons

                # Liste étendue des sélecteurs CSS pour trouver des images
                selectors = [
                    '.image-result img[src]',
                    '.image-result img[data-src]',
                    '.image img[src]',
                    '.image img[data-src]',
                    'img.thumbnail[src]',
                    'img.thumbnail[data-src]',
                    'div[data-role="image"] img[src]',
                    'div[data-role="image"] img[data-src]',
                    '.image_container img[src]',
                    '.image_container img[data-src]',
                    'figure img[src]',
                    'figure img[data-src]',
                    '.gallery img[src]',
                    '.gallery img[data-src]'
                ]

                # Première passe avec les sélecteurs CSS
                for selector in selectors:
                    for element in soup.select(selector):
                        for attr in ['data-src', 'src', 'data-original', 'data-lazy-src', 'data-image', 'data-img']:
                            if element.has_attr(attr):
                                url = element[attr]
                                clean_url = self._clean_image_url(url)
                                if clean_url and self._is_valid_image_url(clean_url):
                                    image_urls.add(clean_url)
                                    if len(image_urls) >= max_results:
                                        break

                # Si pas assez d'images trouvées, essayer les patterns de fallback
                if len(image_urls) < max_results:
                    for pattern in self.fallback_patterns:
                        matches = re.finditer(pattern, response.text, re.IGNORECASE)
                        for match in matches:
                            url = match.group(1)
                            clean_url = self._clean_image_url(url)
                            if clean_url and self._is_valid_image_url(clean_url):
                                image_urls.add(clean_url)
                                if len(image_urls) >= max_results:
                                    break

                # Si toujours pas assez d'images, chercher dans les attributs style
                if len(image_urls) < max_results:
                    for element in soup.find_all(['div', 'a', 'span']):
                        if element.has_attr('style'):
                            style = element['style']
                            matches = re.finditer(r'url\([\'"]?([^\'")\s]+)[\'"]?\)', style)
                            for match in matches:
                                url = match.group(1)
                                clean_url = self._clean_image_url(url)
                                if clean_url and self._is_valid_image_url(clean_url):
                                    image_urls.add(clean_url)
                                    if len(image_urls) >= max_results:
                                        break

                logger.info(f"Nombre total d'images trouvées: {len(image_urls)}")
                # S'assurer qu'on retourne une liste même si aucune image n'est trouvée
                return list(image_urls)[:max_results] if image_urls else []

        except Exception as e:
            logger.error(f"Erreur lors de la recherche d'images: {e}")
            logger.exception("Détails de l'erreur:")
            return []

    def _is_valid_image_url(self, url: str) -> bool:
        """Vérifie si l'URL est valide et pointe vers une image"""
        if not isinstance(url, str):
            return False

        try:
            # Décoder l'URL si elle est encodée
            url = unquote(url)
            result = urlparse(url)

            if not all([result.scheme, result.netloc]):
                return False

            # Liste étendue des extensions d'images valides
            valid_extensions = (
                '.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp',
                '.tiff', '.svg', '.ico', '.heic', '.avif'
            )

            # Vérifier l'extension
            path_lower = result.path.lower()
            if any(path_lower.endswith(ext) for ext in valid_extensions):
                return True

            # Vérifier les patterns d'URL d'images courants
            image_patterns = [
                '/image/', '/images/', '/img/', '/photo/', '/picture/',
                'img=', 'image=', 'photo=', 'src=', 'source=',
                'cdn.', 'static.', 'media.', 'assets.', 'uploads.'
            ]

            url_lower = url.lower()
            return any(pattern in url_lower for pattern in image_patterns)

        except Exception as e:
            logger.warning(f"Erreur lors de la validation de l'URL {url}: {e}")
            return False

    def _clean_image_url(self, url: str) -> Optional[str]:
        """Nettoie et normalise l'URL de l'image"""
        if not isinstance(url, str):
            return None

        try:
            # Décoder l'URL si elle est encodée
            url = unquote(url)

            # Supprimer les paramètres de requête inutiles
            url = re.sub(r'\?(size|width|height|quality|w|h|q|format|resize)=[^&]*(&)?', '?', url)
            url = re.sub(r'\?&', '?', url)
            url = re.sub(r'\?$', '', url)

            # Nettoyer les caractères spéciaux
            url = url.strip()
            url = re.sub(r'[\n\r\t]', '', url)

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