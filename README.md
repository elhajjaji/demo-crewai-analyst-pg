# demo-crewai-analyst-pg 🐝

**Analyse agentique de bases PostgreSQL → Dashboard HTML interactif**

Stack : CrewAI · Ollama (DGX Spark) · mcpo · Plotly.js

> Ce projet expérimente l'utilisation d'agents IA autonomes (CrewAI + LLM local via Ollama) pour explorer une base PostgreSQL inconnue, produire une analyse métier structurée, et générer automatiquement un dashboard HTML interactif — sans écrire une seule ligne de SQL manuellement.
>
> L'utilisateur fournit uniquement des **grandes lignes** (ce qu'il veut comprendre), les agents s'occupent du reste : exploration du schéma, formulation des requêtes, interprétation des résultats, et rendu visuel.

---

## Architecture

Voici la modélisation complète de l'architecture du projet, mise à jour d'après la structure de `pg_analyst_2`. Ce schéma intègre notamment le modèle `qwen2.5-coder:14b` pour le générateur de dashboard, l'invalidation de la délégation pour les workers SQL et Front-end, et l'utilisation de `dashboard_template_reference.html`.

```mermaid
flowchart TB
    %% Définitions des styles de classes
    classDef config fill:#eceff1,stroke:#37474f,stroke-width:1px,color:#263238;
    classDef execution fill:#fff3e0,stroke:#ff9800,stroke-width:1px,color:#e65100;
    classDef agent fill:#e0f2f1,stroke:#009688,stroke-width:1px,color:#004d40;
    classDef task fill:#efebe9,stroke:#8d6e63,stroke-width:1px,color:#4e342e;
    classDef infra fill:#ede7f6,stroke:#673ab7,stroke-width:1px,color:#4a148c;
    classDef output fill:#e8f5e9,stroke:#4caf50,stroke-width:1px,color:#1b5e20;
    classDef user fill:#e3f2fd,stroke:#2196f3,stroke-width:1px,color:#0d47a1;

    subgraph Inputs ["⚙️ Configuration & Entrées"]
        U([👤 Utilisateur]) -->|Définit besoins| Conf["📄 config/datasource.yaml<br/>- mcpo URL & Schema<br/>- Modèles Ollama<br/>- Directives utilisateur (user_guidelines)"]
        MC["⚙️ mcpo-config.json<br/>- Configuration serveur MCP<br/>- PostgreSQL URI"]
        Tpl["📄 dashboard_template_reference.html<br/>- Template HTML de référence visuelle"]
    end
    
    subgraph Execution ["⚡ Point d'Entrée Python"]
        Main["🐍 main.py<br/>- Chargement config & vérifs<br/>- Initialisation des Tools<br/>- Lancement du Crew<br/>- Post-processing HTML/JSON"]
    end

    subgraph CrewAI ["🤖 Orchestration CrewAI (Processus Hiérarchique)"]
        Mgr["🧠 ORCHESTRATEUR (Manager)<br/>- Modèle: qwen2.5:14b<br/>- Délégation: ACTIVÉE<br/>- Rôle: Diriger, cadrer, valider les résultats"]
        
        subgraph Agents ["Agents de Travail (Workers)"]
            A["📊 ANALYSTE<br/>- Modèle: qwen2.5:14b<br/>- Rôle: Définir les axes, interpréter les données<br/>- Outil: write_file_tool<br/>- Délégation: ACTIVÉE"]
            R["🔍 REQUÊTEUR SQL<br/>- Modèle: qwen2.5-coder:7b<br/>- Rôle: Écrire & exécuter le SQL standard<br/>- Outil: mcpo_query_tool<br/>- Délégation: DÉSACTIVÉE"]
            G["🖥️ GÉNÉRATEUR DASHBOARD<br/>- Modèle: qwen2.5-coder:14b<br/>- Rôle: Traduire l'analyse en HTML/CSS/JS<br/>- Outil: Aucun (génère le HTML brut)<br/>- Délégation: DÉSACTIVÉE"]
        end
    end

    subgraph Tasks ["📋 Déroulement des Tâches (tasks.py)"]
        T1["Tâche 1 : Exploration (task_explore)<br/>- Lister les tables<br/>- Décrire structures & relations<br/>- Compter et échantillonner"]
        T2["Tâche 2 : Analyse (task_analyze)<br/>- Définir 4-6 axes (onglets)<br/>- Poser des questions analytiques<br/>- Itérer avec SQL (max_turns)"]
        T3["Tâche 3 : Dashboard (task_dashboard)<br/>- Générer une page autonome (Plotly.js)<br/>- Appliquer le thème sombre pro<br/>- Injecter données & insights"]
    end

    subgraph Infra ["🌐 Infrastructure Locale (Services)"]
        Ollama["🧠 Ollama API<br/>(base_url:11434)<br/>Modèles : qwen2.5:14b & qwen2.5-coder"]
        MCP["🔌 Serveur mcpo (port:8000)<br/>- Wrapper MCP postgres<br/>- Valide & exécute SELECT"]
        DB[("🗄️ PostgreSQL DB<br/>- benefits-dataset<br/>- Docker Compose port 5433")]
    end

    subgraph Outputs ["📦 Livrables (output/)"]
        Out1["🖥️ dashboard.html<br/>- Graphiques interactifs Plotly.js<br/>- Navigation par onglets"]
        Out2["📊 data_export.json<br/>- Données brutes structurées par axes<br/>- KPIs et insights associés"]
        Out3["⚙️ schema_context.json<br/>- Cache de structure PostgreSQL"]
    end

    %% Connexions - Config & Entrée
    Conf --> Main
    MC --> Main
    Tpl -.-> Main
    Main --> Mgr

    %% Connexions - Délégation Hiérarchique
    Mgr -->|Délègue & Valide| A
    Mgr -->|Délègue| R
    Mgr -->|Délègue| G

    %% Collaboration inter-agents
    A -->|1. Demande de schéma / 3. Requêtes SQL| R
    R -->|2. Métadonnées / 4. Résultats bruts| A
    A -->|"5. Rapport structuré (JSON)"| G

    %% Flux des tâches
    Main -->|Lance| T1
    T1 -->|Résultats découverte schéma| T2
    T2 -->|Rapport JSON d'analyse| T3
    T3 -->|HTML brut| Main

    %% Liaison agents <-> tâches
    R -.->|Exécute| T1
    A -.->|Exécute| T2
    G -.->|Exécute| T3

    %% Appels aux services
    Mgr -->|Requêtes LLM| Ollama
    A -->|Requêtes LLM| Ollama
    R -->|Requêtes LLM| Ollama
    G -->|Requêtes LLM| Ollama
    R --->|1. mcpo_query_tool| MCP
    MCP --->|2. Requête SQL SELECT| DB
    DB -.->|3. Données de tables| MCP
    MCP -.->|4. JSON Response| R

    %% Génération des fichiers de sortie
    Main -->|Nettoie & Sauvegarde| Out1
    Main -->|Extrait JSON| Out2
    A -.->|Cache schéma| Out3

    %% Assignation des styles
    class Conf config
    class MC config
    class Tpl config
    class Main execution
    class Mgr agent
    class A agent
    class R agent
    class G agent
    class T1 task
    class T2 task
    class T3 task
    class Ollama infra
    class MCP infra
    class DB infra
    class Out1 output
    class Out2 output
    class Out3 output
    class U user
```


### VERSION LIGHT
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
ollama pull qwen2.5:14b        # orchestrateur + analyste
ollama pull qwen2.5-coder:7b   # requêteur SQL + générateur dashboard
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
