"""
main.py

Point d'entrée qui enchaîne les deux algorithmes du projet :

1) COUVERTURE (couverture.py) : parmi une grille de positions LoRa
   candidates générée automatiquement autour des pylônes fixes
   existants, choisit lesquelles déployer pour couvrir au mieux
   (MCLP) ou entièrement (SCP) les zones mal desservies, selon
   config.OPTIMIZATION_MODE.

2) ROUTAGE (dijkstra.py / routage.py) : une fois le réseau final
   connu (pylônes fixes + modules retenus par la couverture), simule
   l'envoi d'un message d'un LoRa vers un autre et affiche le chemin
   emprunté.

Données d'entrée
----------------
Le CSV de config.PYLONES_CSV_PATH (data/pylones_fixes.csv) contient
UNIQUEMENT les pylônes fixes existants : pas de LoRa dedans, puisque
c'est justement l'algorithme de couverture qui détermine leur nombre
et leur position.

Comme aucun fichier de "zones à couvrir" n'existe dans le projet,
elles sont générées automatiquement : une grille de points est posée
sur la zone géographique couverte par les pylônes fixes (+ une marge
tout autour), et on ne garde que les points hors de portée du réseau
existant -> ce sont les zones "mal desservies". Les candidats LoRa
sont une grille similaire, plus dense, sur la même zone.
"""
import math
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import math

import config
from models import Noeud
import couverture as cv
from dijkstra import construire_graphe, dijkstra
from routage import yen_depuis_noeuds


KM_PAR_DEGRE_LAT = 111.32  # longueur d'1° de latitude (40 008 km / 360)
ID_CANDIDATS_DEPART = 1000  # pour ne jamais entrer en collision avec un ID de pylône fixe
MAX_POINTS_GRILLE = 60  # garde-fou pour ne pas générer un problème d'optimisation énorme


def titre(texte):
    print("\n" + "=" * 60)
    print(texte)
    print("=" * 60)


# ============================================================
# 1. DONNÉES : pylônes fixes réels, avec repli de démonstration
# ============================================================

def filtrer_pylones_valides(pylones):
    """
    Écarte les pylônes dont Latitude/Longitude ne sont pas des nombres
    exploitables (NaN, valeurs manquantes dans le CSV, etc.).

    Sans ce filtrage, un seul NaN dans le CSV suffit à casser tout le
    calcul de grille : la moyenne des latitudes (lat_ref) devient NaN,
    puis math.ceil(NaN) lève ValueError bien plus loin dans le script,
    loin de la ligne du CSV réellement en cause.
    """

    valides = []
    for p in pylones:
        if math.isnan(p.Latitude) or math.isnan(p.Longitude):
            print(f"  ! pylône ignoré (coordonnées invalides) : "
                  f"ID={p.ID}, Nom_Site={p.Nom_Site!r}")
        else:
            valides.append(p)
    return valides


def charger_pylones_fixes_ou_demo():
    """
    Essaie data_loader.charger_pylones_fixes() (config.PYLONES_CSV_PATH,
    ton CSV réel de pylônes fixes). Si le fichier n'existe pas encore,
    génère 3 pylônes fictifs pour que le script reste exécutable tel quel.
    """

    try:
        from data_loader import charger_pylones_fixes
        pylones = charger_pylones_fixes()
        if pylones:
            return pylones, True
    except Exception as e:
        print(f"(pylônes fixes introuvables ({e!s}) -> jeu de démonstration)")

    lat0, lon0 = -18.8792, 47.5079  # Antananarivo
    pas = (0.5 * config.DMAX) / KM_PAR_DEGRE_LAT  # 0.5*DMAX : pylônes déjà connectés entre eux

    pylones = [
        Noeud(ID=1, Latitude=lat0, Longitude=lon0, Nom_Site="Pylone_Analakely",
              type="fixe", batterie=100.0, buffer=5.0),
        Noeud(ID=2, Latitude=lat0 + pas, Longitude=lon0, Nom_Site="Pylone_Ivandry",
              type="fixe", batterie=95.0, buffer=10.0),
        Noeud(ID=3, Latitude=lat0 + 2 * pas, Longitude=lon0, Nom_Site="Pylone_Alarobia",
              type="fixe", batterie=90.0, buffer=15.0),
    ]
    return pylones, False


