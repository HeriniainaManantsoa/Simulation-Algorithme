"""
Test manuel de couverture.py.

Scénario : deux groupes de zones éloignés l'un de l'autre.

    groupe 1 (3 zones, 100 hab. chacune)      groupe 2 (2 zones, 1000 hab. chacune)
        Z1 Z2 Z3                                   Z4 Z5
          ^  ^                                       ^
        N1  N3   (deux noeuds redondants)           N2            Z6 (très loin, hors de portée de tout)

Toutes les positions sont définies en multiples de config.DMAX (la portée
radio théorique calculée dans config.py), donc le test reste valide même
si tu changes TX_POWER_DBM, PATH_LOSS_EXPONENT, etc.

Résultats attendus :
- N1 et N3 couvrent le groupe 1, N2 couvre le groupe 2, personne ne couvre Z6.
- MCLP avec budget 1 -> choisit N2 (2000 hab. > 300 hab.).
- MCLP avec budget 2 -> couvre les 5 zones (2300 hab.), soit N2 + (N1 ou N3).
- SCP sans Z6 -> 2 noeuds suffisent.
- SCP avec Z6 -> statut "Impossible".
"""

import config
from models import Noeud
import couverture as cv


def verifier(condition, message):
    statut = "OK " if condition else "ECHEC"
    print(f"[{statut}] {message}")
    if not condition:
        raise AssertionError(message)


# ============================================================
# 1. Construction du scénario
# ============================================================

# 1 degré de latitude ~ 111.32 km (circonférence terrestre 40 008 km / 360).
# On raisonne uniquement en latitude pour que la conversion soit exacte
# et indépendante de la longitude.
KM_PAR_DEGRE_LAT = 111.32
LAT0, LON0 = -18.8792, 47.5079  # Antananarivo

# pas angulaire correspondant à exactement DMAX kilomètres
d = config.DMAX / KM_PAR_DEGRE_LAT

# --- noeuds candidats ---
N1 = Noeud(ID=1, Latitude=LAT0, Longitude=LON0, Nom_Site="N1",
           batterie=90.0, buffer=10.0)
N3 = Noeud(ID=3, Latitude=LAT0 + 0.1 * d, Longitude=LON0, Nom_Site="N3",
           batterie=40.0, buffer=70.0)
N2 = Noeud(ID=2, Latitude=LAT0 + 3.0 * d, Longitude=LON0, Nom_Site="N2",
           batterie=100.0, buffer=0.0)

noeuds = [N1, N2, N3]

# --- zones à couvrir ---
zones_groupe1 = [
    {"id": "Z1", "Latitude": LAT0 + 0.05 * d, "Longitude": LON0, "population": 100},
    {"id": "Z2", "Latitude": LAT0 + 0.20 * d, "Longitude": LON0, "population": 100},
    {"id": "Z3", "Latitude": LAT0 + 0.30 * d, "Longitude": LON0, "population": 100},
]
zones_groupe2 = [
    {"id": "Z4", "Latitude": LAT0 + 2.80 * d, "Longitude": LON0, "population": 1000},
    {"id": "Z5", "Latitude": LAT0 + 3.20 * d, "Longitude": LON0, "population": 1000},
]
Z6 = {"id": "Z6", "Latitude": LAT0 + 10.0 * d, "Longitude": LON0, "population": 50}

zones = zones_groupe1 + zones_groupe2          # 5 zones couvrables
zones_avec_impossible = zones + [Z6]           # 6 zones dont 1 hors portée

print(f"DMAX (portée radio théorique) = {config.DMAX:.2f} km")
print(f"distance N1-Z1 = {cv._distance_noeud_zone(N1, zones_groupe1[0]):.2f} km")
print(f"distance N1-Z4 = {cv._distance_noeud_zone(N1, zones_groupe2[0]):.2f} km")
print(f"distance N1-Z6 = {cv._distance_noeud_zone(N1, Z6):.2f} km")
print()

# ============================================================
# 2. Couverture et matrice
# ============================================================

couv = cv.construire_couverture(zones, noeuds)

verifier(set(couv[N1.ID]) == {"Z1", "Z2", "Z3"}, "N1 couvre exactement le groupe 1")
verifier(set(couv[N3.ID]) == {"Z1", "Z2", "Z3"}, "N3 couvre exactement le groupe 1")
verifier(set(couv[N2.ID]) == {"Z4", "Z5"}, "N2 couvre exactement le groupe 2")

A = cv.construire_matrice_couverture(zones, noeuds)

verifier(A[N1.ID]["Z1"] == 1, "A[N1][Z1] doit valoir 1")
verifier(A[N1.ID]["Z4"] == 0, "A[N1][Z4] doit valoir 0")
verifier(
    all(v in (0, 1) for ligne in A.values() for v in ligne.values()),
    "la matrice ne contient que des 0 et des 1",
)
print()

# --- format de zone alternatif (lat / lon en minuscules) ---
zone_lat_lon = {"id": "Zbis", "lat": LAT0 + 0.1 * d, "lon": LON0}
verifier(
    cv.construire_couverture([zone_lat_lon], [N1])[N1.ID] == ["Zbis"],
    "le format {'lat': ..., 'lon': ...} est accepté",
)
print()

# ============================================================
# 3. Zones non couvrables
# ============================================================

