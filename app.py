import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import urllib.parse
from datetime import datetime

# Importation du fichier de profil membres
from membres_profil import get_membre_info, get_liste_membres_fixes

# --- CONFIGURATION ---
st.set_page_config(page_title="Méli-Mélo", page_icon="📚", layout="centered")

# Initialisation de la session de connexion
if 'connecte' not in st.session_state:
    st.session_state.connecte = False
if 'user' not in st.session_state:
    st.session_state.user = None

def refresh():
    st.cache_data.clear()
    st.rerun()

def get_gspread_client():
    creds_dict = st.secrets["gcp_service_account"].to_dict()
    if "private_key" in creds_dict:
        creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    return gspread.authorize(creds)

# --- CHARGEMENT DES DONNÉES ---
try:
    client = get_gspread_client()
    spreadsheet = client.open("BiblioClub_Data") 
    sheet_livres = spreadsheet.worksheet("Livres")
    sheet_membres = spreadsheet.worksheet("Membres")
    
    # Données Livres
    data_l = sheet_livres.get_all_records()
    cols_def = ["Titre", "Auteur", "Propriétaire", "Avis_delire", "Statut", "Emprunteur", "Note", "Date_Ajout", "Avis_Lecteurs"]
    df_livres = pd.DataFrame(data_l) if data_l else pd.DataFrame(columns=cols_def)
    
    # Données Membres (pour vérification du code)
    data_m = sheet_membres.get_all_records()
    df_membres = pd.DataFrame(data_m)
except Exception as e:
    st.error(f"Erreur de connexion : {e}")
    st.stop()

COL = {
    "Titre": "Titre", "Auteur": "Auteur", "Proprio": "Propriétaire",
    "Avis": "Avis_delire", "Statut": "Statut", "Emprunteur": "Emprunteur",
    "Note": "Note", "Date": "Date_Ajout", "Avis_Lecteurs": "Avis_Lecteurs"
}

def envoyer_whatsapp(message):
    return f"https://api.whatsapp.com/send?text={urllib.parse.quote(message)}"

# --- LOGIQUE DE CONNEXION ---
if not st.session_state.connecte:
    st.title("🔐 Accès Méli-Mélo")
    st.write("Veuillez vous identifier pour accéder à la bibliothèque.")
    
    liste_noms = get_liste_membres_fixes()
    nom_choisi = st.selectbox("Qui êtes-vous ?", liste_noms)
    code_saisi = st.text_input("Code Secret", type="password", help="Minimum 4 caractères")
    
    if st.button("Se connecter"):
        # Vérification du code dans le DataFrame membres
        # On cherche la ligne correspondant au prénom et on vérifie la colonne 'Code-Secret'
        try:
            ligne_membre = df_membres[df_membres['Prénom'] == nom_choisi]
            code_reel = str(ligne_membre['Code-Secret'].values[0]).strip()
            
            if str(code_saisi).strip() == code_reel and len(str(code_saisi)) >= 4:
                st.session_state.connecte = True
                st.session_state.user = nom_choisi
                st.rerun()
            else:
                st.error("Code incorrect ou trop court (min. 4 caractères).")
        except Exception:
            st.error("Erreur d'identification. Contactez Didier.")
    st.stop() # Arrête l'exécution ici tant qu'on n'est pas connecté

# --- SI CONNECTÉ : L'APPLICATION S'AFFICHE ---
utilisateur = st.session_state.user

st.title(" La boîte à livres à Méli-Mélo ")

col_info, col_refresh, col_logout = st.columns([2, 1, 1])
with col_info:
    st.write(f"👤 Membre : **{utilisateur}**")
with col_refresh:
    if st.button("🔄 Actualiser"):
        refresh()
with col_logout:
    if st.button("🚪 Quitter"):
        st.session_state.connecte = False
        st.session_state.user = None
        st.rerun()

# NOTIFICATIONS FLASH
has_notif = False
nb_demandes = 0
if not df_livres.empty:
    mes_demandes = df_livres[(df_livres[COL["Proprio"]] == utilisateur) & (df_livres[COL["Statut"]] == "Demandé")]
    nb_demandes = len(mes_demandes)
    if nb_demandes > 0:
        has_notif = True
        st.warning(f"🔔 **Alerte** : Tu as {nb_demandes} demande(s) de prêt en attente !")

nom_onglet_emprunt = f"🤝 Emprunts ({nb_demandes})" if has_notif else "🤝 Emprunts"

st.write("---")
onglets_noms = ["📖 Bibliothèque", nom_onglet_emprunt, "👤 Mon Profil", "➕ Ajouter"]
if utilisateur in ["Didier", "Amélie"]:
    onglets_noms.append("👤 Gérance")
onglets_noms.append("❓ Mode d'emploi")

onglets = st.tabs(onglets_noms)

