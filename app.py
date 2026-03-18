import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import urllib.parse
from datetime import datetime

# --- CONFIGURATION ---
st.set_page_config(page_title="Méli-Mélo", page_icon="📚", layout="centered")

# Initialisation de la session
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
@st.cache_data(ttl=60) # Cache de 1 minute pour être réactif aux ajouts dans le Sheet
def load_all_data():
    client = get_gspread_client()
    spreadsheet = client.open("BiblioClub_Data") 
    
    # Lecture Livres
    sh_livres = spreadsheet.worksheet("Livres")
    df_l = pd.DataFrame(sh_livres.get_all_records())
    
    # Lecture Membres
    sh_membres = spreadsheet.worksheet("Membres")
    df_m = pd.DataFrame(sh_membres.get_all_records())
    
    return df_l, df_m, sh_livres, sh_membres

try:
    df_livres, df_membres, sheet_livres, sheet_membres = load_all_data()
except Exception as e:
    st.error(f"Erreur de connexion aux données : {e}")
    st.stop()

COL = {
    "Titre": "Titre", "Auteur": "Auteur", "Proprio": "Propriétaire",
    "Avis": "Avis_delire", "Statut": "Statut", "Emprunteur": "Emprunteur",
    "Note": "Note", "Date": "Date_Ajout", "Avis_Lecteurs": "Avis_Lecteurs"
}

def envoyer_whatsapp(message):
    return f"https://api.whatsapp.com/send?text={urllib.parse.quote(message)}"

# --- ÉCRAN DE CONNEXION ---
if not st.session_state.connecte:
    st.title("🔐 Accès Méli-Mélo")
    st.write("Bienvenue ! Veuillez vous identifier.")
    
    # La liste des noms vient DIRECTEMENT du Sheet (Colonne Prénom)
    noms_disponibles = sorted(df_membres['Prénom'].unique().tolist())
    
    nom_choisi = st.selectbox("Sélectionnez votre prénom", noms_disponibles)
    code_saisi = st.text_input("Votre code secret", type="password")
    
    if st.button("Accéder à la bibliothèque"):
        # On vérifie le code correspondant au prénom dans le DataFrame membres
        membre_info = df_membres[df_membres['Prénom'] == nom_choisi]
        if not membre_info.empty:
            code_reel = str(membre_info['Code-Secret'].values[0]).strip()
            if str(code_saisi).strip() == code_reel:
                st.session_state.connecte = True
                st.session_state.user = nom_choisi
                st.rerun()
            else:
                st.error("Code secret incorrect.")
        else:
            st.error("Utilisateur introuvable.")
    st.stop()

# --- INTERFACE PRINCIPALE (Si connecté) ---
utilisateur = st.session_state.user

col_title, col_logout = st.columns([3, 1])
with col_title:
    st.title("📚 Méli-Mélo")
with col_logout:
    if st.button("🚪 Quitter"):
        st.session_state.connecte = False
        st.session_state.user = None
        st.rerun()

st.success(f"😊 Ravi de vous voir, **{utilisateur}** !")

# Barre d'actions rapide
c_refresh, c_user = st.columns([1, 2])
with c_refresh:
    if st.button("🔄 Actualiser"): refresh()

# Notifications de demandes
mes_demandes = df_livres[(df_livres[COL["Proprio"]] == utilisateur) & (df_livres[COL["Statut"]] == "Demandé")]
if len(mes_demandes) > 0:
    st.warning(f"🔔 Tu as **{len(mes_demandes)}** demande(s) de prêt en attente !")

st.write("---")
onglets_noms = ["📖 Bibliothèque", f"🤝 Emprunts ({len(mes_demandes)})", "👤 Mon Profil", "➕ Ajouter"]
if utilisateur in ["Didier", "Amélie"]:
    onglets_noms.append("⚙️ Gérance")
onglets_noms.append("❓ Aide")

onglets = st.tabs(onglets_noms)

