import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import urllib.parse
from datetime import datetime

# --- CONFIGURATION ---
st.set_page_config(page_title="Méli-Mélo", page_icon="📚", layout="centered")

if 'connecte' not in st.session_state:
    st.session_state.connecte = False
if 'user' not in st.session_state:
    st.session_state.user = None

def refresh():
    st.cache_data.clear()
    st.rerun()

# FONCTION DE CONNEXION ROBUSTE
def get_gspread_client():
    try:
        creds_dict = st.secrets["gcp_service_account"].to_dict()
        if "private_key" in creds_dict:
            creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"Erreur d'authentification Google : {e}")
        return None

# --- CHARGEMENT ---
@st.cache_data(ttl=60)
def load_all_data():
    client = get_gspread_client()
    if client:
        spreadsheet = client.open("BiblioClub_Data") 
        sh_livres = spreadsheet.worksheet("Livres")
        df_l = pd.DataFrame(sh_livres.get_all_records())
        sh_membres = spreadsheet.worksheet("Membres")
        df_m = pd.DataFrame(sh_membres.get_all_records())
        return df_l, df_m, sh_livres, sh_membres
    return None, None, None, None

df_livres, df_membres, sheet_livres, sheet_membres = load_all_data()

if df_livres is None:
    st.error("Impossible de charger les données. Vérifiez la connexion.")
    st.stop()

# --- DEFINITIONS ---
COL = {
    "Titre": "Titre", "Auteur": "Auteur", "Proprio": "Propriétaire",
    "Avis": "Avis_delire", "Statut": "Statut", "Emprunteur": "Emprunteur",
    "Note": "Note", "Date": "Date_Ajout", "Avis_Lecteurs": "Avis_Lecteurs",
    "Cat": "Catégorie"
}

LISTE_CATS = ["Roman", "Policier", "BD / Manga", "Cuisine", "Jeunesse", "Développement Perso", "Autre"]

def envoyer_whatsapp(message):
    return f"https://api.whatsapp.com/send?text={urllib.parse.quote(message)}"

def generer_lien_mail(sujet, corps):
    dest = "didier.jaccoud.144@gmail.com"
    return f"mailto:{dest}?subject={urllib.parse.quote(sujet)}&body={urllib.parse.quote(corps)}"

# --- CONNEXION ---
if not st.session_state.connecte:
    st.title("🔐 Accès Méli-Mélo")
    noms_disponibles = sorted(df_membres['Prénom'].unique().tolist())
    nom_choisi = st.selectbox("Qui êtes-vous ?", noms_disponibles)
    code_saisi = st.text_input("Code Secret", type="password")
    if st.button("Se connecter"):
        membre_info = df_membres[df_membres['Prénom'] == nom_choisi]
        if not membre_info.empty:
            if str(code_saisi).strip() == str(membre_info['Code-Secret'].values[0]).strip():
                st.session_state.connecte = True
                st.session_state.user = nom_choisi
                st.rerun()
            else: st.error("Code incorrect.")
    st.stop()

# --- INTERFACE ---
utilisateur = st.session_state.user

# TITRE & ICONE
c1, c2 = st.columns([1, 4])
with c1:
    image_url = "https://raw.githubusercontent.com/didierjaccoud144-bit/BiblioClub/main/image_3.png"
    st.image(image_url, width=100)
with c2:
    st.title(" La boîte à livres à Méli-Mélo ")

c_info, c_refresh, c_logout = st.columns([2, 1, 1])
with c_info: st.write(f"👤 Membre : **{utilisateur}**")
with c_refresh: 
    if st.button("🔄 Actualiser"): refresh()
with c_logout:
    if st.button("🚪 Quitter"):
        st.session_state.connecte = False; st.session_state.user = None; st.rerun()

mes_demandes_urgentes = df_livres[(df_livres[COL["Proprio"]] == utilisateur) & (df_livres[COL["Statut"]] == "Demandé")]
nb_d = len(mes_demandes_urgentes)
if nb_d > 0: st.warning(f"🔔 **Alerte** : Tu as {nb_d} nouvelle(s) demande(s) !")

st.write("---")
onglets_noms = ["📖 Bibliothèque", f"🤝 Demandes ({nb_d})", "👤 Mon Profil", "➕ Ajouter"]
if utilisateur in ["Didier", "Amélie"]: onglets_noms.append("⚙️ Gérance")
onglets_noms.append("❓ Mode d'emploi")

