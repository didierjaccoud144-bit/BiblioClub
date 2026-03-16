import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="Biblio Club", page_icon="📚", layout="centered")

# --- CONNEXION SÉCURISÉE À GOOGLE SHEETS ---
def get_gspread_client():
    # On récupère le dictionnaire des secrets
    creds_dict = st.secrets["gcp_service_account"].to_dict()
    
    # Nettoyage crucial de la clé privée pour éviter les erreurs PEM
    if "private_key" in creds_dict:
        creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
    
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    return gspread.authorize(creds)

# --- CHARGEMENT DES DONNÉES ---
try:
    client = get_gspread_client()
    # Utilise le nom exact de ton fichier Google Sheet
    spreadsheet = client.open("BiblioClub_Data") 
    sheet_membres = spreadsheet.worksheet("Membres")
    sheet_livres = spreadsheet.worksheet("Livres")

    df_membres = pd.DataFrame(sheet_membres.get_all_records())
    df_livres = pd.DataFrame(sheet_livres.get_all_records())
except Exception as e:
    st.error(#FF4B4B["Erreur de connexion : Vérifiez vos Secrets Streamlit et le nom du fichier Google Sheet."])
    st.stop()

# --- TITRE DE L'APPLICATION ---
st.title("📚 Le Biblio Club")
st.markdown("### Bienvenue dans votre bibliothèque partagée")

# --- MENU DE SÉLECTION DU MEMBRE (VISIBLE SUR MOBILE) ---
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
onglet1, onglet2, onglet3 = st.tabs(["📖 Bibliothèque", "➕ Ajouter un livre", "📤 Import Excel"])

with onglet1:
    st.subheader("Les livres du Club")
    if not df_livres.empty:
        st.dataframe(df_livres, use_container_width=True, hide_index=True)
    else:
        st.write("La bibliothèque est vide pour le moment.")

with onglet2:
    st.subheader("Ajouter une pépite")
    with st.form("ajout_livre", clear_on_submit=True):
        titre = st.text_input("Titre du livre")
        auteur = st.text_input("Auteur")
        avis = st.text_area("Ton avis / Biblio-Score (ex: 📚📚📚)")
        submit = st.form_submit_button("Ajouter au club")
        
        if submit:
            if titre:
                new_row = [titre, auteur, utilisateur, avis]
                sheet_livres.append_row(new_row)
                st.success(f"Bravo {utilisateur}, '{titre}' a été ajouté !")
                st.balloons()
            else:
                st.error("Le titre est obligatoire !")

with onglet3:
    st.subheader("Importation massive")
    st.write("Utilisez un fichier Excel (.xlsx) avec les colonnes : Titre, Auteur, Avis_delire")
    
    uploaded_file = st.file_uploader("Choisir un fichier Excel", type="xlsx")
    if uploaded_file:
        try:
            df_import = pd.read_excel(uploaded_file)
            if st.button("🚀 Confirmer l'import"):
                for _, row in df_import.iterrows():
                    # On ajoute le nom de l'utilisateur actuel pour chaque livre importé
                    sheet_livres.append_row([row['Titre'], row.get('Auteur', ''), utilisateur, row.get('Avis_delire', '')])
                st.success("Importation réussie !")
        except Exception as e:
            st.error(f"Erreur lors de l'import : {e}")

# --- PIED DE PAGE ---
st.write("")
st.write("---")
st.caption("Une création DJA’WEB avec l’aide de Gemini IA")
