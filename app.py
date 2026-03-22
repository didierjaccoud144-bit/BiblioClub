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

# Connexion directe stable
def get_sheets():
    creds_dict = st.secrets["gcp_service_account"].to_dict()
    if "private_key" in creds_dict:
        creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    client = gspread.authorize(creds)
    ss = client.open("BiblioClub_Data")
    return ss.worksheet("Livres"), ss.worksheet("Membres")

@st.cache_data(ttl=60)
def load_data():
    sh_l, sh_m = get_sheets()
    return pd.DataFrame(sh_l.get_all_records()), pd.DataFrame(sh_m.get_all_records())

try:
    df_livres, df_membres = load_data()
except Exception:
    st.error("Connexion interrompue. Cliquez sur Actualiser.")
    st.stop()

# --- DEFINITIONS ---
COL = {
    "Titre": "Titre", "Auteur": "Auteur", "Proprio": "Propriétaire",
    "Avis": "Avis_delire", "Statut": "Statut", "Emprunteur": "Emprunteur",
    "Note": "Note", "Date": "Date_Ajout", "Avis_Lecteurs": "Avis_Lecteurs",
    "Cat": "Catégorie"
}
LISTE_CATS = ["Roman", "Policier", "BD / Manga", "Cuisine", "Jeunesse", "Développement Perso", "Autre"]
LISTE_NOTES = ["❌", "📚", "📚📚", "📚📚📚", "📚📚📚📚"]

def envoyer_whatsapp(message):
    return f"https://api.whatsapp.com/send?text={urllib.parse.quote(message)}"

def generer_lien_mail(sujet, corps):
    dest = "didier.jaccoud.144@gmail.com"
    return f"mailto:{dest}?subject={urllib.parse.quote(sujet)}&body={urllib.parse.quote(corps)}"

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

# HEADER AVEC IMAGE (LIEN CORRIGÉ)
# Note: On utilise le lien "raw" qui est le seul lisible directement par le navigateur
image_url = "https://raw.githubusercontent.com/didierjaccoud144-bit/BiblioClub/main/image_3.png"
st.image(image_url, width=150) # On l'affiche au dessus du titre pour éviter les bugs de colonnes
st.title("La boîte à livres à Méli-Mélo")

c_info, c_refresh, c_logout = st.columns([2, 1, 1])
with c_info: st.write(f"👤 Membre : **{utilisateur}**")
with c_refresh: 
    if st.button("🔄 Actualiser"): refresh()
with c_logout:
    if st.button("🚪 Quitter"): st.session_state.connecte = False; st.rerun()

st.write("---")
nb_demandes = len(df_livres[(df_livres[COL["Proprio"]] == utilisateur) & (df_livres[COL["Statut"]] == "Demandé")])
onglets = st.tabs(["📖 Bibliothèque", f"🤝 Demandes ({nb_demandes})", "👤 Mon Profil", "➕ Ajouter", "⚙️ Gérance", "❓ Mode d'emploi"])

# --- 1. BIBLIOTHÈQUE ---
with onglets[0]:
    rech = st.text_input("🔍 Rechercher...", "").lower()
    df_f = df_livres.copy()
    if rech:
        df_f = df_f[df_f[COL["Titre"]].astype(str).str.lower().str.contains(rech) | 
                    df_f[COL["Auteur"]].astype(str).str.lower().str.contains(rech) |
                    df_f[COL["Cat"]].astype(str).str.lower().str.contains(rech)]
    
    for idx, r in df_f.iloc[::-1].iterrows():
        statut = str(r[COL["Statut"]])
        cat_txt = f" | 🏷️ {r[COL['Cat']]}" if r[COL['Cat']] else ""
        emoji, color = ("📗", "green") if statut == "Libre" else (("⏳", "orange") if statut == "Demandé" else ("📕", "red"))
        
        with st.container():
            st.markdown(f"#### {emoji} {r[COL['Titre']]} {r[COL['Note']]}")
            st.markdown(f"*{r[COL['Auteur']]}*{cat_txt} — Proprio : **{r[COL['Proprio']]}** | :{color}[**({statut})**]")
            col_a, col_b = st.columns([1.5, 3])
            with col_a:
                if statut == "Libre" and r[COL['Proprio']] != utilisateur:
                    if st.button("Demander", key=f"req_{idx}"):
                        sh_l, _ = get_sheets(); real_idx = int(df_livres.index[df_livres[COL['Titre']] == r[COL['Titre']]][0] + 2)
                        sh_l.update_cell(real_idx, 5, "Demandé"); sh_l.update_cell(real_idx, 6, utilisateur); refresh()
                with st.expander("💬 Avis"):
                    n_l = st.select_slider("Note", options=LISTE_NOTES, key=f"n_{idx}")
                    c_l = st.text_area("Retour", key=f"c_{idx}")
                    if st.button("Publier", key=f"p_{idx}"):
                        sh_l, _ = get_sheets(); real_idx = int(df_livres.index[df_livres[COL['Titre']] == r[COL['Titre']]][0] + 2)
                        txt = (str(r[COL["Avis_Lecteurs"]]) + f"\n\n**{utilisateur}** ({n_l}) : {c_l}").strip()
                        sh_l.update_cell(real_idx, 9, txt); refresh()
            with col_b:
                if r[COL['Avis']]: st.caption(f"⭐ **Proprio :** {r[COL['Avis']]}")
                if r[COL['Avis_Lecteurs']]:
                    with st.expander("💬 Avis lecteurs"): st.markdown(r[COL['Avis_Lecteurs']])
            st.markdown("---")

