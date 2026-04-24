## 2. Georeferencement (approche lab / scripts)

### 2.1 Enjeu scientifique et technique

Le georeferencement convertit une image raster "pixel" en couche spatialement exploitable dans un SIG. Dans le laboratoire, cette operation est realisee par le script 1_georef.py.

Objectif concret:

- produire un GeoTIFF georeference a partir de l'image mosaiquee,
- garantir une coherence de projection avec les traitements vectoriels ulterieurs.

### 2.2 Entrees et hypotheses

Entrees principales:

- image source: data/el_harrach_highres_map.png
- bounding box geographique (lat/lon) de la zone cible

Hypotheses de travail:

- l'image issue du stitching est deja alignee sans deformation locale complexe,
- une transformation affine suffit pour passer de l'espace image a l'espace geographique.

### 2.3 Systeme de reference spatial

Le script applique une conversion explicite vers Web Mercator (EPSG:3857):

1. conversion longitude -> X metrique,
2. conversion latitude -> Y metrique,
3. construction de l'emprise metrique [min_x, min_y, max_x, max_y].

Formulation utilisee (rayon terrestre R = 6378137):

$$
X = R \cdot \text{rad}(\lambda), \quad
Y = R \cdot \ln\left(\tan\left(\frac{\pi}{4} + \frac{\text{rad}(\varphi)}{2}\right)\right)
$$

Le choix EPSG:3857 est coherent avec l'origine web des tuiles raster.

### 2.4 Construction de la transformee affine

La transformee est calculee via rasterio.from_bounds:

- bornes metriques de la zone,
- largeur et hauteur reelles de l'image.

Cette operation lie chaque pixel (colonne, ligne) a une coordonnee projetee continue. C'est le coeur du georeferencement dans cette architecture.

### 2.5 Ecriture du GeoTIFF optimise

Le script ecrit data/el_harrach_georef.tif avec les options suivantes:

- driver GTiff,
- 3 bandes RGB,
- crs = EPSG:3857,
- compression DEFLATE,
- predictor = 2,
- tuilage interne 256x256.

Ces parametres reduisent le volume disque et accelerent les lectures fenetrees lors des etapes de segmentation/vectorisation.

### 2.6 Validation effectuee en laboratoire

Verifications typiques:

- ouverture du GeoTIFF dans QGIS/ArcGIS,
- controle visuel de l'alignement avec des fonds de reference,
- verification des metadonnees CRS et emprise.

Le passage en EPSG:3857 est ensuite impose comme precondition dans plusieurs scripts aval (vectorisation, nettoyage, visualisation).

### 2.7 Sorties et impact sur le pipeline experimental

Sortie principale:

- data/el_harrach_georef.tif

Ce fichier devient l'entree unique de la chaine de vectorisation:

- extraction des classes polygones,
- extraction des classes lineaires,
- nettoyage geometrique,
- production de masques de visualisation.

### 2.8 Limites et risques

- precision dependante de la qualite de la bbox d'entree,
- approximation inherente a la projection Mercator (distorsions surfaciques),
- absence de points de controle terrain explicites (GCP) dans le script lab.

Pour l'objectif du projet (vectorisation thematique de carte web), ce compromis reste acceptable et operationnel.
