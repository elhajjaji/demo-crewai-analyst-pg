"""
write_file_tool.py
------------------
Tool permettant à l'agent Dashboard d'écrire les fichiers de sortie.
C'est lui qui décide du contenu — ce tool ne fait qu'écrire.
"""

import os
from crewai.tools import tool

_OUTPUT_DIR: str = "output/"


def configure(output_dir: str):
    global _OUTPUT_DIR
    _OUTPUT_DIR = output_dir
    os.makedirs(_OUTPUT_DIR, exist_ok=True)


@tool("Écrire un fichier dans le répertoire de sortie")
def write_file_tool(filename: str, content: str) -> str:
    """
    Écrit le contenu fourni dans output/filename.
    Utiliser pour générer dashboard.html et data_export.json.
    
    Args:
        filename: Nom du fichier (ex: 'dashboard.html', 'data_export.json')
        content:  Contenu complet du fichier à écrire
        
    Returns:
        Confirmation du chemin du fichier créé ou message d'erreur.
    """
    try:
        # Sécurité : pas de path traversal
        safe_name = os.path.basename(filename)
        path = os.path.join(_OUTPUT_DIR, safe_name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        size_kb = os.path.getsize(path) / 1024
        return f"✅ Fichier écrit : {path} ({size_kb:.1f} KB)"
    except Exception as e:
        return f"❌ Erreur écriture {filename} : {e}"
