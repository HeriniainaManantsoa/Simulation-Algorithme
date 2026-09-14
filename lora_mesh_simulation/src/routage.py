import copy
from dijkstra import dijkstra

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
