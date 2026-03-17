# Contenu du fichier membres_profil.py (à créer sur GitHub)
import pandas as pd

# Tes 10 membres avec leurs infos fixes
MEMBRES_FIXES = {
    'Didier': {
        'Avatar': 'https://storage.googleapis.com/notion-avatars/b/4/9/4f7c2a71a94d86b5155f9c42636a0d24_1603590500742.png',
        'Téléphone': '+41791234567',
        'Infos_Retrait': 'au bureau lundi',
        'Position': 'Colombier'
    },
    'Amélie': {
        'Avatar': 'https://storage.googleapis.com/notion-avatars/b/4/9/4f7c2a71a94d86b5155f9c42636a0d24_1603590500742.png',
        'Téléphone': '+41797654321',
        'Infos_Retrait': 'à mon domicile le soir',
        'Position': 'Colombier'
    },
    # AJOUTE LES 8 AUTRES ICI
    
}

# La liste des 12 avatars Notion que tu m'as envoyés (à remplir avec tes 12 liens)
AVATARS_LIST = [
    'https://storage.googleapis.com/notion-avatars/b/4/9/4f7c2a71a94d86b5155f9c42636a0d24_1603590500742.png', # Avatar 1
    # AJOUTE LES 11 AUTRES LIENS ICI
]

def get_membre_info(prenom):
    """Retourne les infos d'un membre à partir de son prénom (depuis le dictionnaire fixe)."""
    return MEMBRES_FIXES.get(prenom, None)

def get_liste_membres_fixes():
    """Retourne la liste des prénoms des membres fixes."""
    return list(MEMBRES_FIXES.keys())
