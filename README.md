# 🚦 Moniteur de trafic — Guide de mise en place

Un système automatisé pour surveiller et analyser le trafic sur vos tronçons routiers.  
**Coût total : 0 €.** Stack : Python · GitHub Actions · Google Sheets · GitHub Pages.

---

## Architecture

```
GitHub Actions (cron horaire)
    └─▶ collect.py
            └─▶ Google Maps Distance Matrix API
            └─▶ Google Sheets REST API v4 (stockage CSV)
                    └─▶ GitHub Pages (index.html)
                            └─▶ Chart.js (graphiques)
```

---

## Étape 1 — Créer le dépôt GitHub

1. Créez un nouveau dépôt GitHub (ex : `trafic-monitor`)
2. Copiez-y tous les fichiers dans cette structure :
   ```
   .github/workflows/collect.yml
   collector/collect.py
   collector/requirements.txt
   docs/index.html
   README.md
   ```
3. Dans **Settings → Pages** :
   - Source : `Deploy from branch`
   - Branch : `main`, dossier : `/docs`
   - Votre site sera accessible à `https://VOTRE-USER.github.io/trafic-monitor/`

---

## Étape 2 — Clé API Google Maps

1. Allez sur [console.cloud.google.com](https://console.cloud.google.com)
2. Créez un projet ou sélectionnez-en un
3. Activez l'API **Distance Matrix API** :  
   `APIs & Services → Bibliothèque → Distance Matrix API → Activer`
4. Dans **APIs & Services → Identifiants → Créer des identifiants → Clé API**
5. Cliquez sur la clé → **Restriction d'API** → cochez uniquement **Distance Matrix API**
6. Enregistrez et copiez la clé

> **Quota gratuit** : 10 000 requêtes/mois.  
> Avec 3 tronçons toutes les heures : ~2 160 req/mois × 3 = **6 480/mois** → dans la limite gratuite.

---

## Étape 3 — Compte de service Google

### 3a. Créer le compte de service

1. Dans GCP : **IAM et administration → Comptes de service → Créer**
   - Nom : `trafic-collector`
   - Cliquez **Créer et continuer → OK**

> ⚠️ La création de clés JSON est désactivée par défaut sur les nouveaux comptes GCP.  
> On utilise à la place le **Workload Identity Federation** (WIF) — plus sécurisé.

### 3b. Activer les APIs nécessaires

Activez ces deux APIs dans **APIs & Services → Bibliothèque** :
- **Google Sheets API**
- **Google Drive API**

### 3c. Configurer Workload Identity Federation

1. Dans GCP : **IAM → Fédération d'identité de charge de travail → Créer un pool**
   - Nom du pool : `github-actions-pool`
   - ID du pool : `github-actions-pool`

2. Ajouter un fournisseur dans ce pool :
   - Type : **OIDC**
   - Nom : `GitHub Actions`
   - ID : `github-actions-provider`
   - URL de l'émetteur : `https://token.actions.githubusercontent.com`
   - Mappage d'attributs :
     - `google.subject` → `assertion.sub`
     - `attribute.repository` → `assertion.repository`
   - Condition d'attribut : `attribute.repository == "VOTRE-USERNAME/VOTRE-DEPOT"`

3. Sur la page du pool → **Accorder l'accès** :
   - Compte de service : `trafic-collector`
   - Nom d'attribut : `repository`
   - Valeur : `VOTRE-USERNAME/VOTRE-DEPOT`

### 3d. Accorder les rôles IAM au compte de service

Dans **IAM → Accorder l'accès**, ajoutez deux entrées :

| Principal | Rôle |
|-----------|------|
| `trafic-collector@...iam.gserviceaccount.com` | Créateur de jetons du compte de service |
| `principalSet://iam.googleapis.com/projects/NUMERO/locations/global/workloadIdentityPools/github-actions-pool/attribute.repository/VOTRE-USERNAME/VOTRE-DEPOT` | Créateur de jetons du compte de service |

### 3e. Partager le Google Sheet avec le compte de service

1. Créez un Google Sheet
2. Cliquez **Partager** → ajoutez `trafic-collector@VOTRE-PROJET.iam.gserviceaccount.com` en **Éditeur**
3. L'onglet `traficdata` sera créé automatiquement par le script au premier lancement

---

## Étape 4 — Secrets GitHub

Dans votre dépôt : **Settings → Secrets and variables → Actions → New repository secret**

| Secret | Valeur |
|--------|--------|
| `GMAPS_API_KEY` | Votre clé API Google Maps |
| `GSHEET_ID` | L'ID de votre Google Sheet (dans l'URL : `/spreadsheets/d/ICI/edit`) |
| `WIF_PROVIDER` | `projects/NUMERO/locations/global/workloadIdentityPools/github-actions-pool/providers/github-actions-provider` |
| `WIF_SERVICE_ACCOUNT` | `trafic-collector@VOTRE-PROJET.iam.gserviceaccount.com` |

