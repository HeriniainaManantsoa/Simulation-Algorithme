import heapq
import itertools
import config


def calculer_cout_arete(n1, n2) -> float:
    """
    Calcule le coût composite d'une liaison radio entre n1 et n2.
    Plus le coût est bas, plus la liaison est optimale.
    """
    # composante Distance (normalisée [0, 1])
    c_dist = n1.distance_normalisee(n2)

    # composante Signal RSSI (1 - rssi_normalise car RSSI fort = coût faible)
    c_signal = 1.0 - n1.rssi_normalise(n2)

    # composante Congestion (moyenne des buffers des deux nœuds)
    c_buffer = (n1.buffer_normalise() + n2.buffer_normalise()) / 2.0

    # composante Batterie (coût élevé si batterie faible : 1 - niveau_batterie)
    c_batterie = ( (1.0 - n1.batterie_normalisee()) + (1.0 - n2.batterie_normalisee()) ) / 2.0

    # Coût pondéré selon config.py
    cout_total = (
        config.ALPHA_DISTANCE * c_dist +
        config.BETA_SIGNAL * c_signal +
        config.GAMMA_CONGESTION * c_buffer +
        config.DELTA_BATTERY * c_batterie
    )

    return max(0.0001, cout_total)  # Garantit un coût strictement positif


def construire_graphe(noeuds):
    """
    Construit le graphe pondéré du réseau LoRa.
    """
    graphe = {n.ID: {} for n in noeuds}

    for i, n1 in enumerate(noeuds):
        for n2 in noeuds[i + 1:]:
            if n1.liaison_possible(n2):
                # Utilisation du coût composite au lieu de la simple distance
                poids = calculer_cout_arete(n1, n2)
                graphe[n1.ID][n2.ID] = poids
                graphe[n2.ID][n1.ID] = poids

    return graphe


def dijkstra(graphe, source, destination):
    """
    Algorithme de Dijkstra adapté à la recherche du chemin de coût minimal.
    """
    if source not in graphe or destination not in graphe:
        return float('inf'), []

    distances = {sommet: float('inf') for sommet in graphe}
    predecesseurs = {sommet: None for sommet in graphe}
    distances[source] = 0.0

    compteur = itertools.count()
    filePriorite = [(0.0, next(compteur), source)]
    visites = set()

    while filePriorite:
        distActuelle, _, sommetActuelle = heapq.heappop(filePriorite)

        if sommetActuelle == destination:
            break

        if sommetActuelle in visites:
            continue

        visites.add(sommetActuelle)

        # Parcours des voisins présents dans la sous-copie du graphe
        for voisin, poids in graphe.get(sommetActuelle, {}).items():
            if voisin in visites:
                continue

            nouvelleDist = distActuelle + poids

            if voisin in distances and nouvelleDist < distances[voisin]:
                distances[voisin] = nouvelleDist
                predecesseurs[voisin] = sommetActuelle
                heapq.heappush(filePriorite, (nouvelleDist, next(compteur), voisin))

    # Reconstruction du chemin
    chemin = []
    courant = destination
    if distances[destination] != float('inf'):
        while courant is not None:
            chemin.insert(0, courant)
            courant = predecesseurs[courant]

    return distances[destination], chemin
