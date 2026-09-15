"""
Algorithmes d'optimisation de couverture :
- MCLP : Maximum Covering Location Problem
- SCP  : Set Covering Problem

Responsabilité du module :
    - déterminer quelles zones sont couvertes par quels noeuds ;
    - construire la matrice de couverture ;
    - résoudre le MCLP ;
    - résoudre le SCP.

Compatibilité avec le reste du projet
-------------------------------------
- Les noeuds sont des objets `models.Noeud` (attributs `ID`, `Latitude`,
  `Longitude`, `batterie`, `buffer`, ...), fournis par
  `data_loader.charger_pylones_fixes()`.
- Les distances sont calculées avec `Noeud.calculer_distance()`
  (Haversine, en km) : sur des coordonnées GPS, la distance euclidienne
  sur (lat, lon) n'a pas de sens physique, car 1° de longitude ne vaut
  pas la même distance qu'1° de latitude (facteur cos(latitude)).
- Les valeurs par défaut (dmax, budget, mode) viennent de `config.py`.
"""

import pulp

import config


# ============================================================
# 1. ADAPTATION DES ZONES
# ============================================================

class _PointZone:
    """
    Petit adaptateur qui donne à une zone l'interface minimale
    attendue par `Noeud.calculer_distance()`, c'est-à-dire les
    attributs `Latitude` et `Longitude`.

    Grâce à ça on réutilise directement la formule de Haversine
    déjà écrite dans models.py, au lieu d'en réécrire une copie ici.
    """

    __slots__ = ("Latitude", "Longitude")

    def __init__(self, latitude, longitude):
        self.Latitude = float(latitude)
        self.Longitude = float(longitude)


def _coordonnees_zone(zone):
    """
    Récupère les coordonnées d'une zone.

    Formats acceptés :
        - objet `Noeud` (ou tout objet avec .Latitude / .Longitude)
        - dict {"Latitude": ..., "Longitude": ...}
        - dict {"latitude": ..., "longitude": ...}
        - dict {"lat": ..., "lon": ...} ou {"lat": ..., "lng": ...}
    """

    if hasattr(zone, "Latitude") and hasattr(zone, "Longitude"):
        return float(zone.Latitude), float(zone.Longitude)

    if isinstance(zone, dict):
        for cle_lat, cle_lon in (
            ("Latitude", "Longitude"),
            ("latitude", "longitude"),
            ("lat", "lon"),
            ("lat", "lng"),
        ):
            if cle_lat in zone and cle_lon in zone:
                return float(zone[cle_lat]), float(zone[cle_lon])

    raise KeyError(
        "Zone sans coordonnées exploitables : "
        "attendu Latitude/Longitude (ou lat/lon)."
    )


def _id_zone(zone):
    """
    Récupère l'identifiant d'une zone.
    """

    if isinstance(zone, dict):
        for cle in ("ID", "id", "Id", "nom", "Nom"):
            if cle in zone:
                return zone[cle]
        raise KeyError("Zone sans identifiant (clé 'ID' ou 'id' attendue).")

    if hasattr(zone, "ID"):
        return zone.ID

    raise KeyError("Zone sans identifiant.")


def _population_zone(zone):
    """
    Récupère le poids (population) d'une zone.

    Par défaut 1 : dans ce cas le MCLP maximise simplement
    le NOMBRE de zones couvertes.
    """

    if isinstance(zone, dict):
        return float(zone.get("population", 1))

    return float(getattr(zone, "population", 1))


def _distance_noeud_zone(noeud, zone):
    """
    Distance en km entre un `Noeud` et une zone, via Haversine.
    """

    lat, lon = _coordonnees_zone(zone)

    return noeud.calculer_distance(_PointZone(lat, lon))


# ============================================================
# 2. CONSTRUCTION DE LA COUVERTURE
# ============================================================