# --- 1. BIBLIOTHÈQUE ---
with onglets[0]:
    recherche = st.text_input("🔍 Rechercher un titre ou auteur...", "").lower()
    df_biblio = df_livres.copy()
    if recherche:
        df_biblio = df_biblio[df_biblio[COL["Titre"]].str.lower().str.contains(recherche) | df_biblio[COL["Auteur"]].str.lower().str.contains(recherche)]
    
    # Tri
    tri = st.selectbox("Trier par", ["Derniers ajouts", "Note", "A-Z"], label_visibility="collapsed")
    if tri == "A-Z": df_biblio = df_biblio.sort_values(by=COL["Titre"])
    elif tri == "Note": df_biblio = df_biblio.sort_values(by=COL["Note"], ascending=False)
    else: df_biblio = df_biblio.iloc[::-1]

    for idx, row in df_biblio.iterrows():
        statut = str(row[COL["Statut"]]).strip() or "Libre"
        p_livre = str(row[COL["Proprio"]]).strip()
        emoji, color = ("📗", "green") if statut == "Libre" else (("⏳", "orange") if statut == "Demandé" else ("📕", "red"))
        
        with st.container():
            st.markdown(f"#### {emoji} {row[COL['Titre']]} {row.get(COL['Note'], '')}")
            st.markdown(f"*{row[COL['Auteur']]}* — Proprio : **{p_livre}** | :{color}[**({statut})**]")
            
            c1, c2 = st.columns([1, 2])
            with c1:
                if statut == "Libre" and p_livre != utilisateur:
                    if st.button(f"Demander", key=f"req_{idx}"):
                        oidx = int(df_livres.index[df_livres[COL['Titre']] == row[COL['Titre']]][0] + 2)
                        sheet_livres.update_cell(oidx, 5, "Demandé")
                        sheet_livres.update_cell(oidx, 6, utilisateur); refresh()
                with st.expander("💬 Avis"):
                    n_l = st.select_slider("Note", options=["📚","📚📚","📚📚📚","📚📚📚📚"], key=f"n_{idx}")
                    c_l = st.text_area("Retour", key=f"c_{idx}", height=70)
                    if st.button("Publier", key=f"p_{idx}"):
                        oidx = int(df_livres.index[df_livres[COL['Titre']] == row[COL['Titre']]][0] + 2)
                        total = (str(row.get(COL["Avis_Lecteurs"], "")) + f"\n\n**{utilisateur}** ({n_l}) : {c_l}").strip()
                        sheet_livres.update_cell(oidx, 9, total); refresh()
            with c2:
                if row.get(COL['Avis']): st.caption(f"⭐ **Proprio :** {row[COL['Avis']]}")
                if row.get(COL['Avis_Lecteurs']):
                    with st.expander("💬 Avis lecteurs"): st.markdown(row[COL['Avis_Lecteurs']])
            st.markdown("<hr style='margin:5px 0px'>", unsafe_allow_html=True)

# --- 2. EMPRUNTS (GESTION DES DEMANDES) ---
with onglets[1]:
    st.subheader("🤝 Gestion de mes livres")
    res = df_livres[(df_livres[COL["Proprio"]] == utilisateur) & (df_livres[COL["Statut"]].isin(['Demandé', 'Emprunté']))]
    if not res.empty:
        for idx, r in res.iterrows():
            emp = r[COL["Emprunteur"]]
            st.info(f"**{emp}** souhaite : **{r[COL['Titre']]}**")
            if r[COL["Statut"]] == "Demandé":
                col_a, col_b = st.columns(2)
                with col_a:
                    if st.button(f"✅ Valider", key=f"v_{idx}"):
                        oidx = int(df_livres.index[df_livres[COL['Titre']] == r[COL['Titre']]][0] + 2)
                        sheet_livres.update_cell(oidx, 5, "Emprunté")
                        st.link_button("📱 WhatsApp", envoyer_whatsapp(f"C'est OK pour '{r[COL['Titre']]}'. On s'organise ?"))
                with col_b:
                    if st.button(f"❌ Refuser", key=f"d_{idx}"):
                        oidx = int(df_livres.index[df_livres[COL['Titre']] == r[COL['Titre']]][0] + 2)
                        sheet_livres.update_cell(oidx, 5, "Libre"); sheet_livres.update_cell(oidx, 6, ""); refresh()
            else:
                if st.button(f"🔄 Marquer comme Rendu", key=f"r_{idx}"):
                    oidx = int(df_livres.index[df_livres[COL['Titre']] == r[COL['Titre']]][0] + 2)
                    sheet_livres.update_cell(oidx, 5, "Libre"); sheet_livres.update_cell(oidx, 6, ""); refresh()
    else: st.write("Aucun mouvement sur vos livres.")

