## 4. Validation topologique (approche lab / scripts)

### 4.1 Objectif

La validation topologique vise a detecter les incoherences geometriques et semantiques dans les couches vectorielles produites. Elle intervient apres les phases de vectorisation, de nettoyage geometrique et de visualisation de controle. Le script principal est 7_validation_topo.py.

L'approche adoptee est une validation par regles d'intersection entre classes.

### 4.2 Strategie de controle

Le script charge plusieurs couches (lignes et polygones), applique un nettoyage de base (geometries valides, non vides), puis execute des tests spatiaux via indexation spatiale.

Fonction centrale:

- find_intersections(a, b)

Cette fonction:

1. construit l'index spatial de la couche b,
2. recherche les candidats par emprise (bounding boxes),
3. teste l'intersection geometrique exacte,
4. collecte les geometries conflictuelles.

### 4.3 Regles de validation implementees

Les verifications explicites du script couvrent notamment:

- batiments intersectant l'eau,
- batiments intersectant le reseau routier,
- incoherences entre hierarchies routieres,
- zones residentielles intersectant l'eau,
- conflits metro vs batiments / eau.

Le script exporte ensuite des couches d'erreurs en GeoJSON (errors_*.geojson) pour audit cartographique.

Ces conflits ne sont pas seulement detectes: ils servent aussi de base a une phase de nettoyage et de resolution contextuelle. L'idee est de conserver la classe la plus pertinente selon le contexte cartographique. Par exemple, en cas de chevauchement entre une route et un batiment, on privilegie la route et on ajuste ou retire la geometrie du batiment sur la zone de conflit.

### 4.4 Interet methodologique

Cette approche permet:

- une validation reproductible et scriptable,
- une separation claire entre detection et correction,
- une exploitation facile des erreurs dans un SIG pour revue experte.

Dans un contexte academique, cela formalise des contraintes metier sous forme de regles calculables.

### 4.5 Conclusion section lab

Le travail laboratoire fournit une base complete:

- extraction raster et legende,
- georeferencement,
- vectorisation multi-geometries,
- nettoyage,
- visualisation de controle,
- debut de validation topologique.

La valeur principale de cette phase est d'avoir transforme une demarche exploratoire en briques algorithmiques reemployables dans la version pipeline.
