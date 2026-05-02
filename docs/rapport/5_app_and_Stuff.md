## Industrialized Pipeline: From Lab Prototype to Flow Orchestration

### 1. General Positioning

In the laboratory prototype, each step of geospatial processing was first expressed as autonomous scripts: acquisition, georeferencing, vectorization, cleaning, visualization and topological validation. The pipeline version follows exactly this functional logic, but transforms it into a suite of triggerable, observable flows deployed in infrastructure separate from the input frontend.

This change is significant from a methodological standpoint. We are no longer dealing with a simple local processing tool, but a distributed computing system where:

- the frontend only collects user inputs and presents progress status,
- the API plays the control plane role,
- the pipeline carries heavy geospatial computation,
- PostgreSQL maintains metadata and job state,
- Hugging Face serves as object bucket for large files,
- GitHub Actions automates deployment to HF Spaces.

This separation is that of a data-oriented architecture. It is more suitable than a classical monolithic application, because the main load is not CRUD logic, but manipulation of rasters, GeoJSON, PNG masks and large variable-sized artifacts.

### 2. From Script to Flow

The transition from lab to pipeline does not consist of rewriting geospatial logic. It consists of encapsulating it within more robust execution boundaries.

In the lab directory, scripts serve as scientific prototype:

- `1_georef.py` for referencing,
- `2_vectorization_*.py` for segmentation and vector extraction,
- `3_clean_*.py` for geometric cleaning and gap filling,
- `6_viz_*.py` for control visualization,
- `7_validation_topo.py` for topological validation rules.

In `services/pipeline`, these steps become Plombery flows. The business logic remains close, but execution is recomposed around several technical properties:

- atomic and chainable steps,
- progress published at each subtask,
- easier recovery in case of failure,
- workspace isolated by UUID,
- data exchange via temporary local files rather than shared memory.

The pipeline thus behaves as a state machine for geospatial processing rather than a simple single function.

### 3. Overall System Architecture

The complete system rests on three application services and two infrastructure layers.

The Vite frontend, in `services/app`, provides the input and consultation interface. It receives a file, a bounding box with two points and then opens an SSE stream to track execution.

The FastAPI API, in `services/api`, receives the upload, validates input structure, persists metadata, sends the image to Hugging Face, then triggers the pipeline via HTTP call to the compute service.

The pipeline, in `services/pipeline`, executes heavy geospatial transformations in a `pangeo/pangeo-notebook:6f9fda2` container, which natively provides Python 3.12, GDAL, GEOS and necessary geospatial components.

PostgreSQL stores the following relational objects:

- `inputs` for user inputs and progress,
- `outputs` for 1-1 link with input,
- `output_files` for exported artifacts,
- `overlay_images` for visualization masks.

Hugging Face serves as external object storage. Large files are not copied as blobs in the database, but as bucket/repository type paths. This approach greatly reduces SQL transaction size and allows moving artifacts without overloading PostgreSQL.

### 4. Ingestion and Control on API Side

The application entry point is `POST /api/upload`.

The frontend sends a multipart form containing:

- the image file,
- the bounding box serialized as `{"points":[{"lat":...,"lng":...},{"lat":...,"lng":...}]}`.

The API applies several control treatments:

- JSON structure validation,
- conversion of points into four numeric bounds,
- job UUID generation,
- image transfer to Hugging Face bucket,
- creation of `Input` row in database with initial progress at `0`.

The API does not directly launch geospatial processes. It serves as transactional gateway between user world and compute layer. Once upload is persisted, it calls `trigger_pipeline_with_retry`, which contacts the first pipeline flow with retry policy and timeout. This point is essential: if the pipeline takes a few seconds to start or if the service is momentarily unavailable, the frontend does not block waiting for synchronous computation.

This logic transforms a classic web request into an asynchronous task processed out-of-band.

### 5. Real-Time Channel and Execution Return

Progress consultation is done via Server-Sent Events.

The frontend opens `GET /api/events/{uuid}` right after sending the upload. The backend first returns a snapshot from the database, then relays events published by the pipeline via `POST /api/events/notify`.

This mechanism addresses two needs:

- give immediate feedback to the user,
- avoid aggressive polling on the API.

As output, `GET /api/result/{uuid}` assembles the preview URL, list of overlays and list of exported files. The frontend can then display the final result and maintain certain local states to accelerate subsequent requests.

