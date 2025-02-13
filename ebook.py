import os
import logging
import asyncio
import tempfile
import requests
from openai import OpenAI
from typing import Dict, Any, Optional, Tuple
from urllib.parse import unquote

logger = logging.getLogger(__name__)

class EbookClient:
    def __init__(self):
        """Initialise le client pour la recherche et le téléchargement d'ebooks"""
        self.api_key = os.getenv('PERPLEXITY_API_KEY')
        if not self.api_key:
            raise ValueError("PERPLEXITY_API_KEY non trouvée dans les variables d'environnement")

        logger.info("Initialisation du client pour les ebooks")
        self.client = OpenAI(
            api_key=self.api_key,
            base_url="https://api.perplexity.ai"
        )

    def _extract_urls(self, text: str) -> list:
        """Extrait les URLs des résultats de recherche de manière plus exhaustive"""
        words = text.split()
        # Amélioration du filtrage des URLs
        urls = []
        for word in words:
            if word.startswith(('http://', 'https://')):
                # Nettoyage de l'URL
                url = word.strip('.,;:()[]{}\'\"')
                # Extensions de fichiers supportées
                supported_extensions = [
                    '.pdf', '.epub', '.mobi', '.txt', '.djvu',
                    '.azw', '.azw3', '.fb2', '.lit', '.prc',
                    '.rtf', '.doc', '.docx', '.cbz', '.cbr'
                ]
                # Domaines de confiance pour les livres
                trusted_domains = [
                    'archive.org', 'gutenberg.org', 'manybooks.net',
                    'feedbooks.com', 'standardebooks.org', 'fadedpage.com',
                    'wikisource.org', 'books.google.com', 'gallica.bnf.fr',
                    'europeana.eu', 'bibliotheque-numerique.fr', 'openlib.org',
                    'bibliotheque.numerique.gouv.fr', 'perseus.tufts.edu',
                    'digital.library.upenn.edu', 'sacred-texts.com'
                ]
                # Vérification des extensions et des domaines connus
                is_valid = any(ext in url.lower() for ext in supported_extensions)
                is_trusted = any(domain in url.lower() for domain in trusted_domains)

                if is_valid or is_trusted:
                    urls.append(url)
        return urls

    def _parse_command(self, command: str) -> Tuple[str, str]:
        """Parse la commande /ebook pour extraire le titre et la langue"""
        parts = command.strip().split()
        if len(parts) < 2:
            return "", "fr"  # Langue par défaut: français

        # Si la dernière partie est un code de langue de 2-3 caractères
        if len(parts[-1]) in [2, 3] and parts[-1].isalpha():
            return " ".join(parts[:-1]), parts[-1].lower()

        return " ".join(parts), "fr"

    async def _download_ebook(self, url: str, title: str) -> Optional[str]:
        """Télécharge l'ebook depuis l'URL donnée avec gestion améliorée des types de fichiers"""
        try:
            logger.info(f"Tentative de téléchargement depuis: {url}")
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(url, stream=True, timeout=30, headers=headers)

            if response.status_code == 200:
                # Détection intelligente du type de fichier
                content_type = response.headers.get('content-type', '').lower()
                content_disp = response.headers.get('content-disposition', '')
                logger.debug(f"Content-Type: {content_type}")
                logger.debug(f"Content-Disposition: {content_disp}")

                # Déterminer l'extension du fichier
                ext = None

                # Vérification du Content-Type
                content_type_map = {
                    'application/pdf': 'pdf',
                    'application/epub+zip': 'epub',
                    'application/x-mobipocket-ebook': 'mobi',
                    'text/plain': 'txt',
                    'application/msword': 'doc',
                    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'docx',
                    'application/rtf': 'rtf'
                }

                for mime_type, extension in content_type_map.items():
                    if mime_type in content_type:
                        ext = extension
                        break

                # Si l'extension n'est pas détectée par le Content-Type, essayer l'URL
                if not ext:
                    url_ext = url.split('.')[-1].lower()
                    valid_extensions = ['pdf', 'epub', 'mobi', 'txt', 'doc', 'docx', 'rtf']
                    if url_ext in valid_extensions:
                        ext = url_ext
                    else:
                        logger.warning(f"Extension non reconnue dans l'URL: {url_ext}")
                        ext = 'pdf'  # Extension par défaut

                logger.info(f"Extension détectée: {ext}")

                # Création du fichier temporaire
                with tempfile.NamedTemporaryFile(delete=False, suffix=f'.{ext}') as temp_file:
                    total_size = 0
                    try:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                temp_file.write(chunk)
                                total_size += len(chunk)
                                if total_size > 100 * 1024 * 1024:  # Limite de 100MB
                                    logger.warning(f"Fichier trop volumineux: {total_size/1024/1024:.2f}MB")
                                    os.unlink(temp_file.name)
                                    return None

                        # Renommer le fichier avec le titre
                        final_path = temp_file.name
                        safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).strip()
                        new_path = os.path.join(os.path.dirname(final_path), f"{safe_title}.{ext}")
                        os.rename(final_path, new_path)
                        logger.info(f"Fichier téléchargé avec succès: {new_path}")
                        return new_path

                    except Exception as e:
                        logger.error(f"Erreur pendant le téléchargement du fichier: {str(e)}")
                        if os.path.exists(temp_file.name):
                            os.unlink(temp_file.name)
                        return None

            else:
                logger.error(f"Échec du téléchargement. Status code: {response.status_code}")
                return None

        except requests.exceptions.Timeout:
            logger.error(f"Timeout lors du téléchargement depuis {url}")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Erreur lors du téléchargement depuis {url}: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Erreur inattendue lors du téléchargement: {str(e)}")
            return None

    async def search_and_download_ebook(self, command: str) -> Dict[str, Any]:
        """Recherche et télécharge un ebook avec une recherche plus exhaustive"""
        try:
            title, lang = self._parse_command(command)
            if not title:
                return {"error": "Veuillez spécifier un titre de livre"}

            logger.info(f"Recherche de l'ebook: {title} en {lang}")

            # Construction des termes de recherche en fonction de la langue
            lang_terms = {
                "fr": [
                    "livre ebook gratuit français",
                    "télécharger livre gratuit",
                    "bibliothèque numérique",
                    "archive numérique livre",
                    "ebook gratuit download",
                    "livre pdf gratuit"
                ],
                "en": [
                    "free ebook download",
                    "free book pdf",
                    "digital library",
                    "archive.org book",
                    "free online library",
                    "download free book"
                ],
                "es": [
                    "libro ebook gratis español",
                    "descargar libro gratis",
                    "biblioteca digital",
                    "libros electronicos gratis",
                    "descargar pdf gratis",
                    "archivo digital libro"
                ],
                "de": [
                    "kostenloses ebook deutsch",
                    "buch download kostenlos",
                    "digitale bibliothek",
                    "gratis bücher pdf",
                    "ebook archiv deutsch",
                    "elektronische bücher frei"
                ],
                "it": [
                    "ebook gratuito italiano",
                    "scaricare libro gratis",
                    "biblioteca digitale",
                    "libri elettronici gratuiti",
                    "download pdf gratis",
                    "archivio libri digitali"
                ],
                "pt": [
                    "livro ebook grátis português",
                    "baixar livro grátis",
                    "biblioteca digital",
                    "arquivo digital livro",
                    "pdf grátis download",
                    "ebooks gratuitos"
                ]
            }
            search_terms = lang_terms.get(lang, lang_terms["fr"])

            # Construire le prompt pour une recherche plus exhaustive
            messages = [
                {
                    "role": "system",
                    "content": f"""Tu es un expert en recherche de livres numériques. 
                    Recherche spécifiquement le livre "{title}" en {lang}.
                    Concentre-toi uniquement sur les liens de téléchargement direct (PDF, EPUB, MOBI, etc.).
                    Ignore les sites commerciaux et les plateformes payantes.
                    Retourne UNIQUEMENT les URLs de téléchargement, une par ligne.
                    N'inclus PAS de texte explicatif."""
                }
            ]

            # Effectuer plusieurs recherches avec différents termes
            all_urls = set()
            for search_term in search_terms:
                messages.append({
                    "role": "user",
                    "content": f'{title} {search_term}'
                })

                logger.info(f"Envoi de la requête à l'API Perplexity avec le terme: {search_term}")
                response = await asyncio.wait_for(
                    asyncio.to_thread(
                        self.client.chat.completions.create,
                        model="sonar-pro",
                        messages=messages,
                        temperature=0.1,
                        stream=False
                    ),
                    timeout=45.0
                )

                content = response.choices[0].message.content
                urls = self._extract_urls(content)
                all_urls.update(urls)
                messages.pop()  # Retirer le dernier message pour la prochaine recherche

            if not all_urls:
                return {"error": f"Aucun lien de téléchargement trouvé pour '{title}'"}

            # Essayer de télécharger depuis chaque URL jusqu'à ce qu'un téléchargement réussisse
            for url in all_urls:
                file_path = await self._download_ebook(url, title)
                if file_path:
                    return {
                        "success": True,
                        "file_path": file_path,
                        "title": title,
                        "original_url": url
                    }

            return {"error": "Impossible de télécharger l'ebook depuis les liens trouvés"}

        except asyncio.TimeoutError:
            logger.error("Timeout lors de la recherche de l'ebook")
            return {"error": "La recherche prend trop de temps. Veuillez réessayer."}
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Erreur lors de la recherche de l'ebook: {error_msg}")
            logger.exception("Détails complets de l'erreur:")

            if "quota" in error_msg.lower():
                return {"error": "Limite de requêtes atteinte"}
            elif "unauthorized" in error_msg.lower():
                return {"error": "Erreur d'authentification avec l'API"}

            return {"error": f"Une erreur est survenue: {error_msg}"}