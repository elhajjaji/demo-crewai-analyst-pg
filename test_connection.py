"""
test_connection.py
------------------
Vérifie que mcpo est accessible et que PostgreSQL répond.
Lance avant main.py pour diagnostiquer les problèmes de connexion.

Usage : python test_connection.py
"""

import requests
import json
import sys
import yaml


def test_mcpo(config_path="config/datasource.yaml"):
    print("\n🔍 Test de connexion pg_analyst\n" + "─" * 40)

    config = yaml.safe_load(open(config_path))
    mcpo_url    = config["connection"]["mcpo_url"]
    mcpo_server = config["connection"]["mcpo_server"]
    schema      = config["connection"]["schema"]

    # 1. mcpo accessible ?
    print(f"1. mcpo sur {mcpo_url} ...")
    try:
        r = requests.get(f"{mcpo_url}/docs", timeout=5)
        if r.status_code == 200:
            print("   ✅ mcpo accessible")
        else:
            print(f"   ⚠️  mcpo répond {r.status_code}")
    except Exception as e:
        print(f"   ❌ mcpo inaccessible : {e}")
        print(f"\n   → Lancer : mcpo --config mcpo-config.yaml --port 8000\n")
        sys.exit(1)

    # 2. Lister les tools mcpo
    print(f"\n2. Tools disponibles sur mcpo ...")
    try:
        r = requests.get(f"{mcpo_url}/{mcpo_server}/tools", timeout=5)
        tools = r.json()
        print(f"   ✅ {len(tools)} tools disponibles : {[t.get('name','?') for t in tools[:5]]}")
    except Exception as e:
        print(f"   ⚠️  Impossible de lister les tools : {e}")

    # 3. Requête test PostgreSQL
    print(f"\n3. Requête test sur schéma '{schema}' ...")
    try:
        r = requests.post(
            f"{mcpo_url}/{mcpo_server}/query",
            json={"sql": f"SELECT table_name, (SELECT COUNT(*) FROM {schema}.\"{{}}\".format(table_name)) FROM information_schema.tables WHERE table_schema = '{schema}' LIMIT 10"},
            timeout=10
        )
        # Requête simplifiée
        r2 = requests.post(
            f"{mcpo_url}/{mcpo_server}/query",
            json={"sql": f"SELECT table_name FROM information_schema.tables WHERE table_schema = '{schema}'"},
            timeout=10
        )
        result = r2.json()
        if "rows" in result:
            tables = [row[0] if isinstance(row, list) else list(row.values())[0] for row in result["rows"]]
            print(f"   ✅ Tables trouvées dans '{schema}' : {tables}")
        else:
            print(f"   ⚠️  Réponse inattendue : {result}")
    except Exception as e:
        print(f"   ❌ Erreur requête : {e}")
        print(f"\n   → Vérifier que PostgreSQL est démarré (docker compose up -d)\n")
        sys.exit(1)

    # 4. Test volumétrie rapide
    print(f"\n4. Volumétrie rapide ...")
    for table in tables:
        try:
            r = requests.post(
                f"{mcpo_url}/{mcpo_server}/query",
                json={"sql": f'SELECT COUNT(*) as n FROM {schema}."{table}"'},
                timeout=10
            )
            res = r.json()
            count = res["rows"][0][0] if res.get("rows") else "?"
            print(f"   📊 {schema}.{table} : {count:,} lignes" if isinstance(count, int) else f"   📊 {schema}.{table} : {count} lignes")
        except Exception as e:
            print(f"   ⚠️  {table} : {e}")

    print(f"\n✅ Tout est opérationnel — tu peux lancer : python main.py\n")


if __name__ == "__main__":
    test_mcpo()