def construire_couverture(zones, noeuds, dmax=None):
    """
    Construit la couverture entre les noeuds et les zones.

    Un noeud couvre une zone lorsque :

        distance_haversine(noeud, zone) <= dmax

    Parameters
    ----------
    zones : list
        Liste des zones à couvrir.

    noeuds : list[Noeud]
        Liste des objets Noeud (pylônes fixes et/ou candidats).

    dmax : float, optionnel
        Portée maximale de couverture en km.
        Par défaut `config.DMAX`, la portée radio théorique déduite
        du bilan de liaison LoRa dans config.py.

    Returns
    -------
    dict
        Exemple :

        {
            1: ["Z1", "Z2"],
            2: ["Z2", "Z3"]
        }
        (les clés sont les `Noeud.ID`)
    """

    if dmax is None:
        dmax = config.DMAX

    couverture = {}

    for noeud in noeuds:

        couverture[noeud.ID] = [
            _id_zone(zone)
            for zone in zones
            if _distance_noeud_zone(noeud, zone) <= dmax
        ]

    return couverture


def construire_matrice_couverture(zones, noeuds, dmax=None):
    """
    Construit la matrice A de couverture.

        A[n][z] = 1 si le noeud n couvre la zone z
        A[n][z] = 0 sinon

    Returns
    -------
    dict
        {
            1: {"Z1": 1, "Z2": 0, ...},
            ...
        }
    """

    if dmax is None:
        dmax = config.DMAX

    matrice = {}

    for noeud in noeuds:

        ligne = {}

        for zone in zones:

            d = _distance_noeud_zone(noeud, zone)

            ligne[_id_zone(zone)] = 1 if d <= dmax else 0

        matrice[noeud.ID] = ligne

    return matrice


# ============================================================
# 3. SCORE DE QUALITÉ D'UN NOEUD
# ============================================================

def score_couverture(noeud, zone):
    """
    Score de qualité (dans [0, 1]) de la desserte d'une zone par un noeud.
    Plus le score est élevé, meilleure est la desserte.

    Formule, avec les poids définis dans config.py :

        score = ALPHA_DISTANCE * (1 - distance_normalisee)
              + BETA_SIGNAL    * rssi_normalise
              + GAMMA_CONGESTION * (1 - buffer_normalise)
              + DELTA_BATTERY  * batterie_normalisee

    D'où viennent les termes :

    - `distance_normalisee` vaut 0 à distance nulle et 1 à DMAX
      (cf. Noeud.normaliser). On veut récompenser la PROXIMITÉ,
      donc on prend son complément (1 - d).
    - `rssi_normalise` vaut 0 au seuil de sensibilité (RSSI_MIN) et 1
      au meilleur cas (RSSI_MAX) : il est déjà "plus grand = mieux",
      on le garde tel quel.
    - `buffer_normalise` est le taux de remplissage du buffer, donc la
      congestion : plus il est grand, pire c'est -> complément.
    - `batterie_normalisee` vaut 1 à 100 % de batterie : déjà
      "plus grand = mieux", on le garde tel quel.

    Les quatre poids de config.py somment à 1 (0.2 + 0.4 + 0.3 + 0.1),
    donc le score reste bien dans [0, 1].
    """

    lat, lon = _coordonnees_zone(zone)
    point = _PointZone(lat, lon)

    return (
        config.ALPHA_DISTANCE * (1 - noeud.distance_normalisee(point))
        + config.BETA_SIGNAL * noeud.rssi_normalise(point)
        + config.GAMMA_CONGESTION * (1 - noeud.buffer_normalise())
        + config.DELTA_BATTERY * noeud.batterie_normalisee()
    )


# ============================================================
# 4. MCLP
# ============================================================

