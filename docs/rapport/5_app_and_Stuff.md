## Pipeline industrialise: du prototype labo aux flows orchestration

### 1. Positionnement general

Dans le prototype de laboratoire, chaque etape du traitement geospatial a d abord ete exprimee sous forme de scripts autonomes: acquisition, georeferencement, vectorisation, nettoyage, visualisation et validation topologique. La version pipeline reprend exactement cette logique fonctionnelle, mais la transforme en une suite de flows declenchables, observables et deploies dans une infrastructure separee du front de saisie.

Le changement est important sur le plan methodologique. On ne traite plus un simple outil de traitement local, mais un systeme de calcul distribue ou:

- le frontend ne fait que collecter les entrees utilisateur et presenter l etat d avancement,
- l API joue le role de plan de controle,
- le pipeline porte le calcul geospatial lourd,
- PostgreSQL conserve les metadonnees et l etat des jobs,
- Hugging Face sert de bucket objet pour les fichiers volumineux,
- GitHub Actions automatise le deploiement sur les Spaces HF.

Cette separation est celle d une architecture orientee donnees. Elle est plus adaptee qu une application classique monolithique, car la charge principale n est pas une logique CRUD, mais la manipulation de rasters, de GeoJSON, de masques PNG et d artefacts de taille variable lourde.

### 2. Du script au flow

Le passage du labo au pipeline ne consiste pas a reescrire la logique geospatiale. Il consiste a l encapsuler dans des frontieres d execution plus robustes.

Dans le repertoire lab, les scripts servent de prototype scientifique:

- `1_georef.py` pour la mise en referentiel,
- `2_vectorization_*.py` pour la segmentation et l extraction vectorielle,
- `3_clean_*.py` pour le nettoyage geometrique et le gap filling,
- `6_viz_*.py` pour la visualisation de controle,
- `7_validation_topo.py` pour les regles de validation topologique.

Dans `services/pipeline`, ces etapes deviennent des flows Plombery. Le code metier reste proche, mais l execution est recomposee autour de plusieurs proprietes techniques:

- etapes atomiques et chainables,
- progression publiee a chaque sous-tache,
- reprises plus faciles en cas d echec,
- workspace isole par UUID,
- echanges de donnees via fichiers locaux temporaires plutot que via memoire partagee.

Le pipeline se comporte ainsi comme une machine a etats de traitement geospatial plutot que comme une simple fonction unique.

### 3. Architecture globale du systeme

Le systeme complet repose sur trois services applicatifs et deux couches d infrastructure.

Le frontend Vite, dans `services/app`, fournit l interface de saisie et de consultation. Il recoit un fichier, une bounding box a deux points et ouvre ensuite un flux SSE pour suivre l execution.

L API FastAPI, dans `services/api`, recoit l upload, valide la structure des entrees, persiste les metadonnees, envoie l image vers Hugging Face, puis declenche le pipeline via un appel HTTP vers le service de calcul.

Le pipeline, dans `services/pipeline`, execute les transformations geospatiales lourdes dans une base `pangeo/pangeo-notebook:6f9fda2`, ce qui apporte nativement Python 3.12, GDAL, GEOS et les briques geospatiales necessaires.

PostgreSQL stocke les objets relationnels suivants:

- `inputs` pour les entrees utilisateur et l avancement,
- `outputs` pour le lien 1-1 avec l entree,
- `output_files` pour les artefacts exportes,
- `overlay_images` pour les masques de visualisation.

Hugging Face sert de stockage objet externe. Les fichiers lourds n y sont pas copies sous forme de blob en base, mais sous forme de chemins de type bucket/repository. Cette approche reduit fortement la taille des transactions SQL et permet de deplacer les artefacts sans surcharger PostgreSQL.

### 4. Ingestion et controle cote API

Le point d entree applicatif est `POST /api/upload`.

Le frontend envoie un formulaire multipart contenant:

- le fichier image,
- la bounding box serialisee sous la forme `{"points":[{"lat":...,"lng":...},{"lat":...,"lng":...}]}`.

L API applique plusieurs traitements de controle:

- validation de la structure JSON,
- conversion des points en quatre bornes numeriques,
- generation d un UUID de job,
- transfert de l image vers le bucket Hugging Face,
- creation de la ligne `Input` en base avec progression initiale a `0`.

L API ne lance pas directement les traitements geospatiaux. Elle sert de passerelle transactionnelle entre le monde utilisateur et la couche de calcul. Une fois l upload persisté, elle appelle `trigger_pipeline_with_retry`, qui contacte le premier flow du pipeline avec politique de retry et timeout. Ce point est essentiel: si le pipeline met quelques secondes a demarrer ou si le service est momentanement indisponible, le front ne bloque pas en attente d un calcul synchrone.

Cette logique transforme une requete web classique en tache asynchrone traitee hors bande.

### 5. Canal temps reel et retour d execution

La consultation de l avancement se fait via Server-Sent Events.

