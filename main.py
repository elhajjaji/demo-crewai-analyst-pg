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
import json
import os
import re
import sys
import yaml
from datetime import datetime
from crewai import Crew, Process, LLM

# ── Imports locaux ───────────────────────────────────────────────────────
from tools import mcpo_tool, write_file_tool
from agents import build_agents, resolve_llm
from tasks import build_tasks


def load_config(config_path: str) -> dict:
    """Charge et valide la configuration datasource.yaml."""
    if not os.path.exists(config_path):
        print(f"❌ Config introuvable : {config_path}")
        sys.exit(1)
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # Validation minimale
    required = ["name", "connection", "analysis", "output"]
    for key in required:
        if key not in config:
            print(f"❌ Clé manquante dans la config : '{key}'")
            sys.exit(1)

    # Au moins une source LLM doit être présente
    if "llms" not in config and "ollama" not in config:
        print("❌ Config invalide : section 'llms' ou 'ollama' requise")
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


def save_data_export(task_analyze, config: dict):
    """
    Extrait le JSON structuré du résultat de task_analyze et sauvegarde data_export.json.
    Bypass fiable : ne dépend pas des tool calls de l'agent.
    """
    output_dir = config["output"]["dir"]
    json_path = os.path.join(output_dir, "data_export.json")

    # Si le fichier existe déjà avec du contenu réel, ne pas écraser
    if os.path.exists(json_path) and os.path.getsize(json_path) > 500:
        return

    if not (task_analyze.output and task_analyze.output.raw):
        print("⚠️  task_analyze.output vide — data_export.json non généré")
        return

    raw = task_analyze.output.raw

    # Chercher un bloc ```json ... ```
    match = re.search(r'```json\s*(\{.*?\})\s*```', raw, re.DOTALL)
    if not match:
        # Chercher un JSON brut avec la clé "axes"
        match = re.search(r'(\{\s*"axes"\s*:.*\})', raw, re.DOTALL)

    if match:
        try:
            data = json.loads(match.group(1))
            export = {
                "source": config["name"],
                "generated_at": datetime.now().isoformat(),
            }
            export.update(data)
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(export, f, ensure_ascii=False, indent=2)
            size = os.path.getsize(json_path) // 1024
            print(f"✅ data_export.json sauvegardé ({size} KB)")
        except json.JSONDecodeError as e:
            print(f"⚠️  JSON invalide dans task_analyze.output : {e}")
    else:
        print("⚠️  Impossible d'extraire le JSON de task_analyze.output")


def fix_dashboard_html(task_dashboard, config: dict):
    """
    Si dashboard.html contient du markdown (```html wrapper), nettoie le fichier.
    CrewAI output_file sauvegarde le raw output, qui peut inclure du markdown.
    """
    output_dir = config["output"]["dir"]
    html_path = os.path.join(output_dir, "dashboard.html")

    if not os.path.exists(html_path):
        print("⚠️  dashboard.html non trouvé après output_file — extraction depuis raw")
        # Fallback : extraire depuis task_dashboard.output.raw
        if task_dashboard.output and task_dashboard.output.raw:
            raw = task_dashboard.output.raw
            # Bloc ```html ... ```
            match = re.search(r'```html\s*(.*?)\s*```', raw, re.DOTALL)
            if not match:
                # HTML direct (commence par <!DOCTYPE)
                match = re.search(r'(<!DOCTYPE\s+html>.*?</html>)', raw, re.DOTALL | re.IGNORECASE)
            if match:
                with open(html_path, "w", encoding="utf-8") as f:
                    f.write(match.group(1))
                size = os.path.getsize(html_path) // 1024
                print(f"✅ dashboard.html extrait depuis raw ({size} KB)")
        return

    with open(html_path, "r", encoding="utf-8") as f:
        content = f.read().strip()

    # Nettoyer le wrapper markdown si présent
    if content.startswith("```"):
        match = re.search(r'```(?:html)?\s*(<!DOCTYPE.*?</html>)', content, re.DOTALL | re.IGNORECASE)
        if match:
            clean = match.group(1)
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(clean)
            size = os.path.getsize(html_path) // 1024
            print(f"✅ dashboard.html nettoyé (markdown retiré, {size} KB)")


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
    llms_cfg = config.get("llms", {})
    default_llm_id = llms_cfg.get("default") or config.get("ollama", {}).get("model", "?")
    print(f"✅ LLM défaut   : {default_llm_id}")
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
    
    # Manager LLM = LLM de l'orchestrateur
    manager_llm = resolve_llm(config, "orchestrator")
    
    # ── Assembler et lancer le Crew ──────────────────────────────────────
    crew = Crew(
        agents=[analyst, sql_requester, dashboard_generator],
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

    # ── Post-processing : sauvegarde des fichiers de sortie ──────────────
    # data_export.json : extrait du résultat de task_analyze (bypass tool calls)
    save_data_export(task_analyze, config)
    # dashboard.html : sauvegardé par output_file, nettoyage markdown si besoin
    fix_dashboard_html(task_dashboard, config)

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