---

## Étape 5 — Configurer vos tronçons

Dans `collector/collect.py`, modifiez la section `SEGMENTS` :

```python
SEGMENTS = [
    {
        "name": "Troncon_A_B",
        "origin": "45.8566, 6.7179",      # coordonnées GPS ou "Ville, France"
        "destination": "45.9012, 6.1234",
    },
    {
        "name": "Troncon_A_C",
        "origin": "45.8566, 6.7179",
        "destination": "45.7890, 6.4567",
    },
]
```

> Les coordonnées GPS sont plus fiables que les noms de villes pour l'API Google Maps.

---

## Étape 6 — Tester

1. Committez et pushez tous les fichiers
2. Dans GitHub : **Actions → Collecte trafic horaire → Run workflow**
3. Vérifiez que le workflow se termine en ✅ vert
4. Ouvrez votre Google Sheet → l'onglet `traficdata` apparaît avec les données

---

## Étape 7 — Activer le site web (après ~1 mois de données)

1. Dans Google Sheets : **Fichier → Partager → Publier sur le Web**
   - Feuille : `traficdata` · Format : **CSV** · Publier
   - Copiez l'URL générée
2. Dans `docs/index.html`, remplacez :
   ```js
   const CSV_URL = "VOTRE_URL_GOOGLE_SHEETS_CSV_ICI";
   ```
3. Committez → GitHub Pages publie automatiquement

---

## Structure des données (Google Sheets — onglet `traficdata`)

| Colonne | Description |
|---------|-------------|
| `timestamp_utc` | Horodatage UTC |
| `timestamp_local` | Horodatage local |
| `segment` | Nom du tronçon |
| `duration_normal_s` | Durée sans trafic (secondes) |
| `duration_traffic_s` | Durée avec trafic (secondes) |
| `duration_normal_min` | Durée sans trafic (minutes) |
| `duration_traffic_min` | Durée avec trafic (minutes) |
| `delay_min` | Retard dû au trafic (minutes) |
| `distance_m` | Distance (mètres) |
| `distance_km` | Distance (km) |
| `traffic_ratio` | Ratio trafic/normal (1.5 = 50% de plus) |
| `status` | `OK` ou message d'erreur |

---

## Graphiques disponibles sur le site

| # | Graphique | Description |
|---|-----------|-------------|
| 01 | **Heatmap heure × jour** | Affluence moyenne par heure et jour de semaine |
| 02 | **Top 5 pires semaines** | Les 5 semaines avec le ratio de trafic le plus élevé |
| 03 | **Semaine vs Week-end par mois** | Comparaison heure par heure par mois |
| 04 | **Semaine vs Week-end par saison** | Même comparaison par saison |

---

## Dépannage

| Erreur | Cause probable | Solution |
|--------|---------------|----------|
| `REQUEST_DENIED` (Maps) | Clé API non configurée ou mauvaise restriction | Vérifier la clé dans les secrets GitHub et la restriction Distance Matrix |
| `unauthorized_client` (WIF) | Condition d'attribut incorrecte | Vérifier `attribute.repository == "USER/DEPOT"` dans le fournisseur WIF |
| `PERMISSION_DENIED` (Sheets) | Rôles IAM manquants | Ajouter le rôle "Créateur de jetons" au compte de service |
| `400 Bad Request` (Sheets) | Onglet inexistant | Le script crée automatiquement l'onglet `traficdata` au premier run |
| `401 Unauthorized` (Sheets) | Sheet non partagé avec le compte de service | Partager le Sheet avec l'email du compte de service en Éditeur |

---

## Évolutions possibles

- Ajouter des **alertes email/Telegram** quand le trafic dépasse un seuil
- Intégrer un **modèle prédictif** pour estimer la durée future
- Connecter à **Home Assistant** pour déclencher des automatisations
