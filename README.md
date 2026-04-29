# 🚦 Moniteur de trafic — Analyse du trafic routier
**Collecte et visualisation automatisée des temps de trajet en temps réel**  

**Live demo** : https://bapti100.github.io/proto_circulation/

---

---

## Architecture

```
GitHub Actions (cron ~toutes les heures)
    └─▶ collect.py
            └─▶ Google Maps Distance Matrix API
            └─▶ Google Sheets REST API v4 (stockage)
                    └─▶ Google Apps Script (proxy JSON)
                            └─▶ GitHub Pages (index.html)
                                    └─▶ Chart.js (graphiques)
```

---

## Note sur la fréquence de collecte

Le cron GitHub Actions est configuré sur `5 * * * *` (toutes les heures à :05), mais GitHub ne garantit pas une exécution exacte. En période de forte charge sur leurs serveurs, les runs peuvent avoir **15 à 30 minutes de retard**, voire être sautés. C'est une limitation connue et documentée de GitHub Actions — rien ne peut être fait de notre côté. En pratique, vous obtiendrez entre 18 et 24 mesures par jour par tronçon, ce qui est largement suffisant pour les analyses.

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
> Avec 3 tronçons et ~20 collectes/jour : ~1800 req/mois par tronçon × 3 = **~5400/mois** → dans la limite gratuite.

---

## Étape 3 — Compte de service Google

### 3a. Créer le compte de service

1. Dans GCP : **IAM et administration → Comptes de service → Créer**
   - Nom : `trafic-collector`
   - Cliquez **Créer et continuer → OK**

> ⚠️ La création de clés JSON est désactivée par défaut sur les nouveaux comptes GCP.  
> On utilise le **Workload Identity Federation** (WIF) à la place — plus sécurisé, aucune clé à stocker.

### 3b. Activer les APIs nécessaires

Dans **APIs & Services → Bibliothèque**, activez :
- **Google Sheets API**
- **Google Drive API**

### 3c. Configurer Workload Identity Federation

1. Dans GCP : **IAM → Fédération d'identité de charge de travail** (= Workload Identity Federation) **→ Créer un pool**
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

### 3d. Accorder les rôles IAM

Dans **IAM → Accorder l'accès**, ajoutez deux entrées :

| Principal | Rôle |
|-----------|------|
| `trafic-collector@...iam.gserviceaccount.com` | Créateur de jetons du compte de service |
| `principalSet://iam.googleapis.com/projects/NUMERO/locations/global/workloadIdentityPools/github-actions-pool/attribute.repository/VOTRE-USERNAME/VOTRE-DEPOT` | Créateur de jetons du compte de service |

### 3e. Partager le Google Sheet avec le compte de service

1. Créez un Google Sheet
2. Créez manuellement un onglet nommé exactement **`traficdata`**
3. Cliquez **Partager** → ajoutez `trafic-collector@VOTRE-PROJET.iam.gserviceaccount.com` en **Éditeur**

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

> Les coordonnées GPS sont plus fiables que les noms de villes.

---

## Étape 6 — Corriger le fuseau horaire

Par défaut le runner GitHub tourne en UTC. Pour avoir l'heure locale française dans `timestamp_local`, modifiez `collect.py` :

```python
import zoneinfo
tz = zoneinfo.ZoneInfo("Europe/Paris")
ts_local = datetime.datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")
```

---

## Étape 7 — Google Apps Script (proxy pour le site web)

Le site web ne peut pas appeler directement l'API Google Sheets (credentials privées). On utilise un Apps Script comme proxy public en lecture seule.

1. Dans Google Sheets : **Extensions → Apps Script**
2. Remplacez tout le contenu par le fichier `apps_script.gs`
3. Cliquez **Déployer → Nouveau déploiement** :
   - Type : **Application Web**
   - Exécuter en tant que : **Moi**
   - Accès : **Tout le monde**
4. Validez le message de sécurité Google (normal pour un script personnel)
5. Copiez l'URL de déploiement
6. Dans `docs/index.html`, remplacez `VOTRE_URL_APPS_SCRIPT_ICI` par cette URL
7. Committez

> **Sécurité** : ce lien permet uniquement de lire les données de trafic de l'onglet `traficdata`. Il ne donne accès à rien d'autre de votre compte Google.

---

## Étape 8 — Tester

1. Committez et pushez tous les fichiers
2. Dans GitHub : **Actions → Collecte trafic horaire → Run workflow**
3. Vérifiez que le workflow se termine en ✅ vert
4. Ouvrez votre Google Sheet → l'onglet `traficdata` contient des données
5. Ouvrez votre GitHub Pages URL → le site affiche vos vrais tronçons

---

## Structure des données (onglet `traficdata`)

| Colonne | Description |
|---------|-------------|
| `timestamp_utc` | Horodatage UTC |
| `timestamp_local` | Horodatage local (Europe/Paris) |
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
| 03 | **Semaine vs Week-end par mois** | Comparaison heure par heure, filtrable par mois |
| 04 | **Semaine vs Week-end par saison** | Même comparaison agrégée par saison |

---

## Dépannage

| Erreur | Cause probable | Solution |
|--------|---------------|----------|
| `REQUEST_DENIED` (Maps) | Clé API mal configurée | Vérifier la restriction Distance Matrix API et le secret `GMAPS_API_KEY` |
| `unauthorized_client` (WIF) | Condition d'attribut incorrecte | Vérifier `attribute.repository == "USER/DEPOT"` dans le fournisseur WIF |
| `PERMISSION_DENIED` (Sheets) | Rôles IAM manquants | Ajouter le rôle "Créateur de jetons" au compte de service et au pool WIF |
| `400 Bad Request` (Sheets) | Onglet inexistant | Créer l'onglet `traficdata` manuellement dans le Google Sheet |
| `401 Unauthorized` (Sheets) | Sheet non partagé | Partager le Sheet avec l'email du compte de service en Éditeur |
| Site bloqué en chargement | URL Apps Script incorrecte | Vérifier `APPS_SCRIPT_URL` dans `index.html` |

---

## Évolutions possibles

- Ajouter des **alertes email/Telegram** quand le trafic dépasse un seuil
- Intégrer un **modèle prédictif** pour estimer la durée future
- Connecter à **Home Assistant** pour déclencher des automatisations
- Ajouter un **filtre par période** sur le site web
---

## Auteur

**Baptiste Fantou** — Projet personnel (2026)

---

## Licence

Ce projet est un prototype personnel. Les données collectées concernent des tronçons routiers publics et ne contiennent aucune information sensible. Pour toute question ou réutilisation, merci de contacter l'auteur.

---

## Contact

- Email : [baptiste.de.livry@gmail.com](mailto:baptiste.de.livry@gmail.com)
- GitHub : [Bapti100](https://github.com/Bapti100)

---

**© 2026 - Baptiste Fantou**
