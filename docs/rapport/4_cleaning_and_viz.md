## 4. Nettoyage geometrique et visualisation de controle (approche lab / scripts)

### 4.1 Role dans la chaine de traitement

Apres la vectorisation brute, les geometries produites ne sont pas encore directement exploitables comme resultat scientifique final. Cette etape intermediaire a deux objectifs complementaires:

1. stabiliser les geometries avant les controles topologiques,
2. fournir une verification visuelle rapide de la qualite des extractions.

Dans le laboratoire, cette couche de post-traitement est assuree par:

- 3_clean_noise_poly.py
- 3_clean_gapfill.py
- 6_viz_line.py
- 6_viz_poly.py

Le principe general est le suivant:

- nettoyer les artefacts geometriques issus de la rasterisation et du seuillage couleur,
- normaliser les types geometriques,
- corriger les ruptures ou trous les plus evidents,
- rasteriser a nouveau les resultats pour obtenir des masques et overlays de controle.

### 4.2 Nettoyage geometrique des polygones

Le script 3_clean_noise_poly.py traite les couches polygonales classe par classe. Il implante un pipeline de sanitation geometrique volontairement conservateur, construit pour supprimer le bruit sans deformer excessivement les entites.

Les operations appliquees sont les suivantes:

1. suppression des geometries nulles ou vides,
2. correction des geometries invalides avec make_valid,
3. explosion des MultiPolygon en entites elementaires,
4. filtrage de securite sur les types Polygon et MultiPolygon,
5. verification stricte du CRS d'entree,
6. calcul de surface et filtrage par seuil minimal,
7. revalidation finale apres nettoyage.

Le script impose explicitement un espace de travail en EPSG:3857. Cette contrainte est essentielle, car le calcul de surface et le raster de debug reposent sur des unites metriques coherentes.

Le seuil min_area_m2 joue un role central:

- il elimine les fragments residuels issus du bruit raster,
- il evite de conserver des polygones parasites dans des zones de forte densite graphique,
- il limite la propagation de micro-objets dans les phases de validation ulterieures.

Le script produit ensuite deux sorties par couche nettoyee:

- un GeoJSON nettoye,
- une image PNG de debug rasterisee sur la base du raster georeference.

### 4.3 Traitement specialise de la classe water

Le script 3_clean_gapfill.py applique un traitement cible sur la classe water. Cette classe est particulierement sensible, car la cartographie scannee peut introduire des interruptions visuelles dues au texte, aux variations de teinte ou a des coupures de trait.

Le workflow est le suivant:

1. chargement de la couche water,
2. verification de la presence des donnees et du CRS,
3. union geometrique de toutes les entites,
4. buffer positif puis buffer negatif pour refermer les lacunes fines,
5. suppression explicite des trous internes,
6. simplification geometrique legere,
7. reecriture de la couche nettoyee,
8. rasterisation du resultat pour produire un masque de controle.

Le couple buffer(+BUFFER_DIST) / buffer(-BUFFER_DIST) agit comme une fermeture morphologique geometrique. Il permet de reconnecter des segments proches et de lisser des discontinuites fines sans reconstruire manuellement la couche.

La suppression des trous internes est importante dans un contexte cartographique:

- elle limite les faux trous crees par des artefacts de scan,
- elle produit une representation plus stable pour la suite du pipeline,
- elle facilite les verifications visuelles et les comparaisons inter-couches.

Le script reexporte ensuite:

- output/vect/poly/water.geojson,
- output/vect/poly/water.png.

Cette double sortie permet de verifier simultanement la geometrie vectorielle et sa coherence spatiale avec l'image de reference.

### 4.4 Visualisation de controle des sorties vectorielles

Les scripts 6_viz_poly.py et 6_viz_line.py sont utilises pour produire une validation visuelle systematique des couches extraitees.

Ils reposent sur une meme logique:

1. chargement de la table semantique legend_class_geo.csv,
2. association de chaque classe a un indice entier z,
3. lecture du raster georeference comme support de reference,
4. chargement de toutes les couches GeoJSON produites par vectorisation,
5. rasterisation de l'ensemble des geometries en un raster de classes unique,
6. extraction par comparaison numpy pour produire masques et overlays par classe.

Le point cle d'optimisation est la construction d'un raster unique class_raster de type uint16. Ce choix evite de rasteriser une couche complete pour chaque classe et reduit fortement les couts de calcul lorsque le nombre de classes augmente.

Ensuite, pour chaque classe:

- un masque RGBA est genere,
- un overlay RGB est genere sur l'image de base,
- les fichiers sont exportes dans output/viz.

Cette strategie permet une verification tres rapide des resultats, classe par classe, sans repasser par un SIG interactif a chaque iteration.

### 4.5 Interet methodologique

Cette etape de nettoyage et de visualisation a une valeur scientifique nette:

- elle distingue les erreurs de segmentation des erreurs de projection,
- elle permet de reperer les sur-segmentations ou les coupures excessives,
- elle fournit un support reproductible pour l'analyse comparative des parametres,
- elle permet de documenter la robustesse du pipeline avant les controles topologiques formels.

Dans un contexte academique, ces sorties servent de preuve intermediaire de qualite: elles ne sont pas le resultat final, mais elles montrent que la transformation des donnees raster en objets geometriques a ete controlee a plusieurs niveaux.

### 4.6 Conclusion

Cette couche de post-traitement reste heuristique.

- le seuil min_area_m2 doit etre ajuste selon l'echelle et la densite graphique,
- le buffer gap filling peut lisser certaines structures fines s'il est trop large,
- la visualisation de controle reste qualitative et ne remplace pas une validation topologique formelle,
- la logique de nettoyage est encore specifique a certaines classes, notamment water.

Cette etape est indispensable: elle transforme des sorties de vectorisation brutes en couches plus stables, plus lisibles et mieux preparees pour l'etape de validation topologique.

### 4.7 Figures (nettoyage et gap filling)

Figure 3 - Avant nettoyage des polygones (bruit et points parasites)

<img src="images/scripts/2_before_poly_clean.png" alt="Avant nettoyage polygones" width="100%">

Figure 4 - Apres nettoyage des polygones

<img src="images/scripts/2_after_poly_clean.png" alt="Apres nettoyage polygones" width="100%">

Figure 5 - Avant gap filling (rivière avec interruptions)

<img src="images/scripts/3_before_gapfill.png" alt="Avant gap filling" width="100%">

Figure 6 - Apres gap filling

<img src="images/scripts/3_after_gapfill.png" alt="Apres gap filling" width="100%">

Figure 7 - Resultat final (sans OSM)

<img src="images/scripts/4_final_result_noosm.png" alt="Resultat final sans OSM" width="100%">

Figure 8 - Resultat final (avec OSM)

<img src="images/scripts/4_final_result_osm.png" alt="Resultat final avec OSM" width="100%">