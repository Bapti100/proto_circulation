# ?? Moniteur de trafic — Guide de mise en place

Un système automatisé pour surveiller et analyser le trafic sur vos tronçons routiers.  
**Coût total : 0 €.** Stack : Python · GitHub Actions · Google Sheets · GitHub Pages.

---

## Architecture

```
GitHub Actions (cron horaire)
    +-? collect.py
            +-? Google Maps Distance Matrix API
            +-? Google Sheets (stockage CSV)
                    +-? GitHub Pages (index.html)
                            +-? Chart.js (graphiques)
```

---

## Étape 1 — Créer le dépôt GitHub

1. Créez un nouveau dépôt GitHub (ex : `trafic-monitor`)
2. Copiez-y tous les fichiers de ce projet dans la même structure :
   ```
   .github/workflows/collect.yml
   collector/collect.py
   collector/requirements.txt
   docs/index.html
   README.md
   ```
3. Dans **Settings ? Pages**, configurez :
   - Source : `Deploy from branch`
   - Branch : `main`, dossier : `/docs`
   - Votre site sera accessible à `https://VOTRE-USER.github.io/trafic-monitor/`

---

## Étape 2 — Clé API Google Maps

1. Allez sur [console.cloud.google.com](https://console.cloud.google.com)
2. Créez un projet (ou sélectionnez-en un)
3. Activez l'API **Distance Matrix API**
4. Dans **Identifiants ? Créer des identifiants ? Clé API**
5. (Recommandé) Restreignez la clé à l'API Distance Matrix uniquement
6. Copiez la clé ? vous en aurez besoin à l'étape 4

> **Quota gratuit** : 10 000 requêtes/mois.  
> Avec 3 tronçons collectés toutes les heures : ~2 160 req/mois par tronçon × 3 = **6 480/mois** ? dans la limite gratuite.

---

## Étape 3 — Créer le Google Sheet et le compte de service

### 3a. Créer le Google Sheet

1. Allez sur [sheets.google.com](https://sheets.google.com)
2. Créez un nouveau fichier (ex : `trafic-data`)
3. Copiez l'**ID du sheet** depuis l'URL :  
   `https://docs.google.com/spreadsheets/d/**VOTRE_ID**/edit`

### 3b. Créer un compte de service Google

1. Sur [console.cloud.google.com](https://console.cloud.google.com), allez dans **IAM ? Comptes de service**
2. Cliquez **Créer un compte de service**
   - Nom : `trafic-collector`
   - Cliquez **Créer et continuer** ? **OK**
3. Dans la liste, cliquez sur votre compte de service ? onglet **Clés**
4. **Ajouter une clé ? Créer une nouvelle clé ? JSON**
5. Un fichier `.json` est téléchargé ? **gardez-le précieusement**
6. Activez l'API **Google Sheets API** et **Google Drive API** sur votre projet

### 3c. Partager le Sheet avec le compte de service

1. Ouvrez votre Google Sheet
2. Cliquez **Partager**
3. Collez l'email du compte de service (ex: `trafic-collector@mon-projet.iam.gserviceaccount.com`)
4. Donnez-lui les droits **Éditeur**

### 3d. Publier le Sheet en CSV (pour le site web)

1. Dans Google Sheets : **Fichier ? Partager ? Publier sur le Web**
2. Choisissez :
   - Feuille : `trafic_data`
   - Format : **Valeurs séparées par des virgules (.csv)**
3. Cliquez **Publier**
4. Copiez l'URL générée (du type `https://docs.google.com/spreadsheets/d/.../pub?...&output=csv`)
5. Collez cette URL dans `docs/index.html` à la ligne :
   ```js
   const CSV_URL = "COLLER_VOTRE_URL_ICI";
   ```

---

## Étape 4 — Configurer les secrets GitHub

Dans votre dépôt GitHub : **Settings ? Secrets and variables ? Actions ? New repository secret**

Créez ces 3 secrets :

| Nom du secret       | Valeur |
|---------------------|--------|
| `GMAPS_API_KEY`     | Votre clé API Google Maps (étape 2) |
| `GSHEET_ID`         | L'ID de votre Google Sheet (étape 3a) |
| `GSHEET_CREDENTIALS`| Le **contenu complet** du fichier JSON téléchargé (étape 3b) |

> Pour `GSHEET_CREDENTIALS` : ouvrez le fichier JSON téléchargé, sélectionnez tout le contenu, collez-le tel quel comme valeur du secret.

---

## Étape 5 — Configurer vos tronçons

Ouvrez `collector/collect.py` et modifiez la section `SEGMENTS` :

```python
SEGMENTS = [
    {
        "name": "Troncon_A_B",
        "origin": "Megeve, France",        # ? votre point de départ
        "destination": "Annecy, France",   # ? votre destination
    },
    {
        "name": "Troncon_A_C",
        "origin": "Megeve, France",
        "destination": "Sallanches, France",
    },
]
```

Utilisez des noms de villes précis, ou des coordonnées GPS (`"45.857,6.617"`).

---

## Étape 6 — Tester

1. Commitez et pushez tous les fichiers
2. Dans GitHub : **Actions ? Collecte trafic horaire ? Run workflow**
3. Vérifiez que le workflow se termine en ? vert
4. Ouvrez votre Google Sheet ? vous devriez voir des lignes apparaître dans l'onglet `trafic_data`
5. Ouvrez votre GitHub Pages URL ? le site s'affiche avec les données

---

## Structure des données (Google Sheets)

| Colonne | Description |
|---------|-------------|
| `timestamp_utc` | Horodatage UTC de la mesure |
| `timestamp_local` | Horodatage local |
| `segment` | Nom du tronçon (`Troncon_A_B`) |
| `duration_normal_s` | Durée sans trafic (secondes) |
| `duration_traffic_s` | Durée avec trafic (secondes) |
| `duration_normal_min` | Durée sans trafic (minutes) |
| `duration_traffic_min` | Durée avec trafic (minutes) |
| `delay_min` | Retard dû au trafic (minutes) |
| `distance_m` | Distance en mètres |
| `distance_km` | Distance en kilomètres |
| `traffic_ratio` | Ratio trafic/normal (1.5 = 50% de plus) |
| `status` | `OK` ou message d'erreur |

---

## Graphiques disponibles sur le site

| # | Graphique | Description |
|---|-----------|-------------|
| 01 | **Heatmap heure × jour** | Vue globale de l'affluence moyenne par heure et jour de semaine |
| 02 | **Top 5 pires semaines** | Les 5 semaines avec le ratio de trafic le plus élevé, profil horaire détaillé |
| 03 | **Semaine vs Week-end par mois** | Comparaison heure par heure, filtrable par mois |
| 04 | **Semaine vs Week-end par saison** | Même comparaison agrégée par saison (Hiver/Printemps/Été/Automne) |

---

## Dépannage

**Le workflow échoue avec "quota exceeded"**  
? Vérifiez que la Distance Matrix API est activée sur votre projet GCP et que vous n'avez pas dépassé le quota.

**"Spreadsheet not found"**  
? Vérifiez que le Sheet est bien partagé avec l'email du compte de service.

**Le site affiche "Mode démo"**  
? Vous n'avez pas encore remplacé `CSV_URL` dans `docs/index.html`.

**Les données n'apparaissent pas dans Sheets**  
? Vérifiez le contenu du secret `GSHEET_CREDENTIALS` (doit être le JSON complet, pas encodé en base64).

---

## Évolutions possibles

- Ajouter des **alertes email/Telegram** quand le trafic dépasse un seuil
- Intégrer un **modèle prédictif** (régression linéaire) pour estimer la durée future
- Ajouter un **filtre par date** sur le site web
- Connecter à **Home Assistant** pour déclencher des automatisations