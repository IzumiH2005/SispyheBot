import os
import logging
from openai import OpenAI
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class FicheClient:
    def __init__(self):
        """Initialise le client pour la création de fiches d'animes/séries"""
        self.api_key = os.getenv('PERPLEXITY_API_KEY')
        if not self.api_key:
            raise ValueError("PERPLEXITY_API_KEY non trouvée dans les variables d'environnement")

        logger.info("Initialisation du client pour les fiches")
        self.client = OpenAI(
            api_key=self.api_key,
            base_url="https://api.perplexity.ai"
        )

    async def create_fiche(self, titre: str) -> Dict[str, Any]:
        """Crée une fiche détaillée pour un anime/série/webtoon"""
        try:
            if not titre.strip():
                return {"error": "Le titre ne peut pas être vide"}

            logger.info(f"Création d'une fiche pour: {titre}")

            # Configuration du prompt pour la recherche d'informations
            system_content = """Tu es un expert en anime, manga, séries et webtoons.
            Ta tâche est de créer une fiche détaillée et complète.

            Recherche et collecte TOUTES les informations suivantes :
            - Titre complet en français/anglais
            - Titre original en japonais
            - Type exact (anime, film, série TV, OVA, webtoon, etc.)
            - Créateur(s) et équipe de production
            - Studio/Production
            - Année et période de diffusion
            - Genres précis
            - Nombre d'épisodes/chapitres/durée
            - Description détaillée de l'univers
            - Synopsis complet
            - Personnages principaux (3-4 maximum) avec descriptions
            - Thèmes majeurs (3-4 maximum)
            - Adaptations et œuvres dérivées

            Retourne UNIQUEMENT les informations organisées dans ce format EXACT :

┌───────────────────────────────────────────────┐
│               ✦ [TITRE] ✦                    │
│              *[TITRE EN JAPONAIS]*            │
└───────────────────────────────────────────────┘

◈ **Type** : [Type]  
◈ **Créateur** : [Créateur]  
◈ **Studio** : [Studio]  
◈ **Année** : [Année]  
◈ **Genres** : [Genres]  
◈ **Épisodes** : [Nombre d'épisodes]  
◈ **Univers** : [Description de l'univers]  

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  
✦ **SYNOPSIS** ✦  
▪ [Résumé du synopsis]  

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  
✦ **PERSONNAGES PRINCIPAUX** ✦  
🔹 **[Nom du personnage]** – [Description]  
🔹 **[Nom du personnage]** – [Description]  
🔹 **[Nom du personnage]** – [Description]  

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  
✦ **THÈMES MAJEURS** ✦  
◈ [Thème 1]  
◈ [Thème 2]  
◈ [Thème 3]  

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  
✦ **ADAPTATIONS & ŒUVRES ANNEXES** ✦  
▪ [Manga/Anime/etc.]  
▪ [Manga/Anime/etc.]  

IMPORTANT :
1. Utilise EXACTEMENT ce format avec tous les caractères spéciaux
2. Remplace les [crochets] par les vraies informations
3. Garde les sections vides si pas d'information
4. Conserve la mise en forme Markdown (**, *, etc.)
5. Garde les lignes de séparation ━━━
6. N'ajoute rien d'autre que ce format"""

            messages = [
                {
                    "role": "system",
                    "content": system_content
                },
                {
                    "role": "user",
                    "content": f"Crée une fiche détaillée pour : {titre}"
                }
            ]

            logger.info("Envoi de la requête à l'API Perplexity")
            response = self.client.chat.completions.create(
                model="sonar-pro",
                messages=messages,
                temperature=0.2,
                top_p=0.9,
                stream=False
            )

            logger.info(f"Réponse reçue du modèle: {response.model}")
            logger.info(f"ID de la réponse: {response.id}")

            # Extraire le contenu et les citations
            content = response.choices[0].message.content
            citations = []

            if hasattr(response, 'citations'):
                logger.info("Citations trouvées dans l'objet response")
                citations = response.citations
            else:
                logger.info("Extraction des URLs depuis le contenu")
                # On garde les liens pour les ajouter à la fin
                citations = [url for url in response.choices[0].message.content.split() if url.startswith('http')]

            # Ajout des sources à la fin de la fiche
            if citations:
                content += "\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                content += "✦ **LIENS & RÉFÉRENCES** ✦\n"
                for source in citations:
                    content += f"🔗 {source}\n"

            return {
                "fiche": content,
                "sources": citations
            }

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Erreur lors de la création de la fiche: {error_msg}")
            logger.exception("Détails complets de l'erreur:")

            if "quota" in error_msg.lower():
                return {"error": "Limite de requêtes atteinte"}
            elif "unauthorized" in error_msg.lower():
                return {"error": "Erreur d'authentification avec l'API"}
            elif "timeout" in error_msg.lower():
                return {"error": "La requête a pris trop de temps"}

            return {"error": f"Une erreur est survenue: {error_msg}"}