verifier(cv.zones_non_couvrables(zones, noeuds) == [],
         "aucune zone impossible dans le jeu de 5 zones")
verifier(cv.zones_non_couvrables(zones_avec_impossible, noeuds) == ["Z6"],
         "Z6 doit être détectée comme non couvrable")
print()

# ============================================================
# 4. Score de couverture
# ============================================================

score_n1 = cv.score_couverture(N1, zones_groupe1[0])
score_n3 = cv.score_couverture(N3, zones_groupe1[0])

verifier(0.0 <= score_n1 <= 1.0, "le score doit rester dans [0, 1]")

# Z1 a été placée EXACTEMENT à mi-chemin entre N1 (LAT0) et N3 (LAT0 + 0.1d).
# Les deux noeuds sont donc à la même distance de Z1 : les termes distance
# et RSSI du score s'annulent, et seuls la batterie et le buffer départagent.
verifier(score_n1 > score_n3,
         "à distance égale, N1 (batterie 90 %, buffer 10 %) doit mieux scorer "
         "que N3 (40 %, 70 %)")
print(f"score N1/Z1 = {score_n1:.4f}   score N3/Z1 = {score_n3:.4f}")
print()

# ============================================================
# 5. MCLP et SCP (nécessitent pulp)
# ============================================================

try:
    import pulp  # noqa: F401
except ImportError:
    print("pulp n'est pas installé : tests MCLP/SCP ignorés.")
    print("Installe-le avec :  pip install pulp")
    raise SystemExit(0)

# --- MCLP avec un seul noeud autorisé ---
res = cv.resoudre_mclp(zones, noeuds, nombre_max=1)

verifier(res["statut"] == "Optimal", "MCLP (budget 1) doit être résolu")
verifier(res["nombre_noeuds"] == 1, "MCLP (budget 1) sélectionne 1 seul noeud")
verifier(res["noeuds_selectionnes"] == [N2.ID],
         "avec 1 seul noeud, il faut choisir N2 (2000 hab. contre 300)")
verifier(res["population_couverte"] == 2000, "population couverte = 2000")
verifier(abs(res["taux_couverture"] - 2000 / 2300) < 1e-9,
         "taux de couverture = 2000/2300")
print(f"MCLP budget 1 : {res['noeuds_selectionnes']}, "
      f"{res['population_couverte']:.0f} hab. "
      f"({res['taux_couverture']*100:.1f} %)")
print()

# --- MCLP avec deux noeuds autorisés ---
res2 = cv.resoudre_mclp(zones, noeuds, nombre_max=2)

verifier(res2["nombre_noeuds"] == 2, "MCLP (budget 2) sélectionne 2 noeuds")
verifier(set(res2["zones_couvertes"]) == {"Z1", "Z2", "Z3", "Z4", "Z5"},
         "MCLP (budget 2) doit couvrir les 5 zones")
verifier(N2.ID in res2["noeuds_selectionnes"], "N2 doit faire partie de la solution")
verifier(abs(res2["taux_couverture"] - 1.0) < 1e-9, "taux de couverture = 100 %")
print(f"MCLP budget 2 : {res2['noeuds_selectionnes']}, "
      f"{res2['population_couverte']:.0f} hab.")
print()

# --- MCLP avec le budget par défaut de config.py ---
res_defaut = cv.resoudre_mclp(zones, noeuds)
verifier(res_defaut["statut"] == "Optimal",
         f"MCLP avec le budget par défaut (config.BUDGET_P_MODULES="
         f"{config.BUDGET_P_MODULES}) doit être résolu")
print()

# --- SCP sur les zones couvrables ---
res_scp = cv.resoudre_scp(zones, noeuds)

verifier(res_scp["statut"] == "Optimal", "SCP doit être résolu")
verifier(res_scp["nombre_noeuds"] == 2, "2 noeuds suffisent à tout couvrir")
verifier(N2.ID in res_scp["noeuds_selectionnes"],
         "N2 est obligatoire (seul à couvrir le groupe 2)")
verifier(res_scp["zones_non_couvrables"] == [], "aucune zone non couvrable")
print(f"SCP : {res_scp['noeuds_selectionnes']}")
print()

# --- SCP avec une zone impossible ---
res_scp_ko = cv.resoudre_scp(zones_avec_impossible, noeuds)

verifier(res_scp_ko["statut"] == "Impossible",
         "le SCP doit renvoyer 'Impossible' quand une zone est hors de portée")
verifier(res_scp_ko["zones_non_couvrables"] == ["Z6"],
         "le SCP doit signaler Z6 comme non couvrable")
print()

# ============================================================
# 6. Fonction générale
# ============================================================

res_both = cv.analyser_couverture(zones, noeuds, mode="BOTH")

verifier(res_both["mclp"] is not None and res_both["scp"] is not None,
         "le mode BOTH doit lancer les deux algorithmes")

res_mclp_seul = cv.analyser_couverture(zones, noeuds, mode="MCLP")

verifier(res_mclp_seul["scp"] is None, "le mode MCLP ne doit pas lancer le SCP")

try:
    cv.analyser_couverture(zones, noeuds, mode="NIMPORTEQUOI")
    verifier(False, "un mode inconnu doit lever une ValueError")
except ValueError:
    verifier(True, "un mode inconnu lève bien une ValueError")

print()
print("Tous les tests sont passés.")
