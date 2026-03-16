import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="Biblio Club", page_icon="📚", layout="centered")

# --- CONNEXION SÉCURISÉE À GOOGLE SHEETS ---
def get_gspread_client():
    # Utilisation des Secrets Streamlit (configurés dans le dashboard)
    creds_dict = st.secrets["gcp_service_account"]
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    return gspread.authorize(creds)

# --- CHARGEMENT DES DONNÉES ---
client = get_gspread_client()
# Remplace par le NOM exact de ton fichier Google Sheet si nécessaire
spreadsheet = client.open("BiblioClub_Data") 
sheet_membres = spreadsheet.worksheet("Membres")
sheet_livres = spreadsheet.worksheet("Livres")

# Conversion en DataFrame Pandas
df_membres = pd.DataFrame(sheet_membres.get_all_records())
df_livres = pd.DataFrame(sheet_livres.get_all_records())

# --- TITRE DE L'APPLICATION ---
st.title("📚 Le Biblio Club")
st.markdown("### Bienvenue dans votre bibliothèque partagée")

# --- NOUVEAU MENU : SÉLECTION DU MEMBRE (VISIBLE SUR MOBILE) ---
# On place le menu ici pour qu'il soit immédiatement visible sans ouvrir le menu latéral
st.write("---")
liste_membres = df_membres['Nom'].tolist()

col1, col2 = st.columns([1, 2])
with col1:
    st.markdown("#### 👤 Membre :")
with col2:
    utilisateur = st.selectbox("Qui suis-je ?", liste_membres, label_visibility="collapsed")

st.info(f"Ravi de vous voir, **{utilisateur}** ! 👋")
st.write("---")

# --- NAVIGATION PAR ONGLETS ---
# Pour smartphone, les onglets sont plus simples à manipuler que la barre latérale
onglet1, onglet2, onglet3 = st.tabs(["📖 Bibliothèque", "➕ Ajouter un livre", "📤 Import Excel"])

with onglet1:
    st.subheader("Les livres du Club")
    # Affichage des livres filtrés ou non
    st.dataframe(df_livres, use_container_width=True)

with onglet2:
    st.subheader("Ajouter une pépite")
    with st.form("ajout_livre"):
        titre = st.text_input("Titre du livre")
        auteur = st.text_input("Auteur")
        avis = st.text_area("Ton avis (Biblio-Score)")
        submit = st.form_submit_button("Ajouter au club")
        
        if submit:
            if titre:
                new_row = [titre, auteur, utilisateur, avis]
                sheet_livres.append_row(new_row)
                st.success(f"Bravo {utilisateur}, '{titre}' est ajouté !")
            else:
                st.error("Le titre est obligatoire !")

with onglet3:
    st.subheader("Importation massive")
    st.write("Utilisez le modèle Excel pour ajouter plusieurs livres d'un coup.")
    # Ici tu peux ajouter ton code pour l'import Excel que nous avons vu
    uploaded_file = st.file_uploader("Choisir un fichier Excel", type="xlsx")
    if uploaded_file:
        st.info("Traitement du fichier en cours...")
        # Logique d'import ici

# --- PIED DE PAGE ---
st.write("")
st.write("---")
st.caption("Une création DJA’WEB avec l’aide de Gemini IA")
