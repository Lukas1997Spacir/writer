import streamlit as st
import json
import os
from datetime import datetime

# =========================
# KONFIGURACE
# =========================

DATA_DIR = "data"
PROJECTS_DIR = os.path.join(DATA_DIR, "projects")
os.makedirs(PROJECTS_DIR, exist_ok=True)

AVAILABLE_MODELS = {
    "GPT-4o (OpenAI)": "gpt-4o",
    "GPT-4.1": "gpt-4.1",
    "Lokální LLM (Ollama)": "ollama",
}

# =========================
# POMOCNÉ FUNKCE
# =========================

def load_project(project_name):
    path = os.path.join(PROJECTS_DIR, f"{project_name}.json")
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_project(project_name, data):
    path = os.path.join(PROJECTS_DIR, f"{project_name}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def list_projects():
    return [f.replace(".json", "") for f in os.listdir(PROJECTS_DIR) if f.endswith(".json")]


def build_prompt(project, chapter_instruction):
    characters = "\n".join(
        [f"- {c['name']}: {c['description']}" for c in project["characters"]]
    )

    previous_chapters = "\n\n".join(
        [f"Kapitola {i+1}:\n{ch}" for i, ch in enumerate(project["chapters"])]
    )

    prompt = f"""
Jsi profesionální český spisovatel beletrie.
Píšeš román žánru SOAP OPERA pro dospělé publikum.

=== POSTAVY (MUSÍ ZŮSTAT KONZISTENTNÍ) ===
{characters}

=== DOSAVADNÍ DĚJ ===
{previous_chapters}

=== INSTRUKCE PRO NOVOU KAPITOLU ===
{chapter_instruction}

Napiš plnohodnotnou kapitolu v češtině.
Dbej na:
- kontinuitu děje
- konzistentní charakter postav
- dramatické dialogy
- emocionální hloubku
"""
    return prompt.strip()


def generate_chapter(prompt, model_key):
    # ZDE PŘIPOJÍŠ SKUTEČNÝ MODEL
    # --------------------------------
    # OpenAI, Ollama, LM Studio, apod.
    # --------------------------------

    # DEMO PLACEHOLDER:
    return f"(GENEROVANÝ TEXT MODELEM {model_key})\n\n{prompt[:500]}...\n\n[ZDE BUDE SKUTEČNÝ PŘÍBĚH]"


# =========================
# STREAMLIT UI
# =========================

st.set_page_config(page_title="AI Romanopisec", layout="wide")
st.title("📖 AI Romanopisec – česká beletrie")

# -------------------------
# VÝBĚR / VYTVOŘENÍ PROJEKTU
# -------------------------

st.sidebar.header("📚 Projekty")

projects = list_projects()
selected_project = st.sidebar.selectbox("Vyber projekt", ["— nový —"] + projects)

if selected_project == "— nový —":
    new_name = st.sidebar.text_input("Název nové knihy")
    if st.sidebar.button("Vytvořit projekt") and new_name:
        save_project(new_name, {
            "created": str(datetime.now()),
            "characters": [],
            "chapters": []
        })
        st.experimental_rerun()
else:
    project = load_project(selected_project)

    # -------------------------
    # MODEL
    # -------------------------

    st.sidebar.header("🤖 AI Model")
    model_name = st.sidebar.selectbox("Vyber model", list(AVAILABLE_MODELS.keys()))
    model_key = AVAILABLE_MODELS[model_name]

    # -------------------------
    # POSTAVY
    # -------------------------

    st.subheader("🎭 Postavy")

    with st.expander("Správa postav"):
        for i, char in enumerate(project["characters"]):
            st.markdown(f"**{char['name']}** – {char['description']}")

        name = st.text_input("Jméno postavy")
        desc = st.text_area("Popis (vzhled, povaha, vztahy)")

        if st.button("Přidat postavu"):
            project["characters"].append({
                "name": name,
                "description": desc
            })
            save_project(selected_project, project)
            st.experimental_rerun()

    # -------------------------
    # KAPITOLY
    # -------------------------

    st.subheader("📑 Kapitoly")

    for i, chapter in enumerate(project["chapters"]):
        with st.expander(f"Kapitola {i+1}"):
            st.text(chapter)
            if st.button(f"Smazat kapitolu {i+1}", key=f"del_{i}"):
                project["chapters"].pop(i)
                save_project(selected_project, project)
                st.experimental_rerun()

    # -------------------------
    # NOVÁ KAPITOLA
    # -------------------------

    st.subheader("✍️ Nová kapitola")

    chapter_instruction = st.text_area(
        "Popis děje kapitoly (co se má stát)",
        height=150
    )

    if st.button("Vygenerovat kapitolu"):
        prompt = build_prompt(project, chapter_instruction)
        chapter_text = generate_chapter(prompt, model_key)
        project["chapters"].append(chapter_text)
        save_project(selected_project, project)
        st.experimental_rerun()
