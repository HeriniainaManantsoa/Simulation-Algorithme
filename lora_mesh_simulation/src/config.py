"""
src/config.py
--------------
Fichier de configuration central du projet de simulation LoRa.
Contient les paramètres radio, les contraintes géométriques, les coefficients 
de coût pour Dijkstra et les paramètres d'optimisation (MCLP / SCP).
"""
import math

# ==========================================
# 1. PARAMÈTRES RADIO ET PHYSIQUES (Profil 2)
# ==========================================
# Puissance d'émission par défaut en dBm (ex: 14 dBm = limite légale UE 868 MHz)
TX_POWER_DBM: float = 14.0

# Fréquence LoRaWAN Europe (MHz)
FREQ_MHZ: float = 868.0

# Seuil de sensibilité RSSI en dBm (au-dessous, le paquet est perdu)
# SF10 typique ~ -125 dBm avec marge de sécurité
RSSI_THRESHOLD: float = -125.0

# Exposant d'atténuation du milieu (Path Loss Exponent n)
# 2.0 = Vide / Vue directe idéale (Free Space)
# 2.7 à 3.5 = Milieu rural / vallonné (Zone Blanche)
PATH_LOSS_EXPONENT: float = 2.8

# Calcul théorique de d_max (en km) basé sur Friis / Log-distance
# d_max = 10^((TX_POWER - RSSI_THRESHOLD - 32.44 - 20*log10(FREQ)) / (10 * n))
PL_1KM = 32.44 + 20 * math.log10(FREQ_MHZ)  # Atténuation à 1 km
MAX_DISTANCE_KM = 10 ** ((TX_POWER_DBM - RSSI_THRESHOLD - PL_1KM) / (10 * PATH_LOSS_EXPONENT))


# ==========================================
# 2. POIDS DE PONDÉRATION DE ROUTAGE (Profil 3)
# ==========================================
# Fonction de coût composite : C = alpha*D + beta*S + gamma*K + delta*B
# La somme des poids doit égaler 1.0 pour une normalisation cohérente
ALPHA_DISTANCE: float = 2 / 10   # Poids de la distance géométrique
BETA_SIGNAL: float = 4 / 10      # Poids de la dégradation du signal (RSSI)
GAMMA_CONGESTION: float = 3 / 10 # Poids du taux d'occupation du buffer (trafic)
DELTA_BATTERY: float = 1 / 10    # Poids du niveau de décharge de batterie


# ==========================================
# 3. CONTRAINTES D'OPTIMISATION & COUVERTURE (Profil 4)
# ==========================================
# Budget maximum p (nombre maximal de nouveaux modules LoRa à déployer)
BUDGET_P_MODULES: int = 5

# Mode d'optimisation par défaut : "MCLP" (Maximal Cover) ou "SCP" (Set Covering)
OPTIMIZATION_MODE: str = "MCLP"


# ==========================================
# 4. CHEMINS DE FICHIERS & CHARGEMENT (Profil 1)
# ==========================================
DATA_DIR: str = "data/"
PYLONES_CSV_PATH: str = "data/pylones_fixes.csv"
TERRITOIRE_JSON_PATH: str = "data/territoire.json"

ALPHA_PORTEE_RADIO: float = 0.15     # Transparence des disques de couverture (0 à 1)