def resoudre_mclp(zones, noeuds, dmax=None, nombre_max=None):
    """
    Résout le problème MCLP.

    Objectif :
        Maximiser la population couverte en sélectionnant au plus
        `nombre_max` noeuds.

    Modèle :

        max   somme_z  population[z] * y[z]
        s.c.  somme_n  x[n] <= nombre_max
              y[z] <= somme_n A[n][z] * x[n]     pour chaque zone z
              x[n], y[z] binaires

    La deuxième contrainte dit : une zone ne peut être déclarée
    couverte (y[z] = 1) que si au moins un noeud sélectionné la couvre.

    Parameters
    ----------
    dmax : float, optionnel
        Par défaut `config.DMAX`.
    nombre_max : int, optionnel
        Par défaut `config.BUDGET_P_MODULES`.
    """

    if dmax is None:
        dmax = config.DMAX

    if nombre_max is None:
        nombre_max = config.BUDGET_P_MODULES

    A = construire_matrice_couverture(zones, noeuds, dmax)

    noeuds_ids = [noeud.ID for noeud in noeuds]
    zones_ids = [_id_zone(zone) for zone in zones]

    population = {
        _id_zone(zone): _population_zone(zone)
        for zone in zones
    }

    # --------------------------------------------------------
    # Création du problème
    # --------------------------------------------------------

    probleme = pulp.LpProblem("MCLP", pulp.LpMaximize)

    # x[n] = 1 si le noeud n est sélectionné
    x = pulp.LpVariable.dicts("x", noeuds_ids, cat=pulp.LpBinary)

    # y[z] = 1 si la zone z est couverte
    y = pulp.LpVariable.dicts("y", zones_ids, cat=pulp.LpBinary)

    # Objectif : maximiser la population couverte
    probleme += pulp.lpSum(
        population[z] * y[z]
        for z in zones_ids
    )

    # Contrainte de budget
    probleme += (
        pulp.lpSum(x[n] for n in noeuds_ids) <= nombre_max
    ), "Limite_nombre_noeuds"

    # Contraintes de couverture
    for z in zones_ids:
        probleme += (
            y[z] <= pulp.lpSum(A[n][z] * x[n] for n in noeuds_ids)
        ), f"Couverture_{z}"

    probleme.solve(pulp.PULP_CBC_CMD(msg=False))

    statut = pulp.LpStatus[probleme.status]

    if statut != "Optimal":
        return {
            "statut": statut,
            "noeuds_selectionnes": [],
            "zones_couvertes": [],
            "population_couverte": 0.0,
            "nombre_noeuds": 0,
            "taux_couverture": 0.0,
        }

    # Le solveur renvoie des flottants (0.9999999, 1.0000001...) :
    # on teste donc > 0.5 plutôt qu'une égalité exacte à 1.
    noeuds_selectionnes = [
        n for n in noeuds_ids
        if pulp.value(x[n]) is not None and pulp.value(x[n]) > 0.5
    ]

    zones_couvertes = [
        z for z in zones_ids
        if pulp.value(y[z]) is not None and pulp.value(y[z]) > 0.5
    ]

    population_couverte = sum(population[z] for z in zones_couvertes)
    population_totale = sum(population[z] for z in zones_ids)

    return {
        "statut": statut,
        "noeuds_selectionnes": noeuds_selectionnes,
        "zones_couvertes": zones_couvertes,
        "population_couverte": population_couverte,
        "nombre_noeuds": len(noeuds_selectionnes),
        "taux_couverture": (
            population_couverte / population_totale
            if population_totale > 0 else 0.0
        ),
    }


# ============================================================
# 5. VÉRIFICATION DES ZONES IMPOSSIBLES
# ============================================================

def zones_non_couvrables(zones, noeuds, dmax=None):
    """
    Recherche les zones qu'aucun noeud candidat ne peut couvrir.

    Utile avant un SCP : si une seule zone est hors de portée de tous
    les noeuds, la contrainte "chaque zone couverte" est infaisable et
    le solveur renverrait juste "Infeasible" sans expliquer pourquoi.

    Returns
    -------
    list
        Identifiants des zones impossibles à couvrir.
    """

    if dmax is None:
        dmax = config.DMAX

    A = construire_matrice_couverture(zones, noeuds, dmax)

    return [
        _id_zone(zone)
        for zone in zones
        if not any(A[n][_id_zone(zone)] == 1 for n in A)
    ]


# ============================================================
# 6. SCP
# ============================================================

