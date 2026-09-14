import pandas as pd

from models import Noeud
from config import PYLONES_CSV_PATH


def charger_pylones_fixes(filepath: str = PYLONES_CSV_PATH):
    """
    Charge les pylônes fixes existants depuis un fichier CSV et
    retourne la liste des Noeud correspondants.

    Le CSV est attendu avec (au minimum) les colonnes :
    ID, Code_Pylone, Nom_Site, Operateur, Region, District,
    Commune, Hauteur_Metres, Latitude, Longitude.

    Paramètre
    ---------
    filepath : str
        Chemin vers le fichier CSV des pylônes fixes.

    Retour
    ------
    list[Noeud]
        Liste des nœuds représentant les pylônes fixes.
    """

    df = pd.read_csv(filepath)
    pylones = []

    for ligne in df.itertuples():
        noeud = Noeud(
            ID=int(ligne.ID),
            Latitude=float(ligne.Latitude),
            Longitude=float(ligne.Longitude),
            Code_Pylone=ligne.Code_Pylone,
            Nom_Site=ligne.Nom_Site,
            Operateur=ligne.Operateur,
            Region=ligne.Region,
            District=ligne.District,
            Commune=ligne.Commune,
            Hauteur=float(ligne.Hauteur_Metres),
            type="fixe",
        )
        pylones.append(noeud)

    return pylones