# --- 3. PROFIL ---
with onglets[2]:
    st.subheader(f"👤 {utilisateur}")
    c_p, c_e = st.columns(2)
    with c_p:
        st.markdown("**Mes prêts (sortis)**")
        st.dataframe(df_livres[(df_livres[COL["Proprio"]] == utilisateur) & (df_livres[COL["Statut"]] != "Libre")][[COL["Titre"], COL["Emprunteur"]]])
    with c_e:
        st.markdown("**Mes emprunts (chez moi)**")
        st.dataframe(df_livres[(df_livres[COL["Emprunteur"]] == utilisateur) & (df_livres[COL["Statut"]] != "Libre")][[COL["Titre"], COL["Proprio"]]])
    
    st.write("---")
    if st.button("🗑️ Gérer ma collection (Supprimer des livres)"):
        mes_l = df_livres[df_livres[COL["Proprio"]] == utilisateur]
        for idx, r in mes_l.iterrows():
            if st.button(f"Supprimer {r[COL['Titre']]}", key=f"del_{idx}"):
                oidx = int(df_livres.index[df_livres[COL['Titre']] == r[COL['Titre']]][0] + 2)
                sheet_livres.delete_rows(oidx); refresh()

# --- 4. AJOUTER ---
with onglets[3]:
    m = st.radio("Mode", ["Manuel", "Excel"], horizontal=True)
    if m == "Manuel":
        with st.form("add"):
            t, a = st.text_input("Titre"), st.text_input("Auteur")
            n = st.select_slider("Note", ["📚","📚📚","📚📚📚","📚📚📚📚"])
            c = st.text_area("Avis")
            if st.form_submit_button("Ajouter"):
                sheet_livres.append_row([t, a, utilisateur, c, "Libre", "", n, datetime.now().strftime("%Y-%m-%d"), ""]); refresh()
    else:
        st.link_button("📥 Modèle Excel", "https://raw.githubusercontent.com/didierjaccoud144-bit/BiblioClub/main/BiblioMod.xlsx")
        up = st.file_uploader("Fichier", type="xlsx")
        if up and st.button("Importer"):
            df_i = pd.read_excel(up).fillna("")
            lignes = [[str(ri['Titre']), str(ri.get('Auteur','')), utilisateur, str(ri.get('Avis','')), "Libre", "", str(ri.get('Note','📚📚')), datetime.now().strftime("%Y-%m-%d"), ""] for _, ri in df_i.iterrows()]
            sheet_livres.append_rows(lignes); refresh()

# --- 5. GÉRANCE ---
if utilisateur in ["Didier", "Amélie"]:
    with onglets[4]:
        st.subheader("⚙️ Administration des membres")
        with st.form("new_member"):
            new_n = st.text_input("Prénom")
            new_c = st.text_input("Code Secret (4 chiffres)")
            new_t = st.text_input("Téléphone")
            if st.form_submit_button("Créer le membre"):
                sheet_membres.append_row([new_n, new_c, new_t, "", "", ""])
                st.success(f"Membre {new_n} créé ! N'oubliez pas de l'ajouter aussi dans membres_profil.py sur GitHub pour qu'il apparaisse dans la liste.")
                refresh()

# --- 6. AIDE ---
with onglets[-1]:
    st.markdown("### 📖 Aide & Mode d'emploi")
    with st.expander("📱 Installer sur mobile"):
        st.write("iPhone : Safari > Partager > Sur l'écran d'accueil")
        st.write("Android : Chrome > 3 points > Installer l'application")
    with st.expander("🤝 Comment emprunter ?"):
        st.write("1. Trouvez un livre vert 📗 et cliquez sur Demander.")
        st.write("2. Attendez que le propriétaire valide (il reçoit une alerte).")
        st.write("3. Une fois validé, contactez-le via le bouton WhatsApp pour fixer le RDV !")

st.caption("Une création DJA’WEB avec l’aide de Gemini IA")