def resoudre_scp(zones, noeuds, dmax=None):
    """
    Résout le problème SCP.

    Objectif :
        Couvrir TOUTES les zones avec le minimum de noeuds.

    Modèle :

        min   somme_n  x[n]
        s.c.  somme_n  A[n][z] * x[n] >= 1     pour chaque zone z
              x[n] binaire

    Contrairement au MCLP, il n'y a pas de variable y : chaque zone
    DOIT être couverte, donc la contrainte est directement ">= 1".
    """

    if dmax is None:
        dmax = config.DMAX

    A = construire_matrice_couverture(zones, noeuds, dmax)

    noeuds_ids = [noeud.ID for noeud in noeuds]
    zones_ids = [_id_zone(zone) for zone in zones]

    zones_impossibles = zones_non_couvrables(zones, noeuds, dmax)

    if zones_impossibles:
        return {
            "statut": "Impossible",
            "noeuds_selectionnes": [],
            "zones_couvertes": [],
            "nombre_noeuds": 0,
            "zones_non_couvrables": zones_impossibles,
        }

    probleme = pulp.LpProblem("SCP", pulp.LpMinimize)

    x = pulp.LpVariable.dicts("x", noeuds_ids, cat=pulp.LpBinary)

    # Objectif : minimiser le nombre de noeuds déployés
    probleme += pulp.lpSum(x[n] for n in noeuds_ids)

    # Chaque zone doit être couverte par au moins un noeud
    for z in zones_ids:
        probleme += (
            pulp.lpSum(A[n][z] * x[n] for n in noeuds_ids) >= 1
        ), f"Couverture_{z}"

    probleme.solve(pulp.PULP_CBC_CMD(msg=False))

    statut = pulp.LpStatus[probleme.status]

    if statut != "Optimal":
        return {
            "statut": statut,
            "noeuds_selectionnes": [],
            "zones_couvertes": [],
            "nombre_noeuds": 0,
            "zones_non_couvrables": [],
        }

    noeuds_selectionnes = [
        n for n in noeuds_ids
        if pulp.value(x[n]) is not None and pulp.value(x[n]) > 0.5
    ]

    # Dans une solution SCP optimale, toutes les zones sont couvertes.
    return {
        "statut": statut,
        "noeuds_selectionnes": noeuds_selectionnes,
        "zones_couvertes": list(zones_ids),
        "nombre_noeuds": len(noeuds_selectionnes),
        "zones_non_couvrables": [],
    }


# ============================================================
# 7. FONCTIONS GÉNÉRALES
# ============================================================

def analyser_couverture(zones, noeuds, dmax=None, nombre_max=None, mode=None):
    """
    Exécute l'algorithme de couverture demandé.

    Parameters
    ----------
    mode : str, optionnel
        "MCLP", "SCP" ou "BOTH". Par défaut `config.OPTIMIZATION_MODE`.

    Returns
    -------
    dict
        {"mode": ..., "mclp": {...} ou None, "scp": {...} ou None}
    """

    if mode is None:
        mode = config.OPTIMIZATION_MODE

    mode = mode.upper()

    resultat = {"mode": mode, "mclp": None, "scp": None}

    if mode in ("MCLP", "BOTH"):
        resultat["mclp"] = resoudre_mclp(zones, noeuds, dmax, nombre_max)

    if mode in ("SCP", "BOTH"):
        resultat["scp"] = resoudre_scp(zones, noeuds, dmax)

    if resultat["mclp"] is None and resultat["scp"] is None:
        raise ValueError(
            f"Mode d'optimisation inconnu : {mode!r} "
            "(attendu 'MCLP', 'SCP' ou 'BOTH')."
        )

    return resultat


def analyser_couverture_depuis_csv(zones, filepath=None, dmax=None,
                                   nombre_max=None, mode=None):
    """
    Variante qui charge elle-même les pylônes fixes via
    `data_loader.charger_pylones_fixes()` puis lance l'analyse.

    L'import de data_loader est fait ici (et non en haut du module)
    pour que couverture.py reste importable même sans pandas installé
    ni fichier CSV présent.
    """

    from data_loader import charger_pylones_fixes

    if filepath is None:
        filepath = config.PYLONES_CSV_PATH

    noeuds = charger_pylones_fixes(filepath)

    return analyser_couverture(zones, noeuds, dmax, nombre_max, mode)
