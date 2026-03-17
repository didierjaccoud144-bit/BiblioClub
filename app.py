import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import urllib.parse
from PIL import Image
import base64
from io import BytesIO

# Importation du fichier de profil membres (créé séparément)
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
    # On n'utilise plus sheet_membres, on utilise le dictionnaire fixe
    df_livres = pd.DataFrame(sheet_livres.get_all_records())
except Exception as e:
    st.error(f"Erreur : {e}")
    st.stop()

# --- DÉTECTION COLONNES ---
col_m = "Membre" if "Membre" in df_livres.columns else df_livres.columns[2]

def envoyer_whatsapp(telephone, message):
    return f"https://wa.me/{str(telephone).replace(' ', '')}?text={urllib.parse.quote(message)}"

def show_avatar(url, size=40):
    """Affiche un avatar Notion proprement (contour rond)."""
    if url:
        st.markdown(f'<img src="{url}" style="width:{size}px; height:{size}px; border-radius:50%; margin-right:10px;">', unsafe_allow_html=True)

# --- INTERFACE ---
st.title("📚 Le Biblio Club")

# Sélection Utilisateur (visible sur mobile)
liste_membres = get_liste_membres_fixes()
col_u1, col_u2 = st.columns([1, 4])
with col_u1:
    # Affiche l'avatar Notion du membre sélectionné
    prenom_user = st.session_state.get('user', liste_membres[0]) # Par défaut le premier
    infos_user = get_membre_info(prenom_user)
    show_avatar(infos_user.get('Avatar',''), size=50)

with col_u2:
    utilisateur = st.selectbox("", liste_membres, key='user', label_visibility="collapsed")
    infos_user = get_membre_info(utilisateur)

st.write("---")
onglets = st.tabs(["📖 Bibliothèque", "🤝 Emprunts", "👤 Mon Profil", "➕ Ajouter", "📤 Import"])

# --- 1. BIBLIOTHÈQUE ---
with onglets[0]:
    # Affiche juste la liste des livres
    for idx, row in df_livres.iloc[::-1].iterrows():
        # ... (Le code d'affichage des livres reste identique)
        with st.container():
            c1, c2 = st.columns([1, 4])
            with c1: st.title("📕")
            with c2:
                # Affichage simple : titre, auteur, proprio, avis
                st.markdown(f"### {row['Titre']}")
                st.write(f"**Auteur :** {row.get('Auteur')} | **Proprio :** {row.get(col_m)}")
                if row.get('Avis_delire'):
                    st.success(f"💬 **Avis :** {row['Avis_delire']}")
            st.write("---")

