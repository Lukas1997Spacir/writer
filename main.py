import streamlit as st
import json, os, io, requests
from datetime import datetime
from PIL import Image

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

def load_project(name):
    path = os.path.join(PROJECTS_DIR, f"{name}.json")
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_project(name, data):
    path = os.path.join(PROJECTS_DIR, f"{name}.json")
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
Píšeš román žánru SOAP OPERA pro dospělé.

=== POSTAVY (MUSÍ ZŮSTAT KONZISTENTNÍ) ===
{characters}

=== DOSAVADNÍ DĚJ ===
{previous_chapters}

=== INSTRUKCE PRO NOVOU KAPITOLU ===
{chapter_instruction}

Napiš plnohodnotnou kapitolu v češtině.
Dbej na kontinuitu děje, konzistenci postav, dramatické dialogy a emocionální hloubku.
"""
    return prompt.strip()

# =========================
# VOLÁNÍ TEXTOVÉHO MODELU (OpenRouter)
# =========================
def generate_chapter(prompt, model_cfg):
    api_key = st.secrets.get(model_cfg.get("api_key_env"))
    if not api_key:
        return "CHYBA: API klíč není v secrets."
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": model_cfg["model"],
        "messages": [{"role": "user", "content": prompt}],
        "temperature": model_cfg.get("temperature", 0.9),
        "max_tokens": model_cfg.get("max_tokens", 1500)
    }
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=300)
        r.raise_for_status()
        result = r.json()
        return result["choices"][0]["message"]["content"]
    except Exception as e:
        return f"CHYBA při generování kapitoly: {e}"

# =========================
# GENEROVÁNÍ OBRÁZKŮ
# =========================
def generate_image(prompt: str):
    api_key = st.secrets.get("OPENROUTER_API_KEY")
    if not api_key:
        st.error("OPENROUTER_API_KEY není nastaven v secrets.toml")
        return None

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": "sourceful/riverflow-v2-fast-preview",
        "messages": [{"role": "user", "content": prompt}],
        "modalities": ["image", "text"]
    }

    try:
        r = requests.post(url, headers=headers, json=payload, timeout=300)
        r.raise_for_status()
        result = r.json()
        if result.get("choices") and result["choices"][0]["message"].get("images"):
            image_url = result["choices"][0]["message"]["images"][0]["image_url"]["url"]
            img_data = requests.get(image_url).content
            img = Image.open(io.BytesIO(img_data))
            return img
        else:
            st.warning("Žádný obrázek nebyl vygenerován.")
            return None
    except Exception as e:
        st.error(f"CHYBA při generování obrázku: {e}")
        return None

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
# SAFE REFRESH
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
    # POSTAVY S NÁHRÁVÁNÍM OBRÁZKŮ Z PC
    # -------------------------
    st.subheader("🎭 Postavy")
    with st.expander("Správa postav"):
        for i, char in enumerate(project["characters"]):
            col1, col2, col3, col4 = st.columns([3,1,1,1])
            with col1:
                st.markdown(f"**{char['name']}** – {char['description']}")
                if "image" in char:
                    st.image(char["image"], caption=char["name"], use_column_width=True)
            with col2:
                if st.button("❌ Smazat", key=f"del_char_{i}"):
                    project["characters"].pop(i)
                    save_project(selected_project, project)
                    safe_refresh()
            with col3:
                if st.button("🖼️ Generovat obrázek", key=f"gen_char_img_{i}"):
                    prompt = f"Illustration of {char['name']}, {char['description']}, realistic, detailed, high quality"
                    img = generate_image(prompt)
                    if img:
                        char["image"] = img
                        save_project(selected_project, project)
                        safe_refresh()
            with col4:
                uploaded_file = st.file_uploader(f"Nahrát obrázek pro {char['name']}", type=["png","jpg","jpeg"], key=f"upload_char_{i}")
                if uploaded_file:
                    img = Image.open(uploaded_file)
                    char["image"] = img
                    save_project(selected_project, project)
                    st.success(f"Obrázek pro {char['name']} byl nahrán.")
                    safe_refresh()

    # -------------------------
    # KAPITOLY S NÁHRÁVÁNÍM OBRÁZKŮ Z PC
    # -------------------------
    st.subheader("📑 Kapitoly")
    for i, chapter in enumerate(project["chapters"]):
        with st.expander(f"Kapitola {i+1}"):
            col1, col2, col3, col4, col5 = st.columns(5)
            with col5:
                uploaded_file = st.file_uploader(f"Nahrát obrázek pro kapitolu {i+1}", type=["png","jpg","jpeg"], key=f"upload_chapter_{i}")
                if uploaded_file:
                    img = Image.open(uploaded_file)
                    chapter["image"] = img
                    save_project(selected_project, project)
                    st.success(f"Obrázek pro kapitolu {i+1} byl nahrán.")
                    safe_refresh()
