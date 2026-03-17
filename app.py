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

# Vider le cache pour forcer la mise à jour des données à chaque action
st.cache_data.clear()

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
    sheet_membres = spreadsheet.worksheet("Membres")
    data = sheet_livres.get_all_records()
    cols_def = ["Titre", "Auteur", "Propriétaire", "Avis_delire", "Statut", "Emprunteur", "Note", "Date_Ajout", "Avis_Lecteurs"]
    df_livres = pd.DataFrame(data) if data else pd.DataFrame(columns=cols_def)
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

# --- INTERFACE ---
st.title(" La boîte à livres à Méli-Mélo ")

liste_membres = get_liste_membres_fixes()
utilisateur = st.selectbox("Utilisateur", liste_membres, key='user', label_visibility="collapsed")
infos_user = get_membre_info(utilisateur)

# --- LOGIQUE NOTIFICATION FLASH ---
has_notif = False
nb_demandes = 0
if not df_livres.empty:
    mes_demandes_en_attente = df_livres[(df_livres[COL["Proprio"]] == utilisateur) & (df_livres[COL["Statut"]] == "Demandé")]
    nb_demandes = len(mes_demandes_en_attente)
    if nb_demandes > 0:
        has_notif = True
        # Notification FLASH en haut de page
        st.warning(f"🔔 **{utilisateur}**, tu as {nb_demandes} demande(s) d'emprunt en attente dans l'onglet Emprunts !")

nom_onglet_emprunt = f"🤝 Emprunts ({nb_demandes})" if has_notif else "🤝 Emprunts"

st.write("---")
onglets_noms = ["❓ Mode d'emploi", "📖 Bibliothèque", nom_onglet_emprunt, "👤 Mon Profil", "➕ Ajouter"]
if utilisateur in ["Didier", "Amélie"]:
    onglets_noms.append("👤 Ajouter un membre")
onglets = st.tabs(onglets_noms)

# --- 0. MODE D'EMPLOI ---
with onglets[0]:
    st.subheader("🚀 Guide du lecteur")
    st.markdown("""
    * 📗 **Livre Vert** : Disponible !
    * 📙 **Livre Orange** : En attente du propriétaire.
    * 📕 **Livre Rouge** : En prêt.
    * 💬 **Avis** : Tu peux ajouter ton avis sur n'importe quel livre, même si tu ne l'empruntes pas !
    """)

# --- 1. BIBLIOTHÈQUE ---
with onglets[1]:
    if df_livres.empty:
        st.info("La boîte est vide.")
    else:
        tri = st.selectbox("Trier par", ["Derniers ajouts", "Note", "Titre (A-Z)"])
        df_tri = df_livres.copy()
        if tri == "Titre (A-Z)": df_tri = df_tri.sort_values(by=COL["Titre"])
        elif tri == "Note": df_tri = df_tri.sort_values(by=COL["Note"], ascending=False)
        else: df_tri = df_tri.iloc[::-1]

        for idx, row in df_tri.iterrows():
            statut = str(row.get(COL["Statut"], 'Libre')).strip() or "Libre"
            p_livre = str(row[COL["Proprio"]]).strip()
            emoji, color = ("📗", "green") if statut == "Libre" else (("📙", "orange") if statut == "Demandé" else ("📕", "red"))
            
            with st.container():
                c1, c2 = st.columns([1, 4])
                with c1: st.title(emoji)
                with c2:
                    st.markdown(f"### {row[COL['Titre']]} {row.get(COL['Note'], '')} :{color}[ ({statut})]")
                    st.write(f"**{row[COL['Auteur']]}** | **Propriétaire :** {p_livre}")
                    
                    if row.get(COL['Avis']): st.success(f"⭐ **Proprio :** {row[COL['Avis']]}")
                    if row.get(COL['Avis_Lecteurs']):
                        with st.expander("💬 Avis des lecteurs"): st.markdown(row[COL['Avis_Lecteurs']])
                    
                    # AJOUT AVIS LIBRE
                    with st.expander("📝 Donner mon avis sur ce livre"):
                        n_l = st.select_slider("Note", options=["📚", "📚📚", "📚📚📚", "📚📚📚📚"], key=f"n_{idx}")
                        c_l = st.text_area("Commentaire", key=f"c_{idx}")
                        if st.button("Publier", key=f"p_{idx}"):
                            oidx = df_livres.index[df_livres[COL['Titre']] == row[COL['Titre']]][0] + 2
                            total = (str(row.get(COL["Avis_Lecteurs"], "")) + f"\n\n**{utilisateur}** ({n_l}) : {c_l}").strip()
                            sheet_livres.update_cell(oidx, 9, total)
                            st.rerun()

                    if statut == "Libre" and p_livre != utilisateur.strip():
                        if st.button(f"Demander", key=f"req_{idx}"):
                            oidx = df_livres.index[df_livres[COL['Titre']] == row[COL['Titre']]][0] + 2
                            sheet_livres.update_cell(oidx, 5, "Demandé")
                            sheet_livres.update_cell(oidx, 6, utilisateur)
                            st.rerun()
                st.write("---")