# ============================================================
# 2. GÉNÉRATION AUTOMATIQUE DE LA GRILLE (zones + candidats)
# ============================================================

def _calculer_bbox(pylones_fixes, marge_km):
    """
    Rectangle englobant (lat_min, lat_max, lon_min, lon_max) des
    pylônes fixes, élargi de `marge_km` de chaque côté pour regarder
    aussi juste au-delà du réseau existant.
    """

    lats = [n.Latitude for n in pylones_fixes]
    lons = [n.Longitude for n in pylones_fixes]
    lat_ref = sum(lats) / len(lats)

    # 1° de longitude vaut KM_PAR_DEGRE_LAT * cos(latitude) km : les
    # méridiens se rapprochent en s'éloignant de l'équateur.
    km_par_degre_lon = KM_PAR_DEGRE_LAT * math.cos(math.radians(lat_ref))

    marge_lat = marge_km / KM_PAR_DEGRE_LAT
    marge_lon = marge_km / km_par_degre_lon

    return (
        min(lats) - marge_lat, max(lats) + marge_lat,
        min(lons) - marge_lon, max(lons) + marge_lon,
        lat_ref,
    )


def _generer_grille(bbox, pas_km, max_points):
    """
    Pose une grille régulière de points sur le rectangle `bbox`, avec
    un pas de `pas_km` kilomètres. Si le nombre de points dépasserait
    `max_points`, le pas est automatiquement agrandi (le problème
    d'optimisation reste de taille raisonnable pour la démo -- avec un
    vrai solveur pulp installé, tu peux augmenter max_points).

    Retour
    ------
    list[tuple[float, float]]
        Liste de (latitude, longitude).
    """

    lat_min, lat_max, lon_min, lon_max, lat_ref = bbox

    km_par_degre_lon = KM_PAR_DEGRE_LAT * math.cos(math.radians(lat_ref))
    pas_lat = pas_km / KM_PAR_DEGRE_LAT
    pas_lon = pas_km / km_par_degre_lon

    n_lat = max(1, math.ceil((lat_max - lat_min) / pas_lat) + 1)
    n_lon = max(1, math.ceil((lon_max - lon_min) / pas_lon) + 1)

    if n_lat * n_lon > max_points:
        # on agrandit le pas dans les mêmes proportions pour les deux
        # axes, de façon à repasser sous max_points
        facteur = math.sqrt((n_lat * n_lon) / max_points)
        pas_lat *= facteur
        pas_lon *= facteur
        n_lat = max(1, math.ceil((lat_max - lat_min) / pas_lat) + 1)
        n_lon = max(1, math.ceil((lon_max - lon_min) / pas_lon) + 1)

    points = []
    for i in range(n_lat):
        lat = lat_min + i * pas_lat
        for j in range(n_lon):
            lon = lon_min + j * pas_lon
            points.append((lat, lon))

    return points


