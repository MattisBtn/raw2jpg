# raw2jpg

Service FastAPI pour convertir des fichiers RAW en JPG.

## Fonctionnalités

- Conversion de fichiers RAW vers JPG
- Formats supportés : ARW, CR2, DNG, NEF, RAW
- API REST simple

## Déploiement

### Railway

1. Connectez votre repository GitHub à Railway
2. Railway détectera automatiquement le Dockerfile
3. Le service sera déployé sur le port configuré par Railway

### Variables d'environnement

- `PORT` : Port du serveur (configuré automatiquement par Railway)

## API

### POST /convert

Convertit un fichier RAW en JPG.

**Paramètres :**

- `file` : Fichier RAW à convertir (multipart/form-data)

**Réponse :**

- Fichier JPG en streaming
- Headers Content-Disposition avec nom de fichier

**Exemple :**

```bash
curl -X POST "https://your-app.railway.app/convert" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@photo.raw"
```
