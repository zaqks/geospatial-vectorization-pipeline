## 2. Georeferencement industrialise (flow 1)

### 2.1 Position du georef dans l'orchestration

Le flow 1_georef est execute apres setup_workspace. Il transforme l'image utilisateur en GeoTIFF georeference, base commune de tous les traitements geospatiaux aval.

Enchainement:

- entree: /tmp/<uuid>/data/input.png + bornes stockees en DB,
- sortie: /tmp/<uuid>/data/georef.tif,
- progression: 10%,
- trigger suivant: 2_vectorization_line.

### 2.2 Recuperation des parametres geospatiaux

Le service get_input_georef_bounds lit lat1/lat2/lng1/lng2 depuis la table inputs.

Le flow:

1. ordonne les bornes (south<north, west<east),
2. convertit WGS84 vers Web Mercator (EPSG:3857),
3. construit la transformee affine avec rasterio.from_bounds.

Ce design garantit que le georeferencement est derive de la metadonnee transactionnelle, et non d'un etat local fragile.

### 2.3 Ecriture raster optimisee

Le GeoTIFF est genere avec:

- compression DEFLATE,
- predictor=2,
- tuilage interne 256x256.

Ces choix diminuent:

- le volume disque,
- la latence de lecture partielle,
- la pression memoire lors des flows de segmentation.

### 2.4 Mode d'execution asynchrone

Le flow est defini async, mais les operations CPU/IO lourdes sont executees dans des threads via asyncio.to_thread. Cela evite de bloquer la boucle event-loop de l'orchestrateur.

Bonnes pratiques appliquees:

- encapsulation des operations lourdes dans fonctions locales synchrones,
- offload thread pour PIL+rasterio,
- notification progression hors thread principal de l'orchestrateur.

### 2.5 Mecanisme de chaining

Apres succes georef:

- update_input_progress(uuid, 10)
- notify_api_progress(... task="1_georef.georef_main")
- tirrger_flow("2_vectorization_line", uuid)

Le chaining compose un graphe de calcul deterministic par transitions explicites entre flows.

### 2.6 Robustesse et nettoyages

Le flow execute un GC de fin (run_gc_cleanup) pour limiter l'accumulation d'objets Python apres operations raster volumineuses.

En contexte HPC/multi-job:

- ce pattern reduit le risque d'emballement memoire,
- il facilite une meilleure stabilite lorsque plusieurs jobs se succedent.

### 2.7 Limites et axes d'amelioration

- pas de recalage par points de controle externes,
- precision dependante de la bbox fournie par l'utilisateur,
- projection unique EPSG:3857 (pas de pipeline multi-CRS natif).

Pour ce cas d'usage (cartographie web style OSM), ce compromis est pertinent et cohérent avec la vectorisation couleur.