onglets = st.tabs(onglets_noms)

# --- 1. BIBLIOTHÈQUE ---
with onglets[0]:
    recherche_bib = st.text_input("🔍 Rechercher...", "").lower()
    tri = st.selectbox("Trier par", ["Derniers ajouts", "Note", "Titre (A-Z)", "📗 Disponible uniquement"])
    df_tri = df_livres.copy()
    if tri == "📗 Disponible uniquement": df_tri = df_tri[df_tri[COL["Statut"]] == "Libre"]
    if recherche_bib:
        df_tri = df_tri[df_tri[COL["Titre"]].astype(str).str.lower().str.contains(recherche_bib) | 
                        df_tri[COL["Auteur"]].astype(str).str.lower().str.contains(recherche_bib) |
                        df_tri[COL["Cat"]].astype(str).str.lower().str.contains(recherche_bib)]
    
    if tri == "Titre (A-Z)": df_tri = df_tri.sort_values(by=COL["Titre"])
    elif tri == "Note": df_tri = df_tri.sort_values(by=COL["Note"], ascending=False)
    else: df_tri = df_tri.iloc[::-1]

    for idx, row in df_tri.iterrows():
        statut, p_livre = str(row[COL["Statut"]]), str(row[COL["Proprio"]])
        cat_livre = str(row.get(COL["Cat"], ""))
        emoji, color = ("📗", "green") if statut == "Libre" else (("⏳", "orange") if statut == "Demandé" else ("📕", "red"))
        
        with st.container():
            st.markdown(f"#### {emoji} {row[COL['Titre']]} {row.get(COL['Note'], '')}")
            txt_cat = f" | 🏷️ {cat_livre}" if cat_livre else ""
            st.markdown(f"*{row[COL['Auteur']]}*{txt_cat} — Proprio : **{p_livre}** | :{color}[**({statut})**]")
            c_act, c_av = st.columns([1.5, 3])
            with c_act:
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
            with c_av:
                if row.get(COL['Avis']): st.caption(f"⭐ **Proprio :** {row[COL['Avis']]}")
                if row.get(COL['Avis_Lecteurs']):
                    with st.expander("💬 Voir les avis"): st.markdown(row[COL['Avis_Lecteurs']])
            st.markdown("<hr style='margin:10px 0px'>", unsafe_allow_html=True)

# --- 2. DEMANDES ---
with onglets[1]:
    st.subheader("⏳ Demandes à traiter")
    search_dem = st.text_input("🔍 Filtrer les demandes...").lower()
    df_dem_filtered = mes_demandes_urgentes.copy()
    if search_dem:
        df_dem_filtered = df_dem_filtered[df_dem_filtered[COL["Titre"]].str.lower().str.contains(search_dem) | 
                                          df_dem_filtered[COL["Emprunteur"]].str.lower().str.contains(search_dem)]

    if not df_dem_filtered.empty:
        for idx, r in df_dem_filtered.iterrows():
            emp = r[COL["Emprunteur"]]
            st.info(f"👉 **{emp}** attend : **{r[COL['Titre']]}**")
            c1, c2 = st.columns(2)
            with c1:
                if st.button(f"✅ Valider", key=f"v_{idx}"):
                    oidx = int(df_livres.index[df_livres[COL['Titre']] == r[COL['Titre']]][0] + 2)
                    sheet_livres.update_cell(oidx, 5, "Emprunté")
                    st.success("Validé !"); st.link_button("📱 WhatsApp", envoyer_whatsapp(f"C'est OK pour '{r[COL['Titre']]}'. On s'organise ?"))
            with c2:
                if st.button(f"❌ Décliner", key=f"d_{idx}"):
                    oidx = int(df_livres.index[df_livres[COL['Titre']] == r[COL['Titre']]][0] + 2)
                    sheet_livres.update_cell(oidx, 5, "Libre"); sheet_livres.update_cell(oidx, 6, ""); refresh()
    else: st.write("Aucune nouvelle demande.")

