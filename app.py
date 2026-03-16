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
    df_livres.columns = [c.strip() for c in df_livres.columns]
    df_membres.columns = [c.strip() for c in df_membres.columns]
except Exception as e:
    st.error(f"Erreur de connexion : {e}")
    st.stop()

# --- CONFIG COLONNES ---
col_p = "Prénom" if "Prénom" in df_membres.columns else df_membres.columns[0]
c_titre = "Titre"
c_auteur = "Auteur"
c_proprio = "Maître" if "Maître" in df_livres.columns else "Maitre"
c_statut = "Statut"
c_squat = "Squatteur"

def envoyer_wa(tel, msg):
    return f"https://wa.me/{str(tel).replace(' ', '')}?text={urllib.parse.quote(msg)}"

# --- INTERFACE ---
st.title("📚 Le Biblio Club")
utilisateur = st.selectbox("👤 Qui êtes-vous ?", df_membres[col_p].tolist())
infos_user = df_membres[df_membres[col_p] == utilisateur].iloc[0]

st.write("---")

# --- NAVIGATION (Onglet Admin conditionnel) ---
menu = ["📖 Bibliothèque", "🤝 Emprunts", "👤 Mon Profil", "➕ Ajouter", "📤 Import"]
if utilisateur in ["Didier", "Amélie"]:
    menu.append("⚙️ Admin")

onglets = st.tabs(menu)

# --- 1. BIBLIOTHÈQUE (Icônes dynamiques) ---
with onglets[0]:
    for idx, row in df_livres.iloc[::-1].iterrows():
        s = str(row.get(c_statut, 'Libre')).strip()
        statut = s if s != "" else "Libre"
        
        # Logique des couleurs et icônes
        if statut == "Libre":
            icone, color = "📗", "green"
        elif statut == "Demandé":
            icone, color = "📙", "orange"
        else: # Emprunté
            icone, color = "📕", "red"
        
        with st.container():
            c1, c2 = st.columns([1, 4])
            with c1: st.title(icone)
            with c2:
                st.markdown(f"### {row[c_titre]} :{color}[ ({statut})]")
                st.write(f"**Auteur :** {row[c_auteur]} | **Proprio :** {row[c_proprio]}")
                if row.get('Avis_Delire'): st.success(f"💬 {row['Avis_Delire']}")
                
                if statut == "Libre" and str(row[c_proprio]).strip() != utilisateur.strip():
                    if st.button(f"Demander ce livre", key=f"req_{idx}"):
                        sheet_livres.update_cell(idx + 2, list(df_livres.columns).index(c_statut)+1, "Demandé")
                        sheet_livres.update_cell(idx + 2, list(df_livres.columns).index(c_squat)+1, utilisateur)
                        st.success("Demande envoyée !"); st.rerun()
            st.write("---")

# --- 2. EMPRUNTS ---
with onglets[1]:
    mask = df_livres[c_statut].isin(['Demandé', 'Emprunté'])
    if not df_livres[mask].empty:
        st.table(df_livres[mask][[c_titre, c_proprio, c_squat, c_statut]])
    else: st.info("Rien en mouvement.")

# --- 3. MON PROFIL ---
with onglets[2]:
    st.subheader(f"Espace de {utilisateur}")
    mes_livres = df_livres[df_livres[c_proprio].astype(str).str.strip() == utilisateur.strip()]
    if not mes_livres.empty:
        for idx, row in mes_livres.iterrows():
            st.markdown(f"**{row[c_titre]}**")
            s = str(row.get(c_statut, '')).strip()
            if s == "Demandé":
                dem = row.get(c_squat)
                st.warning(f"🔔 {dem} attend ta réponse")
                col_a, col_r = st.columns(2)
                with col_a:
                    if st.button(f"✅ Valider {dem}", key=f"ok_{idx}"):
                        sheet_livres.update_cell(idx + 2, list(df_livres.columns).index(c_statut)+1, "Emprunté")
                        tel_d = df_membres[df_membres[col_p] == dem].iloc[0].get('Téléphone', '')
                        msg = f"Hello {dem} ! C'est {utilisateur}. Prêt OK pour '{row[c_titre]}' ! Retrait : {infos_user.get('Coordonnees', 'Contacte-moi !')}"
                        st.link_button("📱 WhatsApp", envoyer_wa(tel_d, msg))
                with col_r:
                    if st.button(f"❌ Refuser", key=f"no_{idx}"):
                        sheet_livres.update_cell(idx + 2, list(df_livres.columns).index(c_statut)+1, "Libre")
                        sheet_livres.update_cell(idx + 2, list(df_livres.columns).index(c_squat)+1, "")
                        st.rerun()
            elif s == "Emprunté":
                if st.button(f"🔄 Rendu", key=f"end_{idx}"):
                    sheet_livres.update_cell(idx + 2, list(df_livres.columns).index(c_statut)+1, "Libre")
                    sheet_livres.update_cell(idx + 2, list(df_livres.columns).index(c_squat)+1, "")
                    st.rerun()
            st.write("---")

# --- 4 & 5 (AJOUT/IMPORT) ---
with onglets[3]:
    with st.form("add"):
        t, a = st.text_input("Titre"), st.text_input("Auteur")
        n = st.select_slider("Note", options=["📚","📚📚","📚📚📚","📚📚📚📚"])
        if st.form_submit_button("Ajouter"):
            sheet_livres.append_row(["", t, a, utilisateur, "", "", n, "Libre"])
            st.rerun()

with onglets[4]:
    up = st.file_uploader("Excel", type="xlsx")
    if up and st.button("Importer"):
        df_im = pd.read_excel(up)
        for _, r in df_im.iterrows():
            sheet_livres.append_row(["", r['Titre'], r.get('Auteur',''), utilisateur, "", "", "", "Libre"])
        st.success("Fait !"); st.rerun()

# --- 6. ONGLET ADMIN (Didier & Amélie uniquement) ---
if utilisateur in ["Didier", "Amélie"]:
    with onglets[5]:
        st.subheader("⚙️ Gestion des membres")
        with st.form("add_member"):
            new_p = st.text_input("Prénom du nouveau membre")
            new_t = st.text_input("Téléphone (ex: 41791234567)")
            new_c = st.text_area("Coordonnées / Infos retrait")
            if st.form_submit_button("Créer le membre"):
                if new_p and new_t:
                    sheet_membres.append_row([new_p, new_t, new_c])
                    st.success(f"Bienvenue à {new_p} dans le club !")
                    st.rerun()
                else:
                    st.error("Le prénom et le téléphone sont obligatoires.")

st.write("---")
st.caption("Une création DJA’WEB avec l’aide de Gemini IA")
