## 2. Georeferencement (approche lab / scripts)

### 2.1 Enjeu scientifique et technique

Le georeferencement convertit une image raster "pixel" en couche spatialement exploitable dans un SIG. Dans le laboratoire, cette operation est realisee par le script `1_georef.py`.

Objectif concret:

* produire un GeoTIFF georeference a partir de l'image mosaiquee,
* garantir une coherence de projection avec les traitements vectoriels ulterieurs.

### 2.2 Entrees

Entrees principales:

* image source: `data/el_harrach_highres_map.png`
* bounding box geographique (lat/lon) de la zone cible, obtenue via le service de geocodage en amont

Points de controle utilises:

* coin haut-gauche (top-left) de la bounding box,
* coin bas-droit (bottom-right) de la bounding box

Ces deux points proviennent de donnees terrain issues du service de geocodage et correspondent a des coordonnees reelles, non hypothetiquees. La bounding box est suffisamment precise pour definir exactement l'emprise spatiale de l'image.

Etant donne que la zone est representee par une emprise strictement rectangulaire, ces deux points suffisent a reconstruire l'ensemble de la transformation. L'utilisation de quatre points n'apporterait aucune difference dans le resultat final, car les coins restants sont mathematiquement deduits de la meme bounding box.

* l'image issue du stitching est deja alignee sans deformation locale complexe,
* une transformation affine suffit pour passer de l'espace image a l'espace geographique,
* la bounding box fournie est parfaitement coherente avec l'image (alignement exact sans offset).

### 2.3 Systeme de reference spatial

Le script applique une conversion explicite vers Web Mercator (EPSG:3857):

1. conversion longitude -> X metrique,
2. conversion latitude -> Y metrique,
3. construction de l'emprise metrique `[min_x, min_y, max_x, max_y]`.

Formulation utilisee (rayon terrestre R = 6378137):

$$
X = R \cdot \text{rad}(\lambda), \quad
Y = R \cdot \ln\left(\tan\left(\frac{\pi}{4} + \frac{\text{rad}(\varphi)}{2}\right)\right)
$$

Le choix EPSG:3857 est coherent avec l'origine web des tuiles raster.

### 2.4 Construction de la transformee affine

La transformee est calculee via `rasterio.from_bounds` a partir:

* des bornes metriques derivees de la bounding box,
* de la largeur et de la hauteur reelles de l'image.

Les deux points de controle (top-left et bottom-right) definissent integralement et de facon unique cette emprise. Dans le cas present, ils sont suffisants et equivalents a une configuration a quatre points, puisque la geometrie est strictement rectangulaire et parfaitement definie par la bounding box terrain.

La transformation affine en decoule directement, en assurant la correspondance:

* pixel (0, 0) -> coin haut-gauche,
* pixel (width, height) -> coin bas-droit.

Cette operation lie chaque pixel (colonne, ligne) a une coordonnee projetee continue.

Extrait minimal (depuis lab/1_georef.py):

```py
transform = from_bounds(
	min_x, min_y,
	max_x, max_y,
	width, height
)
```

### 2.5 Ecriture du GeoTIFF optimise

Le script ecrit `data/el_harrach_georef.tif` avec les options suivantes:

* driver GTiff,
* 3 bandes RGB,
* crs = EPSG:3857,
* compression DEFLATE,
* predictor = 2,
* tuilage interne 256x256.

Ces parametres reduisent le volume disque et accelerent les lectures fenetrees lors des etapes de segmentation/vectorisation.

Extrait minimal (ecriture GeoTIFF):

```py
with rasterio.open(output_tif, "w", driver="GTiff", crs="EPSG:3857", transform=transform) as dst:
	dst.write(img_np[:, :, 0], 1)
	dst.write(img_np[:, :, 1], 2)
	dst.write(img_np[:, :, 2], 3)
```

### 2.6 Validation effectuee en laboratoire

Verifications typiques:

* ouverture du GeoTIFF dans QGIS/ArcGIS,
* controle visuel de l'alignement avec des fonds de reference,
* verification des metadonnees CRS et emprise.

Le passage en EPSG:3857 est ensuite impose comme precondition dans plusieurs scripts aval (vectorisation, nettoyage, visualisation).

### 2.7 Sorties et impact sur le pipeline experimental

Sortie principale:

* `data/el_harrach_georef.tif`

Ce fichier devient l'entree unique de la chaine de vectorisation:

* extraction des classes polygones,
* extraction des classes lineaires,
* nettoyage geometrique,
* production de masques de visualisation.

### 2.8 Conclusion

* la precision depend directement de la qualite de la bounding box d'entree, issue de donnees terrain fiables,
* deux points de controle (coins opposes) sont suffisants car l'emprise est strictement rectangulaire et parfaitement connue,
* le resultat obtenu est equivalent a une configuration a quatre points dans ce cas particulier,
* approximation inherente a la projection Mercator (distorsions surfaciques),
* absence de points de controle terrain supplementaires (GCP) n'affecte pas la precision globale dans ce contexte specifique.

### 2.9 Figure de verification QGIS

Figure 2 - Premiere verification de la vectorisation et du georeferencement dans QGIS

<img src="images/scripts/1_qgis_georef_check_poly.png" alt="Verification QGIS georef et vectorisation" width="100%">
