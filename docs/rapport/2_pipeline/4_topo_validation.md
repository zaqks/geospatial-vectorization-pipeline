## 4. Validation topologique dans l'architecture pipeline

### 4.1 Etat actuel dans la version pipeline

La chaine pipeline industrialisee implemente deja une validation geometrique partielle via:

- nettoyage de validite des polygones (make_valid),
- suppression des geometres nulles/vides,
- filtrage par surface minimale,
- controle de recouvrement raster/vector sur la couche water,
- correction de trous et simplification ciblee.

En revanche, un moteur complet de validation topologique metier (au niveau du script lab 7_validation_topo.py) n'est pas encore active comme flow dedie de production.

### 4.2 Ce qui est deja securise en pre-validation

Au cours des flows 3 et 4:

- geometries invalides corrigees,
- micro-polygones parasites elimines,
- coherence CRS geree avec reprojection si necessaire,
- generation de masques de visualisation pour validation humaine rapide.

Ces etapes reduisent fortement les erreurs structurelles avant export final.

### 4.3 Validation applicative en sortie

Cote API + frontend, la validation fonctionnelle repose sur:

- progression etat (0 -> 100),
- disponibilite des artifacts media,
- rendu superpose map + overlays,
- verification visuelle interactive couche par couche.

Le frontend fournit une inspection multicouche (toggles overlays) qui joue le role de QA visuelle operationnelle.

### 4.4 Gap entre prototype labo et production

Prototype labo:

- regles explicites d'intersection semantique (batiments/eau, routes, etc.),
- export d'erreurs thematiques.

Pipeline production actuelle:

- priorite a la robustesse de calcul et d'export,
- pas encore de flow 7_topology_rules integre dans l'orchestrateur.

Ce decalage est classique dans une migration prototype -> plateforme.

### 4.5 Proposition d'integration topologique complete

Pour aligner la production sur les exigences academiques:

1. creer un flow dedie 6_topo_validation,
2. reutiliser les regles du script lab en version parametrique,
3. ecrire erreurs topologiques dans output/errors/*.geojson,
4. pousser un score qualite (ex: nb conflits / km2) en base,
5. exposer ces metriques via API/result.

### 4.6 Optimisations HPC pour la topo-validation

Pour une validation sur grands volumes:

- utiliser index spatiaux persistants,
- partitionner les couches par tuiles geographiques,
- executer les regles en parallele par famille d'objets,
- agregation finale des conflits.

Complexite theorique:

- brute force proche de O(n x m),
- avec index spatial, le nombre de comparaisons est fortement reduit en pratique.

### 4.7 Conclusion technique

L'architecture actuelle est deja robuste pour:

- ingestion,
- georeferencement,
- vectorisation,
- nettoyage,
- publication des resultats.

La prochaine marche de maturite scientifique est l'integration complete d'un flow topologique metier, afin de fermer la boucle qualite de maniere automatique et mesurable.