# --- 2. DEMANDES ---
with onglets[1]:
    demandes = df_livres[(df_livres[COL["Proprio"]] == utilisateur) & (df_livres[COL["Statut"]] == "Demandé")]
    if not demandes.empty:
        for idx, r in demandes.iterrows():
            st.info(f"👉 **{r[COL['Emprunteur']]}** attend : **{r[COL['Titre']]}**")
            if st.button("✅ Valider le prêt", key=f"v_{idx}"):
                sh_l, _ = get_sheets(); real_idx = int(df_livres.index[df_livres[COL['Titre']] == r[COL['Titre']]][0] + 2)
                sh_l.update_cell(real_idx, 5, "Emprunté"); refresh()
    else: st.write("Aucune demande.")

# --- 3. PROFIL (AVEC ÉDITION) ---
with onglets[2]:
    st.write(f"## 👤 Profil de {utilisateur}")
    search_prof = st.text_input("🔍 Rechercher dans mon historique...", "").lower()

    st.write("### 📚 Ma collection")
    mes_c = df_livres[df_livres[COL["Proprio"]] == utilisateur]
    if search_prof:
        mes_c = mes_c[mes_c[COL["Titre"]].astype(str).str.lower().str.contains(search_prof) | mes_c[COL["Auteur"]].astype(str).str.lower().str.contains(search_prof)]
    
    for idx, r in mes_c.iterrows():
        with st.expander(f"📙 {r[COL['Titre']]} - {r[COL['Auteur']]}"):
            # FORMULAIRE DE MODIFICATION
            with st.form(f"edit_{idx}"):
                new_t = st.text_input("Titre", value=r[COL['Titre']])
                new_a = st.text_input("Auteur", value=r[COL['Auteur']])
                new_cat = st.selectbox("Catégorie", LISTE_CATS, index=LISTE_CATS.index(r[COL['Cat']]) if r[COL['Cat']] in LISTE_CATS else 0)
                new_note = st.select_slider("Note", options=LISTE_NOTES, value=r[COL['Note']] if r[COL['Note']] in LISTE_NOTES else "❌")
                new_avis = st.text_area("Mon avis", value=r[COL['Avis']])
                
                c_edit, c_del = st.columns(2)
                if c_edit.form_submit_button("💾 Enregistrer les modifications"):
                    sh_l, _ = get_sheets()
                    real_idx = int(df_livres.index[df_livres[COL['Titre']] == r[COL['Titre']]][0] + 2)
                    # Mise à jour des colonnes A, B, D, G, J (Titre, Auteur, Avis_delire, Note, Catégorie)
                    sh_l.update_cell(real_idx, 1, new_t)
                    sh_l.update_cell(real_idx, 2, new_a)
                    sh_l.update_cell(real_idx, 4, new_avis)
                    sh_l.update_cell(real_idx, 7, new_note)
                    sh_l.update_cell(real_idx, 10, new_cat)
                    st.success("Modifications enregistrées !"); refresh()
                
                if c_del.form_submit_button("❌ Supprimer le livre"):
                    sh_l, _ = get_sheets(); real_idx = int(df_livres.index[df_livres[COL['Titre']] == r[COL['Titre']]][0] + 2)
                    sh_l.delete_rows(real_idx); refresh()

# --- 4. AJOUTER ---
with onglets[3]:
    st.subheader("➕ Ajouter un nouveau livre")
    with st.form("add_form", clear_on_submit=True):
        t = st.text_input("Titre"); a = st.text_input("Auteur"); cat = st.selectbox("Catégorie", LISTE_CATS)
        note = st.select_slider("Note de départ", options=LISTE_NOTES, value="❌")
        avis = st.text_area("Mon avis de proprio")
        if st.form_submit_button("Valider"):
            if t and a:
                sh_l, _ = get_sheets(); sh_l.append_row([t, a, utilisateur, avis, "Libre", "", note, datetime.now().strftime("%Y-%m-%d"), "", cat])
                st.success("Ajouté !"); st.balloons()
            else: st.warning("Titre et Auteur requis.")

# --- 5/6 GÉRANCE & AIDE ---
with onglets[4]:
    if utilisateur in ["Didier", "Amélie"]:
        with st.form("new_mem"):
            nm = st.text_input("Prénom"); sm = st.text_input("Code")
            if st.form_submit_button("Créer"):
                _, sh_m = get_sheets(); sh_m.append_row([nm, sm, "", "", "", ""]); refresh()

with onglets[5]:
    st.title("📖 Mode d'emploi Méli-Mélo")
    with st.expander("📱 Installation", expanded=True): st.write("iPhone: Partage -> Écran d'accueil. Android: 3 points -> Installer.")
    with st.expander("🔐 Connexion"): st.write("Utilisez votre prénom et votre code secret.")
    with st.expander("✏️ Modification"): st.write("Allez dans 'Mon Profil', dépliez un livre pour modifier ses informations.")

st.caption("DJA’WEB avec l’aide de Gemini IA")
