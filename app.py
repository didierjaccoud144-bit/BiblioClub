import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import urllib.parse
from datetime import datetime, timedelta

# Importation du fichier de profil membres
from membres_profil import get_membre_info, get_liste_membres_fixes

# --- CONFIGURATION ---
st.set_page_config(page_title="Biblio Club", page_icon="📚", layout="centered")

def get_gspread_client():
    creds_dict = st.secrets["gcp_service_account"].to_dict()
    if "private_key" in creds_dict:
        creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    return gspread.authorize(creds)

# --- CHARGEMENT ---
try:
    client = get_gspread_client()
    spreadsheet = client.open("BiblioClub_Data") 
    sheet_livres = spreadsheet.worksheet("Livres")
    df_livres = pd.DataFrame(sheet_livres.get_all_records())
except Exception as e:
    st.error(f"Erreur de lecture : {e}")
    st.stop()

# --- CONSTANTES COLONNES ---
COL = {
    "Titre": "Titre", "Auteur": "Auteur", "Proprio": "Propriétaire",
    "Avis": "Avis_delire", "Statut": "Statut", "Emprunteur": "Emprunteur",
    "Note": "Note", "Date": "Date_Ajout"
}

def envoyer_whatsapp(telephone, message):
    if not telephone: return "#"
    return f"https://wa.me/{str(telephone).replace(' ', '')}?text={urllib.parse.quote(message)}"

def show_avatar(url, size=40):
    if url:
        st.markdown(f'<img src="{url}" style="width:{size}px; height:{size}px; border-radius:50%; margin-right:10px; object-fit: cover;">', unsafe_allow_html=True)

# --- INTERFACE ---
st.title("📚 Le Biblio Club")

liste_membres = get_liste_membres_fixes()
col_u1, col_u2 = st.columns([1, 4])
with col_u1:
    prenom_user = st.session_state.get('user', liste_membres[0])
    infos_user = get_membre_info(prenom_user)
    show_avatar(infos_user.get('Avatar',''), size=55)
with col_u2:
    utilisateur = st.selectbox("", liste_membres, key='user', label_visibility="collapsed")
    infos_user = get_membre_info(utilisateur)

st.write("---")
onglets = st.tabs(["📖 Bibliothèque", "🤝 Emprunts", "👤 Mon Profil", "➕ Ajouter"])

# --- 1. BIBLIOTHÈQUE ---
with onglets[0]:
    st.markdown("### 🔍 Trier par")
    tri = st.selectbox("", ["Derniers ajouts", "Note", "Titre (A-Z)", "Auteur", "Propriétaire"], label_visibility="collapsed")
    
    # Préparation du dataframe trié
    df_tri = df_livres.copy()
    if tri == "Titre (A-Z)": df_tri = df_tri.sort_values(by=COL["Titre"])
    elif tri == "Auteur": df_tri = df_tri.sort_values(by=COL["Auteur"])
    elif tri == "Propriétaire": df_tri = df_tri.sort_values(by=COL["Proprio"])
    elif tri == "Note": df_tri = df_tri.sort_values(by=COL["Note"], ascending=False)
    else: df_tri = df_tri.iloc[::-1]

    for idx, row in df_tri.iterrows():
        statut = str(row.get(COL["Statut"], 'Libre')).strip() or "Libre"
        
        # --- CORRECTION VISUELLE : Choix de l'emoji livre ---
        if statut == "Libre":
            emoji_livre = "📗" # Vert pour Libre
            color = "green"
        elif statut == "Demandé":
            emoji_livre = "📙" # Orange pour Demandé
            color = "orange"
        else: # Emprunté
            emoji_livre = "📕" # Rouge pour En prêt
            color = "red"
        
        # Badge Nouveauté (7 jours)
        badge_new = ""
        try:
            date_l = datetime.strptime(str(row[COL["Date"]]), "%Y-%m-%d")
            if datetime.now() - date_l < timedelta(days=7):
                badge_new = "🆕 "
        except: pass

        with st.container():
            c1, c2 = st.columns([1, 4])
            with c1: st.title(emoji_livre) # Affichage du livre de la bonne couleur
            with c2:
                # Titre + Note + Statut à côté
                st.markdown(f"### {badge_new}{row[COL['Titre']]} {row.get(COL['Note'], '')} :{color}[ ({statut})]")
                st.write(f"**{row[COL['Auteur']]}** | **Propriétaire :** {row[COL['Proprio']]}")
                if row.get(COL['Avis']):
                    st.success(f"💬 {row[COL['Avis']]}")
                
                # --- CORRECTION SÉCURITÉ : Bouton "Demander" ---
                # Il n'apparaît QUE si Libre ET si le propriétaire n'est PAS moi
                if statut == "Libre" and str(row[COL['Proprio']]) != utilisateur:
                    if st.button(f"Demander ce livre", key=f"req_{idx}"):
                        original_idx = df_livres.index[df_livres[COL['Titre']] == row[COL['Titre']]][0] + 2
                        sheet_livres.update_cell(original_idx, 5, "Demandé")
                        sheet_livres.update_cell(original_idx, 6, utilisateur)
                        st.rerun()
            st.write("---")

# --- LE RESTE DU CODE (EMPRUNTS / PROFIL / AJOUT) ---
# ... Identique à la version stable précédente, utilisant COL["Proprio"]