# --- 1. BIBLIOTHÈQUE ---
with onglets[0]:
    recherche = st.text_input("🔍 Rechercher...", "").lower()
    tri = st.selectbox("Trier par", ["Derniers ajouts", "Note", "Titre (A-Z)"])
    df_tri = df_livres.copy()
    if recherche:
        df_tri = df_tri[df_tri[COL["Titre"]].str.lower().str.contains(recherche) | df_tri[COL["Auteur"]].str.lower().str.contains(recherche)]
    if tri == "Titre (A-Z)": df_tri = df_tri.sort_values(by=COL["Titre"])
    elif tri == "Note": df_tri = df_tri.sort_values(by=COL["Note"], ascending=False)
    else: df_tri = df_tri.iloc[::-1]

    for idx, row in df_tri.iterrows():
        statut = str(row.get(COL["Statut"], 'Libre')).strip() or "Libre"
        p_livre = str(row[COL["Proprio"]]).strip()
        emoji, color = ("📗", "green") if statut == "Libre" else (("⏳", "orange") if statut == "Demandé" else ("📕", "red"))
        
        with st.container():
            st.markdown(f"#### {emoji} {row[COL['Titre']]} {row.get(COL['Note'], '')}")
            st.markdown(f"*{row[COL['Auteur']]}* — Proprio : **{p_livre}** | :{color}[**({statut})**]")
            
            c_actions, c_avis = st.columns([1.5, 3])
            with c_actions:
                if statut == "Libre" and p_livre != utilisateur:
                    if st.button(f"Demander", key=f"req_{idx}"):
                        oidx = int(df_livres.index[df_livres[COL['Titre']] == row[COL['Titre']]][0] + 2)
                        sheet_livres.update_cell(oidx, 5, "Demandé"); sheet_livres.update_cell(oidx, 6, utilisateur); refresh()
                with st.expander("💬 Avis/Note"):
                    n_l = st.select_slider("Ma Note", options=["📚","📚📚","📚📚📚","📚📚📚📚"], key=f"n_{idx}")
                    c_l = st.text_area("Retour", key=f"c_{idx}", height=70)
                    if st.button("Publier", key=f"p_{idx}"):
                        oidx = int(df_livres.index[df_livres[COL['Titre']] == row[COL['Titre']]][0] + 2)
                        total = (str(row.get(COL["Avis_Lecteurs"], "")) + f"\n\n**{utilisateur}** ({n_l}) : {c_l}").strip()
                        sheet_livres.update_cell(oidx, 9, total); refresh()
            with c_avis:
                if row.get(COL['Avis']): st.caption(f"⭐ **Proprio :** {row[COL['Avis']]}")
                if row.get(COL['Avis_Lecteurs']):
                    with st.expander("💬 Voir les avis"): st.markdown(row[COL['Avis_Lecteurs']])
            st.markdown("<hr style='margin:10px 0px'>", unsafe_allow_html=True)

# --- 2. EMPRUNTS ---
with onglets[1]:
    st.subheader("🤝 Suivi des demandes")
    res = df_livres[(df_livres[COL["Proprio"]] == utilisateur) & (df_livres[COL["Statut"]].isin(['Demandé', 'Emprunté']))]
    if not res.empty:
        for idx, r in res.iterrows():
            emp = r[COL["Emprunteur"]]
            st.warning(f"🔔 **{emp}** attend : **{r[COL['Titre']]}**")
            if r[COL["Statut"]] == "Demandé":
                col1, col2 = st.columns(2)
                with col1:
                    if st.button(f"✅ Valider", key=f"v_{idx}"):
                        oidx = int(df_livres.index[df_livres[COL['Titre']] == r[COL['Titre']]][0] + 2)
                        sheet_livres.update_cell(oidx, 5, "Emprunté")
                        st.link_button("📱 WhatsApp", envoyer_whatsapp(f"C'est OK pour '{r[COL['Titre']]}'. On s'organise ?"))
                with col2:
                    if st.button(f"❌ Décliner", key=f"d_{idx}"):
                        oidx = int(df_livres.index[df_livres[COL['Titre']] == r[COL['Titre']]][0] + 2)
                        sheet_livres.update_cell(oidx, 5, "Libre"); sheet_livres.update_cell(oidx, 6, ""); refresh()
            elif r[COL["Statut"]] == "Emprunté":
                if st.button(f"🔄 Rendu", key=f"r_{idx}"):
                    oidx = int(df_livres.index[df_livres[COL['Titre']] == r[COL['Titre']]][0] + 2)
                    sheet_livres.update_cell(oidx, 5, "Libre"); sheet_livres.update_cell(oidx, 6, ""); refresh()
    else: st.write("Aucune demande en attente.")

