import streamlit as st
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import joblib, os, warnings
warnings.filterwarnings('ignore')

st.set_page_config(page_title='Scoring Credit', page_icon='🏦', layout='wide')

BASE = '/content'

@st.cache_resource
def load_all():
    m = joblib.load(os.path.join(BASE, 'modele_champion.pkl'))
    s = joblib.load(os.path.join(BASE, 'seuil_optimal.pkl'))
    f = joblib.load(os.path.join(BASE, 'feature_names.pkl'))
    X = pd.read_csv(os.path.join(BASE, 'X_features.csv'))
    y = pd.read_csv(os.path.join(BASE, 'y_target.csv')).squeeze()
    return m, s, f, X, y

try:
    modele, SEUIL, features, X_all, y_all = load_all()
except Exception as e:
    st.error(f'Erreur chargement : {e}')
    st.stop()

def add_features(df):
    df = df.copy()
    df['alerte_financiere']   = df['ratio_endettement'] * (1 / (df['nb_transactions_30j'] + 1))
    df['client_fantome']      = df['jours_depuis_derniere_trans'] / (df['anciennete_mobile_money_mois'] + 1)
    df['pression_pret']       = df['montant_demande_fcfa'] / (df['montant_total_fcfa'] + 1)
    df['instabilite']         = df['montant_max_fcfa'] / (df['montant_moyen_fcfa'] + 1)
    df['dependance_credit']   = df['nb_achat_credit'] / (df['nb_transactions_total'] + 1)
    df['score_vulnerabilite'] = (df['ratio_endettement']*3.0 + df['ratio_retrait_depot']*2.0
                                + df['recence_normalisee']*1.5 - df['engagement_paiement']*2.0
                                - df['ratio_volume_trans_pret']*1.0)
    df['score_rfm']           = (df['nb_transactions_total']*0.4 + df['montant_total_fcfa']*0.0001
                                + (1/(df['jours_depuis_derniere_trans']+1))*100)
    df['engagement_client']   = (df['anciennete_mobile_money_mois']
                                * df['intensite_utilisation'] * df['engagement_paiement'])
    return df

X_enrichi   = add_features(X_all)
y_proba_all = modele.predict_proba(X_enrichi)[:, 1]
y_pred_all  = (y_proba_all >= SEUIL).astype(int)

st.title('🏦 Dashboard Scoring Credit')
st.caption('Modele LightGBM · Seuil 0.30 · Direction Generale')
st.markdown('---')

onglet = st.sidebar.radio('Navigation', [
    '📊 Vue Generale',
    '🔍 Analyse Client',
    '📈 Performance',
    '💰 Impact Business'
])

if onglet == '📊 Vue Generale':
    st.subheader('Indicateurs cles du portefeuille')
    c1, c2, c3, c4 = st.columns(4)
    c1.metric('Total dossiers',  f'{len(y_all):,}')
    c2.metric('Taux de defaut',  f'{y_all.mean()*100:.1f}%')
    c3.metric('AUC du modele',   '0.62')
    c4.metric('Defauts evites',  '30 / 40')
    st.markdown('---')
    col1, col2 = st.columns(2)
    with col1:
        st.markdown('**Distribution des scores de risque**')
        fig, ax = plt.subplots(figsize=(6,3))
        ax.hist(y_proba_all[y_all==0], bins=20, alpha=0.6,
                color='#2196F3', label='Non defaut', density=True)
        ax.hist(y_proba_all[y_all==1], bins=20, alpha=0.6,
                color='#F44336', label='Defaut', density=True)
        ax.axvline(SEUIL, color='orange', linestyle='--',
                   linewidth=2, label=f'Seuil {SEUIL}')
        ax.set_xlabel('Score de risque')
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.2)
        st.pyplot(fig)
        plt.close()
    with col2:
        st.markdown('**Decisions du modele**')
        fig, axes = plt.subplots(1, 2, figsize=(6,3))
        vc = y_all.value_counts().sort_index()
        axes[0].pie(vc, labels=['Non defaut','Defaut'],
                    autopct='%1.1f%%', colors=['#2196F3','#F44336'],
                    startangle=90, wedgeprops={'edgecolor':'white'})
        axes[0].set_title('Reel', fontsize=9)
        pvc = pd.Series(y_pred_all).value_counts().sort_index()
        axes[1].pie(pvc, labels=['Accorde','Refuse'],
                    autopct='%1.1f%%', colors=['#4CAF50','#FF9800'],
                    startangle=90, wedgeprops={'edgecolor':'white'})
        axes[1].set_title('Modele', fontsize=9)
        st.pyplot(fig)
        plt.close()

