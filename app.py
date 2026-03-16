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
    
    # Lecture des données
    df_membres = pd.DataFrame(sheet_membres.get_all_records())
    df_livres = pd.DataFrame(sheet_livres.get_all_records())
    
    # NETTOYAGE DES COLONNES (supprime espaces et gère les accents)
    df_livres.columns = [c.strip() for c in df_livres.columns]
    df_membres.columns = [c.strip() for c in df_membres.columns]
except Exception as e:
    st.error(f"Erreur de connexion : {e}")
    st.stop()

# --- DÉTECTION INTELLIGENTE DES COLONNES ---
# On cherche les colonnes même si l'orthographe varie un peu
def find_col(df, possible_names):
    for name in possible_names:
        if name in df.columns: return name
    return df.columns[0] # Par défaut la première si rien n'est trouvé

c_titre = find_col(df_livres, ["Titre", "TITRE"])
c_auteur = find_col(df_livres, ["Auteur", "AUTEUR"])
c_proprio = find_col(df_livres, ["Maître", "Maitre", "Propriétaire", "Maitre"])
c_statut = find_col(df_livres, ["Statut", "STATUT"])
c_emprunteur = find_col(df_livres, ["Squatteur", "SQUATTEUR", "Emprunteur"])
c_avis = find_col(df_livres, ["Avis_Delire", "Avis_delire", "Avis"])

col_p = find_col(df_membres, ["Prénom", "Prenom", "Nom"])
liste_membres = df_membres[col_p].tolist()

def envoyer_whatsapp(telephone, message):
    return f"https://wa.me/{str(telephone).replace(' ', '')}?text={urllib.parse.quote(message)}"

# --- INTERFACE ---
st.title("📚 Le Biblio Club")
utilisateur = st.selectbox("👤 Qui êtes-vous ?", liste_membres)
infos_user = df_membres[df_membres[col_p] == utilisateur].iloc[0]

st.write("---")
onglets = st.tabs(["📖 Bibliothèque", "🤝 Emprunts", "👤 Mon Profil", "➕ Ajouter", "📤 Import"])

# --- 1. BIBLIOTHÈQUE ---
with onglets[0]:
    for idx, row in df_livres.iloc[::-1].iterrows():
        raw_s = str(row.get(c_statut, 'Libre')).strip()
        statut = raw_s if raw_s != "" else "Libre"
        color = "green" if statut == "Libre" else "orange" if statut == "Demandé" else "red"
        
        with st.container():
            c1, c2 = st.columns([1, 4])
            with c1: st.title("📕")
            with c2:
                st.markdown(f"### {row[c_titre]} :{color}[ ({statut})]")
                st.write(f"**Auteur :** {row[c_auteur]} | **Proprio :** {row[c_proprio]}")
                
                if row.get(c_avis):
                    st.success(f"💬 **Avis :** \n{row[c_avis]}")
                
                if statut == "Libre" and str(row[c_proprio]) != utilisateur:
                    if st.button(f"Demander ce livre", key=f"req_{idx}"):
                        # On cherche l'index de la colonne Statut (H) et Squatteur (E)
                        idx_statut = list(df_livres.columns).index(c_statut) + 1
                        idx_squat = list(df_livres.columns).index(c_emprunteur) + 1
                        sheet_livres.update_cell(idx + 2, idx_statut, "Demandé")
                        sheet_livres.update_cell(idx + 2, idx_squat, utilisateur)
                        st.success("Demande envoyée !")
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

# --- 3. MON PROFIL ---
with onglets[2]:
    st.subheader(f"Espace de {utilisateur}")
    mes_livres = df_livres[df_livres[c_proprio] == utilisateur]
    if not mes_livres.empty:
        for idx, row in mes_livres.iterrows():
            st.write(f"📙 **{row[c_titre]}**")
            s = str(row.get(c_statut, ''))
            if s == "Demandé":
                dem = row.get(c_emprunteur)
                st.warning(f"🔔 {dem} veut ce livre")
                if st.button(f"✅ Valider prêt pour {dem}", key=f"ok_{idx}"):
                    idx_statut = list(df_livres.columns).index(c_statut) + 1
                    sheet_livres.update_cell(idx + 2, idx_statut, "Emprunté")
                    tel_d = df_membres[df_membres[col_p] == dem].iloc[0].get('Téléphone', '')
                    msg = f"Hello {dem} ! C'est {utilisateur}. Prêt OK pour '{row[c_titre]}' ! Retrait : {infos_user.get('Infos_Retrait', 'Contacte-moi !')}"
                    st.link_button("📱 WhatsApp", envoyer_whatsapp(tel_d, msg))
            elif s == "Emprunté":
                if st.button(f"🔄 Rendu", key=f"back_{idx}"):
                    idx_statut = list(df_livres.columns).index(c_statut) + 1
                    idx_squat = list(df_livres.columns).index(c_emprunteur) + 1
                    sheet_livres.update_cell(idx + 2, idx_statut, "Libre")
                    sheet_livres.update_cell(idx + 2, idx_squat, "")
                    st.rerun()
            st.write("---")

# --- 4 & 5 (AJOUT / IMPORT) ---
with onglets[3]:
    with st.form("add"):
        t, a = st.text_input("Titre"), st.text_input("Auteur")
        note = st.select_slider("Note", options=["📚", "📚📚", "📚📚📚", "📚📚📚📚"])
        com = st.text_area("Avis")
        if st.form_submit_button("Ajouter"):
            sheet_livres.append_row(["", t, a, utilisateur, "", "", f"{note} {com}", "Libre"])
            st.success("Ajouté !"); st.rerun()

with onglets[4]:
    up = st.file_uploader("Excel", type="xlsx")
    if up and st.button("Importer"):
        df_im = pd.read_excel(up)
        for _, r in df_im.iterrows():
            sheet_livres.append_row(["", r['Titre'], r.get('Auteur',''), utilisateur, "", "", r.get('Avis_delire',''), "Libre"])
        st.success("Fait !"); st.rerun()

st.caption("Une création DJA’WEB avec l’aide de Gemini IA")
