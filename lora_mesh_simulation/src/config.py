import math

# ==========================================================
# PARAMÈTRES RADIO LoRaWAN
# ==========================================================

TX_POWER_DBM: float = 14.0

# Fréquence LoRaWAN Europe (MHz)
FREQ_MHZ: float = 868.0

# Seuil de sensibilité RSSI en dBm (au-dessous, le paquet est perdu)
RSSI_THRESHOLD: float = -125.0

# Exposant d'atténuation du milieu (Path Loss Exponent n)
PATH_LOSS_EXPONENT: float = 2.8

# Calcul théorique de d_max (en km) basé sur Friis / Log-distance
PL_1KM = 32.44 + 20 * math.log10(FREQ_MHZ)  # Atténuation à 1 km
MAX_DISTANCE_KM = 10 ** ((TX_POWER_DBM - RSSI_THRESHOLD - PL_1KM) / (10 * PATH_LOSS_EXPONENT))

# Alias utilisé par models.py (portée radio maximale, en km)
DMAX: float = MAX_DISTANCE_KM

# Bornes RSSI utilisées pour la normalisation dans models.py
# (RSSI_MAX = meilleur cas théorique, RSSI_MIN = seuil de sensibilité)
RSSI_MAX: float = TX_POWER_DBM
RSSI_MIN: float = RSSI_THRESHOLD

# Distance plancher (en km) pour éviter log10(0) quand deux nœuds
# sont quasiment à la même position (~1 mètre)
DISTANCE_PLANCHER_KM: float = 0.001

# ==========================================================
# PONDÉRATION DU SCORE DE COUVERTURE
# ==========================================================

ALPHA_DISTANCE: float = 2 / 10   # Poids de la distance géométrique
BETA_SIGNAL: float = 4 / 10      # Poids de la dégradation du signal (RSSI)
GAMMA_CONGESTION: float = 3 / 10 # Poids du taux d'occupation du buffer (trafic)
DELTA_BATTERY: float = 1 / 10    # Poids du niveau de décharge de batterie

# Budget maximum p (nombre maximal de nouveaux modules LoRa à déployer)
BUDGET_P_MODULES: int = 5

# Mode d'optimisation par défaut : "MCLP" (Maximal Cover) ou "SCP" (Set Covering)
OPTIMIZATION_MODE: str = "MCLP"

# ==========================================================
# SIMULATION D'ÉTAT (batterie / trafic)
# ==========================================================

CONSOMMATION_BATTERIE_MIN: float = 0.1   # % de batterie perdue par pas de simulation
CONSOMMATION_BATTERIE_MAX: float = 2.0

VARIATION_BUFFER_MIN: float = -5.0       # variation du taux de remplissage du buffer (%)
VARIATION_BUFFER_MAX: float = 10.0

# ==========================================================
# CHEMINS DE DONNÉES
# ==========================================================

DATA_DIR: str = "data/"
PYLONES_CSV_PATH: str = "data/pylones_fixes.csv"
TERRITOIRE_JSON_PATH: str = "data/territoire.json"

ALPHA_PORTEE_RADIO: float = 0.15     # Transparence des disques de couverture (0 à 1)
