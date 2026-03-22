import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import urllib.parse
from datetime import datetime

# --- CONFIGURATION ---
st.set_page_config(page_title="Méli-Mélo", page_icon="📚", layout="centered")

if 'connecte' not in st.session_state:
    st.session_state.connecte = False
if 'user' not in st.session_state:
    st.session_state.user = None

def refresh():
    st.cache_data.clear()
    st.rerun()

# Connexion simplifiée et plus directe
def get_client():
    creds_dict = st.secrets["gcp_service_account"].to_dict()
    if "private_key" in creds_dict:
        creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    return gspread.authorize(creds)

# Chargement SANS cache pour l'écriture
def get_sheets():
    client = get_client()
    ss = client.open("BiblioClub_Data")
    return ss.worksheet("Livres"), ss.worksheet("Membres")

# Chargement AVEC cache pour l'affichage
@st.cache_data(ttl=30)
def load_data():
    sh_l, sh_m = get_sheets()
    return pd.DataFrame(sh_l.get_all_records()), pd.DataFrame(sh_m.get_all_records())

try:
    df_livres, df_membres = load_data()
except:
    st.error("Erreur de connexion. Rafraîchissez la page.")
    st.stop()

# --- DEFINITIONS ---
COL = {"Titre": "Titre", "Auteur": "Auteur", "Proprio": "Propriétaire", "Avis": "Avis_delire", "Statut": "Statut", "Emprunteur": "Emprunteur", "Note": "Note", "Date": "Date_Ajout", "Avis_Lecteurs": "Avis_Lecteurs", "Cat": "Catégorie"}
LISTE_CATS = ["Roman", "Policier", "BD / Manga", "Cuisine", "Jeunesse", "Développement Perso", "Autre"]

# --- CONNEXION ---
if not st.session_state.connecte:
    st.title("🔐 Accès Méli-Mélo")
    nom_choisi = st.selectbox("Qui êtes-vous ?", sorted(df_membres['Prénom'].unique().tolist()))
    code_saisi = st.text_input("Code Secret", type="password")
    if st.button("Se connecter"):
        info = df_membres[df_membres['Prénom'] == nom_choisi]
        if not info.empty and str(code_saisi).strip() == str(info['Code-Secret'].values[0]).strip():
            st.session_state.connecte = True; st.session_state.user = nom_choisi; st.rerun()
        else: st.error("Code incorrect.")
    st.stop()

utilisateur = st.session_state.user

# HEADER AVEC TON IMAGE
c1, c2 = st.columns([1, 4])
with c1: st.image("https://raw.githubusercontent.com/didierjaccoud144-bit/BiblioClub/main/image_3.png", width=100)
with c2: st.title("La boîte à livres")

c_info, c_refresh, c_logout = st.columns([2, 1, 1])
with c_info: st.write(f"👤 **{utilisateur}**")
with c_refresh: 
    if st.button("🔄"): refresh()
with c_logout:
    if st.button("🚪"): st.session_state.connecte = False; st.rerun()

st.write("---")
onglets = st.tabs(["📖 Bibliothèque", "🤝 Demandes", "👤 Mon Profil", "➕ Ajouter", "⚙️ Gérance", "❓ Aide"])

# --- 1. BIBLIO ---
with onglets[0]:
    rech = st.text_input("🔍 Rechercher...").lower()
    df_f = df_livres.copy()
    if rech:
        df_f = df_f[df_f[COL["Titre"]].astype(str).str.lower().str.contains(rech) | df_f[COL["Auteur"]].astype(str).str.lower().str.contains(rech)]
    for idx, r in df_f.iloc[::-1].iterrows():
        st.markdown(f"**{r[COL['Titre']]}** ({r[COL['Auteur']]})")
        if r[COL['Statut']] == "Libre" and r[COL['Proprio']] != utilisateur:
            if st.button("Demander", key=idx):
                sh_l, _ = get_sheets()
                real_idx = df_livres.index[df_livres[COL['Titre']] == r[COL['Titre']]][0] + 2
                sh_l.update_cell(real_idx, 5, "Demandé"); sh_l.update_cell(real_idx, 6, utilisateur); refresh()
        st.write("---")

# --- 2. DEMANDES ---
with onglets[1]:
    demandes = df_livres[(df_livres[COL["Proprio"]] == utilisateur) & (df_livres[COL["Statut"]] == "Demandé")]
    if not demandes.empty:
        for idx, r in demandes.iterrows():
            st.warning(f"{r[COL['Emprunteur']]} veut '{r[COL['Titre']]}'")
            if st.button("Valider le prêt", key=f"v_{idx}"):
                sh_l, _ = get_sheets()
                real_idx = df_livres.index[df_livres[COL['Titre']] == r[COL['Titre']]][0] + 2
                sh_l.update_cell(real_idx, 5, "Emprunté"); refresh()
    else: st.write("Pas de demandes.")

# --- 3. PROFIL ---
with onglets[2]:
    st.write("### Mes livres prêtés")
    prets = df_livres[(df_livres[COL["Proprio"]] == utilisateur) & (df_livres[COL["Statut"]] != "Libre")]
    for idx, r in prets.iterrows():
        st.write(f"{r[COL['Titre']]} ({r[COL['Emprunteur']]})")
        if st.button("🔄 Rendu", key=f"r_{idx}"):
            sh_l, _ = get_sheets()
            real_idx = df_livres.index[df_livres[COL['Titre']] == r[COL['Titre']]][0] + 2
            sh_l.update_cell(real_idx, 5, "Libre"); sh_l.update_cell(real_idx, 6, ""); refresh()
    
    st.write("---")
    st.write("### Signaler un bug / Suggestion")
    msg = st.text_area("Message")
    if st.button("Envoyer mail"):
        st.link_button("📧 Mail", f"mailto:didier.jaccoud.144@gmail.com?subject=MeliMelo&body={msg}")

# --- 4. AJOUTER (VERSION SIMPLIFIÉE) ---
with onglets[3]:
    st.subheader("➕ Ajouter un livre")
    with st.form("add_form"):
        titre = st.text_input("Titre")
        auteur = st.text_input("Auteur")
        cate = st.selectbox("Catégorie", LISTE_CATS)
        avis = st.text_area("Avis")
        note = st.select_slider("Note", ["📚","📚📚","📚📚📚","📚📚📚📚"])
        btn = st.form_submit_button("Valider l'ajout")
        
    if btn:
        if titre and auteur:
            with st.spinner("Envoi en cours..."):
                sh_l, _ = get_sheets()
                sh_l.append_row([titre, auteur, utilisateur, avis, "Libre", "", note, datetime.now().strftime("%Y-%m-%d"), "", cate])
                st.success("Livre ajouté ! Cliquez sur 'Bibliothèque' pour le voir.")
                st.balloons()
        else:
            st.error("Remplissez le titre et l'auteur.")

# --- 5. GÉRANCE ---
with onglets[4]:
    if utilisateur in ["Didier", "Amélie"]:
        with st.form("new_mem"):
            st.write("Nouveau membre")
            nm = st.text_input("Prénom"); sm = st.text_input("Code")
            if st.form_submit_button("Créer"):
                _, sh_m = get_sheets(); sh_m.append_row([nm, sm, "", "", "", ""]); refresh()
    else: st.write("Accès réservé.")

# --- 6. AIDE ---
with onglets[5]:
    st.write("### Aide détaillée")
    st.write("1. Installez l'appli sur votre écran d'accueil.")
    st.write("2. Connectez-vous avec votre code.")
    st.write("3. Demandez des livres et validez vos prêts dans 'Demandes'.")

st.caption("DJA’WEB x Gemini IA")