# --- 3. PROFIL ---
with onglets[2]:
    st.write(f"## 👤 Profil de {utilisateur}")
    st.markdown("""<div style="display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 20px;">
            <a href="#prets" style="text-decoration: none; background-color: #f0f2f6; color: #31333F; padding: 5px 12px; border-radius: 5px; border: 1px solid #dcdcdc; font-size: 13px;">📤 Prêts</a>
            <a href="#emprunts" style="text-decoration: none; background-color: #f0f2f6; color: #31333F; padding: 5px 12px; border-radius: 5px; border: 1px solid #dcdcdc; font-size: 13px;">📥 Emprunts</a>
            <a href="#collection" style="text-decoration: none; background-color: #f0f2f6; color: #31333F; padding: 5px 12px; border-radius: 5px; border: 1px solid #dcdcdc; font-size: 13px;">📚 Collection</a>
            <a href="#support" style="text-decoration: none; background-color: #f0f2f6; color: #31333F; padding: 5px 12px; border-radius: 5px; border: 1px solid #dcdcdc; font-size: 13px;">🛠️ Support</a>
        </div>""", unsafe_allow_html=True)

    search_prof = st.text_input("🔍 Rechercher dans mon historique...", "").lower()

    st.markdown('<div id="prets"></div>', unsafe_allow_html=True)
    st.write("### 📤 Mes livres en voyage (Prêts)")
    mes_sorties = df_livres[(df_livres[COL["Proprio"]] == utilisateur) & (df_livres[COL["Statut"]] != "Libre")]
    if search_prof:
        mes_sorties = mes_sorties[mes_sorties[COL["Titre"]].astype(str).str.lower().str.contains(search_prof) | 
                                  mes_sorties[COL["Auteur"]].astype(str).str.lower().str.contains(search_prof) |
                                  mes_sorties[COL["Emprunteur"]].astype(str).str.lower().str.contains(search_prof)]
    if not mes_sorties.empty:
        for idx, rs in mes_sorties.iterrows():
            stat_txt = "⏳ Attente" if rs[COL["Statut"]] == "Demandé" else "📕 Prêté"
            with st.container():
                cc1, cc2, cc3 = st.columns([3, 1.5, 1])
                cc1.write(f"**{rs[COL['Titre']]}**\n({rs[COL['Auteur']]}) - Emprunté par : {rs[COL['Emprunteur']]}")
                cc2.write(stat_txt)
                with cc3:
                    if st.button("🔄 Rendu", key=f"rendu_{idx}"):
                        oidx = int(df_livres.index[df_livres[COL['Titre']] == rs[COL['Titre']]][0] + 2)
                        sheet_livres.update_cell(oidx, 5, "Libre"); sheet_livres.update_cell(oidx, 6, ""); refresh()
                st.markdown("---")
    else: st.info("Aucun résultat.")

    st.write("---")
    st.markdown('<div id="emprunts"></div>', unsafe_allow_html=True)
    st.write("### 📥 Livres que j'ai empruntés")
    mes_emprunts = df_livres[(df_livres[COL["Emprunteur"]] == utilisateur) & (df_livres[COL["Statut"]] != "Libre")]
    if search_prof:
        mes_emprunts = mes_emprunts[mes_emprunts[COL["Titre"]].astype(str).str.lower().str.contains(search_prof) | 
                                    mes_emprunts[COL["Auteur"]].astype(str).str.lower().str.contains(search_prof) |
                                    mes_emprunts[COL["Proprio"]].astype(str).str.lower().str.contains(search_prof)]
    if not mes_emprunts.empty:
        recap_e = mes_emprunts[[COL["Titre"], COL["Auteur"], COL["Proprio"], COL["Statut"]]].copy()
        recap_e[COL["Statut"]] = recap_e[COL["Statut"]].replace({"Demandé": "⏳ En attente", "Emprunté": "🏠 Chez moi"})
        st.table(recap_e)
    
    st.write("---")
    st.markdown('<div id="collection"></div>', unsafe_allow_html=True)
    st.write("### 📚 Ma collection complète")
    mes_l = df_livres[df_livres[COL["Proprio"]] == utilisateur]
    if search_prof:
        mes_l = mes_l[mes_l[COL["Titre"]].astype(str).str.lower().str.contains(search_prof) | 
                      mes_l[COL["Auteur"]].astype(str).str.lower().str.contains(search_prof)]
    if not mes_l.empty:
        for idx, r in mes_l.iterrows():
            with st.expander(f"📙 {r[COL['Titre']]} - {r[COL['Auteur']]} ({r[COL['Statut']]})"):
                if st.button("❌ Supprimer définitivement", key=f"del_{idx}"):
                    oidx = int(df_livres.index[df_livres[COL['Titre']] == r[COL['Titre']]][0] + 2); sheet_livres.delete_rows(oidx); refresh()

    st.write("---")
    st.subheader("💡 Une idée ? Un problème ?")
    with st.expander("🛠️ Signaler un bug ou faire une suggestion"):
        msg_bug = st.text_area("Votre message")
        type_msg = st.selectbox("Type", ["Suggestion", "Bug"])
        c_m, c_w = st.columns(2)
        with c_m:
            st.link_button("📧 Mail", generer_lien_mail(f"Meli-Melo - {type_msg}", f"Message de {utilisateur}:\n{msg_bug}"))
        with c_w:
            st.link_button("📱 WhatsApp", envoyer_whatsapp(f"*Méli-Mélo Support*\n{utilisateur}: {msg_bug}"))