elif onglet == '🔍 Analyse Client':
    st.subheader('Simulateur de scoring client')
    st.info('Remplissez le profil et cliquez sur Calculer.')

    st.markdown('**Profil personnel**')
    col1, col2, col3 = st.columns(3)
    age_s        = col1.text_input('Age', '35')
    revenu_s     = col2.text_input('Revenu mensuel (FCFA)', '150000')
    anciennete_s = col3.text_input('Anciennete mobile money (mois)', '18')

    st.markdown('**Informations du pret**')
    col4, col5 = st.columns(2)
    montant_s = col4.text_input('Montant demande (FCFA)', '300000')
    duree_s   = col5.text_input('Duree (mois) — ex: 3, 6, 9, 12, 18, 24', '12')

    st.markdown('**Transactions**')
    col6, col7, col8 = st.columns(3)
    nb_trans_30j_s   = col6.text_input('Transactions 30j', '20')
    nb_trans_total_s = col7.text_input('Transactions total', '80')
    montant_total_s  = col8.text_input('Volume total (FCFA)', '800000')

    col9, col10, col11 = st.columns(3)
    montant_moyen_s  = col9.text_input('Montant moyen (FCFA)', '15000')
    montant_max_s    = col10.text_input('Montant max (FCFA)', '45000')
    montant_std_s    = col11.text_input('Ecart-type (FCFA)', '12000')

    col12, col13, col14 = st.columns(3)
    nb_retraits_s    = col12.text_input('Retraits', '25')
    nb_depots_s      = col13.text_input('Depots', '20')
    nb_paiements_s   = col14.text_input('Paiements factures', '15')

    col15, col16, col17 = st.columns(3)
    nb_transferts_s  = col15.text_input('Transferts', '10')
    nb_achat_s       = col16.text_input('Achats credit', '10')
    jours_recence_s  = col17.text_input('Jours depuis derniere transaction', '15')

    col18, col19 = st.columns(2)
    nb_types_s      = col18.text_input('Types distincts', '3')
    nb_operateurs_s = col19.text_input('Operateurs distincts', '1')

    st.markdown('')
    calculer = st.button('🎯 Calculer le score de risque', use_container_width=True)

    if calculer:
        try:
            age             = float(age_s)
            revenu          = float(revenu_s)
            anciennete      = float(anciennete_s)
            montant         = float(montant_s)
            duree           = float(duree_s)
            nb_trans_30j    = float(nb_trans_30j_s)
            nb_trans_total  = float(nb_trans_total_s)
            montant_total   = float(montant_total_s)
            montant_moyen   = float(montant_moyen_s)
            montant_max     = float(montant_max_s)
            montant_std     = float(montant_std_s)
            nb_retraits     = float(nb_retraits_s)
            nb_depots       = float(nb_depots_s)
            nb_paiements    = float(nb_paiements_s)
            nb_transferts   = float(nb_transferts_s)
            nb_achat_credit = float(nb_achat_s)
            jours_recence   = float(jours_recence_s)
            nb_types        = float(nb_types_s)
            nb_operateurs   = float(nb_operateurs_s)

            charge_mens   = montant / duree
            ratio_endet   = charge_mens / revenu
            cap_rembours  = revenu - charge_mens
            tot           = nb_trans_total + 1
            intensite     = nb_trans_total / (anciennete + 1)
            ratio_vol_pr  = montant_total / (montant + 1)
            ratio_ret_dep = nb_retraits / (nb_depots + 1)
            engage_paie   = nb_paiements / tot
            recence_norm  = jours_recence / 181

            input_dict = {
                'montant_demande_fcfa'         : montant,
                'duree_mois'                   : duree,
                'nb_transactions_30j'          : nb_trans_30j,
                'age'                          : age,
                'revenu_mensuel_fcfa'           : revenu,
                'anciennete_mobile_money_mois'  : anciennete,
                'nb_transactions_total'         : nb_trans_total,
                'montant_total_fcfa'            : montant_total,
                'montant_moyen_fcfa'            : montant_moyen,
                'montant_max_fcfa'              : montant_max,
                'montant_std_fcfa'              : montant_std,
                'nb_types_distincts'            : nb_types,
                'nb_operateurs_distincts'       : nb_operateurs,
                'jours_depuis_derniere_trans'   : jours_recence,
                'nb_achat_credit'               : nb_achat_credit,
                'nb_depot'                     : nb_depots,
                'nb_paiement_facture'           : nb_paiements,
                'nb_retrait'                   : nb_retraits,
                'nb_transfert'                 : nb_transferts,
                'charge_mensuelle_fcfa'         : charge_mens,
                'ratio_endettement'             : ratio_endet,
                'capacite_remboursement'        : cap_rembours,
                'ratio_montant_revenu_annuel'   : montant / (revenu * 12),
                'montant_par_mois'              : charge_mens,
                'intensite_utilisation'         : intensite,
                'ratio_moy_trans_revenu'        : montant_moyen / revenu,
                'ratio_volume_trans_pret'       : ratio_vol_pr,
                'regularite_transactions'       : montant_std / (montant_moyen + 1),
                'ratio_trans_30j_total'         : nb_trans_30j / tot,
                'score_diversification'         : nb_types * nb_operateurs,
                'recence_normalisee'            : recence_norm,
                'actif_30j'                    : int(jours_recence <= 30),
                'actif_7j'                     : int(jours_recence <= 7),
                'pct_achat_credit'              : nb_achat_credit / tot,
                'pct_depot'                    : nb_depots / tot,
                'pct_paiement_facture'          : nb_paiements / tot,
                'pct_retrait'                  : nb_retraits / tot,
                'pct_transfert'                : nb_transferts / tot,
                'ratio_retrait_depot'           : ratio_ret_dep,
                'engagement_paiement'           : engage_paie,
                'tranche_age'                  : (0 if age<25 else 1 if age<35 else 2 if age<45 else 3),
                'segment_anciennete'            : (0 if anciennete<=6 else 1 if anciennete<=18 else 2 if anciennete<=36 else 3),
                'segment_revenu'               : (0 if revenu<80000 else 1 if revenu<120000 else 2 if revenu<180000 else 3),
                'alerte_financiere'             : ratio_endet * (1/(nb_trans_30j+1)),
                'client_fantome'               : jours_recence / (anciennete+1),
                'pression_pret'                : montant / (montant_total+1),
                'instabilite'                  : montant_max / (montant_moyen+1),
                'dependance_credit'             : nb_achat_credit / tot,
                'score_vulnerabilite'           : (ratio_endet*3.0 + ratio_ret_dep*2.0
                                                + recence_norm*1.5 - engage_paie*2.0
                                                - ratio_vol_pr*1.0),
                'score_rfm'                    : (nb_trans_total*0.4 + montant_total*0.0001
                                               + (1/(jours_recence+1))*100),
                'engagement_client'             : anciennete * intensite * engage_paie,
            }

            X_client = pd.DataFrame([input_dict])[features]
            score    = modele.predict_proba(X_client)[0, 1]
            decision = score >= SEUIL
            couleur  = '#F44336' if decision else '#4CAF50'
            emoji    = '🔴' if decision else '🟢'
            label    = 'RISQUE ELEVE — Pret deconseille' if decision else 'RISQUE FAIBLE — Pret recommande'

            st.markdown('---')
            st.markdown(f'## {emoji} Score : {score*100:.1f}%')
            st.markdown(f'### {label}')

            fig, ax = plt.subplots(figsize=(8, 1.2))
            ax.barh(0, 1,     color='#E0E0E0', height=0.5)
            ax.barh(0, score, color=couleur,   height=0.5)
            ax.axvline(SEUIL, color='orange', linewidth=2.5,
                       linestyle='--', label=f'Seuil {SEUIL}')
            ax.set_xlim(0, 1)
            ax.set_yticks([])
            ax.set_xlabel('Score (0 = faible risque  |  1 = risque eleve)')
            ax.legend(loc='upper right', fontsize=9)
            for sp in ax.spines.values(): sp.set_visible(False)
            st.pyplot(fig)
            plt.close()

            st.markdown('**Detail du profil**')
            m1, m2, m3 = st.columns(3)
            m1.metric('Ratio endettement',
                      f'{ratio_endet*100:.1f}%',
                      'Eleve' if ratio_endet > 0.5 else 'Correct')
            m2.metric('Capacite remboursement',
                      f'{cap_rembours:,.0f} FCFA',
                      'Faible' if cap_rembours < 30000 else 'OK')
            m3.metric('Activite 30j',
                      f'{nb_trans_30j:.0f} transactions',
                      'Faible' if nb_trans_30j < 10 else 'Active')

        except Exception as e:
            st.error(f'Erreur : {e}  — Verifiez que toutes les valeurs sont des nombres.')

