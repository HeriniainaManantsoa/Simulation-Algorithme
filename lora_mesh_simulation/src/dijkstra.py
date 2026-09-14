import heapq
import itertools


def construire_graphe(noeuds):
    """
    Construit le graphe pondéré du réseau à partir d'une liste de Noeud
    (pylônes fixes + modules candidats, cf. models.Noeud / data_loader.py).

    Le graphe est un dict de dicts : {ID_noeud: {ID_voisin: poids}}.

    On utilise Noeud.ID (int) comme clé, PAS l'objet Noeud lui-même :
    Noeud est un @dataclass qui génère un __eq__ mais pas de __hash__,
    donc un Noeud est unhashable et ne peut pas servir de clé de dict
    ni entrer dans le set `visites` de dijkstra().

    Une arête (i, j) existe si n1.liaison_possible(n2) est vraie
    (distance <= config.DMAX, portée radio théorique calculée dans
    config.py à partir du bilan de liaison LoRa). Le poids de l'arête
    est la distance Haversine en km (Noeud.calculer_distance), donc
    dijkstra() minimise la distance physique totale du trajet.

    Paramètre
    ---------
    noeuds : list[Noeud]

    Retour
    ------
    dict[int, dict[int, float]]
        Graphe utilisable directement par dijkstra() et yen().
    """

    graphe = {n.ID: {} for n in noeuds}

    for i, n1 in enumerate(noeuds):
        for n2 in noeuds[i + 1:]:
            if n1.liaison_possible(n2):
                d = n1.calculer_distance(n2)
                graphe[n1.ID][n2.ID] = d
                graphe[n2.ID][n1.ID] = d  # liaison radio symétrique

    return graphe


def dijkstra(graphe, source, destination):
    # initialisation des distances à l'infini et des prédécesseurs
    distances = {sommet: float('inf') for sommet in graphe}
    predecesseurs = {sommet: None for sommet in graphe}
    distances[source] = 0

    # compteur utilisé comme deuxième clé de tri dans le tas : heapq
    # compare les tuples élément par élément, donc en cas d'égalité de
    # distance il comparerait sinon les sommets entre eux. Avec des ID
    # (int) ça ne plante pas, mais ça briserait l'ordre d'insertion et
    # ça planterait si graphe est un jour construit avec des clés non
    # comparables (ex. des tuples ou objets) -> ce compteur rend le tri
    # toujours valide, peu importe le type des sommets.
    compteur = itertools.count()

    # file de priorité (distance, compteur, sommet)
    filePriorite = [(0, next(compteur), source)]
    visites = set()

    while filePriorite:
        distActuelle, _, sommetActuelle = heapq.heappop(filePriorite)
        if sommetActuelle == destination:
            break
        if sommetActuelle in visites:
            continue
        visites.add(sommetActuelle)

        # exploration des voisins
        for voisin, poids in graphe.get(sommetActuelle, {}).items():
            # si le voisin a été supprimé (utile pour l'algorithme de Yen)
            if voisin not in distances:
                continue

            nouvelleDist = distActuelle + poids
            if nouvelleDist < distances[voisin]:
                distances[voisin] = nouvelleDist
                predecesseurs[voisin] = sommetActuelle
                heapq.heappush(filePriorite, (nouvelleDist, next(compteur), voisin))

    # reconstruction du chemin
    chemin = []
    courant = destination
    if distances[destination] != float('inf'):
        while courant is not None:
            chemin.insert(0, courant)
            courant = predecesseurs[courant]

    return distances[destination], chemin