def generer_zones_et_candidats_auto(pylones_fixes, max_points=MAX_POINTS_GRILLE):
    """
    Génère automatiquement :

    - les ZONES à couvrir : une grille au pas de `config.DMAX` (une
      zone représente une cellule de la taille de la portée radio),
      dont on ne garde QUE les points hors de portée de tous les
      pylônes fixes existants (les zones déjà desservies n'ont pas
      besoin d'un nouveau module).

    - les CANDIDATS LoRa : une grille plus dense, au pas de
      `0.6 * config.DMAX` (des positions rapprochées pour laisser de
      vrais choix à l'optimiseur), en écartant celles trop proches
      (< 0.3*DMAX) d'un pylône fixe existant, où déployer un nouveau
      module serait redondant.

    La marge autour du rectangle englobant des pylônes fixes est
    `config.DMAX`, pour regarder aussi juste au-delà du réseau actuel.

    population des zones : 1 par défaut (aucune donnée démographique
    fournie) -> MCLP maximise alors simplement le NOMBRE de zones
    couvertes. Remplace `"population": 1` par une vraie donnée dès que
    tu en as une.
    """

    bbox = _calculer_bbox(pylones_fixes, marge_km=config.DMAX)

    # --- zones : grille au pas de DMAX, seulement les points hors de portée ---
    points_zones = _generer_grille(bbox, pas_km=config.DMAX, max_points=max_points)

    zones = []
    for i, (lat, lon) in enumerate(points_zones):
        zone = {"id": f"Z{i + 1}", "Latitude": lat, "Longitude": lon, "population": 1}
        deja_desservie = any(
            cv._distance_noeud_zone(pylone, zone) <= config.DMAX
            for pylone in pylones_fixes
        )
        if not deja_desservie:
            zones.append(zone)

    # --- candidats : grille plus dense, en écartant les doublons de pylônes existants ---
    points_candidats = _generer_grille(bbox, pas_km=0.6 * config.DMAX, max_points=max_points)

    candidats = []
    prochain_id = ID_CANDIDATS_DEPART
    for lat, lon in points_candidats:
        candidat = Noeud(
            ID=prochain_id, Latitude=lat, Longitude=lon,
            Nom_Site=f"Candidat_{prochain_id}", type="candidat",
            batterie=100.0, buffer=0.0,
        )
        trop_proche_existant = any(
            pylone.calculer_distance(candidat) < 0.3 * config.DMAX
            for pylone in pylones_fixes
        )
        if not trop_proche_existant:
            candidats.append(candidat)
            prochain_id += 1

    return zones, candidats


# ============================================================
# 3. PROGRAMME PRINCIPAL
# ============================================================

