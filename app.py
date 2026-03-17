import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import urllib.parse
from datetime import datetime, timedelta

# Importation du fichier de profil membres
from membres_profil import get_membre_info, get_liste_membres_fixes

# --- CONFIGURATION ---
st.set_page_config(page_title="Méli-Mélo", page_icon="📚", layout="centered")

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
    sheet_membres = spreadsheet.worksheet("Membres") # Pour l'ajout de membres
    df_livres = pd.DataFrame(sheet_livres.get_all_records())
except Exception as e:
    st.error(f"Erreur de connexion : {e}")
    st.stop()

# --- CONSTANTES ---
COL = {
    "Titre": "Titre", "Auteur": "Auteur", "Proprio": "Propriétaire",
    "Avis": "Avis_delire", "Statut": "Statut", "Emprunteur": "Emprunteur",
    "Note": "Note", "Date": "Date_Ajout"
}

def envoyer_whatsapp(telephone, message):
    if not telephone: return "#"
    return f"https://wa.me/{str(telephone).replace(' ', '')}?text={urllib.parse.quote(message)}"

def show_avatar(url, size=55):
    if url and str(url).startswith("http"):
        st.markdown(f'<img src="{url}" style="width:{size}px; height:{size}px; border-radius:50%; margin-right:10px; object-fit: cover; border: 2px solid #eee;">', unsafe_allow_html=True)
    else:
        st.markdown(f'<div style="width:{size}px; height:{size}px; border-radius:50%; background:#f0f2f6; display:flex; align-items:center; justify-content:center; font-size:25px; border: 2px solid #eee;">👤</div>', unsafe_allow_html=True)

# --- INTERFACE ---
st.title(" La boîte à livres à Méli-Mélo ")

liste_membres = get_liste_membres_fixes()
col_u1, col_u2 = st.columns([1, 4])
with col_u1:
    prenom_user = st.session_state.get('user', liste_membres[0])
    infos_user = get_membre_info(prenom_user)
    show_avatar(infos_user.get('Avatar',''))
with col_u2:
    utilisateur = st.selectbox("", liste_membres, key='user', label_visibility="collapsed")
    infos_user = get_membre_info(utilisateur)

st.write("---")

# Gestion des onglets (Admin visible uniquement pour Didier et Amélie)
onglets_noms = ["📖 Bibliothèque", "🤝 Emprunts", "👤 Mon Profil", "➕ Ajouter"]
if utilisateur in ["Didier", "Amélie"]:
    onglets_noms.append("⚙️ Gérance")

onglets = st.tabs(onglets_noms)

# --- 1. BIBLIOTHÈQUE ---
with onglets[0]:
    st.markdown("### 🔍 Trier par")
    tri = st.selectbox("", ["Derniers ajouts", "Note", "Titre (A-Z)", "Auteur", "Propriétaire"], label_visibility="collapsed")
    
    df_tri = df_livres.copy()
    if tri == "Titre (A-Z)": df_tri = df_tri.sort_values(by=COL["Titre"])
    elif tri == "Auteur": df_tri = df_tri.sort_values(by=COL["Auteur"])
    elif tri == "Propriétaire": df_tri = df_tri.sort_values(by=COL["Proprio"])
    elif tri == "Note": df_tri = df_tri.sort_values(by=COL["Note"], ascending=False)
    else: df_tri = df_tri.iloc[::-1]

    for idx, row in df_tri.iterrows():
        statut = str(row.get(COL["Statut"], 'Libre')).strip() or "Libre"
        p_livre = str(row[COL["Proprio"]]).strip()
        
        emoji_livre, color = ("📗", "green") if statut == "Libre" else (("📙", "orange") if statut == "Demandé" else ("📕", "red"))
        
        badge_new = ""
        try:
            date_l = datetime.strptime(str(row[COL["Date"]]), "%Y-%m-%d")
            if datetime.now() - date_l < timedelta(days=7):
                badge_new = "🆕 "
        except: pass

        with st.container():
            c1, c2 = st.columns([1, 4])
            with c1: st.title(emoji_livre)
            with c2:
                st.markdown(f"### {badge_new}{row[COL['Titre']]} {row.get(COL['Note'], '')} :{color}[ ({statut})]")
                st.write(f"**{row[COL['Auteur']]}** | **Propriétaire :** {p_livre}")
                if row.get(COL['Avis']): st.success(f"💬 {row[COL['Avis']]}")
                
                if statut == "Libre" and p_livre != utilisateur:
                    if st.button(f"Demander ce livre", key=f"req_{idx}"):
                        oidx = df_livres.index[df_livres[COL['Titre']] == row[COL['Titre']]][0] + 2
                        sheet_livres.update_cell(oidx, 5, "Demandé")
                        sheet_livres.update_cell(oidx, 6, utilisateur)
                        st.success("Demande envoyée !"); st.rerun()
            st.write("---")

