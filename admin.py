from dataclasses import dataclass
from typing import Dict, Optional

@dataclass
class Admin:
    user_id: int
    nickname: str
    aliases: list[str]

class AdminManager:
    def __init__(self):
        self.admins: Dict[int, Admin] = {
            580187559: Admin(
                user_id=580187559,
                nickname="Marceline",
                aliases=["Marcy", "Altaīr"]
            ),
            6419892672: Admin(
                user_id=6419892672,
                nickname="Daniel",
                aliases=["Créateur", "Izumi"]
            )
        }
    
    def is_admin(self, user_id: int) -> bool:
        """Vérifie si l'utilisateur est un admin"""
        return user_id in self.admins
    
    def get_admin(self, user_id: int) -> Optional[Admin]:
        """Récupère les informations d'un admin"""
        return self.admins.get(user_id)
    
    def get_nickname(self, user_id: int, username: str) -> str:
        """Récupère le surnom à utiliser pour l'utilisateur"""
        admin = self.get_admin(user_id)
        if admin:
            return admin.nickname
        return username
