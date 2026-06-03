"""
main.py
-------
Point d'entrée de pg_analyst.
Lance le crew CrewAI pour analyser une base PostgreSQL et générer un dashboard HTML.

Usage :
    python main.py
    python main.py --config config/autre_source.yaml
    python main.py --verbose
"""

import argparse
import os
import sys
import yaml
from datetime import datetime
from crewai import Crew, Process, LLM

# ── Imports locaux ───────────────────────────────────────────────────────
from tools import mcpo_tool, write_file_tool
from agents import build_agents
from tasks import build_tasks


def load_config(config_path: str) -> dict:
    """Charge et valide la configuration datasource.yaml."""
    if not os.path.exists(config_path):
        print(f"❌ Config introuvable : {config_path}")
        sys.exit(1)
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # Validation minimale
    required = ["name", "connection", "ollama", "analysis", "output"]
    for key in required:
        if key not in config:
            print(f"❌ Clé manquante dans la config : '{key}'")
            sys.exit(1)

    return config


def check_mcpo(mcpo_url: str) -> bool:
    """Vérifie que le serveur mcpo est accessible."""
    import requests
    try:
        resp = requests.get(f"{mcpo_url}/docs", timeout=5)
        return resp.status_code == 200
    except Exception:
        return False


def main():
    # ── Arguments CLI ────────────────────────────────────────────────────
    parser = argparse.ArgumentParser(description="pg_analyst — Analyse agentique PostgreSQL")
    parser.add_argument("--config",   default="config/datasource.yaml", help="Chemin vers datasource.yaml")
    parser.add_argument("--verbose",  action="store_true", help="Mode verbose CrewAI")
    args = parser.parse_args()

    print("\n" + "═" * 60)
    print("  🐝 pg_analyst — Analyse agentique PostgreSQL")
    print("═" * 60)
    print(f"  Config    : {args.config}")
    print(f"  Démarrage : {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print("═" * 60 + "\n")

    # ── Charger la config ────────────────────────────────────────────────
    config = load_config(args.config)
    print(f"✅ Source       : {config['name']}")
    print(f"✅ Schema       : {config['connection']['schema']}")
    print(f"✅ Modèle LLM   : {config['ollama']['model']}")
    print(f"✅ Output dir   : {config['output']['dir']}\n")

    # ── Vérification mcpo ────────────────────────────────────────────────
    mcpo_url = config["connection"]["mcpo_url"]
    print(f"🔌 Vérification mcpo sur {mcpo_url}...")
    if not check_mcpo(mcpo_url):
        print(f"""
❌ mcpo inaccessible sur {mcpo_url}

Pour lancer mcpo :
    mcpo --config mcpo-config.yaml --port 8000

Vérifier que PostgreSQL est bien démarré :
    docker compose up -d  (depuis benefits-dataset/)
""")
        sys.exit(1)
    print(f"✅ mcpo accessible\n")

    # ── Configurer les tools avec la config ──────────────────────────────
    mcpo_tool.configure(
        mcpo_url=config["connection"]["mcpo_url"],
        mcpo_server=config["connection"]["mcpo_server"]
    )
    write_file_tool.configure(
        output_dir=config["output"]["dir"]
    )
    os.makedirs(config["output"]["dir"], exist_ok=True)

    # ── Construire les agents ────────────────────────────────────────────
    print("🤖 Initialisation des agents...")
    
    agents = build_agents(config)
    analyst, sql_requester, dashboard_generator = agents[1], agents[2], agents[3]

    print("✅ 4 agents initialisés\n")

    # ── Construire les tasks ─────────────────────────────────────────────
    task_explore, task_analyze, task_dashboard = build_tasks(
        analyst, sql_requester, dashboard_generator, config
    )
    
    # Manager LLM = l'orchestrateur, mais géré par CrewAI nativement
    manager_llm = LLM(
        model=f"ollama/{config['ollama']['model']}",
        base_url=config["ollama"]["base_url"],
        temperature=0.1
    )
    
    # ── Assembler et lancer le Crew ──────────────────────────────────────
    crew = Crew(
        agents=[analyst, sql_requester, dashboard_generator],  # sans orchestrator
        tasks=[task_explore, task_analyze, task_dashboard],
        process=Process.hierarchical,
        manager_llm=manager_llm,
        verbose=True,
        memory=False,
        max_rpm=10
    )

    print("🚀 Lancement du crew d'analyse...\n")
    print("─" * 60)

    start_time = datetime.now()
    try:
        result = crew.kickoff()
    except KeyboardInterrupt:
        print("\n⚠️  Analyse interrompue par l'utilisateur.")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Erreur lors de l'analyse : {e}")
        raise

    elapsed = datetime.now() - start_time

    # ── Résumé final ─────────────────────────────────────────────────────
    print("\n" + "═" * 60)
    print("  ✅ ANALYSE TERMINÉE")
    print("═" * 60)
    print(f"  Durée         : {elapsed}")
    print(f"  Dashboard     : {config['output']['dir']}dashboard.html")
    print(f"  Export JSON   : {config['output']['dir']}data_export.json")
    print(f"  Schéma cache  : {config['output']['dir']}schema_context.json")
    print("═" * 60 + "\n")

    # Vérification que les fichiers existent
    dashboard_path = os.path.join(config["output"]["dir"], "dashboard.html")
    if os.path.exists(dashboard_path):
        size = os.path.getsize(dashboard_path) / 1024
        print(f"📊 dashboard.html généré ({size:.0f} KB)")
        print(f"   Ouvrir dans le navigateur : file://{os.path.abspath(dashboard_path)}\n")
    else:
        print("⚠️  dashboard.html non trouvé — vérifier les logs du crew\n")

    return result


if __name__ == "__main__":
    main()
