import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="Biblio Club", page_icon="📚", layout="centered")

# --- CONNEXION SÉCURISÉE À GOOGLE SHEETS ---
def get_gspread_client():
    creds_dict = st.secrets["gcp_service_account"].to_dict()
    if "private_key" in creds_dict:
        creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
    
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    return gspread.authorize(creds)

# --- CHARGEMENT DES DONNÉES ---
try:
    client = get_gspread_client()
    spreadsheet = client.open("BiblioClub_Data") 
    sheet_membres = spreadsheet.worksheet("Membres")
    sheet_livres = spreadsheet.worksheet("Livres")

    df_membres = pd.DataFrame(sheet_membres.get_all_records())
    df_livres = pd.DataFrame(sheet_livres.get_all_records())
except Exception as e:
    st.error(f"Erreur de connexion : {e}")
    st.stop()

# --- TITRE DE L'APPLICATION ---
st.title("📚 Le Biblio Club")
st.markdown("##### Votre bibliothèque partagée par DJA’WEB")

# --- MENU DE SÉLECTION DU MEMBRE ---
st.write("---")
if 'Prénom' in df_membres.columns:
    liste_membres = df_membres['Prénom'].tolist()
elif 'Nom' in df_membres.columns:
    liste_membres = df_membres['Nom'].tolist()
else:
    st.error("Colonne 'Prénom' ou 'Nom' introuvable dans le Sheet.")
    st.stop()

col1, col2 = st.columns([1, 2])
with col1:
    st.markdown("#### 👤 Membre :")
with col2:
    utilisateur = st.selectbox("Qui suis-je ?", liste_membres, label_visibility="collapsed")

st.info(f"Ravi de vous voir, **{utilisateur}** ! 👋")
st.write("---")

# --- NAVIGATION PAR ONGLETS ---
onglet1, onglet2, onglet3 = st.tabs(["📖 Bibliothèque", "➕ Ajouter", "📤 Import"])

with onglet1:
    st.subheader("📖 Les pépites du Club")
    
    if not df_livres.empty:
        # Inverser l'ordre pour voir les derniers ajouts en haut
        for index, row in df_livres.iloc[::-1].iterrows():
            with st.container():
                c1, c2 = st.columns([1, 5])
                with c1:
                    st.write("") # Petit espacement
                    st.title("📕")
                with c2:
                    st.markdown(f"### {row['Titre']}")
                    st.markdown(f"**Auteur :** {row.get('Auteur', 'Inconnu')}")
                    
                    # Design de l'avis
                    avis_texte = row.get('Avis_delire')
                    if avis_texte:
                        st.success(f"💬 **L'avis de {row.get('Membre', 'un membre')}** :  \n{avis_texte}")
                    
                    st.caption(f"Ajouté par {row.get('Membre', 'le club')}")
                st.write("---")
    else:
        st.info("La bibliothèque est vide. Soyez le premier à ajouter un livre !")

with onglet2:
    st.subheader("➕ Ajouter un nouveau livre")
    with st.form("ajout_livre", clear_on_submit=True):
        t = st.text_input("Titre du livre")
        a = st.text_input("Auteur")
        av = st.text_area("Ton avis et ton Biblio-Score (ex: 📚📚📚)")
        submit = st.form_submit_button("Partager avec le club")
        
        if submit:
            if t:
                # IMPORTANT : L'ordre ici doit correspondre aux colonnes de ton Sheet Livres
                # [Titre, Auteur, Membre, Avis_delire]
                sheet_livres.append_row([t, a, utilisateur, av])
                st.success(f"Parfait ! '{t}' a rejoint la collection.")
                st.balloons()
            else:
                st.error("Le titre est indispensable !")

with onglet3:
    st.subheader("📤 Importation groupée")
    st.write("Envoyez un fichier Excel avec les colonnes : **Titre**, **Auteur**, **Avis_delire**")
    
    uploaded_file = st.file_uploader("Fichier Excel", type="xlsx")
    if uploaded_file:
        try:
            df_import = pd.read_excel(uploaded_file)
            if st.button("🚀 Lancer l'importation"):
                for _, row in df_import.iterrows():
                    sheet_livres.append_row([
                        str(row.get('Titre', 'Sans titre')), 
                        str(row.get('Auteur', '')), 
                        utilisateur, 
                        str(row.get('Avis_delire', ''))
                    ])
                st.success("Import terminé ! Allez voir l'onglet Bibliothèque.")
        except Exception as e:
            st.error(f"Erreur : {e}")

# --- PIED DE PAGE ---
st.write("")
st.write("---")
st.caption("Une création DJA’WEB avec l’aide de Gemini IA")
