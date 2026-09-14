import heapq

def dijkstra(graphe, source, destination):
    # initialisation des distances à l'infini et des prédécesseurs
    distances = {sommet: float('inf') for sommet in graphe}
    predecesseurs = {sommet: None for sommet in graphe}
    distances[source] = 0
    
    # file de priorité (distance, sommet)
    filePriorite = [(0, source)]
    visites = set()

    while filePriorite:
        distActuelle, sommetActuelle = heapq.heappop(filePriorite)
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
                heapq.heappush(filePriorite, (nouvelleDist, voisin))

    # reconstruction du chemin
    chemin = []
    courant = destination
    if distances[destination] != float('inf'):
        while courant is not None:
            chemin.insert(0, courant)
            courant = predecesseurs[courant]
            
    return distances[destination], chemin