# --- 3. PROFIL ---
with onglets[2]:
    st.subheader(f"👤 Profil de {utilisateur}")
    st.markdown("### 📤 Prêts (Livres sortis)")
    mes_prets = df_livres[(df_livres[COL["Proprio"]] == utilisateur) & (df_livres[COL["Statut"]].isin(['Demandé', 'Emprunté']))]
    if not mes_prets.empty:
        st.table(mes_prets[[COL["Titre"], COL["Emprunteur"], COL["Statut"]]])
    
    st.markdown("### 📥 Emprunts (Livres chez moi)")
    mes_emprunts = df_livres[(df_livres[COL["Emprunteur"]] == utilisateur) & (df_livres[COL["Statut"]].isin(['Demandé', 'Emprunté']))]
    if not mes_emprunts.empty:
        recap_e = mes_emprunts[[COL["Titre"], COL["Proprio"], COL["Statut"]]].copy()
        recap_e[COL["Statut"]] = recap_e[COL["Statut"]].replace({"Demandé": "⏳ En attente", "Emprunté": "🏠 Chez moi"})
        st.table(recap_e)
    
    st.write("---")
    st.markdown("#### 📢 Suggérer un membre")
    with st.form("sugg"):
        s = st.text_input("Nom, Prénom")
        if st.form_submit_button("WhatsApp"):
            st.link_button("📱 WhatsApp Admin", envoyer_whatsapp(f"Sugg : {s}"))
    
    st.write("---")
    st.markdown("#### 📚 Ma collection")
    mes_l = df_livres[df_livres[COL["Proprio"]] == utilisateur]
    for idx, r in mes_l.iterrows():
        with st.expander(f"📙 {r[COL['Titre']]} ({r[COL['Statut']]})"):
            if st.button("Supprimer", key=f"del_{idx}"):
                oidx = int(df_livres.index[df_livres[COL['Titre']] == r[COL['Titre']]][0] + 2)
                sheet_livres.delete_rows(oidx); refresh()

# --- 4. AJOUTER ---
with onglets[3]:
    mode = st.radio("Méthode :", ["✅ Manuel", "📤 Import Excel"], horizontal=True)
    if mode == "✅ Manuel":
        with st.form("add"):
            t, a, n, c = st.text_input("Titre"), st.text_input("Auteur"), st.select_slider("Note", ["📚","📚📚","📚📚📚","📚📚📚📚"]), st.text_area("Avis")
            if st.form_submit_button("Ajouter"):
                sheet_livres.append_row([t, a, utilisateur, c, "Libre", "", n, datetime.now().strftime("%Y-%m-%d"), ""]); refresh()
    else:
        st.link_button("📥 Modèle Excel", "https://raw.githubusercontent.com/didierjaccoud144-bit/BiblioClub/main/BiblioMod.xlsx")
        up = st.file_uploader("Fichier", type="xlsx")
        if up and st.button("Lancer l'import"):
            try:
                df_i = pd.read_excel(up).fillna("")
                lignes = [[str(ri['Titre']), str(ri.get('Auteur','')), utilisateur, str(ri.get('Avis','')), "Libre", "", str(ri.get('Note','📚📚')), datetime.now().strftime("%Y-%m-%d"), ""] for _, ri in df_i.iterrows()]
                sheet_livres.append_rows(lignes); refresh()
            except Exception as e: st.error(f"Erreur : {e}")

# --- 5. GÉRANCE ---
if utilisateur in ["Didier", "Amélie"]:
    with onglets[4]:
        st.subheader("👤 Ajouter un membre")
        with st.form("nm"):
            n, t, s, p, r = st.text_input("Prénom"), st.text_input("Tél"), st.text_input("Code Secret"), st.text_input("Lieu"), st.text_input("Retrait")
            if st.form_submit_button("Enregistrer"):
                sheet_membres.append_row([n, s, t, "", p, r]); st.success("Membre ajouté !"); refresh()

# --- 6. MODE D'EMPLOI ---
with onglets[-1]:
    st.title("📖 Mode d'emploi Méli-Mélo")
    with st.expander("📱 Installation", expanded=True):
        st.markdown("* **iPhone** : Safari -> Partage -> « Sur l'écran d'accueil ».\n* **Android** : Chrome -> 3 points -> « Installer ».")
    with st.expander("🔍 Légende et Recherche"):
        st.markdown("* 📗 **Vert** : Disponible.\n* ⏳ **Sablier** : Demande envoyée.\n* 📕 **Rouge** : Prêté.")
    with st.expander("💬 Partager mon avis"):
        st.markdown("Cliquez sur **💬 Avis/Note** sous un livre pour laisser votre retour.")
    with st.expander("🤝 Emprunter / Prêter"):
        st.markdown("Tout se passe par **WhatsApp** une fois que le propriétaire a validé la demande.")

st.caption("Une création DJA’WEB avec l’aide de Gemini IA")
