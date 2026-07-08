# Architecture cible des bases de données

## Vision générale

Le système repose sur deux domaines strictement séparés :

- un domaine data sur AWS, organisé selon la logique bronze / silver / gold
- un domaine applicatif dédié au fonctionnement métier de l'application

Cette séparation est structurelle et définit l'architecture finale du projet.

## Domaine data sur AWS

### Bronze

La couche bronze reçoit les données brutes issues des sources externes.

Elle existe uniquement dans AWS et ne fait pas partie du périmètre local ou applicatif.

Elle représente la zone d'atterrissage initiale du pipeline data.

### Silver

La couche silver contient les données nettoyées, normalisées et fiabilisées.

Elle constitue la source de consommation principale pour les usages data opérationnels.

### Gold

La couche gold contient les données enrichies, agrégées et préparées pour les usages avancés.

Elle sert aux traitements de niveau supérieur, notamment l'IA, l'analyse et la préparation des prédictions.

## Domaine applicatif

L'application dispose de sa propre base de données métier, distincte du pipeline data.

Cette base ne contient pas les données brutes, nettoyées ou enrichies issues des flux AWS.

Elle sert exclusivement au fonctionnement interne de l'application.

### Données métiers applicatives

Cette base contient les informations liées à l'usage de l'application, par exemple :

- comptes utilisateurs
- inscription
- authentification
- profils
- préférences utilisateur
- paramètres applicatifs
- abonnements et relations propres à l'application

## Principe d'isolation

Les données data et les données applicatives ne doivent jamais être mélangées.

Chaque domaine a son rôle propre :

- le domaine data alimente les traitements, les modèles et les analyses
- le domaine applicatif porte l'expérience utilisateur et les règles métier de l'application

## Structure finale retenue

L'architecture finale du projet est organisée ainsi :

- bronze sur AWS pour les données brutes
- silver sur AWS pour les données propres
- gold sur AWS pour les données enrichies et préparées
- une base applicative séparée pour le métier de l'application

## Résultat attendu

Cette architecture garantit :

- une séparation claire entre data et métier
- une meilleure lisibilité du système
- une maintenance simplifiée
- une évolution indépendante des pipelines AWS et de l'application
