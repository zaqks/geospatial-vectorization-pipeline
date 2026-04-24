## 3. Vectorisation et post-traitement (approche lab / scripts)

### 3.1 Principe general

La vectorisation transforme des motifs raster en objets geometriques (LineString, Polygon) classes semantiquement. Dans le laboratoire, cette phase est distribuee sur plusieurs scripts:

- 2_vectorization_line.py
- 2_vectorization_dotted.py
- 2_vectorization_poly.py
- 3_clean_noise_poly.py
- 3_clean_gapfill.py

Le referentiel de classes est fourni par data/legend_class_geo.csv.

### 3.2 Vectorisation des polygones

Le script 2_vectorization_poly.py suit une logique de classification exacte RGB:

1. lecture du raster georeference,
2. construction d'une table couleur -> classe,
3. encodage des pixels (RGB -> index de classe),
4. extraction des formes via rasterio.features.shapes,
5. generation d'un GeoJSON par classe.

Points techniques:

- traitement sur les 3 bandes RGB,
- classes sans correspondance ignorees (label = -1),
- export par classe dans output/vect/poly.

Ce choix est efficace lorsque la cartographie source utilise des couleurs plates stables.

### 3.3 Vectorisation des lignes continues

Le script 2_vectorization_line.py traite les classes lineaires hors railway:

1. masquage couleur avec tolerance,
2. fermeture morphologique (closing) pour reconnecter les ruptures mineures,
3. suppression des objets trop petits (seuil en m2 converti en pixels),
4. skeletonization (axe median),
5. conversion en geometries lineaires,
6. simplification et filtrage par longueur minimale.

Parametres structurants:

- COLOR_TOLERANCE,
- CLOSING_RADIUS,
- MIN_OBJECT_SIZE_M2,
- MIN_LINE_LENGTH,
- SIMPLIFY_TOLERANCE.

Ces parametres pilotent le compromis precision/robustesse.

### 3.4 Vectorisation des lignes pointillees (railway)

Le script 2_vectorization_dotted.py adresse explicitement la classe railway, plus difficile a extraire:

- masquage par intervalle de couleur (borne basse/haute),
- ouverture + fermeture morphologique (denoising et bridge),
- skeletonization,
- detection des endpoints,
- reconnection des extremites proches via KDTree,
- export GeoJSON lineaire.

Cette methode est adaptee aux graphes discontinus et symboles pointilles.

### 3.5 Nettoyage geometrique des polygones

Le script 3_clean_noise_poly.py applique un pipeline de sanitation:

- suppression des geometries nulles/vides,
- correction de validite geometrique (make_valid),
- explode des MultiPolygon,
- filtrage sur type geometrique,
- elimination des petites surfaces.

Objectif:

- supprimer les artefacts issus du bruit raster,
- conserver un schema geometrique plus stable pour l'analyse.

### 3.6 Gap filling cible sur la classe water

Le script 3_clean_gapfill.py realise un traitement specialise pour water:

1. union des objets,
2. buffer positif puis buffer negatif (fermeture des trous fins),
3. suppression des trous internes,
4. simplification geometrique,
5. re-export de la couche water.

Ce traitement corrige les vides crees par du texte cartographique ou des interruptions de teinte.

### 3.7 Visualisation de controle (etape de validation visuelle)

Les scripts 6_viz_line.py et 6_viz_poly.py rasterisent toutes les classes et produisent:

- masques RGBA par classe,
- overlays sur image de base.

Une optimisation notable est deja presente:

- raster unique de classes (uint16) puis extraction de chaque masque par comparaison numpy.

### 3.8 Sorties vectorielles

Repertoire principal:

- output/vect/poly/*.geojson
- output/vect/line/*.geojson

Sorties complementaires:

- PNG de debug/overlay pour inspection qualitative.

Ces sorties sont ensuite reprises par l'etape de nettoyage et de visualisation de controle, documentee dans le chapitre suivant, avant d'entrer dans la validation topologique.

### 3.9 Conclusion

- sensibilite aux collisions chromatiques entre classes,
- risque de sur-segmentation des bords,
- nettoyage encore heuristique (parametres a calibrer selon zone et style cartographique),
- methodes basees couleur peu robustes aux changements de style de carte.

La chaine lab est suffisamment mature pour produire une BDG exploitable et robuste pour la suite des controles topologiques.
