## 4. Validation topologique (approche lab / scripts)

### 4.1 Objectif

La validation topologique vise a detecter les incoherences geometriques et semantiques dans les couches vectorielles produites. Le script principal est 7_validation_topo.py.

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

### 4.4 Interet methodologique

Cette approche permet:

- une validation reproductible et scriptable,
- une separation claire entre detection et correction,
- une exploitation facile des erreurs dans un SIG pour revue experte.

Dans un contexte academique, cela formalise des contraintes metier sous forme de regles calculables.

### 4.5 Limites de l'implementation actuelle

La version actuelle du script presente des incoherences de code qui doivent etre corrigees pour une execution production:

- appels a load_clean alors que la fonction definie est load,
- dependance a des chemins de fichiers specifiques (noms "*_clean"),
- absence de parametrage centralise des couches et regles.

En consequence, le script decrit correctement la logique de validation, mais requiert une phase de fiabilisation pour etre integre tel quel dans une chaine automatisee.

### 4.6 Recommandations de consolidation

Pour une industrialisation de la validation topo:

1. externaliser les regles dans un fichier de configuration,
2. uniformiser les conventions de nommage des couches,
3. ajouter des tests unitaires sur chaque regle,
4. produire un rapport quantitatif (nb erreurs par type, densite, severite),
5. chaîner automatiquement validation -> correction -> revalidation.

### 4.7 Conclusion section lab

Le travail laboratoire fournit une base complete:

- extraction raster et legende,
- georeferencement,
- vectorisation multi-geometries,
- nettoyage,
- debut de validation topologique.

La valeur principale de cette phase est d'avoir transforme une demarche exploratoire en briques algorithmiques reemployables dans la version pipeline.
