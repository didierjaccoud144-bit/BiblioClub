import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import urllib.parse

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="Biblio Club", page_icon="📚", layout="centered")

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

# --- DÉTECTION INTELLIGENTE DES COLONNES (Basé sur ton Excel) ---
# Onglet Membres
col_p = "Prénom" if "Prénom" in df_membres.columns else df_membres.columns[0]
liste_membres = df_membres[col_p].tolist()

# Onglet Livres (Colonnes de ton image)
c_titre = "Titre"
c_auteur = "Auteur"
c_proprio = "Maître"
c_statut = "Statut"
c_emprunteur = "Squatteur"
c_avis = "Avis_Delire"

def envoyer_whatsapp(telephone, message):
    msg_code = urllib.parse.quote(message)
    return f"https://wa.me/{str(telephone).replace(' ', '')}?text={msg_code}"

# --- INTERFACE ---
st.title("📚 Le Biblio Club")
utilisateur = st.selectbox("👤 Qui êtes-vous ?", liste_membres)
infos_user = df_membres[df_membres[col_p] == utilisateur].iloc[0]

st.write("---")
onglets = st.tabs(["📖 Bibliothèque", "🤝 Emprunts", "👤 Mon Profil", "➕ Ajouter", "📤 Import"])

# --- 1. BIBLIOTHÈQUE ---
with onglets[0]:
    for idx, row in df_livres.iloc[::-1].iterrows():
        raw_statut = str(row.get(c_statut, 'Libre')).strip()
        statut = raw_statut if raw_statut != "" else "Libre"
        color = "green" if statut == "Libre" else "orange" if statut == "Demandé" else "red"
        
        with st.container():
            col_img, col_txt = st.columns([1, 4])
            with col_img: st.title("📕")
            with col_txt:
                st.markdown(f"### {row[c_titre]} :{color}[ ({statut})]")
                st.write(f"**Auteur :** {row[c_auteur]} | **Proprio :** {row[c_proprio]}")
                
                if row.get(c_avis):
                    st.success(f"💬 **L'avis de {row[c_proprio]}** :  \n{row[c_avis]}")
                
                # BOUTON DEMANDER (Si libre et pas mon livre)
                if statut == "Libre" and str(row[c_proprio]) != utilisateur:
                    if st.button(f"Demander à {row[c_proprio]}", key=f"req_{idx}"):
                        sheet_livres.update_cell(idx + 2, 8, "Demandé") # Col H = Statut (8)
                        sheet_livres.update_cell(idx + 2, 5, utilisateur) # Col E = Squatteur (5)
                        st.success("Demande enregistrée !")
                        st.rerun()
            st.write("---")

# --- 2. EMPRUNTS ---
with onglets[1]:
    st.subheader("🤝 Livres en mouvement")
    mask = df_livres[c_statut].isin(['Demandé', 'Emprunté'])
    if not df_livres[mask].empty:
        st.dataframe(df_livres[mask][[c_titre, c_proprio, c_emprunteur, c_statut]], hide_index=True)
    else:
        st.info("Tous les livres sont chez leurs maîtres !")

# --- 3. MON PROFIL (Gestion des demandes reçues) ---
with onglets[2]:
    st.subheader(f"Espace de {utilisateur}")
    mes_livres = df_livres[df_livres[c_proprio] == utilisateur]
    
    if not mes_livres.empty:
        for idx, row in mes_livres.iterrows():
            st.write(f"📙 **{row[c_titre]}**")
            s = str(row.get(c_statut, ''))
            
            if s == "Demandé":
                demandeur = row.get(c_emprunteur)
                st.warning(f"🔔 {demandeur} veut ce livre")
                if st.button(f"✅ Valider prêt pour {demandeur}", key=f"ok_{idx}"):
                    sheet_livres.update_cell(idx + 2, 8, "Emprunté")
                    tel_d = df_membres[df_membres[col_p] == demandeur].iloc[0].get('Téléphone', '')
                    msg = f"Hello {demandeur} ! C'est {utilisateur}. Ton prêt pour '{row[c_titre]}' est validé ! Retrait : {infos_user.get('Infos_Retrait', 'Contacte-moi !')}"
                    st.link_button("📱 WhatsApp de confirmation", envoyer_whatsapp(tel_d, msg))
            elif s == "Emprunté":
                if st.button(f"🔄 Marquer comme rendu", key=f"back_{idx}"):
                    sheet_livres.update_cell(idx + 2, 8, "Libre")
                    sheet_livres.update_cell(idx + 2, 5, "")
                    st.rerun()
            st.write("---")

# --- 4. AJOUTER ---
with onglets[3]:
    with st.form("form_add"):
        t = st.text_input("Titre")
        a = st.text_input("Auteur")
        note = st.select_slider("Note", options=["📚", "📚📚", "📚📚📚", "📚📚📚📚"])
        com = st.text_area("Avis")
        if st.form_submit_button("Ajouter au club"):
            sheet_livres.append_row(["", t, a, utilisateur, "", "", f"{note} {com}", "Libre"])
            st.success("Livre ajouté !"); st.rerun()

# --- 5. IMPORT ---
with onglets[4]:
    up = st.file_uploader("Fichier Excel", type="xlsx")
    if up and st.button("Lancer l'import"):
        df_im = pd.read_excel(up)
        for _, r in df_im.iterrows():
            sheet_livres.append_row(["", r['Titre'], r.get('Auteur',''), utilisateur, "", "", r.get('Avis_delire',''), "Libre"])
        st.success("Import réussi !"); st.rerun()

st.write("---")
st.caption("Une création DJA’WEB avec l’aide de Gemini IA")
