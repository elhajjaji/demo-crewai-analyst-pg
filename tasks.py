"""
tasks.py
--------
Définition des tasks CrewAI.
Les tasks définissent CE QUI doit être accompli et par QUI.
Les agents décident EUX-MÊMES COMMENT le faire.
"""

import os
from crewai import Task


def build_tasks(analyst, sql_requester, dashboard_generator, config: dict):
    """
    Construit les tasks dans l'ordre d'exécution.
    """

    source_name = config["name"]
    schema      = config["connection"]["schema"]
    guidelines  = config["analysis"]["user_guidelines"]
    max_turns   = config["analysis"]["max_enrichment_turns"]

    # ── Task 1 : Exploration du schéma ───────────────────────────────────
    task_explore = Task(
        description=f"""
            Explore la base de données "{source_name}" (schéma PostgreSQL : "{schema}").

            ÉTAPE 1 — Commence OBLIGATOIREMENT par lister toutes les tables
            du schéma "{schema}".

            ÉTAPE 2 — Pour chaque table trouvée :
            - Récupère ses colonnes et leurs types
            - Compte ses lignes
            - Échantillonne quelques lignes pour comprendre la sémantique
            - Plages min/max des dates et montants

            ÉTAPE 3 — Identifie les clés étrangères entre tables.
        """,
        agent=sql_requester,
        expected_output="""
            Un rapport complet de découverte du schéma incluant :
            - Liste des tables avec leur nombre de lignes
            - Description de chaque table : colonnes, types, sémantique métier déduite
            - Relations entre tables (quelles colonnes font référence à quelles tables)
            - Exemples de valeurs représentatives pour les colonnes clés
            - Plages temporelles des données (dates min/max)
            - Plages de montants si applicable
        """
    )

    # ── Task 2 : Analyse et enrichissement itératif ──────────────────────
    task_analyze = Task(
        description=f"""
            En te basant sur le rapport de découverte du schéma (task précédente),
            mène une analyse approfondie de la base "{source_name}".

            Grandes lignes de l'utilisateur :
            {guidelines}
            
            Ton processus :
            
            ÉTAPE 1 — Définir les axes d'analyse
            À partir du schéma découvert ET des grandes lignes utilisateur,
            identifie 4 à 6 axes d'analyse. Chaque axe deviendra un onglet 
            dans le dashboard. Nomme chaque axe de façon claire et métier.
            
            ÉTAPE 2 — Requêtes initiales
            Pour chaque axe, formule 2-3 questions analytiques précises et
            demande au Requêteur de les exécuter. Attend les résultats avant
            de passer à l'axe suivant.
            
            ÉTAPE 3 — Interprétation et enrichissement (max {max_turns} tours)
            Pour chaque résultat reçu :
            - Identifie les tendances, anomalies, patterns remarquables
            - Si un résultat est surprenant ou incomplet, formule une question
              complémentaire et demande une nouvelle requête
            - Continue jusqu'à avoir une vision suffisamment riche par axe
            
            ÉTAPE 4 — Synthèse
            Produis un rapport structuré complet prêt pour la génération du dashboard.
        """,
        agent=analyst,
        context=[task_explore],
        expected_output="""
            Un rapport JSON structuré contenant pour chaque axe d'analyse :
            {{
              "axes": [
                {{
                  "axis_name": "Nom de l'onglet",
                  "axis_description": "Description métier de cet axe",
                  "kpis": [
                    {{"label": "Nom du KPI", "value": "valeur", "unit": "unité"}}
                  ],
                  "queries_and_results": [
                    {{
                      "question": "Question analytique posée",
                      "sql": "SELECT ...",
                      "columns": ["col1", "col2"],
                      "rows": [[...], [...]],
                      "insight": "Interprétation en langage naturel"
                    }}
                  ],
                  "key_findings": ["Finding 1", "Finding 2"],
                  "recommended_chart": "bar|line|pie|scatter|heatmap"
                }}
              ]
            }}
        """
    )

    # ── Task 3 : Génération du Dashboard ────────────────────────────────
    output_dir = config.get("output", {}).get("dir", "output/")
    dashboard_output_file = os.path.join(output_dir, "dashboard.html")

    task_dashboard = Task(
        description=f"""
            Tu reçois le rapport d'analyse structuré de la task précédente
            contenant les axes, KPIs, requêtes SQL et résultats.

            Tu dois générer un fichier HTML interactif complet.

            RÈGLE ABSOLUE : ta réponse doit contenir UNIQUEMENT le code HTML.
            - Commence OBLIGATOIREMENT par : <!DOCTYPE html>
            - Termine OBLIGATOIREMENT par : </html>
            - N'ajoute AUCUNE explication avant ou après le HTML
            - N'utilise PAS de balises markdown (pas de ```html)
            - N'appelle AUCUN tool — écris directement le HTML

            CONTENU DU DASHBOARD :
            - Header : "{source_name}", date de génération
            - Navigation par onglets (un onglet par axe d'analyse)
            - Dans chaque onglet :
              * Rangée de KPI cards avec les valeurs réelles
              * Graphique Plotly.js (type adapté : bar/line/pie selon recommended_chart)
              * Section insights avec les key_findings
              * Table des données de l'axe
            - Footer : "Généré par pg_analyst • Ollama • CrewAI"

            TECHNIQUE :
            - CDN Plotly.js : https://cdn.plot.ly/plotly-2.27.0.min.js
            - Design sombre : background #0f1117, surface #1a1d27, accent #00d4aa
            - Toutes les données dans const DASHBOARD_DATA = {{...}} en <script>
            - Fichier autonome (zéro serveur requis)
        """,
        agent=dashboard_generator,
        context=[task_explore, task_analyze],
        expected_output="Code HTML complet commençant par <!DOCTYPE html> et finissant par </html>",
        output_file=dashboard_output_file,
    )

    return task_explore, task_analyze, task_dashboard