Le frontend ouvre `GET /api/events/{uuid}` juste apres l envoi de l upload. Le backend retourne d abord un snapshot issu de la base, puis relaie les evenements publies par le pipeline via `POST /api/events/notify`.

Ce mecanisme repond a deux besoins:

- donner un retour immediat a l utilisateur,
- eviter de faire du polling agressif sur l API.

En sortie, `GET /api/result/{uuid}` assemble l URL du preview, la liste des overlays et la liste des fichiers exportes. Le frontend peut alors afficher le resultat final et conserver certains etats locaux pour accelerer les consultations suivantes.

Dans cette architecture, le SSE joue le role de bus leger de progression. Il ne remplace pas la persistance, mais il la complete avec une couche UX temps reel.

### 6. Stockage objet Hugging Face et role de PostgreSQL

Le systeme fait une separation stricte entre metadonnees et payloads.

PostgreSQL porte le controle transactionnel:

- UUID de job,
- nom du fichier,
- ref de stockage,
- bornes geographiques,
- pourcentage de progression,
- relations entre entree, export et overlays.

Hugging Face porte les fichiers:

- image d entree uploadée,
- GeoJSON exportes,
- archive `output.zip`,
- images de visualisation,
- masques PNG.

Le chemin de stockage est derive de l UUID, ce qui donne une structure stable et previsible du type `uploads/<uuid>/input/<name>`. Le bucket par defaut est configure par `HF_BUCKET_REPO_ID` et la connexion repose sur `HF_TOKEN`.

Cette conception est plus robuste qu un stockage integral en base pour trois raisons:

- elle evite d alourdir les tables avec de gros binaires,
- elle permet de versionner ou migrer les artefacts comme des objets independants,
- elle facilite le partage entre API et pipeline sans duplication de logique de serialization.

### 7. Flows de calcul et correspondance avec les scripts lab

Le pipeline reprend la sequence scientifique du laboratoire, mais la rend executable et reproductible dans un environnement serveur.

#### 7.1 Flow 0: preparation du workspace

`0_setup_workspace` initialise un workspace isole sous `/tmp/<uuid>`.

Ses responsabilites sont les suivantes:

- creer l arborescence locale de calcul,
- recuperer l image depuis Hugging Face a partir de `Input.image_ref`,
- la reconvertir en PNG local de travail,
- copier les fichiers de configuration metier `legend_class_geo.csv` et `colors.csv`,
- notifier le backend de la progression initiale,
- enchaîner vers le georeferencement.

Cette etape est la charniere entre le plan de controle et le plan de donnees. Elle garantit que chaque job a son propre espace de travail et que les flows suivants n ont pas a dependre d etats globaux partages.

#### 7.2 Flow 1: georeferencement

Le flow de georeferencement transforme l image brute en GeoTIFF spatialement coherent.

Il recupere les bornes stockees en base, les remet dans le bon ordre, puis construit une transformation affine en partant de la bbox utilisateur. Le raster est ecrit avec compression et tuilage internes pour reduire la taille disque et optimiser les lectures partielles.

Le resultat de ce flow devient la reference commune pour toutes les etapes suivantes. C est a partir de ce point que l image n est plus seulement un document, mais un raster georeference exploitable comme support geospatial.

#### 7.3 Flow 2: vectorisation

La vectorisation est decomposee en plusieurs flows specialises selon le type d objet:

- lignes continues,
- lignes pointillees,
- polygones.

Cette decomposition correspond directement aux scripts prototypes du laboratoire, mais avec une execution orchestrable et un reporting de progression plus fin.

Le principe general reste le meme que dans les scripts experimentaux:

- classification couleur,
- nettoyage morphologique,
- extraction des composantes,
- simplification geometrique,
- export GeoJSON.

Cette phase concentre l essentiel de la charge compute. C est pourquoi elle est isolee dans le pipeline et ne doit pas etre executee dans une simple couche API synchrone.

#### 7.4 Flow 3: nettoyage geometrique et gap filling

Les scripts de nettoyage du labo ont ete conserves comme logique de reference et transformes en etapes de pipeline dediees.

Le nettoyage joue un double role:

- supprimer le bruit geometrique issu de la segmentation,
- stabiliser les entites avant la visualisation et la validation.

La couche polygonale applique notamment:

- correction des geometries invalides,
- suppression des entites vides,
- filtrage par aire minimale,
- revalidation apres nettoyage.

Le cas de la classe `water` est particulier, car il beneficie d un traitement de gap filling par operations de buffer positif puis negatif, afin de refermer les lacunes fines et de produire une geometrie plus continue.

Dans une architecture data-intensive, cette etape est importante: elle reduit les faux positifs visibles ensuite dans la validation et limite les corrections manuelles.

#### 7.5 Flow 4: visualisation de controle

Les scripts de visualisation ne servent pas seulement a produire de jolies figures. Ils constituent un mecanisme de QA reproductible.

L idee est de rasteriser les sorties vectorielles dans un espace unique de classes, puis de generer pour chaque classe:

- un masque,
- un overlay sur l image de reference,
- une sortie PNG dans le dossier de viz.

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