elif onglet == '📈 Performance':
    st.subheader('Performance du modele')
    c1, c2, c3, c4 = st.columns(4)
    c1.metric('AUC-ROC',       '0.62', 'Discrimination globale')
    c2.metric('Gini',          '0.24', 'Pouvoir separatif')
    c3.metric('KS',            '0.19', 'Ecart max')
    c4.metric('Recall Defaut', '75%',  'Seuil 0.30')
    st.markdown('---')
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    cm = np.array([[74, 28], [10, 30]])
    axes[0].imshow(cm, cmap='Blues')
    axes[0].set_xticks([0,1])
    axes[0].set_yticks([0,1])
    axes[0].set_xticklabels(['Predit Non defaut','Predit Defaut'])
    axes[0].set_yticklabels(['Reel Non defaut','Reel Defaut'])
    axes[0].set_title('Matrice de confusion')
    for i in range(2):
        for j in range(2):
            axes[0].text(j, i, cm[i,j], ha='center', va='center',
                        fontsize=20, fontweight='bold',
                        color='white' if cm[i,j]>50 else 'black')
    cats = ['Vrais Negatifs\n74','Faux Positifs\n28','Faux Negatifs\n10','Vrais Positifs\n30']
    vals = [74, 28, 10, 30]
    clrs = ['#4CAF50','#FF9800','#F44336','#2196F3']
    brs  = axes[1].bar(cats, vals, color=clrs, edgecolor='white', width=0.5)
    for b, v in zip(brs, vals):
        axes[1].text(b.get_x()+b.get_width()/2, b.get_height()+0.5,
                    str(v), ha='center', fontsize=11, fontweight='bold')
    axes[1].set_title('Detail des predictions')
    axes[1].set_ylabel('Nombre de clients')
    axes[1].tick_params(axis='x', labelsize=8)
    axes[1].grid(True, alpha=0.2, axis='y')
    st.pyplot(fig)
    plt.close()
    st.info('Le modele detecte 30 defauts sur 40 (75%). Seuls 10 mauvais payeurs passent a travers le filtre.')

