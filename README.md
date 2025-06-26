# Scripts

## docusaurusify.py

Convertit automatiquement des fichiers Markdown pour la compatibilité Docusaurus.

### Fonctionnalités

- Ajoute des en-têtes Docusaurus avec `id` et `title`
- Corrige les liens markdown selon les règles Docusaurus
- Normalise les noms de fichiers (minuscules, tirets)
- Renomme `README.md` → `overview.md`
- Supprime le préfixe `Documentation/` des chemins

### Usage

```bash
python docusaurusify.py <dossier_source> [-o <dossier_sortie>] [-v] [-f]
```

### Example

```bash
python docusaurusify.py -f /path/to/4D-AIKit /path/to/docs/docs/aikit
```
