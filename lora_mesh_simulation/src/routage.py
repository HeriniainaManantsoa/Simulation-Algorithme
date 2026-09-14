import copy
from dijkstra import dijkstra, construire_graphe

def yen(graphe, source, destination, nbrChemin):
    # stocke les K plus courts chemins validés
    courtsChemins = []
    # stocke les chemins candidats potentiels
    cheminsCandidats = []

    # trouver le premier chemin le plus court
    cout, premierChemin = dijkstra(graphe, source, destination)
    if not premierChemin:
        # aucun chemin existant
        return courtsChemins 

    courtsChemins.append((cout, premierChemin))

    # boucle pour trouver les K-1 chemins suivants
    for k in range(1, nbrChemin):
        # chemin de référence est le dernier ajouté à courtsChemins
        cheminPrecedent = courtsChemins[-1][1]
        
        # itèration sur chaque sommet du chemin précédent sauf la destination
        for i in range(len(cheminPrecedent) - 1):
            sommetDeviation = cheminPrecedent[i]
            cheminRacine = cheminPrecedent[:i + 1]

            # copie de travail du graphe pour modifications temporaires
            grapheATravailler = copy.deepcopy(graphe)

            # supprimer les arcs déjà utilisés dans les chemins de courtsChemins 
            # qui partagent le même chemin racine
            for courtchemin, p in courtsChemins:
                if len(p) > i and p[:i + 1] == cheminRacine:
                    u = p[i]
                    v = p[i + 1]
                    if u in grapheATravailler and v in grapheATravailler[u]:
                        del grapheATravailler[u][v]

            # supprimer les sommets du chemin racine (sauf le sommet de déviation)
            # pour éviter de boucler et forcer un chemin simple
            for sommet in cheminRacine[:-1]:
                if sommet in grapheATravailler:
                    del grapheATravailler[sommet]
                for u in grapheATravailler:
                    if sommet in grapheATravailler[u]:
                        del grapheATravailler[u][sommet]

            # calculer le sous-chemin le plus court du sommet de déviation à la destination
            coutDeviation, cheminDeviation = dijkstra(grapheATravailler, sommetDeviation, destination)

            if cheminDeviation:
                # combiner le chemin racine et le chemin déviation
                cheminCandidat = cheminRacine[:-1] + cheminDeviation
                
                # calculer le coût total du candidat
                coutTotal = 0
                for j in range(len(cheminCandidat) - 1):
                    coutTotal += graphe[cheminCandidat[j]][cheminCandidat[j+1]]
                
                # ajouter aux candidats s'il n'y est pas déjà
                if (coutTotal, cheminCandidat) not in cheminsCandidats:
                    cheminsCandidats.append((coutTotal, cheminCandidat))

        if not cheminsCandidats:
            # plus aucun chemin candidat disponible
            break 

        # trier les candidats par coût et extraire le plus court
        cheminsCandidats.sort(key=lambda x: x[0])
        meilleurCandidat = cheminsCandidats.pop(0)
        courtsChemins.append(meilleurCandidat)

    return courtsChemins


def yen_depuis_noeuds(noeuds, id_source, id_destination, nbrChemin):
    """
    Variante de yen() qui prend directement la liste de Noeud renvoyée
    par data_loader.charger_pylones_fixes() (ou toute liste de Noeud,
    fixes + candidats), au lieu d'exiger un graphe déjà construit à la main.

    - Construit le graphe via dijkstra.construire_graphe(noeuds), qui
      relie les nœuds selon liaison_possible() (portée radio DMAX) et
      pondère chaque arête par la distance Haversine.
    - Appelle yen() normalement (elle travaille sur des ID, donc rien
      à changer côté algorithme).
    - Retraduit chaque chemin d'une liste d'ID vers une liste de Noeud,
      pour rester cohérent avec le reste du projet qui manipule des
      objets Noeud (ex. pour afficher Nom_Site, Operateur, etc. via
      Noeud.__str__).

    Paramètres
    ----------
    noeuds : list[Noeud]
    id_source, id_destination : int
        ID des nœuds de départ/arrivée (attribut Noeud.ID).
    nbrChemin : int
        Nombre de chemins à calculer (K de l'algorithme de Yen).

    Retour
    ------
    list[tuple[float, list[Noeud]]]
        Liste de (coût_total_km, chemin) triée par coût croissant.
    """

    graphe = construire_graphe(noeuds)
    resultats = yen(graphe, id_source, id_destination, nbrChemin)

    noeuds_par_id = {n.ID: n for n in noeuds}

    return [
        (cout, [noeuds_par_id[id_] for id_ in chemin])
        for cout, chemin in resultats
    ]
