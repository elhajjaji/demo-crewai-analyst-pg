# demo-crewai-analyst-pg 🐝

**Analyse agentique de bases PostgreSQL → Dashboard HTML interactif**

Stack : CrewAI · Ollama (DGX Spark) · mcpo · Plotly.js

---

## Architecture

```mermaid
flowchart TD
    U([👤 Utilisateur\ngrandes lignes]) --> O

    O["🧠 ORCHESTRATEUR\nPilote, délègue, valide"]

    O --> A

    A["📊 ANALYSTE\nDéfinit axes, interprète"]
    R["🔍 REQUÊTEUR SQL\ntool: mcpo\nGénère SQL, exécute via mcpo"]

    A -->|"requête moi X"| R
    R -->|résultats| A

    A --> G

    G["🖥️ GÉNÉRATEUR TDB\ntool: write_file\ndashboard.html · data_export.json"]
```

## Prérequis

1. **Base de données PostgreSQL** — voir [Déploiement benefits-dataset](#déploiement-de-la-base-de-données-benefits-dataset) ci-dessous
2. **Docker Engine + Compose** — pour déployer la base
3. **mcpo** installé et configuré
4. **Ollama** avec le modèle requis
5. **Python 3.11+**

## Déploiement de la base de données (benefits-dataset)

> **Prérequis** : Docker Engine + Compose

Source : [github.com/elhajjaji/benefits-dataset](https://github.com/elhajjaji/benefits-dataset)

### Cloner le dépôt

```bash
cd ..
# Cloner seulement si le dossier n'existe pas encore
[ ! -d "benefits-dataset" ] && git clone https://github.com/elhajjaji/benefits-dataset.git
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
ollama pull qwen2.5:14b
ollama serve  # si pas déjà démarré
```

### 4. Configurer les grandes lignes d'analyse
```yaml
# config/datasource.yaml — seul fichier à modifier
name: "Ma Source"

connection:
  mcpo_url: "http://localhost:8000"
  mcpo_server: "postgres-benefits"  # doit correspondre à mcpo-config.json
  schema: "src"

ollama:
  model: "qwen2.5:14b"
  base_url: "http://localhost:11434"

analysis:
  max_enrichment_turns: 2
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

output:
  dir: "output/"
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

```json
// mcpo-config.json — ajouter le nouveau serveur
{
  "mcpServers": {
    "postgres-nouvelle-source": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-postgres",
        "postgresql://user:pass@localhost:5434/nouvelle_db"
      ]
    }
  }
}
```

```yaml
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
├── agents.py                 ← 4 agents CrewAI (orchestrateur, analyste, requêteur, générateur)
├── tasks.py                  ← 3 tasks (explore, analyze, dashboard)
├── main.py                   ← Point d'entrée
├── mcpo-config.json          ← Config serveur mcpo (npx @modelcontextprotocol/server-postgres)
├── requirements.txt
└── output/                   ← Généré automatiquement
    ├── dashboard.html
    ├── data_export.json
    └── schema_context.json
```
