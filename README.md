# pg_analyst 🐝

**Analyse agentique de bases PostgreSQL → Dashboard HTML interactif**

Stack : CrewAI · Ollama (DGX Spark) · mcpo · Plotly.js

---

## Architecture

```
Utilisateur (grandes lignes)
        │
        ▼
┌─────────────────┐
│  ORCHESTRATEUR  │  Pilote, délègue, valide
└────────┬────────┘
         │
    ┌────▼─────┐         ┌──────────────────┐
    │ ANALYSTE │◄────────► REQUÊTEUR SQL     │
    │          │  "requête│ (tool: mcpo)      │
    │ Définit  │   moi X" │                  │
    │ axes,    ├─────────►│ Génère SQL,       │
    │ interprète│ résultats│ exécute via mcpo  │
    └────┬─────┘         └──────────────────┘
         │
         ▼
┌─────────────────────┐
│  GÉNÉRATEUR TDB     │  (tool: write_file)
│  dashboard.html     │
│  data_export.json   │
└─────────────────────┘
```

## Prérequis

1. **PostgreSQL** démarré (benefits-dataset ou autre source)
2. **mcpo** installé et configuré
3. **Ollama** avec le modèle requis
4. **Python 3.11+**

## Installation

### Créer et activer le venv

```bash
python3 -m venv .venv
source .venv/bin/activate
```

> Pour désactiver : `deactivate`

### Installer les dépendances

```bash
pip install -r requirements.txt
pip install mcpo --break-system-packages
```

## Déploiement de la base de données (benefits-dataset)

Source : [github.com/elhajjaji/benefits-dataset](https://github.com/elhajjaji/benefits-dataset)

### Cloner le dépôt

```bash
cd ..
git clone https://github.com/elhajjaji/benefits-dataset.git
cd benefits-dataset
```

### Démarrer les services (PostgreSQL + pgAdmin)

```bash
docker compose -p benefits up -d --build
```

> L'import CSV des 4 tables (`src.individu`, `src.dossier`, `src.permis`, `src.prestation`) se fait automatiquement au premier démarrage.

### Accès PostgreSQL

| Paramètre | Valeur         |
|-----------|----------------|
| Host      | `localhost`    |
| Port      | `5433`         |
| Database  | `pocs`         |
| Schema    | `src`          |
| User      | `user`         |
| Password  | `password`     |

### Repartir de zéro (optionnel)

```bash
docker compose down -v
docker compose -p benefits up -d --build
```

### Arrêter

```bash
docker compose down
```

---

## Démarrage

### 1. Démarrer PostgreSQL (benefits-dataset)
```bash
cd ../benefits-dataset
docker compose -p benefits up -d --build
```

### 2. Démarrer mcpo
```bash
uvx mcpo --config mcpo-config.json --port 8000
```

### 3. Vérifier Ollama
```bash
ollama pull qwen2.5-coder:7b
ollama serve  # si pas déjà démarré
```

### 4. Configurer les grandes lignes d'analyse
```yaml
# config/datasource.yaml → section analysis.user_guidelines
analysis:
  user_guidelines: |
    Je veux comprendre cette base de gestion des bénéficiaires sociaux :

    AXE 1 — Démographie des bénéficiaires
    - Répartition par sexe, tranche d'âge, statut (vivant/décédé)
    - Âge moyen et distribution des âges à l'entrée dans le système
    - Évolution du nombre de bénéficiaires actifs par année

    AXE 2 — Analyse des dossiers
    - Durée moyenne des dossiers, taux de dossiers ouverts
    - Nombre de dossiers par individu, récurrence

    AXE 3 — Prestations : dispersion et profils
    - Fréquence et montant par type de prestation
    - Dispersion par sexe, type de permis, année
    - Prestations uniques vs récurrentes par individu

    AXE 4 — Évolution temporelle
    - Évolution du nombre de bénéficiaires par année
    - Évolution des montants par type de permis et par année
    - Saisonnalité mensuelle des prestations
    - Délai dossier → première prestation

    AXE 5 — Permis et statut administratif
    - Types de permis les plus fréquents
    - Corrélation type de permis × montant de prestation
    - Permis expirés avec prestations encore actives

    AXE 6 — Segmentation des bénéficiaires
    - Top 10% des bénéficiaires par montant total reçu : quel profil ?
    - Segmentation par intensité d'utilisation

    AXE 7 — Qualité des données et anomalies
    - Individus décédés avec prestations postérieures
    - Montants aberrants, dossiers incohérents, doublons NAVS

  max_enrichment_turns: 2
```

### 5. Lancer l'analyse
```bash
python main.py
# ou
python main.py --config config/datasource.yaml --verbose
```

### 6. Ouvrir le dashboard
```bash
open output/dashboard.html  # macOS
xdg-open output/dashboard.html  # Linux
```

## Changer de source de données

Modifier uniquement `config/datasource.yaml` et `mcpo-config.yaml` :

```yaml
# mcpo-config.yaml — ajouter le nouveau serveur
servers:
  postgres-nouvelle-source:
    type: stdio
    command: uvx
    args:
      - mcp-server-postgres
      - postgresql://user:pass@localhost:5434/nouvelle_db

# config/datasource.yaml — pointer vers le nouveau serveur
name: "Nouvelle Source"
connection:
  mcpo_url: "http://localhost:8000"
  mcpo_server: "postgres-nouvelle-source"
  schema: "public"
```

**Zéro changement dans le code.**

## Structure du projet

```
pg_analyst/
├── config/
│   └── datasource.yaml       ← SEUL fichier à modifier par source
├── tools/
│   ├── mcpo_tool.py          ← Wrapper HTTP mcpo (seul algo du projet)
│   └── write_file_tool.py    ← Écriture des fichiers output
├── agents.py                 ← Définition des 4 agents CrewAI
├── tasks.py                  ← Définition des 3 tasks
├── main.py                   ← Point d'entrée
├── mcpo-config.yaml          ← Config serveur mcpo
├── requirements.txt
└── output/                   ← Généré automatiquement
    ├── dashboard.html
    ├── data_export.json
    └── schema_context.json
```
