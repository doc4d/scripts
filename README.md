# Scripts

Ce projet contient des scripts pour automatiser l'intégration de documentation de composants dans Docusaurus.

## Étape 1 : Copie de la doc du composant vers Docusaurus (docs4d)

### docusaurusify.py

Le script `docusaurusify.py` permet de copier automatiquement la documentation d'un composant vers la documentation Docusaurus avec les modifications adéquates.

#### Prérequis

- Le code source du composant
- La [documentation docs4d](https://github.com/doc4d/docs) clonée localement

#### Fonctionnalités

- Ajoute des en-têtes Docusaurus avec `id` et `title`
- Corrige les liens markdown selon les règles Docusaurus
- Normalise les noms de fichiers (minuscules, tirets)
- Renomme `README.md` → `overview.md`
- Supprime le préfixe `Documentation/` des chemins

#### Usage

```bash
python docusaurusify.py <dossier_source> [-o <dossier_sortie>] [-v] [-f]
```

#### Exemple concret : AIKit

Si vous n'avez pas les sources (ou téléchargez avec GitHub Desktop, etc.) :

```bash
git clone https://github.com/4d/4D-AIKit
```

Il faut déterminer le chemin de destination dans la doc, ici ["docs/aikit"](https://github.com/doc4d/docs/tree/main/docs/aikit) :

```bash
python docusaurusify.py -f "/path/to/4D-AIKit" -o "/path/to/docs/docs/aikit"
```

#### Post-traitement

Après l'exécution du script :

1. **Vérifiez les changements** : utilisez `git diff` dans votre repo docs pour voir ce qui a été modifié
2. **Corrections manuelles** : effectuez les corrections nécessaires dues aux particularités :
   - Supprimez les pages non voulues (license, contributing, cla, etc.)
   - Supprimez les morceaux de page non voulus (liens license, badges GitHub)
   - (ex: Pour l'overview d'AIKit, faites un revert s'il n'y a pas de vraies modifications)

## Étape 2 : Modifier la sidebar si nécessaire

Si il y a de nouvelles pages ou des pages supprimées, il faut modifier le fichier de [sidebar](https://github.com/doc4d/docs/blob/main/sidebars.js).

Cela peut se faire manuellement, mais il existe un script [`sidebars_items.py`](https://github.com/doc4d/docs/blob/main/sidebars_items.py) à la racine du projet docs qui peut aider.

### Générer le morceau de JSON de la sidebar pour un dossier de doc précis

```bash
python sidebars_items.py aikit/Classes  
```

Résultat :

```json
[
  "aikit/Classes/openai",
  "aikit/Classes/openaiapiresource",
  "aikit/Classes/openaichatapi",
  ...
]
```

Ensuite, vous pouvez l'intégrer au bon endroit dans `sidebars.js`.

### Mode récursif

Pour générer la sidebar de manière récursive :

```bash
python sidebars_items.py aikit -R
```

Résultat :

```json
[
  "aikit/Classes/openai",
  "aikit/Classes/openaiapiresource",
  "aikit/Classes/openaichatapi",
  ...
  "aikit/asynchronous-call",
  "aikit/compatible-openai",
  "aikit/overview"
]
```

### Édition directe avec le script

Il est possible d'avoir une édition directe avec `--output sidebars.js` :

```bash
python3 sidebars_items.py aikit --output sidebars.js
```

⚠️ **Important** : Il faut tout de même vérifier le résultat obtenu et fixer par exemple l'ordre des pages si vous ne voulez pas de l'ordre alphabétique.
