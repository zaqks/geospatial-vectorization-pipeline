## 1. Acquisition et ingestion distribuee (pipeline + API + app)

### 1.1 Vue systeme

Dans la version industrialisee, l'acquisition ne se limite plus au telechargement de tuiles. Elle devient une chaine distribuee entre:

- app web (services/app) pour la saisie utilisateur,
- API FastAPI (services/api) pour l'ingestion et la persistance,
- pipeline Plombery (services/pipeline) pour le calcul geospatial,
- stockage objet Hugging Face pour les binaires volumineux,
- base relationnelle (PostgreSQL) pour les metadonnees et l'etat de progression.

### 1.2 Frontend: collecte des entrees utilisateur

Le frontend (Vite SPA) realise:

1. selection du fichier image,
2. saisie des 2 points de bounding box (lat1,lng1,lat2,lng2),
3. POST multipart sur /api/upload.

Schema de la bounding box envoyee:

{
  "points": [
    {"lat": ..., "lng": ...},
    {"lat": ..., "lng": ...}
  ]
}

Le frontend ouvre ensuite un flux SSE /api/events/{uuid} pour suivre l'etat asynchrone du calcul.

### 1.3 API: ingestion transactionnelle

L'endpoint /api/upload:

- valide le JSON de bounding box,
- lit le flux binaire image,
- genere un UUID de job,
- stocke l'image dans le bucket HF (uploads/<uuid>/input/<name>),
- cree une ligne Input en base avec:
  - image_ref,
  - image_name,
  - lat1, lat2, lng1, lng2,
  - percent_progress initialise.

Ensuite l'API declenche le premier pipeline via trigger_pipeline_with_retry.

### 1.4 Modelisation de donnees

Tables principales:

- inputs: entree utilisateur + progression,
- outputs: resultat logique 1-1 avec input,
- output_files: artefacts exportes (zip, geojson, etc.),
- overlay_images: masques PNG de visualisation.

Cette decomposition separe nettement:

- metadonnees transactionnelles (DB),
- contenu volumineux (object storage).

### 1.5 Orchestration evenementielle et UX temps reel

Le backend expose un canal SSE:

- snapshot initial depuis la DB,
- evenements webhook internes (/api/events/notify) emis par le pipeline,
- keepalive pour maintenir la connexion.

Le frontend:

- affiche la progression,
- recharge /api/result/{uuid} a maturite,
- recupere image de preview + overlays,
- met en cache local (IndexedDB) la carte et les overlays pour relance rapide.

### 1.6 Decouplage stockage/performance

Choix d'architecture orientes big data:

- les objets lourds ne transitent pas en base SQL,
- references seulement en base (path_in_repo HF),
- download a la demande via endpoints /media,
- front charge en blob pour limiter les couts reseau repetes.

### 1.7 Bootstrap pipeline

Le flow 0_setup_workspace initialise l'environnement de travail par UUID:

- creation /tmp/<uuid>/data,
- recopie de l'image upload en PNG local,
- copie des fichiers de configuration metier:
  - legend_class_geo.csv,
  - colors.csv,
- progression notifiee a l'API,
- chaining vers 1_georef.

### 1.8 Proprietes techniques d'ingestion

Atouts:

- idempotence relative par UUID,
- reprise frontend via cookie upload_uuid,
- observabilite de progression (SSE + DB),
- separation claire entre plan de controle (API/DB) et plan de donnees (HF/FS).

Contraintes:

- dependance reseau vers HF,
- robustesse conditionnee par la qualite des retries et des timeouts,
- securisation a durcir en production (CORS large, secrets, auth pipeline).