In this architecture, SSE plays the role of lightweight progress bus. It does not replace persistence, but completes it with a real-time UX layer.

### 6. Hugging Face Object Storage and PostgreSQL Role

The system makes a strict separation between metadata and payloads.

PostgreSQL carries transactional control:

- job UUID,
- file name,
- storage ref,
- geographic bounds,
- progress percentage,
- relations between input, exports and overlays.

Hugging Face carries files:

- uploaded input image,
- exported GeoJSON,
- `output.zip` archive,
- visualization images,
- PNG masks.

The storage path is derived from UUID, giving a stable and predictable structure of type `uploads/<uuid>/input/<name>`. The default bucket is configured by `HF_BUCKET_REPO_ID` and connection relies on `HF_TOKEN`.

This design is more robust than integral database storage for three reasons:

- it avoids burdening tables with large binaries,
- it allows versioning or migrating artifacts as independent objects,
- it facilitates sharing between API and pipeline without duplicating serialization logic.

### 7. Compute Flows and Correspondence with Lab Scripts

The pipeline follows the scientific sequence of the laboratory, but makes it executable and reproducible in a server environment.

#### 7.1 Flow 0: Workspace Preparation

`0_setup_workspace` initializes an isolated workspace under `/tmp/<uuid>`.

Its responsibilities are as follows:

- create local compute directory structure,
- retrieve image from Hugging Face using `Input.image_ref`,
- reconvert to local working PNG,
- copy business configuration files `legend_class_geo.csv` and `colors.csv`,
- notify backend of initial progress,
- chain to georeferencing.

This step is the hinge between control plane and data plane. It guarantees each job has its own workspace and following flows do not depend on shared global states.

#### 7.2 Flow 1: Georeferencing

The georeferencing flow transforms the raw image into spatially coherent GeoTIFF.

It retrieves bounds stored in database, puts them in correct order, then builds affine transformation starting from user bbox. The raster is written with internal compression and tiling to reduce disk size and optimize partial reads.

The result of this flow becomes the common reference for all following steps. From this point on, the image is no longer just a document, but a georeferenced raster usable as geospatial support.

#### 7.3 Flow 2: Vectorization

Vectorization is decomposed into multiple specialized flows by object type:

- continuous lines,
- dotted lines,
- polygons.

This decomposition directly corresponds to laboratory prototype scripts, but with orchestrable execution and finer progress reporting.

The general principle remains the same as in experimental scripts:

- color classification,
- morphological cleaning,
- component extraction,
- geometric simplification,
- GeoJSON export.

This phase concentrates most compute load. That is why it is isolated in the pipeline and should not run in a simple synchronous API layer.

#### 7.4 Flow 3: Geometric Cleaning and Gap Filling

Lab cleaning scripts have been retained as reference logic and transformed into dedicated pipeline steps.

Cleaning plays a dual role:

- remove geometric noise from segmentation,
- stabilize entities before visualization and validation.

The polygon layer notably applies:

- correction of invalid geometries,
- removal of empty entities,
- filtering by minimum area,
- revalidation after cleaning.

The `water` class case is particular, as it benefits from gap filling treatment via positive then negative buffer operations, to close fine gaps and produce more continuous geometry.

In a data-intensive architecture, this step is important: it reduces false positives visible in later validation and limits manual corrections.

#### 7.5 Flow 4: Control Visualization

Visualization scripts do not only serve to produce pretty figures. They constitute a reproducible QA mechanism.

The idea is to rasterize vector outputs in a unique class space, then generate for each class:

- a mask,
- an overlay on the reference image,
- a PNG output in the viz folder.

Cette approche permet de verifier tres vite si une classe a ete bien extraite, si elle est decalée, sur-segmentée ou absente. Techniquement, la generation d un raster de classes unique limite les couts de calcul par rapport a une rasterisation independante pour chaque couche.

Dans le pipeline, cette etape relie la lecture scientifique des sorties au retour visuel d usage. Elle est donc a la fois un outil d analyse et un outil de debug.

#### 7.6 Flow 5: export final

Le dernier flow archive les sorties, les pousse vers le bucket objet et met a jour l etat final en base.

L export produit typiquement:

- une archive `output.zip`,
- les fichiers GeoJSON,
- les overlays PNG,
- les references persistantes dans `output_files` et `overlay_images`.