elif onglet == '💰 Impact Business':
    st.subheader('Impact financier du modele')
    col_s1, col_s2 = st.columns(2)
    moy_s  = col_s1.text_input('Montant moyen pret (FCFA)', '300000')
    taux_s = col_s2.text_input('Taux de perte en cas de defaut (%)', '80')
    try:
        moy_pret   = float(moy_s)
        taux_perte = float(taux_s)
    except:
        moy_pret, taux_perte = 300000, 80
    perte_u = moy_pret * (taux_perte / 100)
    p_sans  = 40 * perte_u
    p_avec  = 10 * perte_u
    eco     = p_sans - p_avec
    c1, c2, c3 = st.columns(3)
    c1.metric('Pertes sans modele',  f'{p_sans/1e6:.2f}M FCFA')
    c2.metric('Pertes avec modele',  f'{p_avec/1e6:.2f}M FCFA')
    c3.metric('Economies realisees', f'{eco/1e6:.2f}M FCFA')
    st.markdown('---')
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    brs = axes[0].bar(['Sans modele','Avec modele'],
                      [p_sans/1e6, p_avec/1e6],
                      color=['#F44336','#4CAF50'], edgecolor='white', width=0.4)
    for b, v in zip(brs, [p_sans/1e6, p_avec/1e6]):
        axes[0].text(b.get_x()+b.get_width()/2, b.get_height()+0.02,
                    f'{v:.2f}M', ha='center', fontsize=11, fontweight='bold')
    axes[0].set_ylabel('Pertes (Millions FCFA)')
    axes[0].set_title('Reduction des pertes financieres')
    axes[0].grid(True, alpha=0.2, axis='y')
    axes[0].spines['top'].set_visible(False)
    axes[0].spines['right'].set_visible(False)
    axes[1].pie([30,10],
               labels=['Defauts evites (75%)','Defauts residuels (25%)'],
               autopct='%1.0f%%', colors=['#4CAF50','#F44336'],
               startangle=90, wedgeprops={'edgecolor':'white','linewidth':2})
    axes[1].set_title('Taux de detection des defauts')
    st.pyplot(fig)
    plt.close()
    st.success(f'Le modele permet d eviter {eco/1e6:.2f} millions FCFA de pertes en detectant 75% des clients a risque.')
    st.markdown('---')
    st.markdown('**Recommandations pour le DG**')
    st.markdown('- Deployer le modele sur toutes les nouvelles demandes de pret')
    st.markdown('- Reentreiner le modele tous les 3 mois')
    st.markdown('- Collecter davantage de variables comportementales')
    st.markdown('- Suivi mensuel des performances du modele')