# --- 2. GESTION CENTRALISÉE DES EMPRUNTS (REMPLACÉ) ---
with onglets[1]:
    st.subheader("🤝 Livres en mouvement (Demandes & Prêts)")
    
    # Inverser l'ordre pour voir les derniers ajouts/mouvements en haut
    for idx, row in df_livres.iloc[::-1].iterrows():
        statut = str(row.get('Statut', 'Libre')).strip()
        statut = statut if statut != "" else "Libre"
        color = "green" if statut == "Libre" else "orange" if statut == "Demandé" else "red"
        
        # Le proprio c'est moi ou c'est pas moi ?
        c_proprio = str(row.get(col_m))
        
        with st.container():
            c1, c2 = st.columns([1, 4])
            with c1: st.title("📕")
            with c2:
                st.markdown(f"### {row['Titre']} :{color}[ ({statut})]")
                st.write(f"**Auteur :** {row.get('Auteur')} | **Proprio :** {c_proprio}")
                
                # --- ACTIONS (CENTRALISÉES ICI) ---
                
                # A. Je suis demandeur : Demander un livre libre
                if statut == "Libre" and c_proprio != utilisateur:
                    if st.button(f"Faire une demande d'emprunt", key=f"req_{idx}"):
                        sheet_livres.update_cell(idx + 2, 5, "Demandé")
                        sheet_livres.update_cell(idx + 2, 6, utilisateur)
                        st.success("Demande envoyée ! Le propriétaire la recevra.")
                        st.rerun()
                
                # B. Je suis proprio : Gérer une demande (Demandé)
                elif statut == "Demandé" and c_proprio == utilisateur:
                    demandeur = row.get('Emprunteur')
                    st.warning(f"🔔 {demandeur} souhaite emprunter ce livre")
                    
                    if st.button(f"✅ Valider le prêt pour {demandeur}", key=f"ok_{idx}"):
                        sheet_livres.update_cell(idx + 2, 5, "Emprunté")
                        # Récupérer tel du demandeur depuis dictionnaire fixe
                        info_d = get_membre_info(demandeur)
                        tel_d = info_d.get('Téléphone', '')
                        msg = f"Hello {demandeur} ! Ok pour '{row['Titre']}' ! Retrait : {infos_user.get('Infos_Retrait', 'Contacte-moi !')}"
                        st.link_button("📱 Confirmation WhatsApp", envoyer_whatsapp(tel_d, msg))
                
                # C. Je suis proprio : Marquer comme rendu (Emprunté)
                elif statut == "Emprunté" and c_proprio == utilisateur:
                    if st.button(f"🔄 Livre rendu", key=f"back_{idx}"):
                        sheet_livres.update_cell(idx + 2, 5, "Libre")
                        sheet_livres.update_cell(idx + 2, 6, "")
                        st.rerun()
            st.write("---")

# --- 3. MON PROFIL (Avatar, Position, Mes Livres & Suppression) ---
with onglets[2]:
    st.subheader(f"👤 Espace de {utilisateur}")
    
    # Affichage de l'avatar et position (fixe)
    col_p1, col_p2 = st.columns([1, 3])
    with col_p1:
        show_avatar(infos_user.get('Avatar',''), size=80)
    with col_p2:
        st.markdown(f"**📍 Position :** {infos_user.get('Position', 'Non indiquée')}")
        st.markdown(f"**📱 Tél :** {infos_user.get('Téléphone', '---')}")
        st.markdown(f"**🔖 Infos Retrait :** *{infos_user.get('Infos_Retrait', '---')}*")
    
    st.write("---")
    
    # Liste de mes livres avec suppression
    st.subheader(f"🔖 Mes livres ({utilisateur})")
    mes_livres = df_livres[df_livres[col_m] == utilisateur]
    if not mes_livres.empty:
        for idx, row in mes_livres.iterrows():
            with st.expander(f"📙 {row['Titre']}"):
                s = str(row.get('Statut', 'Libre'))
                st.write(f"Statut : {s}")
                
                # Suppression
                st.write("---")
                if st.button(f"🗑️ Supprimer définitivement", key=f"del_{idx}"):
                    sheet_livres.delete_rows(idx + 2)
                    st.error("Livre supprimé.")
                    st.rerun()
            st.write("")
    else:
        st.info("Tu n'as pas encore de livres.")

# --- 4 & 5 (AJOUT/IMPORT - INCHANGÉS) ---
with onglets[3]:
    with st.form("add_vfinal"):
        t, a = st.text_input("Titre"), st.text_input("Auteur")
        note = st.select_slider("Note", options=["📚", "📚📚", "📚📚📚", "📚📚📚📚"])
        com = st.text_area("Commentaire")
        if st.form_submit_button("Ajouter"):
            sheet_livres.append_row([t, a, utilisateur, f"{note} {com}", "Libre", ""])
            st.success("Ajouté !"); st.rerun()

with onglets[4]:
    up = st.file_uploader("Fichier Excel", type="xlsx")
    if up and st.button("Lancer l'import"):
        df_im = pd.read_excel(up)
        for _, r in df_im.iterrows():
            sheet_livres.append_row([r['Titre'], r.get('Auteur',''), utilisateur, r.get('Avis_delire',''), "Libre", ""])
        st.success("Import réussi !"); st.rerun()

st.write("---")
st.caption("Une création DJA’WEB avec l’aide de Gemini IA")
