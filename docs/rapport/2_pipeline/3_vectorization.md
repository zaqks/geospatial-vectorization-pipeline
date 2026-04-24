## 3. Vectorisation a l'echelle et optimisations HPC/big data

### 3.1 Chaine de calcul flow 2 -> flow 5

La vectorisation industrialisee est decoupee en flows specialises:

1. 2_vectorization_line
2. 2_vectorization_dotted
3. 2_vectorization_poly
4. 3_clean_noise_poly
5. 3_clean_gapfill
6. 4_viz_line
7. 4_viz_poly
8. 5_export_output

Chaque flow met a jour la progression DB et notifie l'API pour exposition temps reel.

### 3.2 Pourquoi ce decoupage est adapte au big data

Le decoupage en micro-etapes apporte:

- isolation des pannes (un flow en echec est localise),
- observabilite fine (pourcentage + task),
- modularite d'optimisation (chaque flow peut etre profile independamment),
- possibilite d'evolution vers execution distribuee multi-workers.

### 3.3 Techniques de vectorisation implementees

Lignes standard (hors railway):

- seuillage couleur avec tolerance,
- fermeture morphologique,
- suppression petits objets,
- skeletonization,
- simplification geometrique,
- export GeoJSON.

Railway (pointille/discontinu):

- segmentation par intervalle RGB,
- opening/closing morphologique,
- skeletonization,
- reconnection d'endpoints via KDTree,
- filtrage par longueur.

Polygones:

- encodage massif RGB->index,
- extraction rasterio.features.shapes,
- export classe par classe.

### 3.4 Optimisations explicites dans le code

Optimisations compute:

- usage de numpy vectorise pour comparaisons couleur,
- lecture raster en blocs memoire compacts,
- conversion des calculs lourds en to_thread pour ne pas bloquer l'event loop.

Optimisations I/O:

- workspace local par job sous /tmp/<uuid>,
- export final archive en zip pour limiter le nombre de transferts,
- upload HF en references path (pas de blob SQL).

Optimisations memoire:

- nettoyage GC en fin de flow,
- suppression/recreation des artefacts output avant upsert DB,
- batching de flush DB lors insertion des fichiers GeoJSON.

Optimisations visualisation:

- generation de masques PNG redimensionnes (division par 2),
- compression PNG elevee (compress_level=9).

### 3.5 Points infra orientes HPC

Niveau conteneurs:

- service pipeline sur base pangeo/pangeo-notebook (stack geospatiale lourde preintegree),
- limite memoire docker-compose definie (2G) pour maitriser la contention,
- separation API/pipeline/app pour scaler horizontalement selon charge.

Niveau architecture:

- calcul geospatial concentre dans pipeline,
- API reservee a l'orchestration, persistance, media serving,
- frontend decouple pour experiences utilisateur non bloquantes.

### 3.6 Export et publication des resultats

Le flow 5_export_output:

1. archive output/ en output.zip,
2. upsert DB (Output, OutputFile, OverlayImage),
3. upload artefacts vers HF bucket,
4. progression finale 100% + result_ready=true.

Le frontend consomme ensuite:

- preview image,
- overlays png,
- fichiers telechargeables (zip, et/ou artefacts selon export).

### 3.7 Limites techniques actuelles

- certains enchainements restent synchrones dans le trigger entre flows,
- pas encore de queue externe (type broker) pour orchestration massive,
- absence de partitionnement spatial dynamique sur tres grands rasters,
- vectorisation fortement dependante du style colorimetrique de la carte source.

### 3.8 Feuille de route d'optimisation big data

1. introduire une file de jobs (Kafka/Rabbit/Redis streams),
2. paralleliser par tuiles (windowed raster processing),
3. fusionner les vecteurs en phase reduce,
4. ajouter cache de masques intermediaires,
5. instrumenter metriques CPU/RAM/latence par flow,
6. auto-scaler les workers pipeline selon backlog.
