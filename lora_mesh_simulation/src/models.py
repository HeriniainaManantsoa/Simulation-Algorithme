import math
import random
from dataclasses import dataclass

import config


@dataclass
class Noeud:
    """
    Représente un nœud du réseau LoRaWAN : un pylône fixe existant
    ou un nouveau module LoRa candidat au déploiement.

    Les champs ID / Code_Pylone / ... / Longitude correspondent
    exactement aux colonnes lues dans data_loader.py à partir du
    CSV des pylônes fixes.
    """

    ID: int
    Latitude: float
    Longitude: float

    # Champs descriptifs (optionnels : un nouveau module candidat
    # n'a pas forcément de Code_Pylone / Operateur, etc.)
    Code_Pylone: str = ""
    Nom_Site: str = ""
    Operateur: str = ""
    Region: str = ""
    District: str = ""
    Commune: str = ""
    Hauteur: float = 0.0

    # "fixe" (pylône existant) ou "candidat" (nouveau module LoRa)
    type: str = "fixe"

    # État simulé
    batterie: float = 100.0
    buffer: float = 0.0

    def __post_init__(self):
        """
        Vérifie et normalise les valeurs après la création du nœud.
        """

        # On s'assure que la batterie reste entre 0 et 100.
        self.batterie = max(0.0, min(100.0, self.batterie))

        # On s'assure que le buffer reste entre 0 et 100.
        self.buffer = max(0.0, min(100.0, self.buffer))

    # ==========================================================
    # 1. CALCUL DE DISTANCE (Haversine, résultat en km)
    # ==========================================================

    def calculer_distance(self, autre_noeud):
        """
        Calcule la distance orthodromique (Haversine) entre deux
        nœuds à partir de leurs coordonnées GPS (Latitude, Longitude).

        Retour
        ------
        float
            Distance entre les deux nœuds, en kilomètres.
        """

        rayon_terre_km = 6371.0

        lat1, lon1 = math.radians(self.Latitude), math.radians(self.Longitude)
        lat2, lon2 = math.radians(autre_noeud.Latitude), math.radians(autre_noeud.Longitude)

        dlat = lat2 - lat1
        dlon = lon2 - lon1

        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        c = 2 * math.asin(math.sqrt(a))

        return rayon_terre_km * c

    # ==========================================================
    # 2. ESTIMATION DU RSSI
    # ==========================================================

    def estimer_signal_rssi(self, autre_noeud):
        """
        Estime le RSSI entre deux nœuds à partir du modèle
        log-distance défini dans config.py :

            RSSI(d) = TX_POWER_DBM - (PL_1KM + 10 * n * log10(d))

        où d est la distance en km, n l'exposant d'atténuation
        (PATH_LOSS_EXPONENT) et PL_1KM l'atténuation de référence
        à 1 km (calculée à partir de la fréquence LoRaWAN).

        Retour
        ------
        float
            RSSI estimé en dBm.
        """

        distance_km = self.calculer_distance(autre_noeud)

        # Évite log10(0) lorsque deux nœuds ont quasiment
        # les mêmes coordonnées.
        distance_km = max(distance_km, config.DISTANCE_PLANCHER_KM)

        perte_de_parcours = config.PL_1KM + 10 * config.PATH_LOSS_EXPONENT * math.log10(distance_km)

        rssi = config.TX_POWER_DBM - perte_de_parcours

        return rssi

    # ==========================================================
    # 3. MISE À JOUR DE L'ÉTAT
    # ==========================================================

    def mettre_a_jour_etat(
        self,
        consommation_batterie=None,
        variation_buffer=None
    ):
        """
        Simule l'évolution de l'état du nœud.

        La batterie diminue pour représenter la consommation
        d'énergie.

        Le buffer varie pour représenter les variations
        du trafic réseau.

        Paramètres
        ----------
        consommation_batterie : float, optionnel
            Quantité de batterie consommée.

        variation_buffer : float, optionnel
            Variation du buffer.

        Retour
        ------
        None
        """

        # ------------------------------------------------------
        # Batterie
        # ------------------------------------------------------

        if consommation_batterie is None:
            consommation_batterie = random.uniform(
                config.CONSOMMATION_BATTERIE_MIN,
                config.CONSOMMATION_BATTERIE_MAX
            )

        self.batterie -= consommation_batterie

        # Empêche la batterie de devenir négative.
        self.batterie = max(0.0, self.batterie)

        # ------------------------------------------------------
        # Buffer / trafic
        # ------------------------------------------------------

        if variation_buffer is None:
            variation_buffer = random.uniform(
                config.VARIATION_BUFFER_MIN,
                config.VARIATION_BUFFER_MAX
            )

        self.buffer += variation_buffer

        # Empêche le buffer de sortir de [0, 100].
        self.buffer = max(0.0, min(100.0, self.buffer))

    # ==========================================================
    # 4. NORMALISATION
    # ==========================================================

    @staticmethod
    def normaliser(
        valeur,
        minimum,
        maximum
    ):
        """
        Ramène une valeur dans l'intervalle [0, 1].

        Formule :

            valeur_normalisee =
                (valeur - minimum)
                / (maximum - minimum)

        Les valeurs inférieures au minimum deviennent 0.
        Les valeurs supérieures au maximum deviennent 1.
        """

        if maximum == minimum:
            return 0.0

        resultat = (valeur - minimum) / (maximum - minimum)

        return max(0.0, min(1.0, resultat))

    def batterie_normalisee(self):
        """
        Retourne le niveau de batterie normalisé dans [0, 1].
        """

        return self.normaliser(
            self.batterie,
            0.0,
            100.0
        )

    def buffer_normalise(self):
        """
        Retourne le niveau de remplissage du buffer
        normalisé dans [0, 1].
        """

        return self.normaliser(
            self.buffer,
            0.0,
            100.0
        )

    def distance_normalisee(self, autre_noeud):
        """
        Retourne la distance avec un autre nœud normalisée
        dans [0, 1] à partir de la portée maximale du réseau.
        """

        distance = self.calculer_distance(autre_noeud)

        return self.normaliser(
            distance,
            0.0,
            config.DMAX
        )

    def rssi_normalise(self, autre_noeud):
        """
        Retourne le RSSI normalisé dans [0, 1].

        0 correspond à un signal faible.
        1 correspond à un signal fort.
        """

        rssi = self.estimer_signal_rssi(autre_noeud)

        return self.normaliser(
            rssi,
            config.RSSI_MIN,
            config.RSSI_MAX
        )

    # ==========================================================
    # 5. VÉRIFICATION DE LA LIAISON RADIO
    # ==========================================================

    def liaison_possible(self, autre_noeud):
        """
        Vérifie si deux nœuds peuvent communiquer.

        Une liaison est considérée comme possible si la distance
        entre les deux nœuds ne dépasse pas la portée maximale
        dmax (config.DMAX, en km).
        """

        distance = self.calculer_distance(autre_noeud)

        return distance <= config.DMAX

    # ==========================================================
    # 6. REPRÉSENTATION DU NŒUD
    # ==========================================================

    def __str__(self):
        """
        Représentation lisible du nœud.
        """

        return (
            f"Noeud("
            f"ID={self.ID}, "
            f"Nom_Site={self.Nom_Site!r}, "
            f"Latitude={self.Latitude}, "
            f"Longitude={self.Longitude}, "
            f"type={self.type}, "
            f"batterie={self.batterie:.1f}%, "
            f"buffer={self.buffer:.1f}%"
            f")"
        )
