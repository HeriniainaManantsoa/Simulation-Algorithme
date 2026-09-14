r"""
Test manuel de dijkstra.py / routage.py.

Principe : on construit un petit réseau de 5 Noeud dont les distances
sont calculées EN FONCTION de config.DMAX (la portée radio théorique
de models.py/config.py), pas de valeurs codées en dur. Comme ça le
test reste valide même si tu changes TX_POWER_DBM, PATH_LOSS_EXPONENT,
etc. dans config.py.

Topologie voulue (un "losange") :

        B
       / \
      A   D   <- F (isolé, hors de portée de tout le monde)
       \ /
        C

- A-B, A-C, B-D, C-D : à portée radio -> connectés
- A-D directement : hors de portée -> PAS connecté (il faut passer par B ou C)
- B-C : hors de portée -> pas connecté

=> dijkstra(A, D) doit passer par B ou C (2 sauts).
=> yen_depuis_noeuds(A, D, k=2) doit trouver les 2 chemins A-B-D et A-C-D.
=> dijkstra(A, F) doit renvoyer qu'il n'existe pas de chemin.
"""
import math

import config
from models import Noeud
from dijkstra import construire_graphe, dijkstra
from routage import yen_depuis_noeuds


def verifier(condition, message):
    statut = "OK " if condition else "ECHEC"
    print(f"[{statut}] {message}")
    if not condition:
        raise AssertionError(message)


# ==========================================================
# 1. Construction des nœuds de test
# ==========================================================

# Conversion km -> degrés de latitude/longitude.
# 1 degré de latitude ~ 111.32 km partout sur Terre (longueur d'un
# arc de méridien = circonférence terrestre / 360 = 40 008 km / 360).
# Pour la longitude on divise en plus par cos(latitude), car les
# méridiens se rapprochent en s'éloignant de l'équateur.
KM_PAR_DEGRE_LAT = 111.32
LAT0, LON0 = -18.8792, 47.5079  # Antananarivo, sert juste de point de départ
km_par_degre_lon = KM_PAR_DEGRE_LAT * math.cos(math.radians(LAT0))

# distance A-B, A-C, B-D, C-D : 80% de DMAX -> à portée
d_connecte_km = 0.8 * config.DMAX
delta = d_connecte_km / KM_PAR_DEGRE_LAT  # même delta utilisé en lat et lon

A = Noeud(ID=1, Latitude=LAT0, Longitude=LON0, Nom_Site="A")
B = Noeud(ID=2, Latitude=LAT0 + delta, Longitude=LON0, Nom_Site="B")
C = Noeud(ID=3, Latitude=LAT0, Longitude=LON0 + delta, Nom_Site="C")
D = Noeud(ID=4, Latitude=LAT0 + delta, Longitude=LON0 + delta, Nom_Site="D")

# Nœud isolé : très loin de tout le monde (bien plus que DMAX)
F = Noeud(ID=5, Latitude=LAT0 + 5.0, Longitude=LON0 + 5.0, Nom_Site="F")

noeuds = [A, B, C, D, F]

print(f"DMAX (portée radio théorique) = {config.DMAX:.2f} km")
print(f"distance A-B = {A.calculer_distance(B):.2f} km")
print(f"distance A-D = {A.calculer_distance(D):.2f} km (diagonale, hors portée)")
print()

# ==========================================================
# 2. Test de construire_graphe()
# ==========================================================

graphe = construire_graphe(noeuds)

verifier(B.ID in graphe[A.ID], "A-B doit être connecté")
verifier(C.ID in graphe[A.ID], "A-C doit être connecté")
verifier(D.ID in graphe[B.ID], "B-D doit être connecté")
verifier(D.ID in graphe[C.ID], "C-D doit être connecté")
verifier(D.ID not in graphe[A.ID], "A-D ne doit PAS être connecté directement")
verifier(graphe[F.ID] == {}, "F doit être isolé (aucune arête)")
print()

# ==========================================================
# 3. Test de dijkstra()
# ==========================================================

cout, chemin = dijkstra(graphe, A.ID, D.ID)

verifier(chemin[0] == A.ID and chemin[-1] == D.ID, "le chemin doit aller de A à D")
verifier(len(chemin) == 3, "le chemin A->D doit passer par un intermédiaire (3 nœuds)")
verifier(chemin[1] in (B.ID, C.ID), "l'intermédiaire doit être B ou C")
print(f"chemin A->D trouvé : {chemin}, coût = {cout:.2f} km")
print()

# cas sans chemin (F isolé)
cout_f, chemin_f = dijkstra(graphe, A.ID, F.ID)
verifier(cout_f == float('inf') and chemin_f == [], "aucun chemin A->F ne doit exister")
print()

# ==========================================================
# 4. Test de yen_depuis_noeuds() (k plus courts chemins)
# ==========================================================

resultats = yen_depuis_noeuds(noeuds, A.ID, D.ID, nbrChemin=2)

verifier(len(resultats) == 2, "yen doit trouver 2 chemins distincts A->D")

for i, (cout_i, chemin_noeuds) in enumerate(resultats, start=1):
    noms = [n.Nom_Site for n in chemin_noeuds]
    print(f"chemin #{i} : {noms}, coût = {cout_i:.2f} km")

ids_intermediaires = {chemin_noeuds[1].ID for _, chemin_noeuds in resultats}
verifier(ids_intermediaires == {B.ID, C.ID}, "les 2 chemins doivent passer respectivement par B et par C")

print()
print("Tous les tests sont passés.")
