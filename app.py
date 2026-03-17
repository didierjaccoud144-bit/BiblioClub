import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import urllib.parse

# Importation du fichier de profil membres
from membres_profil import get_membre_info, get_liste_membres_fixes, AVATARS_LIST

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
    sheet_livres = spreadsheet.worksheet("Livres")
    df_livres = pd.DataFrame(sheet_livres.get_all_records())
except Exception as e:
    st.error(f"Erreur de connexion : {e}")
    st.stop()

# --- DÉTECTION INTELLIGENTE DES COLONNES ---
cols = df_livres.columns.tolist()
col_m = next((c for c in cols if "membre" in c.lower() or "proprio" in c.lower()), "Membre")
col_e = next((c for c in cols if "emprunt" in c.lower() and "statut" not in c.lower()), "Emprunteur")
col_s = next((c for c in cols if "statut" in c.lower()), "Statut")

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
onglets = st.tabs(["📖 Bibliothèque", "🤝 Emprunts", "👤 Mon Profil", "➕ Ajouter", "📤 Import"])

# --- 1. BIBLIOTHÈQUE ---
with onglets[0]:
    for idx, row in df_livres.iloc[::-1].iterrows():
        statut = str(row.get(col_s, 'Libre')).strip() or "Libre"
        color = "green" if statut == "Libre" else "orange" if statut == "Demandé" else "red"
        
        with st.container():
            c1, c2 = st.columns([1, 4])
            with c1: st.title("📕")
            with c2:
                st.markdown(f"### {row['Titre']} :{color}[ ({statut})]")
                st.write(f"**Auteur :** {row.get('Auteur')} | **Proprio :** {row.get(col_m)}")
                if row.get('Avis_delire'):
                    st.success(f"💬 {row['Avis_delire']}")
                
                if statut == "Libre" and str(row.get(col_m)) != utilisateur:
                    if st.button(f"Demander ce livre", key=f"bib_req_{idx}"):
                        sheet_livres.update_cell(idx + 2, cols.index(col_s)+1, "Demandé")
                        sheet_livres.update_cell(idx + 2, cols.index(col_e)+1, utilisateur)
                        st.success("Demande envoyée ! Go dans 'Emprunts'.")
                        st.rerun()
            st.write("---")

# --- 2. EMPRUNTS ---
with onglets[1]:
    st.subheader("🤝 Gestion des flux")
    
    st.markdown("#### 📥 Mes demandes faites")
    mes_emprunts = df_livres[df_livres[col_e] == utilisateur]
    if not mes_emprunts.empty:
        for idx, row in mes_emprunts.iterrows():
            st.info(f"📖 **{row['Titre']}** chez **{row[col_m]}** ({row[col_s]})")
    else:
        st.write("Aucune demande en cours.")

    st.write("---")
    
    st.markdown("#### 📤 Demandes sur mes livres")
    mes_livres_mouv = df_livres[(df_livres[col_m] == utilisateur) & (df_livres[col_s].isin(['Demandé', 'Emprunté']))]
    if not mes_livres_mouv.empty:
        for idx, row in mes_livres_mouv.iterrows():
            emprunteur_actuel = row.get(col_e)
            st.warning(f"🔔 **{emprunteur_actuel}** -> **{row['Titre']}**")
            
            if row[col_s] == "Demandé":
                if st.button(f"✅ Valider prêt pour {emprunteur_actuel}", key=f"emp_ok_{idx}"):
                    sheet_livres.update_cell(idx + 2, cols.index(col_s)+1, "Emprunté")
                    info_d = get_membre_info(emprunteur_actuel)
                    msg = f"Hello {emprunteur_actuel} ! Ok pour '{row['Titre']}'. Retrait : {infos_user.get('Infos_Retrait')}"
                    st.link_button("📱 WhatsApp", envoyer_whatsapp(info_d.get('Téléphone',''), msg))
            elif row[col_s] == "Emprunté":
                if st.button(f"🔄 Marquer comme rendu", key=f"emp_back_{idx}"):
                    sheet_livres.update_cell(idx + 2, cols.index(col_s)+1, "Libre")
                    sheet_livres.update_cell(idx + 2, cols.index(col_e)+1, "")
                    st.rerun()
    else:
        st.write("Rien à signaler pour vos livres.")

# --- 3. MON PROFIL ---
with onglets[2]:
    st.subheader(f"👤 Profil de {utilisateur}")
    c_p1, c_p2 = st.columns([1, 3])
    with c_p1: show_avatar(infos_user.get('Avatar',''), size=80)
    with c_p2:
        st.markdown(f"**📍 Position :** {infos_user.get('Position', 'Non renseignée')}")
        st.markdown(f"**🏠 Retrait :** {infos_user.get('Infos_Retrait', 'Non renseignées')}")
    
    st.write("---")
    st.subheader("📚 Ma collection")
    mes_propres_livres = df_livres[df_livres[col_m] == utilisateur]
    for idx, row in mes_propres_livres.iterrows():
        with st.expander(f"📙 {row['Titre']}"):
            if st.button(f"🗑️ Supprimer", key=f"prof_del_{idx}"):
                sheet_livres.delete_rows(idx + 2)
                st.rerun()

# --- 4. AJOUTER ---
with onglets[3]:
    with st.form("add_vfinal"):
        t, a = st.text_input("Titre"), st.text_input("Auteur")
        note = st.select_slider("Note", options=["📚", "📚📚", "📚📚📚", "📚📚📚📚"])
        com = st.text_area("Avis")
        if st.form_submit_button("Partager"):
            sheet_livres.append_row([t, a, utilisateur, f"{note} {com}", "Libre", ""])
            st.success("C'est en ligne !"); st.rerun()

# --- 5. IMPORT ---
with onglets[4]:
    up = st.file_uploader("Fichier Excel", type="xlsx")
    if up and st.button("Lancer l'import"):
        df_im = pd.read_excel(up)
        for _, r in df_im.iterrows():
            sheet_livres.append_row([r['Titre'], r.get('Auteur',''), utilisateur, r.get('Avis_delire',''), "Libre", ""])
        st.success("Import réussi !"); st.rerun()

st.caption("Une création DJA’WEB avec l’aide de Gemini IA")