# --- 4. AJOUTER ---
with onglets[3]:
    mode = st.radio("Méthode :", ["✅ Manuel", "📤 Importer"], horizontal=True)
    if mode == "✅ Manuel":
        with st.form("add"):
            t, a = st.text_input("Titre"), st.text_input("Auteur")
            cat = st.selectbox("Catégorie", LISTE_CATS)
            n, c = st.select_slider("Note", ["📚","📚📚","📚📚📚","📚📚📚📚"]), st.text_area("Avis")
            if st.form_submit_button("Ajouter"):
                # SÉCURITÉ : On vérifie la connexion JUSTE AVANT l'ajout
                try:
                    sheet_livres.append_row([t, a, utilisateur, c, "Libre", "", n, datetime.now().strftime("%Y-%m-%d"), "", cat])
                    refresh()
                except Exception:
                    st.error("Session expirée. Reconnexion en cours...")
                    refresh()
    else:
        st.link_button("📥 Modèle Excel", "https://raw.githubusercontent.com/didierjaccoud144-bit/BiblioClub/main/BiblioMod.xlsx")
        up = st.file_uploader("Fichier Excel", type="xlsx")
        if up and st.button("Lancer"):
            df_i = pd.read_excel(up).fillna("")
            lignes = [[str(ri['Titre']), str(ri.get('Auteur','')), utilisateur, str(ri.get('Avis','')), "Libre", "", str(ri.get('Note','📚📚')), datetime.now().strftime("%Y-%m-%d"), "", str(ri.get('Catégorie', 'Autre'))] for _, ri in df_i.iterrows()]
            sheet_livres.append_rows(lignes); refresh()

# --- 5. GÉRANCE ---
if utilisateur in ["Didier", "Amélie"]:
    with onglets[4]:
        st.subheader("⚙️ Gérance")
        with st.form("nm"):
            n, s, t, p, r = st.text_input("Prénom"), st.text_input("Code Secret"), st.text_input("Tél"), st.text_input("Lieu"), st.text_input("Retrait")
            if st.form_submit_button("Créer"): sheet_membres.append_row([n, s, t, "", p, r]); refresh()

# --- 6. MODE D'EMPLOI ---
with onglets[-1]:
    st.title("📖 Mode d'emploi Méli-Mélo")
    with st.expander("📱 1. Installation", expanded=True):
        st.markdown("* **iPhone (Safari)** : Partage -> « Sur l'écran d'accueil ».\n* **Android (Chrome)** : 3 points -> « Installer l'application ».")
    with st.expander("🔐 2. Connexion"):
        st.markdown("Choisissez votre prénom et entrez votre code secret.")
    with st.expander("🔍 3. Recherche"):
        st.markdown("Filtrez par Titre, Auteur ou Catégorie.")
    with st.expander("🤝 4. Emprunter / Prêter"):
        st.markdown("Demande -> Validation -> WhatsApp. Une fois rendu, cliquez sur **🔄 Rendu**.")
    with st.expander("💬 5. Avis"):
        st.markdown("Notez vos lectures sous chaque livre.")
    with st.expander("👤 6. Profil & Support"):
        st.markdown("Gérez vos livres et utilisez le bouton **🛠️ Support** pour nous contacter.")

st.caption("Une création DJA’WEB avec l’aide de Gemini IA")