La progression passe a `100 %`, et l API peut alors servir un resultat complet au frontend.

### 8. Validation topologique et place dans le pipeline

La validation topologique est documentee dans le laboratoire par le script `7_validation_topo.py`, mais la version pipeline actuelle se concentre d abord sur la robustesse de l execution et la qualite du transport des donnees.

Le pipeline industrialise integre deja des pre-controles utiles:

- correction de geometries invalides,
- suppression des artefacts parasites,
- coherence CRS,
- visualisation intermediaire pour controle humain.

La validation topologique metier a proprement parler reste un niveau supplementaire. Dans une architecture cible, elle vient apres le nettoyage et avant l export final, avec des regles de conflits semantiques, d intersection et de relations spatiales.

Cette distinction est importante pour le rapport: le pipeline n ignore pas la validation, mais il la positionne correctement. Les etapes de pre-validation diminuent deja le risque d erreurs, tandis qu une validation topologique complete peut etre rajoutee comme flow dedie sans remettre en cause l architecture globale.

### 9. GitHub Actions et deploiement sur Hugging Face Spaces

Le projet utilise GitHub Actions pour synchroniser les services vers Hugging Face Spaces.

Deux workflows principaux existent:

- un workflow pour `services/api`, declenche sur push vers `main` et sur execution manuelle,
- un workflow pour `services/pipeline`, declenche sur le meme principe.

Leur logique est simple mais efficace:

1. checkout du depot,
2. initialisation d un depot git dans le dossier cible,
3. configuration de l identite git de CI,
4. ajout du remote Hugging Face,
5. commit des modifications,
6. push force sur le Space cible.

Ce mecanisme est adapte a un projet de ce type car il permet de livrer rapidement une version de demo ou de prototype de production, sans maintenir une chaine de build complexe pour chaque service.

### 10. Infrastructure, HPC et big data

L infrastructure est volontairement decoupee pour supporter des donnees lourdes.

Le pipeline tourne dans un conteneur base sur `pangeo/pangeo-notebook`, ce qui apporte un empilement geospatial plus riche qu une image Python minimale. Le `docker-compose.yml` fixe en outre une limite memoire au service pipeline, afin de rendre le comportement plus previsible lorsque plusieurs jobs ou plusieurs couches sont traitees.

Cette architecture est adaptee aux traitements intensifs pour plusieurs raisons:

- le calcul geospatial est isole dans un service specialise,
- la couche web ne porte pas la charge CPU,
- les artefacts intermediaires sont ecrits localement dans un workspace par UUID,
- les resultats sont exportes hors base,
- les progressions sont publiees sans bloquer l execution.

Du point de vue big data, le point le plus important est la dissociation entre orchestration et calcul. L API ne fait que router, persister et signaler. Le pipeline, lui, prend en charge les operations lourdes sur rasters, vecteurs et masques. Cette separation facilite ensuite une evolution vers du parallélisme plus fin ou une architecture a workers multiples.

### 11. Conclusion

La version pipeline n est pas une simple duplication du code du labo. C est la transformation d une suite d experiments locaux en une architecture de calcul reproductible, observable et deployable. Les scripts ont fourni la logique geospatiale; les flows lui donnent une forme systemique.

Le resultat est une separation claire des responsabilites:

- le frontend collecte et affiche,
- l API controle et persiste,
- le pipeline calcule,
- PostgreSQL trace,
- Hugging Face stocke,
- GitHub Actions deploie.

Cette decomposition est exactement ce qu il faut pour un traitement geospatial data-intensive.

### 12. Figures (application web et dashboard pipeline)

Figure 9 - Ecran d'accueil de l'application web

<img src="images/app_and_stuff/1_home.png" alt="Home screen webapp" width="100%">

Figure 10 - Section de saisie des donnees utilisateur

<img src="images/app_and_stuff/1_home_input.png" alt="Section saisie donnees" width="100%">

Figure 11 - Resultat de vectorisation (vue 1)

<img src="images/app_and_stuff/3_result_1.png" alt="Resultat vectorisation" width="100%">

Figure 12 - Resultat de vectorisation zoome (vue 2)

<img src="images/app_and_stuff/3_result_2.png" alt="Resultat vectorisation zoome" width="100%">

Figure 13 - Capture du dashboard pipeline

<img src="images/app_and_stuff/4_pipeline_dashbaord.png" alt="Dashboard pipeline" width="100%">
