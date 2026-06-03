"""
tasks.py
--------
Définition des tasks CrewAI.
Les tasks définissent CE QUI doit être accompli et par QUI.
Les agents décident EUX-MÊMES COMMENT le faire.
"""

from crewai import Task


def build_tasks(analyst, sql_requester, dashboard_generator, config: dict):
    """
    Construit les tasks dans l'ordre d'exécution.
    Le contexte passe naturellement d'une task à l'autre via CrewAI.
    """

    source_name = config["name"]
    schema      = config["connection"]["schema"]
    guidelines  = config["analysis"]["user_guidelines"]
    max_turns   = config["analysis"]["max_enrichment_turns"]

    # ── Task 1 : Exploration du schéma ───────────────────────────────────
    task_explore = Task(
        description=f"""
            Explore la base de données "{source_name}" (schéma PostgreSQL : "{schema}").
            
            Tu dois interroger la base pour en comprendre complètement la structure :
            - Lister toutes les tables du schéma "{schema}" et leur nombre de lignes
            - Pour chaque table : colonnes, types de données, valeurs nulles
            - Identifier les relations entre tables (clés étrangères)
            - Faire des requêtes d'échantillonnage (SELECT ... LIMIT 5) sur chaque table
              pour comprendre la sémantique réelle des données
            - Identifier les colonnes de dates, de montants, de catégories
            - Détecter les plages de valeurs importantes (min/max des dates, des montants)
            
            Utilise information_schema pour la structure et des SELECT directs 
            pour la sémantique.
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
            dans le dashboard. Nomme chaque axe de façon claire et métier
            (ex: "Démographie des bénéficiaires", "Évolution des prestations", etc.)
            
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
                    {{"label": "Total bénéficiaires", "value": "10,234", "unit": ""}}
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
    task_dashboard = Task(
        description=f"""
            À partir du rapport d'analyse structuré (task précédente),
            génère deux fichiers dans output/ :
            
            ═══════════════════════════════════════
            FICHIER 1 : dashboard.html
            ═══════════════════════════════════════
            
            Un tableau de bord HTML interactif et autonome (tout-en-un).
            
            STRUCTURE GLOBALE :
            - Header avec : nom de la source "{source_name}", date de génération,
              nombre d'axes analysés
            - Navigation par onglets (un par axe d'analyse)
            - Footer avec mention "Généré par pg_analyst • Ollama • CrewAI"
            
            CONTENU DE CHAQUE ONGLET :
            1. Rangée de KPI cards (valeurs clés issues des données)
            2. Graphique Plotly.js principal (type adapté aux données de cet axe)
            3. Section "Insights" avec les findings en langage naturel,
               présentés avec des icônes et une mise en forme soignée
            4. Table de données filtrable (search box) avec pagination
            5. Accordéon "Voir la requête SQL" (collapse par défaut)
            
            CONTRAINTES TECHNIQUES :
            - Fichier HTML autonome (zéro serveur requis)
            - CDN : Plotly.js (https://cdn.plot.ly/plotly-2.27.0.min.js), Tailwind CSS
            - Police : IBM Plex Mono + IBM Plex Sans (Google Fonts)
            - Données intégrées directement en JSON dans un const DASHBOARD_DATA = {{...}}
            - Compatible Chrome/Firefox/Edge
            - Design sombre professionnel :
                --bg: #0f1117, --surface: #1a1d27, --border: #2a2d3a
                --teal: #00d4aa (couleur principale), --amber: #f59e0b (accents)
            - Un fichier de référence HTML existe dans dashboard_template_reference.html —
              inspire-toi de sa structure CSS, de son moteur JS et de ses composants,
              mais adapte le contenu aux données réelles de l'analyse.
            
            ═══════════════════════════════════════
            FICHIER 2 : data_export.json
            ═══════════════════════════════════════
            
            Toutes les données brutes structurées :
            {{
              "source": "{source_name}",
              "generated_at": "ISO datetime",
              "axes": [ ... même structure que le rapport d'analyse ... ]
            }}
            
            Utilise le tool write_file_tool pour écrire chaque fichier.
        """,
        agent=dashboard_generator,
        context=[task_explore, task_analyze],
        expected_output="""
            Confirmation que les deux fichiers ont été créés avec succès :
            - output/dashboard.html (taille en KB)
            - output/data_export.json (taille en KB)
            Avec un résumé du contenu : nombre d'onglets, types de graphiques utilisés.
        """
    )

    return task_explore, task_analyze, task_dashboard
