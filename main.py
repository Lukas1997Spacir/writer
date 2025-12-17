import streamlit as st
import json
import os
from datetime import datetime
import requests
import io

# =========================
# KONFIGURACE
# =========================

DATA_DIR = "data"
PROJECTS_DIR = os.path.join(DATA_DIR, "projects")
os.makedirs(PROJECTS_DIR, exist_ok=True)

# =========================
# NAČTENÍ MODELŮ
# =========================

def load_models():
    with open("models.json", "r", encoding="utf-8") as f:
        return json.load(f)["models"]

MODELS = load_models()
MODEL_LABELS = [m["label"] for m in MODELS]

# =========================
# POMOCNÉ FUNKCE
# =========================

def list_projects():
    return [f.replace(".json", "") for f in os.listdir(PROJECTS_DIR) if f.endswith(".json")]

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

def build_prompt(project, chapter_instruction):
    characters = "\n".join([f"- {c['name']}: {c['description']}" for c in project["characters"]])
    previous_chapters = "\n\n".join([f"Kapitola {i+1}:\n{ch['text']}" for i, ch in enumerate(project["chapters"])])
    plot = project.get("plot", "")
    prompt = f"""
Plán knihy:
{plot}

Jsi profesionální český spisovatel beletrie.

=== POSTAVY (MUSÍ ZŮSTAT KONZISTENTNÍ) ===
{characters}

=== DOSAVADNÍ DĚJ ===
{previous_chapters}

=== INSTRUKCE PRO NOVOU KAPITOLU ===
{chapter_instruction}

Napiš plnohodnotnou kapitolu v češtině.
Dbej na kontinuitu děje, konzistenci postav, dramatické dialogy a emocionální hloubku. Nepiš nic jako číslo, nebo název kapitoly, ani "konec kapitoly".
"""
    return prompt.strip()

# =========================
# VOLÁNÍ MODELŮ
# =========================

def generate_chapter(prompt, model_cfg):
    provider = model_cfg["provider"]
    if provider == "openai":
        return call_openai(prompt, model_cfg)
    elif provider == "ollama":
        return call_ollama(prompt, model_cfg)
    else:
        raise ValueError("Neznámý provider")

def call_openai(prompt, cfg):
    api_key = st.secrets.get(cfg.get("api_key_env"))
    if not api_key:
        return "CHYBA: API klíč není v secrets."
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": cfg["model"],
        "messages": [
            {"role": "system", "content": "Jsi český spisovatel beletrie."},
            {"role": "user", "content": prompt}
        ],
        "temperature": cfg.get("temperature", 0.9),
        "max_tokens": cfg.get("max_tokens", 1500)
    }
    try:
        r = requests.post(cfg["endpoint"], headers=headers, json=payload, timeout=300)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    except requests.exceptions.RequestException as e:
        return f"CHYBA: Nelze se připojit k API: {e}"

def call_ollama(prompt, cfg):
    try:
        payload = {"model": cfg["model"], "prompt": prompt, "stream": False}
        r = requests.post(cfg["endpoint"], json=payload, timeout=300)
        r.raise_for_status()
        return r.json()["response"]
    except requests.exceptions.RequestException as e:
        return f"CHYBA: Nelze se připojit k Ollama endpointu: {e}"

# =========================
# REGENERACE KAPITOLY
# =========================

def regenerate_chapter(project, chapter_index, model_cfg):
    chapter = project["chapters"][chapter_index]
    prompt = build_prompt(project, chapter["instruction"])
    new_text = generate_chapter(prompt, model_cfg)
    if "versions" not in chapter:
        chapter["versions"] = [chapter["text"]]
    chapter["versions"].append(new_text)
    chapter["text"] = new_text

# =========================
# FUNKCE PRO BEZPEČNÝ REFRESH
# =========================

def safe_refresh():
    st.session_state["refresh"] = not st.session_state.get("refresh", False)
    st.stop()

# =========================
# STREAMLIT UI
# =========================

st.set_page_config(page_title="AI Romanopisec", layout="wide")
st.title("📖 AI Romanopisec – česká beletrie")

# -------------------------
# PROJEKTY
# -------------------------

st.sidebar.header("📚 Projekty")
projects = list_projects()
selected_project = st.sidebar.selectbox("Vyber projekt", ["— nový —"] + projects)

if selected_project == "— nový —":
    new_name = st.sidebar.text_input("Název nové knihy")
    if st.sidebar.button("Vytvořit projekt", key="create_proj"):
        if new_name:
            save_project(new_name, {"created": str(datetime.now()), "characters": [], "chapters": [], "plot": ""})
            safe_refresh()