# --- 2. EMPRUNTS ---
with onglets[2]:
    st.subheader("🤝 Mes échanges")
    res = df_livres[(df_livres[COL["Proprio"]] == utilisateur) & (df_livres[COL["Statut"]].isin(['Demandé', 'Emprunté']))]
    if not res.empty:
        for idx, r in res.iterrows():
            emp = r[COL["Emprunteur"]]
            st.info(f"🔔 **{emp}** -> **{r[COL['Titre']]}**")
            if r[COL["Statut"]] == "Demandé":
                col1, col2 = st.columns(2)
                with col1:
                    if st.button(f"✅ Valider", key=f"v_{idx}"):
                        oidx = df_livres.index[df_livres[COL['Titre']] == r[COL['Titre']]][0] + 2
                        sheet_livres.update_cell(oidx, 5, "Emprunté")
                        st.link_button("📱 WhatsApp", envoyer_whatsapp(f"OK pour '{r[COL['Titre']]}'. On s'appelle ?"))
                with col2:
                    if st.button(f"❌ Décliner", key=f"d_{idx}"):
                        oidx = df_livres.index[df_livres[COL['Titre']] == r[COL['Titre']]][0] + 2
                        sheet_livres.update_cell(oidx, 5, "Libre"); sheet_livres.update_cell(oidx, 6, "")
                        st.link_button("📱 WhatsApp", envoyer_whatsapp(f"Désolé, pas dispo pour '{r[COL['Titre']]}'."))
            elif r[COL["Statut"]] == "Emprunté":
                if st.button(f"🔄 Marquer comme rendu", key=f"r_{idx}"):
                    oidx = df_livres.index[df_livres[COL['Titre']] == r[COL['Titre']]][0] + 2
                    sheet_livres.update_cell(oidx, 5, "Libre"); sheet_livres.update_cell(oidx, 6, ""); st.rerun()
    else: st.write("Aucune demande reçue.")

# --- 3. PROFIL & 4. AJOUTER ---
# [Le reste du code Profil et Ajouter est identique et complet]
with onglets[3]:
    st.subheader(f"👤 {utilisateur}")
    with st.form("sugg"):
        s = st.text_input("Suggérer un membre (Nom)")
        if st.form_submit_button("WhatsApp Admin"):
            st.link_button("📱 Envoyer", envoyer_whatsapp(f"Sugg : {s}"))
    st.write("---")
    mes_l = df_livres[df_livres[COL["Proprio"]] == utilisateur]
    for idx, r in mes_l.iterrows():
        with st.expander(f"📙 {r[COL['Titre']]}"):
            if st.button("Supprimer", key=f"del_{idx}"):
                oidx = df_livres.index[df_livres[COL['Titre']] == r[COL['Titre']]][0] + 2
                sheet_livres.delete_rows(oidx); st.rerun()

with onglets[4]:
    mode = st.radio("", ["✅ Manuel", "📤 Import Excel"], horizontal=True)
    if mode == "✅ Manuel":
        with st.form("a"):
            t, a, n, c = st.text_input("Titre"), st.text_input("Auteur"), st.select_slider("Note", ["📚","📚📚","📚📚📚","📚📚📚📚"]), st.text_area("Avis")
            if st.form_submit_button("Ajouter"):
                sheet_livres.append_row([t, a, utilisateur, c, "Libre", "", n, datetime.now().strftime("%Y-%m-%d"), ""]); st.rerun()
    else:
        st.link_button("📥 Modèle Excel", "https://raw.githubusercontent.com/didierjaccoud144-bit/BiblioClub/main/BiblioMod.xlsx")
        up = st.file_uploader("Excel", type="xlsx")
        if up and st.button("Importer"):
            df_i = pd.read_excel(up).fillna("")
            for _, r in df_i.iterrows():
                sheet_livres.append_row([r['Titre'], r.get('Auteur',''), utilisateur, r.get('Avis',''), "Libre", "", r.get('Note',''), datetime.now().strftime("%Y-%m-%d"), ""]); st.rerun()

if utilisateur in ["Didier", "Amélie"]:
    with onglets[-1]:
        st.subheader("👤 Ajouter un membre")
        with st.form("nm"):
            n, t, p, r = st.text_input("Prénom"), st.text_input("Tél"), st.text_input("Lieu"), st.text_input("Retrait")
            if st.form_submit_button("Enregistrer"):
                sheet_membres.append_row([n, t, "", p, r]); st.success("Fait !")

st.caption("Une création DJA’WEB avec l’aide de Gemini IA")
