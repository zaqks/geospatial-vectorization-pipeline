## 1. Acquisition des donnees (approche lab / scripts)

### 1.1 Objectif de l'etape

L'objectif de cette phase est de produire un raster de travail coherent, couvrant la commune cible, avec un niveau de detail suffisant pour permettre une vectorisation par couleur. Dans le dossier lab, cette etape est principalement implemente par:

- 0_data.py
- 0_legend_extract.py
- 0_legend_overlay_poly.py
- 0_legend_overlay_line.py

Cette phase comprend deux volets:

1. acquisition spatiale (telechargement et assemblage des tuiles raster),
2. acquisition semantique (construction de la table de legendes et verification visuelle des classes).

### 1.2 Delimitation spatiale de la zone d'etude

Le script 0_data.py utilise Nominatim (via geopy) pour geocoder la commune "El Harrach, Algeria" et recuperer automatiquement une bounding box (sud, nord, ouest, est).

Hypothese retenue en laboratoire:

- la bounding box Nominatim est suffisamment proche de l'emprise utile,
- un padding est ajoute pour eviter de couper les entites en bord de zone.

Parametres techniques importants:

- ZOOM = 18
- TILE_SIZE = 256
- padding = 1

Le niveau z18 fournit une resolution detaillee (compromis entre precision et volume de donnees).

### 1.3 Conversion geographique vers grille de tuiles

Le script implemente:

- latlon_to_tile(lat, lon, zoom)
- tile_to_latlon(x, y, zoom)

Ces fonctions assurent le passage entre:

- coordonnees geographiques (WGS84, lat/lon),
- index de tuiles web (x, y, z) en projection Web Mercator.

Cette conversion est fondamentale pour savoir exactement quelles tuiles telecharger et pour calculer ensuite l'emprise reelle de l'image mosaiquee.

### 1.4 Telechargement, cache local et assemblage

Les tuiles sont recuperees depuis Carto basemaps (style voyager_nolabels) puis stockees dans un cache local:

- data/tiles/18/x_y.png

Le cache permet:

- la reproductibilite des essais,
- la reduction des requetes reseau,
- l'acceleration des relances de pipeline experimental.

Apres telechargement, les tuiles sont "stitch" dans une image unique:

- sortie: data/el_harrach_highres_map.png

Le script calcule aussi l'emprise finale de la mosaique (north/south/west/east), ce qui facilite la verification geometrique en amont du georeferencement.

### 1.5 Extraction de la signature colorimetrique

Le script 0_legend_extract.py effectue une analyse des couleurs de l'image complete:

- lecture de l'image RGB,
- aplatissement des pixels,
- aggregation des occurrences par triplet (r, g, b) avec Polars,
- calcul des pourcentages d'apparition,
- export des classes dominantes vers data/legend.csv.

Seuil applique dans l'export:

- seules les couleurs >= 0.1% sont conservees.

Interet de cette etape:

- identifier les teintes predominantes avant segmentation,
- detecter les classes rares ou bruites,
- preparer un referentiel de classes exploitable dans les scripts de vectorisation.

### 1.6 Verification visuelle de la legende

Les scripts d'overlay (0_legend_overlay_poly.py, 0_legend_overlay_line.py) appliquent un masquage couleur par classe issue de legend_class_geo.csv.

Principe:

1. conversion hex -> BGR,
2. detection des pixels cibles avec tolerance (souvent 1),
3. generation d'une image de controle ou les pixels detectes sont peints en rouge,
4. export classe par classe dans output/overlays.

Pour les lignes, un pretraitement morphologique (closing et dilatation) est ajoute afin de rendre visuellement lisibles des motifs lineaires fins.

### 1.7 Sorties et artefacts de la phase acquisition

Produits principaux:

- raster de base: data/el_harrach_highres_map.png
- table de couleurs dominantes: data/legend.csv
- table metier des classes: data/legend_class_geo.csv
- overlays de controle: output/overlays/poly/*.png et output/overlays/line/*.png

Ces artefacts alimentent directement les etapes suivantes (georeferencement et vectorisation).

### 1.8 Limites identifiees en mode laboratoire

- dependance a la qualite des couleurs source (compression, aliasing, variations locales),
- forte sensibilite du masquage a la tolerance choisie,
- risque de confusion entre classes chromatiquement proches,
- extraction des classes semantiques encore semi-supervisee (table de legende maintenue manuellement).

Malgre ces limites, la phase d'acquisition fournit une base experimentale robuste pour la chaine geospatiale ulterieure.
