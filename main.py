import streamlit as st
import json, os, io, base64
from datetime import datetime
import requests
from PIL import Image

# =========================
# KONFIGURACE
# =========================
DATA_DIR = "data"
PROJECTS_DIR = os.path.join(DATA_DIR, "projects")
os.makedirs(PROJECTS_DIR, exist_ok=True)

# =========================
# BASE64 HELPERY
# =========================
def pil_to_base64(img):
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()

def base64_to_pil(data):
    return Image.open(io.BytesIO(base64.b64decode(data)))

# =========================
# MODELY
# =========================
def load_models():
    with open("models.json", "r", encoding="utf-8") as f:
        return json.load(f)["models"]

MODELS = load_models()

# =========================
# PROJEKTY
# =========================
def list_projects():
    return [f[:-5] for f in os.listdir(PROJECTS_DIR) if f.endswith(".json")]

def load_project(name):
    path = os.path.join(PROJECTS_DIR, f"{name}.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None

def save_project(name, data):
    with open(os.path.join(PROJECTS_DIR, f"{name}.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def safe_refresh():
    st.session_state["_r"] = not st.session_state.get("_r", False)
    st.stop()

# =========================
# PROMPT
# =========================
def build_prompt(project, instruction):
    chars = "\n".join(f"- {c['name']}: {c['description']}" for c in project["characters"])
    chapters = "\n\n".join(ch["text"] for ch in project["chapters"])
    plot = project.get("plot", "")
    return f"""
Jsi profesionální český spisovatel.
Píšeš dospělou SOAP OPERA beletrii.

PLOT:
{plot}

POSTAVY (KONZISTENTNÍ):
{chars}

DOSAVADNÍ DĚJ:
{chapters}

INSTRUKCE:
{instruction}

Napiš plnohodnotnou kapitolu v češtině.
"""

# =========================
# TEXT – OPENROUTER
# =========================
def generate_text(prompt, model_cfg):
    key = st.secrets.get(model_cfg["api_key_env"])
    r = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json={
            "model": model_cfg["model"],
            "messages": [{"role": "user", "content": prompt}],
            "temperature": model_cfg.get("temperature", 0.9),
            "max_tokens": model_cfg.get("max_tokens", 1500)
        },
        timeout=300
    )
    return r.json()["choices"][0]["message"]["content"]

# =========================
# IMAGE – OPENROUTER
# =========================
def generate_image(prompt):
    key = st.secrets["OPENROUTER_API_KEY"]
    r = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json={
            "model": "sourceful/riverflow-v2-fast-preview",
            "messages": [{"role": "user", "content": prompt}],
            "modalities": ["image", "text"]
        },
        timeout=300
    )
    msg = r.json()["choices"][0]["message"]
    img_url = msg["images"][0]["image_url"]["url"]
    img_bytes = requests.get(img_url).content
    return Image.open(io.BytesIO(img_bytes))

# =========================
# UI
# =========================
st.set_page_config("AI Romanopisec", layout="wide")
st.title("📖 AI Romanopisec")

# -------------------------
# PROJEKTY
# -------------------------
projects = list_projects()
sel = st.sidebar.selectbox("Projekt", ["— nový —"] + projects)

if sel == "— nový —":
    name = st.sidebar.text_input("Název knihy")
    if st.sidebar.button("Vytvořit"):
        save_project(name, {
            "created": str(datetime.now()),
            "plot": "",
            "characters": [],
            "chapters": []
        })
        safe_refresh()
    st.stop()

project = load_project(sel)

# -------------------------
# MODEL
# -------------------------
model_label = st.sidebar.selectbox("Model", [m["label"] for m in MODELS])
model = next(m for m in MODELS if m["label"] == model_label)
model["temperature"] = st.sidebar.slider("Kreativita", 0.1, 1.5, 0.9)
model["max_tokens"] = st.sidebar.slider("Délka", 500, 4000, 1500)

# -------------------------
# PLOT
# -------------------------
st.subheader("🧭 Plot")
plot = st.text_area("Základní děj", project["plot"])
if st.button("Uložit plot"):
    project["plot"] = plot
    save_project(sel, project)
    safe_refresh()

# -------------------------
# POSTAVY
# -------------------------
st.subheader("🎭 Postavy")

for i, c in enumerate(project["characters"]):
    st.markdown(f"### {c['name']}")
    st.write(c["description"])

    if "image" in c:
        st.image(base64_to_pil(c["image"]), width=250)

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("❌ Smazat", key=f"dc{i}"):
            project["characters"].pop(i)
            save_project(sel, project)
            safe_refresh()

    with col2:
        if st.button("🎨 AI obrázek", key=f"ic{i}"):
            img = generate_image(f"Realistic portrait of {c['name']}, {c['description']}")
            c["image"] = pil_to_base64(img)
            save_project(sel, project)
            safe_refresh()

    with col3:
        up = st.file_uploader("Nahrát z PC", ["png","jpg","jpeg"], key=f"uc{i}")
        if up:
            c["image"] = pil_to_base64(Image.open(up))
            save_project(sel, project)
            safe_refresh()

name = st.text_input("Jméno postavy")
desc = st.text_area("Popis postavy")
if st.button("Přidat postavu"):
    project["characters"].append({"name": name, "description": desc})
    save_project(sel, project)
    safe_refresh()

# -------------------------
# KAPITOLY
# -------------------------
st.subheader("📑 Kapitoly")

for i, ch in enumerate(project["chapters"]):
    with st.expander(f"Kapitola {i+1}"):
        st.text_area("Text", ch["text"], height=300)

        if "image" in ch:
            st.image(base64_to_pil(ch["image"]), width=400)

        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("🗑️", key=f"dk{i}"):
                project["chapters"].pop(i)
                save_project(sel, project)
                safe_refresh()

        with col2:
            if st.button("🔁 Regenerovat", key=f"rk{i}"):
                ch["text"] = generate_text(build_prompt(project, ch["instruction"]), model)
                save_project(sel, project)
                safe_refresh()

        with col3:
            up = st.file_uploader("Obrázek", ["png","jpg"], key=f"uk{i}")
            if up:
                ch["image"] = pil_to_base64(Image.open(up))
                save_project(sel, project)
                safe_refresh()

# -------------------------
# NOVÁ KAPITOLA
# -------------------------
st.subheader("✍️ Nová kapitola")
instr = st.text_area("Instrukce kapitoly")

if st.button("Vygenerovat"):
    text = generate_text(build_prompt(project, instr), model)
    project["chapters"].append({
        "instruction": instr,
        "text": text
    })
    save_project(sel, project)
    safe_refresh()

# -------------------------
# EXPORT
# -------------------------
if st.sidebar.button("📄 Export .txt"):
    out = ""
    for i, ch in enumerate(project["chapters"]):
        out += f"\nKapitola {i+1}\n{ch['text']}\n"
    st.download_button("Stáhnout", out, f"{sel}.txt")