# --- 2. EMPRUNTS ---
with onglets[1]:
    st.subheader("🤝 Suivi des emprunts")
    st.markdown("#### 📥 Mes demandes faites")
    mes_dem = df_livres[df_livres[COL["Emprunteur"]] == utilisateur]
    if not mes_dem.empty:
        for _, r in mes_dem.iterrows():
            st.info(f"📖 **{r[COL['Titre']]}** chez {r[COL['Proprio']]} ({r[COL['Statut']]})")
    else: st.write("Aucune demande en cours.")

    st.write("---")
    st.markdown("#### 📤 Demandes reçues")
    mask_mouv = (df_livres[COL["Proprio"]] == utilisateur) & (df_livres[COL["Statut"]].isin(['Demandé', 'Emprunté']))
    mes_reçus = df_livres[mask_mouv]
    if not mes_reçus.empty:
        for idx, r in mes_reçus.iterrows():
            emp = r[COL["Emprunteur"]]
            st.warning(f"🔔 **{emp}** -> **{r[COL['Titre']]}**")
            if r[COL["Statut"]] == "Demandé":
                if st.button(f"✅ Valider prêt pour {emp}", key=f"ok_{idx}"):
                    oidx = df_livres.index[df_livres[COL['Titre']] == r[COL['Titre']]][0] + 2
                    sheet_livres.update_cell(oidx, 5, "Emprunté")
                    info_d = get_membre_info(emp)
                    msg = f"Hello {emp} ! Ok pour '{r[COL['Titre']]}'. Retrait : {infos_user.get('Infos_Retrait')}"
                    st.link_button("📱 WhatsApp", envoyer_whatsapp(info_d.get('Téléphone',''), msg))
            elif r[COL["Statut"]] == "Emprunté":
                if st.button(f"🔄 Marquer comme rendu", key=f"ret_{idx}"):
                    oidx = df_livres.index[df_livres[COL['Titre']] == r[COL['Titre']]][0] + 2
                    sheet_livres.update_cell(oidx, 5, "Libre")
                    sheet_livres.update_cell(oidx, 6, "")
                    st.rerun()
    else: st.write("Rien à signaler.")

# --- 3. MON PROFIL ---
with onglets[2]:
    st.subheader(f"👤 {utilisateur}")
    st.markdown(f"📍 Position : **{infos_user.get('Position')}**")
    st.write("---")
    mes_l = df_livres[df_livres[COL["Proprio"]] == utilisateur]
    if not mes_l.empty:
        for idx, r in mes_l.iterrows():
            with st.expander(f"📙 {r[COL['Titre']]} ({r[COL['Statut']]})"):
                if st.button("Supprimer", key=f"del_{idx}"):
                    oidx = df_livres.index[df_livres[COL['Titre']] == r[COL['Titre']]][0] + 2
                    sheet_livres.delete_rows(oidx); st.rerun()
    else: st.info("Vous n'avez pas encore ajouté de livres.")

# --- 4. AJOUTER ---
with onglets[3]:
    mode = st.radio("", ["✅ Manuel", "📤 Import Excel"], horizontal=True, label_visibility="collapsed")
    if mode == "✅ Manuel":
        with st.form("add_manual"):
            t, a = st.text_input("Titre"), st.text_input("Auteur")
            n = st.select_slider("Note", options=["📚", "📚📚", "📚📚📚", "📚📚📚📚"])
            c = st.text_area("Avis-Délire")
            if st.form_submit_button("Ajouter"):
                d = datetime.now().strftime("%Y-%m-%d")
                sheet_livres.append_row([t, a, utilisateur, c, "Libre", "", n, d])
                st.success("Livre ajouté !"); st.rerun()
    else:
        st.markdown("### 📝 Mode d'emploi Import")
        st.markdown("""
        1. **Télécharge** le modèle `BiblioMod.xlsx` ci-dessous.
        2. **Remplis** les colonnes Titre, Auteur, Avis et Note (📚).
        3. **Charge** le fichier complété pour tout mettre en ligne d'un coup.
        """)
        st.link_button("📥 Télécharger le modèle Excel", "https://raw.githubusercontent.com/TonUser/TonRepo/main/BiblioMod.xlsx")
        up = st.file_uploader("", type="xlsx")
        if up and st.button("Lancer l'importation"):
            df_im = pd.read_excel(up)
            dt = datetime.now().strftime("%Y-%m-%d")
            for _, r in df_im.iterrows():
                sheet_livres.append_row([r['Titre'], r.get('Auteur',''), utilisateur, r.get('Avis',''), "Libre", "", r.get('Note',''), dt])
            st.success("Importation réussie !"); st.rerun()

# --- 5. GÉRANCE (ADMIN) ---
if utilisateur in ["Didier", "Amélie"]:
    with onglets[-1]:
        st.subheader("⚙️ Gérance du Club")
        with st.form("add_member"):
            st.markdown("#### Ajouter un nouveau membre")
            new_name = st.text_input("Prénom")
            new_tel = st.text_input("Téléphone (ex: 41791234567)")
            new_pos = st.text_input("Lieu de domicile")
            new_ret = st.text_input("Infos Retrait (ex: Chez moi le soir)")
            if st.form_submit_button("Créer le compte membre"):
                sheet_membres.append_row([new_name, new_tel, "", new_pos, new_ret])
                st.success(f"Bienvenue à {new_name} ! N'oublie pas de mettre à jour membres_profil.py")

st.caption("Une création DJA’WEB avec l’aide de Gemini IA")
