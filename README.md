# 🐙 Ink Publipostage Grist

Application Flask pour générer des documents PDF personnalisés à partir de données Grist.

## Fonctionnalités

- ✅ Connexion dynamique à Grist (API key et Doc ID saisis par l'utilisateur)
- 📝 Éditeur WYSIWYG avec Quill.js
- 🎨 Design System de la République Française (DSFR)
- 📄 Génération de PDF avec Playwright
- 🔄 Mail merge avec données Grist
- 💾 Sauvegarde de templates
- 🎯 Filtrage des enregistrements
- 📦 Génération en masse (ZIP)

## Déploiement sur Scalingo

### 1. Prérequis

- Compte Scalingo
- Git installé
- CLI Scalingo (optionnel)

### 2. Créer l'application

```bash
# Via la CLI Scalingo
scalingo create mon-publipostage

# Ou via l'interface web : dashboard.scalingo.com
```

### 3. Configurer les variables d'environnement

Sur le dashboard Scalingo, onglet "Environment", ajouter :

```
FLASK_SECRET_KEY=generer-une-cle-secrete-aleatoire
FLASK_ENV=production
FLASK_DEBUG=False
GRIST_SERVER=https://grist.numerique.gouv.fr
```

**Note :** `GRIST_API_KEY` et `GRIST_DOC_ID` ne sont PAS nécessaires car l'utilisateur les saisit dans l'interface.

### 4. Déployer

```bash
# Initialiser Git (si pas déjà fait)
git init
git add .
git commit -m "Initial commit"

# Ajouter le remote Scalingo
git remote add scalingo git@ssh.osc-fr1.scalingo.com:mon-publipostage.git

# Pousser
git push scalingo master
```

### 5. Vérifier le déploiement

```bash
# Voir les logs
scalingo --app mon-publipostage logs --lines 100

# Ouvrir l'app
scalingo --app mon-publipostage open
```

## Structure du projet

```
.
├── app.py                 # Application Flask principale
├── config.py              # Configuration
├── modules/
│   ├── grist_connector.py # Connexion Grist
│   └── document_generator.py # Génération PDF
├── templates/
│   └── index.html         # Interface utilisateur
├── static/
│   ├── css/
│   ├── js/
│   └── dsfr/              # Design System
├── requirements.txt       # Dépendances Python
├── Procfile              # Configuration Scalingo
├── runtime.txt           # Version Python
└── .buildpacks           # Buildpacks Scalingo
```

## Développement local

```bash
# Installer les dépendances
pip install -r requirements.txt

# Installer Playwright
playwright install chromium

# Lancer l'application
python app.py
```

## Support

Pour toute question : ouvrir une issue sur le dépôt Git.

## Licence

MIT