else:
    project = load_project(selected_project)

    # -------------------------
    # EXPORT PROJEKTU
    # -------------------------

    st.sidebar.header("📄 Export")
    if st.sidebar.button("Exportovat projekt jako .txt", key="export_txt"):
        output = io.StringIO()
        output.write(f"Kniha: {selected_project}\n\n")
        output.write("=== Postavy ===\n")
        for c in project["characters"]:
            output.write(f"- {c['name']}: {c['description']}\n")
        output.write("\n=== Děj ===\n")
        for i, ch in enumerate(project["chapters"]):
            output.write(f"Kapitola {i+1}: {ch['text']}\n\n")
        st.download_button(
            "Stáhnout .txt",
            data=output.getvalue(),
            file_name=f"{selected_project}.txt",
            mime="text/plain"
        )

    # -------------------------
    # MODEL + NASTAVENÍ
    # -------------------------

    st.sidebar.header("🤖 AI Model")
    selected_label = st.sidebar.selectbox("Vyber model", [m["label"] for m in MODELS], key="model_select")
    selected_model = next(m for m in MODELS if m["label"] == selected_label)

    st.sidebar.header("⚙️ Nastavení generování")
    temperature = st.sidebar.slider("Kreativita (teplota)", 0.1, 1.5, 0.9, 0.1, key="temp_slider")
    max_tokens = st.sidebar.slider("Délka kapitoly (tokeny)", 500, 4000, 1500, 100, key="tokens_slider")
    selected_model["temperature"] = temperature
    selected_model["max_tokens"] = max_tokens

    # -------------------------
    # PLOT KNIHY
    # -------------------------

    st.subheader("📝 Plot knihy")
    plot_text = st.text_area(
        "Zadej základní děj / plot knihy (kde se odehrává, struktura, klíčové momenty)",
        value=project.get("plot", ""),
        key="book_plot"
    )
    if st.button("Uložit plot", key="save_plot"):
        project["plot"] = plot_text
        save_project(selected_project, project)
        st.success("Plot uložen!")
        safe_refresh()

    # -------------------------
    # POSTAVY
    # -------------------------

    st.subheader("🎭 Postavy")
    with st.expander("Správa postav"):
        for i, char in enumerate(project["characters"]):
            col1, col2 = st.columns([4,1])
            with col1:
                st.markdown(f"**{char['name']}** – {char['description']}")
            with col2:
                if st.button("❌ Smazat", key=f"del_char_{i}"):
                    project["characters"].pop(i)
                    save_project(selected_project, project)
                    safe_refresh()
        name = st.text_input("Jméno postavy", key="new_char_name")
        desc = st.text_area("Popis (vzhled, povaha, vztahy)", key="new_char_desc")
        if st.button("Přidat postavu", key="add_char"):
            project["characters"].append({"name": name, "description": desc})
            save_project(selected_project, project)
            safe_refresh()

    # -------------------------
    # KAPITOLY
    # -------------------------

    st.subheader("📑 Kapitoly")
    for i, chapter in enumerate(project["chapters"]):
        with st.expander(f"Kapitola {i+1}"):
            versions = chapter.get("versions", [chapter["text"]])
            selected_version = st.selectbox(
                "Verze kapitoly",
                range(len(versions)),
                format_func=lambda x: f"Verze {x+1}",
                key=f"chapter_{i}_version"
            )
            st.text_area(
                "Text kapitoly",
                versions[selected_version],
                height=300,
                key=f"chapter_{i}_text"
            )

            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button(f"Smazat kapitolu {i+1}", key=f"del_{i}"):
                    project["chapters"].pop(i)
                    save_project(selected_project, project)
                    safe_refresh()
            with col2:
                if st.button(f"Regenerovat kapitolu {i+1}", key=f"regen_{i}"):
                    regenerate_chapter(project, i, selected_model)
                    save_project(selected_project, project)
                    safe_refresh()
            with col3:
                if st.button(f"Přidat verzi jako samostatnou {i+1}", key=f"copy_{i}"):
                    project["chapters"].append({
                        "instruction": chapter["instruction"],
                        "text": chapter["text"],
                        "versions": chapter.get("versions", [chapter["text"]])
                    })
                    save_project(selected_project, project)
                    safe_refresh()

# =========================
# NOVÁ KAPITOLA – okamžité zobrazení
# =========================

if "new_chapter" not in st.session_state:
    st.session_state["new_chapter"] = None

st.subheader("✍️ Nová kapitola")
chapter_instruction = st.text_area(
    "Popis děje kapitoly (co se má stát)",
    height=150,
    key="new_chapter_instr"
)

# Generování kapitoly
if st.button("Vygenerovat kapitolu", key="gen_chapter"):
    prompt = build_prompt(project, chapter_instruction)
    chapter_text = generate_chapter(prompt, selected_model)
    # uložíme do session_state pro okamžité zobrazení
    st.session_state["new_chapter"] = {
        "instruction": chapter_instruction,
        "text": chapter_text,
        "versions": [chapter_text]
    }

# Zobrazení nově vygenerované kapitoly
if st.session_state["new_chapter"]:
    new_ch = st.session_state["new_chapter"]
    st.text_area("✅ Vygenerovaná kapitola", new_ch["text"], height=300)
    if st.button("Uložit kapitolu do projektu"):
        project["chapters"].append(new_ch)
        save_project(selected_project, project)
        st.session_state["new_chapter"] = None
        st.success("Kapitola uložena do projektu!")
        safe_refresh()
