import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import urllib.parse

# --- CONFIGURATION ---
st.set_page_config(page_title="Biblio Club", page_icon="📚", layout="centered")

def get_gspread_client():
    creds_dict = st.secrets["gcp_service_account"].to_dict()
    if "private_key" in creds_dict:
        creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    return gspread.authorize(creds)

# --- CHARGEMENT ---
try:
    client = get_gspread_client()
    spreadsheet = client.open("BiblioClub_Data") 
    sheet_membres = spreadsheet.worksheet("Membres")
    sheet_livres = spreadsheet.worksheet("Livres")
    df_membres = pd.DataFrame(sheet_membres.get_all_records())
    df_livres = pd.DataFrame(sheet_livres.get_all_records())
except Exception as e:
    st.error(f"Erreur de lecture : {e}")
    st.stop()

# --- DÉTECTION DES COLONNES (POUR ÉVITER LES KEYERROR) ---
col_membre = "Membre" if "Membre" in df_livres.columns else df_livres.columns[2] # Par défaut la 3ème colonne
col_prenom = "Prénom" if "Prénom" in df_membres.columns else df_membres.columns[0]

# --- FONCTION WHATSAPP ---
def envoyer_whatsapp(telephone, message):
    msg_code = urllib.parse.quote(message)
    return f"https://wa.me/{str(telephone).replace(' ', '')}?text={msg_code}"

# --- TITRE ---
st.title("📚 Le Biblio Club")
st.write("---")

# --- SÉLECTION UTILISATEUR ---
liste_membres = df_membres[col_prenom].tolist()
utilisateur = st.selectbox("👤 Qui êtes-vous ?", liste_membres)
infos_user = df_membres[df_membres[col_prenom] == utilisateur].iloc[0]

st.write("---")

# --- NAVIGATION ---
onglets = st.tabs(["📖 Bibliothèque", "🤝 Emprunts", "👤 Mon Profil", "➕ Ajouter", "📤 Import"])

# --- 1. BIBLIOTHÈQUE ---
with onglets[0]:
    st.subheader("Les pépites du Club")
    if not df_livres.empty:
        for idx, row in df_livres.iloc[::-1].iterrows():
            statut = str(row.get('Statut', 'Libre'))
            color = "green" if statut == "Libre" else "orange" if statut == "Demandé" else "red"
            
            with st.container():
                c1, c2 = st.columns([1, 4])
                with c1: st.title("📕")
                with c2:
                    st.markdown(f"### {row['Titre']} :{color}[ ({statut})]")
                    st.write(f"**Auteur :** {row.get('Auteur')} | **Proprio :** {row.get(col_membre)}")
                    
                    if row.get('Avis_delire'):
                        st.success(f"💬 **L'avis de {row.get(col_membre)}** :  \n{row['Avis_delire']}")
                    
                    if statut == "Libre" and row.get(col_membre) != utilisateur:
                        tel_p = df_membres[df_membres[col_prenom] == row.get(col_membre)].iloc[0].get('Téléphone', '')
                        txt = f"Salut {row.get(col_membre)}, c'est {utilisateur} ! Je serais intéressé par ton livre '{row['Titre']}' sur le Biblio Club. Est-il dispo ? 😊"
                        st.link_button(f"Demander à {row.get(col_membre)}", envoyer_whatsapp(tel_p, txt))
                st.write("---")

# --- 2. EMPRUNTS ---
with onglets[1]:
    st.subheader("🤝 Livres en mouvement")
    mask = df_livres['Statut'].isin(['Demandé', 'Emprunté'])
    if not df_livres[mask].empty:
        st.dataframe(df_livres[mask][['Titre', col_membre, 'Emprunteur', 'Statut']], hide_index=True)
    else:
        st.info("Tout est en rayon !")

# --- 3. MON PROFIL & RÉPONSES ---
with onglets[2]:
    st.subheader(f"Mon espace ({utilisateur})")
    mes_livres = df_livres[df_livres[col_membre] == utilisateur]
    
    if not mes_livres.empty:
        for idx, row in mes_livres.iterrows():
            st.write(f"📙 **{row['Titre']}**")
            if row.get('Statut') == "Demandé":
                demandeur = row.get('Emprunteur')
                st.warning(f"⚠️ {demandeur} veut ce livre !")
                tel_d = df_membres[df_membres[col_prenom] == demandeur].iloc[0].get('Téléphone', '')
                msg_ok = f"Hello {demandeur} ! C'est {utilisateur}. Ton prêt pour '{row['Titre']}' est OK ! On se voit pour le retrait : {infos_user.get('Infos_Retrait', 'Contacte-moi !')}"
                st.link_button(f"✅ Valider pour {demandeur}", envoyer_whatsapp(tel_d, msg_ok))
            st.write("---")

# --- 4. AJOUTER (AVEC SYSTÈME DE NOTES) ---
with onglets[3]:
    st.subheader("Ajouter un livre")
    with st.form("add_v3", clear_on_submit=True):
        t = st.text_input("Titre")
        a = st.text_input("Auteur")
        note = st.select_slider("Ma note (Biblio-Score)", options=["📚", "📚📚", "📚📚📚", "📚📚📚📚"])
        com = st.text_area("Mon commentaire")
        if st.form_submit_button("Partager"):
            avis_final = f"{note} {com}"
            sheet_livres.append_row([t, a, utilisateur, avis_final, "Libre", ""])
            st.success("C'est en ligne !"); st.balloons()

# --- 5. IMPORT ---
with onglets[4]:
    up = st.file_uploader("Excel", type="xlsx")
    if up and st.button("Importer"):
        df_im = pd.read_excel(up)
        for _, r in df_im.iterrows():
            sheet_livres.append_row([r['Titre'], r.get('Auteur',''), utilisateur, r.get('Avis_delire',''), "Libre", ""])
        st.success("Fait !")

st.write("---")
st.caption("Une création DJA’WEB avec l’aide de Gemini IA")