def main():

    # --------------------------------------------------------
    # Étape 1 : réseau existant
    # --------------------------------------------------------

    titre("1. RÉSEAU EXISTANT (pylônes fixes)")

    pylones_fixes, donnees_reelles = charger_pylones_fixes_ou_demo()
    source_donnees = config.PYLONES_CSV_PATH if donnees_reelles else "démonstration"
    print(f"Source : {source_donnees}  ({len(pylones_fixes)} pylône(s) chargé(s))\n")

    if donnees_reelles:
        pylones_fixes = filtrer_pylones_valides(pylones_fixes)
        if not pylones_fixes:
            print("Aucun pylône avec des coordonnées valides, arrêt.")
            return

    for p in pylones_fixes:
        print(f"  - {p}")

    # --------------------------------------------------------
    # Étape 2 : génération automatique de la grille (zones + candidats)
    # --------------------------------------------------------

    titre("2. GÉNÉRATION DE LA GRILLE (zones à couvrir + candidats LoRa)")

    zones, candidats = generer_zones_et_candidats_auto(pylones_fixes)

    print(f"pas zones = {config.DMAX:.2f} km, pas candidats = {0.6 * config.DMAX:.2f} km, "
          f"marge = {config.DMAX:.2f} km")
    print(f"{len(zones)} zone(s) mal desservie(s) trouvée(s), "
          f"{len(candidats)} position(s) candidate(s) générée(s)")

    if not zones:
        print("\nAucune zone mal desservie : le réseau fixe couvre déjà tout le secteur analysé.")
        noeuds_retenus = []
    elif not candidats:
        print("\nAucune position candidate disponible (toutes trop proches d'un pylône existant).")
        noeuds_retenus = []
    else:

        # ----------------------------------------------------
        # Étape 3 : algorithme de couverture
        # ----------------------------------------------------

        titre("3. ALGORITHME DE COUVERTURE")
        print(f"mode = {config.OPTIMIZATION_MODE}, dmax = {config.DMAX:.2f} km, "
              f"budget = {config.BUDGET_P_MODULES} module(s)\n")

        candidats_par_id = {n.ID: n for n in candidats}

        try:
            resultat = cv.analyser_couverture(zones, candidats)
        except ImportError as e:
            # pulp n'est pas installé : impossible de résoudre le MCLP/SCP.
            # Pour que le script reste démonstratif de bout en bout (y compris
            # le routage), repli sur une sélection naïve : les
            # `BUDGET_P_MODULES` premiers candidats, SANS optimisation réelle.
            print(f"({e!s})")
            print("-> sélection de secours (sans optimisation) pour la suite du script.\n")
            noeuds_retenus = candidats[: config.BUDGET_P_MODULES]
            for n in noeuds_retenus:
                print(f"  - {n.Nom_Site} (ID={n.ID}) : lat={n.Latitude:.4f}, lon={n.Longitude:.4f}")
        else:
            resultat_algo = resultat["mclp"] if resultat["mclp"] is not None else resultat["scp"]
            nom_algo = "MCLP" if resultat["mclp"] is not None else "SCP"

            print(f"{nom_algo} -> statut : {resultat_algo['statut']}")

            if resultat_algo["statut"] != "Optimal":
                print("Aucune solution trouvée, arrêt.")
                return

            print(f"Nombre de nouveaux modules LoRa retenus : {resultat_algo['nombre_noeuds']}")
            if "population_couverte" in resultat_algo:
                print(f"Zones couvertes : {resultat_algo['population_couverte']:.0f}/{len(zones)} "
                      f"({resultat_algo['taux_couverture'] * 100:.1f} %)")
            print()

            for id_ in resultat_algo["noeuds_selectionnes"]:
                n = candidats_par_id[id_]
                print(f"  - {n.Nom_Site} (ID={n.ID}) : lat={n.Latitude:.4f}, lon={n.Longitude:.4f}")

            noeuds_retenus = [candidats_par_id[id_] for id_ in resultat_algo["noeuds_selectionnes"]]

    # --------------------------------------------------------
    # Étape 4 : réseau final = pylônes fixes + modules retenus
    # --------------------------------------------------------

    titre("4. RÉSEAU FINAL (pylônes fixes + modules retenus)")

    reseau = pylones_fixes + noeuds_retenus
    print(f"Total : {len(reseau)} nœud(s)\n")
    for n in reseau:
        print(f"  - {n}")

    if len(reseau) < 2:
        print("\nPas assez de nœuds pour simuler un envoi de message.")
        return

    # --------------------------------------------------------
    # Étape 5 : routage d'un message
    # --------------------------------------------------------

    titre("5. ROUTAGE D'UN MESSAGE")

    source, destination = reseau[0], reseau[-1]
    print(f"{source.Nom_Site or source.ID} veut envoyer un message à "
          f"{destination.Nom_Site or destination.ID}\n")

    graphe = construire_graphe(reseau)
    cout, chemin_ids = dijkstra(graphe, source.ID, destination.ID)

    if not chemin_ids:
        print("Aucun chemin possible : le réseau n'est pas assez dense "
              "(certains LoRa sont hors de portée les uns des autres).")
        return

    noeuds_par_id = {n.ID: n for n in reseau}
    noms_chemin = [noeuds_par_id[id_].Nom_Site or str(id_) for id_ in chemin_ids]

    print(f"Chemin le plus court ({len(chemin_ids)} nœuds, {cout:.2f} km) :")
    print("  " + "  ->  ".join(noms_chemin))

    # --------------------------------------------------------
    # Étape 6 (bonus) : chemins alternatifs, algorithme de Yen
    # --------------------------------------------------------

    titre("6. CHEMINS ALTERNATIFS (Yen)")

    k = min(3, len(reseau))
    chemins = yen_depuis_noeuds(reseau, source.ID, destination.ID, nbrChemin=k)

    for i, (cout_i, chemin_noeuds) in enumerate(chemins, start=1):
        noms = [n.Nom_Site or str(n.ID) for n in chemin_noeuds]
        print(f"  #{i} ({cout_i:.2f} km) : " + "  ->  ".join(noms))


if __name__ == "__main__":
    main()
