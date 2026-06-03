"""
mcpo_tool.py
------------
Seul composant algorithmique du projet.
Simple wrapper HTTP vers le serveur mcpo qui expose PostgreSQL via MCP.
Tout le raisonnement (choix du SQL, exploration, interprétation) 
est fait par les agents via le LLM — pas ici.
"""

import requests
import json
from crewai.tools import tool


# URL mcpo chargée dynamiquement depuis la config au démarrage
_MCPO_URL: str = "http://localhost:8000"
_MCPO_SERVER: str = "postgres-benefits"


def configure(mcpo_url: str, mcpo_server: str):
    """Appelé par main.py au démarrage pour injecter la config."""
    global _MCPO_URL, _MCPO_SERVER
    _MCPO_URL = mcpo_url.rstrip("/")
    _MCPO_SERVER = mcpo_server


@tool("Exécuter une requête SQL sur PostgreSQL via mcpo")
def mcpo_query_tool(sql: str) -> str:
    """
    Exécute une requête SQL SELECT sur la base PostgreSQL via le serveur mcpo.
    
    IMPORTANT : Uniquement des requêtes SELECT sont autorisées.
    Toute tentative d'écriture (INSERT, UPDATE, DELETE, DROP, TRUNCATE) 
    sera rejetée.
    
    Args:
        sql: La requête SQL SELECT à exécuter
        
    Returns:
        Résultat JSON avec les colonnes et les lignes retournées,
        ou un message d'erreur si la requête échoue.
    """
    # Sécurité : bloquer toute écriture
    sql_lower = sql.lower().strip()
    forbidden = ["insert", "update", "delete", "drop", "truncate", "alter", "create", "grant"]
    for kw in forbidden:
        if kw in sql_lower:
            return json.dumps({
                "error": f"Requête non autorisée : le mot-clé '{kw}' est interdit. Uniquement SELECT.",
                "sql": sql
            })

    try:
        # Appel mcpo — endpoint standard MCP-over-HTTP
        endpoint = f"{_MCPO_URL}/{_MCPO_SERVER}/query"
        response = requests.post(
            endpoint,
            json={"sql": sql},
            timeout=30
        )
        response.raise_for_status()
        result = response.json()

        # Normaliser la réponse pour le LLM
        if "rows" in result:
            return json.dumps({
                "success": True,
                "row_count": len(result["rows"]),
                "columns": result.get("columns", []),
                "rows": result["rows"]
            }, ensure_ascii=False, indent=2)
        else:
            return json.dumps(result, ensure_ascii=False, indent=2)

    except requests.exceptions.ConnectionError:
        return json.dumps({
            "error": f"Impossible de joindre mcpo sur {_MCPO_URL}. "
                     "Vérifier que 'mcpo --config mcpo-config.yaml --port 8000' est lancé.",
            "sql": sql
        })
    except requests.exceptions.Timeout:
        return json.dumps({
            "error": "Timeout : la requête a pris trop de temps. Essayer une requête plus légère.",
            "sql": sql
        })
    except Exception as e:
        return json.dumps({
            "error": str(e),
            "sql": sql
        })
