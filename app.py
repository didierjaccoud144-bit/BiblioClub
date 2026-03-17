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
    st.error(f"Erreur : {e}")
    st.stop()

col_m = "Membre" if "Membre" in df_livres.columns else df_livres.columns[2]

def envoyer_whatsapp(telephone, message):
    return f"https://wa.me/{str(telephone).replace(' ', '')}?text={urllib.parse.quote(message)}"

def show_avatar(url, size=40):
    if url:
        st.markdown(f'<img src="{url}" style="width:{size}px; height:{size}px; border-radius:50%; margin-right:10px;">', unsafe_allow_html=True)

# --- INTERFACE ---
st.title("📚 Le Biblio Club")

liste_membres = get_liste_membres_fixes()
col_u1, col_u2 = st.columns([1, 4])
with col_u1:
    prenom_user = st.session_state.get('user', liste_membres[0])
    infos_user = get_membre_info(prenom_user)
    show_avatar(infos_user.get('Avatar',''), size=50)
with col_u2:
    utilisateur = st.selectbox("", liste_membres, key='user', label_visibility="collapsed")
    infos_user = get_membre_info(utilisateur)

st.write("---")
onglets = st.tabs(["📖 Bibliothèque", "🤝 Emprunts", "👤 Mon Profil", "➕ Ajouter", "📤 Import"])

# --- 1. BIBLIOTHÈQUE (La vitrine avec boutons) ---
with onglets[0]:
    st.subheader("Découvrez les pépites du Club")
    for idx, row in df_livres.iloc[::-1].iterrows():
        statut = str(row.get('Statut', 'Libre')).strip() or "Libre"
        color = "green" if statut == "Libre" else "orange" if statut == "Demandé" else "red"
        
        with st.container():
            c1, c2 = st.columns([1, 4])
            with c1: st.title("📕")
            with c2:
                st.markdown(f"### {row['Titre']} :{color}[ ({statut})]")
                st.write(f"**Auteur :** {row.get('Auteur')} | **Proprio :** {row.get(col_m)}")
                if row.get('Avis_delire'):
                    st.success(f"💬 {row['Avis_delire']}")
                
                # BOUTON DE DEMANDE DIRECT DANS LA BIBLIO
                if statut == "Libre" and str(row.get(col_m)) != utilisateur:
                    if st.button(f"Demander ce livre", key=f"bib_req_{idx}"):
                        sheet_livres.update_cell(idx + 2, 5, "Demandé")
                        sheet_livres.update_cell(idx + 2, 6, utilisateur)
                        st.success("Demande envoyée ! Suis-la dans l'onglet 'Emprunts'.")
                        st.rerun()
            st.write("---")

# --- 2. EMPRUNTS (Le centre de gestion des flux) ---
with onglets[1]:
    st.subheader("Gestion de vos demandes et prêts")
    
    # Section A : Les livres que j'ai demandés ou que j'ai chez moi
    st.markdown("#### 📥 Mes demandes en cours")
    mes_emprunts = df_livres[df_livres['Emprunteur'] == utilisateur]
    if not mes_emprunts.empty:
        for idx, row in mes_emprunts.iterrows():
            st.info(f"📖 **{row['Titre']}** - Statut : {row['Statut']} (chez {row[col_m]})")
    else:
        st.write("Vous n'avez aucune demande active.")
    
    st.write("---")
    
    # Section B : Les demandes que j'ai reçues (Je suis proprio)
    st.markdown("#### 📤 Demandes reçues (mes livres)")
    mes_livres_demandes = df_livres[(df_livres[col_m] == utilisateur) & (df_livres['Statut'].isin(['Demandé', 'Emprunté']))]
    
    if not mes_livres_demandes.empty:
        for idx, row in mes_livres_demandes.iterrows():
            demandeur = row.get('Emprunteur')
            st.warning(f"🔔 **{demandeur}** veut/a votre livre : **{row['Titre']}**")
            
            if row['Statut'] == "Demandé":
                if st.button(f"✅ Valider le prêt pour {demandeur}", key=f"emp_ok_{idx}"):
                    sheet_livres.update_cell(idx + 2, 5, "Emprunté")
                    info_d = get_membre_info(demandeur)
                    st.link_button("📱 Envoyer infos retrait via WhatsApp", envoyer_whatsapp(info_d.get('Téléphone',''), f"Hello {demandeur} ! Ok pour '{row['Titre']}'. Infos retrait : {infos_user.get('Infos_Retrait')}"))
            
            elif row['Statut'] == "Emprunté":
                if st.button(f"🔄 Marquer comme rendu", key=f"emp_back_{idx}"):
                    sheet_livres.update_cell(idx + 2, 5, "Libre")
                    sheet_livres.update_cell(idx + 2, 6, "")
                    st.rerun()
    else:
        st.write("Aucune demande en attente pour vos livres.")

# --- 3. MON PROFIL (Profil pur + Mes livres / Suppression) ---
with onglets[2]:
    st.subheader(f"👤 Profil de {utilisateur}")
    c_p1, c_p2 = st.columns([1, 3])
    with c_p1: show_avatar(infos_user.get('Avatar',''), size=80)
    with c_p2:
        st.markdown(f"**📍 Position :** {infos_user.get('Position', 'Non renseignée')}")
        st.markdown(f"**🏠 Infos Retrait :** {infos_user.get('Infos_Retrait', 'Non renseignées')}")
    
    st.write("---")
    st.subheader("📚 Ma collection")
    mes_propres_livres = df_livres[df_livres[col_m] == utilisateur]
    for idx, row in mes_propres_livres.iterrows():
        with st.expander(f"📙 {row['Titre']}"):
            st.write(f"Statut : {row.get('Statut', 'Libre')}")
            if st.button(f"🗑️ Supprimer du club", key=f"prof_del_{idx}"):
                sheet_livres.delete_rows(idx + 2)
                st.error("Livre retiré.")
                st.rerun()

# --- 4 & 5 (AJOUT / IMPORT) ---
# ... (Gardez le même code pour Ajouter et Import)
