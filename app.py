import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import urllib.parse
import io

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

# --- INTERFACE PRINCIPALE ---
st.title("📚 Le Biblio Club")
utilisateur = st.selectbox("👤 Qui êtes-vous ?", df_membres[col_p].tolist())
infos_user = df_membres[df_membres[col_p] == utilisateur].iloc[0]

# --- LOGIQUE D'ALERTE ET BANNIÈRE FLASH ---
mes_livres_p = df_livres[df_livres[c_proprio].astype(str).str.strip() == utilisateur.strip()]
nb_demandes = len(mes_livres_p[mes_livres_p[c_statut] == "Demandé"])

if nb_demandes > 0:
    icon_profil = f"🔔 ({nb_demandes}) DEMANDE 🙋"
    st.toast(f"Salut {utilisateur} ! Tu as {nb_demandes} demande(s) en attente. 📢", icon="🙋")
else:
    icon_profil = "👤 Mon Profil"

st.write("---")

# --- NAVIGATION ---
menu = ["📖 Bibliothèque", "🤝 Emprunts", icon_profil, "➕ Ajouter", "📤 Import"]
if utilisateur in ["Didier", "Amélie"]: menu.append("⚙️ Admin")
onglets = st.tabs(menu)

# --- 1. BIBLIOTHÈQUE ---
with onglets[0]:
    for idx, row in df_livres.iloc[::-1].iterrows():
        s = str(row.get(c_statut, 'Libre')).strip()
        statut = s if s != "" else "Libre"
        icone, color = ("📗", "green") if statut == "Libre" else ("📙", "orange") if statut == "Demandé" else ("📕", "red")
        
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
    st.subheader("🤝 Livres en mouvement")
    mask = df_livres[c_statut].isin(['Demandé', 'Emprunté'])
    if not df_livres[mask].empty:
        st.table(df_livres[mask][[c_titre, c_proprio, c_squat, c_statut]])
    else: st.info("Tous les livres sont chez leurs maîtres.")

# --- 3. MON PROFIL ---
with onglets[2]:
    st.subheader(f"Espace de {utilisateur}")
    demandes_recues = mes_livres_p[mes_livres_p[c_statut] == "Demandé"]
    if not demandes_recues.empty:
        st.warning(f"Vous avez {len(demandes_recues)} demande(s) à traiter")
        for idx, row in demandes_recues.iterrows():
            demandeur = row.get(c_squat)
            st.write(f"👉 **{demandeur}** veut **{row[c_titre]}**")
            cb1, cb2 = st.columns(2)
            with cb1:
                if st.button("✅ Accepter", key=f"ok_{idx}"):
                    sheet_livres.update_cell(idx + 2, list(df_livres.columns).index(c_statut)+1, "Emprunté")
                    tel_d = df_membres[df_membres[col_p] == demandeur].iloc[0].get('Téléphone', '')
                    msg = f"Hello {demandeur} ! C'est {utilisateur}. Ton prêt pour '{row[c_titre]}' est OK ! 😊"
                    st.link_button("📱 WhatsApp", envoyer_wa(tel_d, msg))
            with cb2:
                if st.button("❌ Refuser", key=f"no_{idx}"):
                    sheet_livres.update_cell(idx + 2, list(df_livres.columns).index(c_statut)+1, "Libre")
                    sheet_livres.update_cell(idx + 2, list(df_livres.columns).index(c_squat)+1, "")
                    tel_d = df_membres[df_membres[col_p] == demandeur].iloc[0].get('Téléphone', '')
                    msg_ref = f"Désolé {demandeur}, je ne peux pas prêter '{row[c_titre]}' pour le moment."
                    st.link_button("📱 Prévenir WA", envoyer_wa(tel_d, msg_ref))
            st.write("---")
    
    livres_pretes = mes_livres_p[mes_livres_p[c_statut] == "Emprunté"]
    if not livres_pretes.empty:
        st.subheader("📚 Mes livres prêtés")
        for idx, row in livres_pretes.iterrows():
            st.write(f"🤝 **{row[c_titre]}** est chez {row[c_squat]}")
            if st.button(f"🔄 Rendu", key=f"ret_{idx}"):
                sheet_livres.update_cell(idx + 2, list(df_livres.columns).index(c_statut)+1, "Libre")
                sheet_livres.update_cell(idx + 2, list(df_livres.columns).index(c_squat)+1, "")
                st.rerun()
            st.write("---")

    st.subheader("📤 Mes demandes envoyées")
    mes_demandes = df_livres[df_livres[c_squat].astype(str).str.strip() == utilisateur.strip()]
    if not mes_demandes.empty:
        for _, row in mes_demandes.iterrows():
            s_envoi = row[c_statut]
            st.write(f"{'⏳' if s_envoi == 'Demandé' else '✅'} **{row[c_titre]}** (chez {row[c_proprio]})")
    else: st.write("Aucune demande en cours.")

# --- 4. AJOUTER ---
with onglets[3]:
    with st.form("add"):
        t, a = st.text_input("Titre"), st.text_input("Auteur")
        n = st.select_slider("Note", options=["📚","📚📚","📚📚📚","📚📚📚📚"])
        if st.form_submit_button("Ajouter"):
            sheet_livres.append_row(["", t, a, utilisateur, "", "", n, "Libre"])
            st.rerun()

# --- 5. IMPORT (VERSION PÉDAGOGIQUE) ---
with onglets[4]:
    st.subheader("📤 Import groupé")
    
    with st.expander("❓ Guide : Comment importer ?", expanded=False):
        st.markdown("""
        1. **Téléchargez** le modèle Excel vert ci-dessous.
        2. **Remplissez** vos livres dans le tableau (sans toucher aux titres).
        3. **Déposez** le fichier fini dans la zone ci-dessous.
        """)

    # Génération du modèle Excel
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        pd.DataFrame(columns=["Titre", "Auteur", "Avis_Delire"]).to_excel(writer, index=False, sheet_name='Modèle')
    
    st.download_button(
        label="📥 Télécharger le modèle Excel (.xlsx)",
        data=output.getvalue(),
        file_name="modele_biblio.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    
    st.write("---")
    up = st.file_uploader("Déposez votre fichier ici", type="xlsx")
    if up and st.button("🚀 Lancer l'import"):
        df_im = pd.read_excel(up)
        for _, r in df_im.iterrows():
            sheet_livres.append_row(["", r['Titre'], r.get('Auteur',''), utilisateur, "", "", r.get('Avis_Delire',''), "Libre"])
        st.success("Import réussi !"); st.rerun()

# --- 6. ADMIN ---
if utilisateur in ["Didier", "Amélie"]:
    with onglets[5]:
        st.subheader("⚙️ Admin")
        with st.form("mbr"):
            p, t, c = st.text_input("Prénom"), st.text_input("Tel"), st.text_area("Infos Retrait")
            if st.form_submit_button("Ajouter membre"):
                sheet_membres.append_row([p, t, c]); st.success("Membre ajouté !"); st.rerun()

st.caption("Une création DJA’WEB avec l’aide de Gemini IA")
