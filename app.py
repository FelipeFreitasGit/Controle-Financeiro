import streamlit as st
import pandas as pd
from datetime import date, datetime
import calendar
import json
import os
import uuid
import re
from dateutil.relativedelta import relativedelta

# --- Nomes dos arquivos de dados ---
DATA_FILE = "finance_data_v2.json"
CATEGORIES_FILE = "finance_categories.json"

# --- Configurações da Página ---
st.set_page_config(
    page_title="Controle Financeiro Avançado",
    layout="wide"
)

# --- CSS (mantido para estilo) ---
st.markdown("""
<style>
    /* Estilos para um layout mais compacto e limpo */
    .st-emotion-cache-1pxxpyh { padding: 0; }
    .st-emotion-cache-1wb35g { padding: 0; margin: 0; }
    .st-emotion-cache-12110c3, .st-emotion-cache-s1h49 { padding-top: 0; padding-bottom: 0; margin-top: 0; margin-bottom: 0; }
    .st-emotion-cache-k7vsyb, .st-emotion-cache-10q740q { margin-top: 0; margin-bottom: 0; padding-top: 0.2rem; padding-bottom: 0.2rem; }
    .st-emotion-cache-r44huj hr { margin: 1rem 0px; }
    .stButton > button {
        width: 100%;
    }
</style>
""", unsafe_allow_html=True)


# --- Funções de Persistência de Dados (Salvar/Carregar) ---
def save_data(filepath, data):
    """Salva dados (transações ou categorias) em um arquivo JSON."""
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def load_data(filepath):
    """Carrega dados de um arquivo JSON. Retorna lista vazia se não existir."""
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []

# --- Função para Gerar Parcelas ---
def generate_installments(original_transaction):
    """Gera transações para todas as parcelas de uma compra."""
    installments = []
    
    parcela_str = str(original_transaction.get('parcela', ''))
    parcela_match = re.match(r"(\d+)/(\d+)", parcela_str)
    
    if not parcela_match:
        original_transaction.pop('parcela', None)
        return [original_transaction]
    
    total_installments = int(parcela_match.group(2))
    
    try:
        original_date = pd.to_datetime(original_transaction['data'])
    except Exception:
        st.error(f"Formato de data inválido para a transação: {original_transaction['descricao']}")
        return []

    for i in range(total_installments):
        new_date = original_date + pd.DateOffset(months=i)
        
        new_transaction = original_transaction.copy()
        new_transaction['data'] = new_date.strftime('%Y-%m-%d')
        new_transaction['descricao'] = f"{original_transaction['descricao']} ({i+1}/{total_installments})"
        new_transaction['parcela'] = f"{i+1}/{total_installments}"
        new_transaction['id'] = str(uuid.uuid4())
        
        installments.append(new_transaction)
        
    return installments

# --- Inicialização do Estado da Sessão ---
if "transactions" not in st.session_state:
    st.session_state.transactions = load_data(DATA_FILE)
    for t in st.session_state.transactions:
        if 'id' not in t:
            t['id'] = str(uuid.uuid4())

if "categories" not in st.session_state:
    default_categories = ["Cartão de Crédito", "Moradia", "Alimentação", "Transporte", "Lazer", "Saúde", "Educação", "Outros"]
    st.session_state.categories = load_data(CATEGORIES_FILE)
    if not st.session_state.categories:
        st.session_state.categories = default_categories

# --- Funções de Formatação e Utilitários ---
def format_currency(value):
    if pd.isna(value): return ""
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# --- Barra Lateral (Sidebar) ---
with st.sidebar:
    st.title("💰 Controle Financeiro")
    
    st.header("Adicionar Transação", divider='rainbow')
    tab1, tab2 = st.tabs(["Receita", "Despesa"])

    with tab1:
        with st.form(key="revenue_form", clear_on_submit=True):
            revenue_description = st.text_input("Descrição", key='receita_descricao')
            revenue_value = st.number_input("Valor (R$)", min_value=0.01, format="%.2f", key='receita_valor')
            revenue_date = st.date_input("Data", date.today(), key='receita_data')
            if st.form_submit_button("Adicionar Receita", use_container_width=True):
                if revenue_description and revenue_value:
                    new_transaction = {
                        "id": str(uuid.uuid4()), "data": str(revenue_date), "descricao": revenue_description,
                        "valor": float(revenue_value), "tipo": "Receita", "categoria": "N/A"
                    }
                    st.session_state.transactions.append(new_transaction)
                    save_data(DATA_FILE, st.session_state.transactions)
                    st.success("Receita adicionada!")

    with tab2:
        with st.form(key="expense_form", clear_on_submit=True):
            expense_description = st.text_input("Descrição")
            expense_value = st.number_input("Valor (R$)", min_value=0.01, format="%.2f")
            expense_date = st.date_input("Data", date.today())
            expense_category = st.selectbox("Categoria", st.session_state.categories)
            is_recurring = st.checkbox("É uma despesa recorrente/fixa?")
            if st.form_submit_button("Adicionar Despesa", use_container_width=True):
                if expense_description and expense_value:
                    new_transaction = {
                        "id": str(uuid.uuid4()), "data": str(expense_date), "descricao": expense_description,
                        "valor": float(expense_value), "tipo": "Despesa", "categoria": expense_category,
                        "recorrente": is_recurring
                    }
                    st.session_state.transactions.append(new_transaction)
                    save_data(DATA_FILE, st.session_state.transactions)
                    st.success("Despesa adicionada!")
        
        with st.expander("💳 Importar Fatura de Cartão de Crédito (CSV)"):
            uploaded_file = st.file_uploader("Selecione o arquivo CSV da fatura", type=["csv"])

            if uploaded_file is not None:
                try:
                    df = pd.read_csv(uploaded_file, sep=None, engine='python', encoding='utf-8-sig')
                    st.write("Pré-visualização dos dados:")
                    st.dataframe(df.head())
                    
                    st.write("Mapeie as colunas do seu arquivo:")
                    cols = df.columns.tolist()
                    col1, col2 = st.columns(2)
                    
                    data_col = col1.selectbox("Coluna da Data", cols, index=0)
                    desc_col = col2.selectbox("Coluna da Descrição/Lançamento", cols, index=1)
                    val_col = col1.selectbox("Coluna do Valor", cols, index=2)
                    parcela_col = col2.selectbox("Coluna da Parcela (Opcional)", ["Nenhuma"] + cols, index=0)
                    
                    cat_index = st.session_state.categories.index("Cartão de Crédito") if "Cartão de Crédito" in st.session_state.categories else 0
                    category_for_csv = st.selectbox("Atribuir todas as despesas à categoria:", st.session_state.categories, index=cat_index)
                    
                    st.warning(f"Atenção: A importação irá **substituir** todas as transações existentes na categoria '{category_for_csv}'.")

                    if st.button("Processar e Importar Fatura", use_container_width=True):
                        
                        st.session_state.transactions = [
                            t for t in st.session_state.transactions 
                            if t.get('categoria') != category_for_csv
                        ]
                        
                        new_transactions_count = 0
                        df_mapped = df[[data_col, desc_col, val_col]].rename(columns={
                            data_col: 'data', desc_col: 'descricao', val_col: 'valor'
                        })
                        if parcela_col != "Nenhuma":
                            df_mapped['parcela'] = df[parcela_col]
                        else:
                            df_mapped['parcela'] = ""
                        
                        df_mapped['valor'] = df_mapped['valor'].astype(str).str.replace(',', '.').astype(float).abs()
                        df_mapped['data'] = pd.to_datetime(df_mapped['data'], dayfirst=True, errors='coerce')
                        df_mapped.dropna(subset=['data', 'valor'], inplace=True)
                        
                        def adjust_last_day_date(d):
                            last_day_of_month = calendar.monthrange(d.year, d.month)[1]
                            if d.day == last_day_of_month:
                                return d + relativedelta(days=1)
                            return d
                        
                        df_mapped['data'] = df_mapped['data'].apply(adjust_last_day_date)
                        
                        for _, row in df_mapped.iterrows():
                            base_transaction = {
                                "tipo": "Despesa", "categoria": category_for_csv, "recorrente": False,
                                **row.to_dict()
                            }
                            
                            generated = generate_installments(base_transaction)
                            st.session_state.transactions.extend(generated)
                            if generated:
                                new_transactions_count += 1
                        
                        save_data(DATA_FILE, st.session_state.transactions)
                        st.success(f"Fatura processada! {new_transactions_count} lançamentos foram importados para a categoria '{category_for_csv}'.")
                        st.rerun()

                except Exception as e:
                    st.error(f"Ocorreu um erro ao processar o arquivo: {e}")

    with st.expander("⚙️ Gerenciar Categorias"):
        for category in st.session_state.categories:
            col1, col2 = st.columns([0.8, 0.2])
            col1.write(category)
            if col2.button("🗑️", key=f"del_cat_{category}", use_container_width=True):
                st.session_state.categories.remove(category)
                save_data(CATEGORIES_FILE, st.session_state.categories)
                st.rerun()

        with st.form("new_category_form", clear_on_submit=True):
            new_category = st.text_input("Nova Categoria")
            if st.form_submit_button("Adicionar", use_container_width=True):
                if new_category and new_category not in st.session_state.categories:
                    st.session_state.categories.append(new_category)
                    save_data(CATEGORIES_FILE, st.session_state.categories)
                    st.rerun()

    st.header("Ferramentas", divider='rainbow')
    if st.session_state.transactions:
        df_export = pd.DataFrame(st.session_state.transactions)
        csv = df_export.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Exportar Dados para CSV",
            data=csv,
            file_name='dados_financeiros.csv',
            mime='text/csv',
            use_container_width=True
        )

    if st.button("🗑️ Limpar Todos os Dados", type="primary", use_container_width=True):
        st.session_state.transactions = []
        save_data(DATA_FILE, st.session_state.transactions)
        st.success("Todos os dados foram apagados.")
        st.rerun()


# --- Página Principal ---
st.title("Dashboard Financeiro")

if not st.session_state.transactions:
    st.info("Nenhuma transação registrada. Adicione uma receita ou despesa na barra lateral para começar.")
else:
    all_dates = [datetime.strptime(t['data'], '%Y-%m-%d') for t in st.session_state.transactions]
    available_years = sorted(list(set(d.year for d in all_dates)), reverse=True)
    if not available_years:
        available_years.append(date.today().year)
    
    selected_year = st.selectbox("Selecione o Ano para visualizar:", available_years)

    df_completo = pd.DataFrame(st.session_state.transactions)
    df_completo['data'] = pd.to_datetime(df_completo['data'])
    
    expanded_transactions = []
    for index, t in df_completo.iterrows():
        if t.get('recorrente'):
            start_date = t['data']
            if start_date.year <= selected_year:
                for month in range(1, 13):
                    if (start_date.year < selected_year) or (start_date.year == selected_year and start_date.month <= month):
                        new_t = t.to_dict()
                        valid_day = min(start_date.day, calendar.monthrange(selected_year, month)[1])
                        new_t['data'] = datetime(selected_year, month, valid_day)
                        new_t['original_id'] = new_t['id']
                        expanded_transactions.append(new_t)
        else:
            if t['data'].year == selected_year:
                expanded_transactions.append(t.to_dict())

    df_display = pd.DataFrame(expanded_transactions)
    if not df_display.empty:
        df_display["mes"] = df_display["data"].dt.month
    
    meses_nomes = [calendar.month_name[i] for i in range(1, 13)]
    tab_list = ["Resumo Anual"] + meses_nomes
    tabs = st.tabs(tab_list)

    with tabs[0]:
        st.header(f"Resumo de {selected_year}")
        df_year = df_display
        
        total_revenue_year = df_year[df_year["tipo"] == "Receita"]["valor"].sum()
        total_expenses_year = df_year[df_year["tipo"] == "Despesa"]["valor"].sum()
        balance_year = total_revenue_year - total_expenses_year

        col1, col2, col3 = st.columns(3)
        col1.metric("Saldo Final", format_currency(balance_year))
        col2.metric("Total de Receitas", format_currency(total_revenue_year))
        col3.metric("Total de Despesas", format_currency(total_expenses_year))

        st.markdown("---")
        
        if not df_year.empty:
            st.subheader("Despesas por Categoria no Ano")
            expenses_by_cat_year = df_year[df_year['tipo'] == 'Despesa'].groupby('categoria')['valor'].sum()
            if not expenses_by_cat_year.empty:
                st.bar_chart(expenses_by_cat_year)
            else:
                st.info("Nenhuma despesa para exibir no gráfico.")
                
            st.subheader("Evolução Mensal (Receitas vs. Despesas)")
            monthly_summary = df_year.groupby(['mes', 'tipo'])['valor'].sum().unstack(fill_value=0)
            if 'Receita' not in monthly_summary: monthly_summary['Receita'] = 0
            if 'Despesa' not in monthly_summary: monthly_summary['Despesa'] = 0
            st.bar_chart(monthly_summary)
        else:
            st.info("Nenhum dado para exibir nos gráficos anuais.")

    for i, mes_nome in enumerate(meses_nomes):
        with tabs[i+1]:
            mes_num = i + 1
            if df_display.empty or df_display[df_display["mes"] == mes_num].empty:
                st.info(f"Nenhuma transação registrada para {mes_nome} de {selected_year}.")
                continue

            df_month = df_display[df_display["mes"] == mes_num]

            st.subheader(f"Resumo de {mes_nome}")
            total_revenue = df_month[df_month["tipo"] == "Receita"]["valor"].sum()
            total_expenses = df_month[df_month["tipo"] == "Despesa"]["valor"].sum()
            current_balance = total_revenue - total_expenses

            m_col1, m_col2, m_col3 = st.columns(3)
            m_col1.metric("Saldo do Mês", format_currency(current_balance))
            m_col2.metric("Total de Receitas", format_currency(total_revenue))
            m_col3.metric("Total de Despesas", format_currency(total_expenses))
            
            # --- NOVO: Bloco para exibir o detalhamento de despesas recorrentes vs. variáveis ---
            total_recurring_expenses = df_month[
                (df_month["tipo"] == "Despesa") & 
                (df_month["recorrente"].fillna(False) == True)
            ]["valor"].sum()
            total_variable_expenses = total_expenses - total_recurring_expenses
            
            m_col4, m_col5 = st.columns(2)
            m_col4.metric(
                label="Total Desp. Recorrentes",
                value=format_currency(total_recurring_expenses),
                help="Soma das despesas marcadas como 'recorrente/fixa'."
            )
            m_col5.metric(
                label="Total Desp. Variáveis",
                value=format_currency(total_variable_expenses),
                help="Soma das despesas não recorrentes, incluindo a fatura do cartão."
            )
            # --- FIM DO NOVO BLOCO ---
            
            expenses_by_cat_month = df_month[df_month['tipo'] == 'Despesa'].groupby('categoria')['valor'].sum()
            if not expenses_by_cat_month.empty:
                st.bar_chart(expenses_by_cat_month)
            
            st.markdown("---")

            def display_transactions(df_trans, type_name):
                st.subheader(type_name)
                if df_trans.empty:
                    st.info(f"Nenhuma transação do tipo '{type_name}' neste mês.")
                    return
                
                if type_name == "Despesas":
                    cols = st.columns([0.15, 0.3, 0.2, 0.2, 0.075, 0.075])
                    cols[0].markdown("**Data**")
                    cols[1].markdown("**Descrição**")
                    cols[2].markdown("**Categoria**")
                    cols[3].markdown("**Valor**")
                    cols[4].markdown("**Editar**")
                    cols[5].markdown("**Excluir**")
                else:
                    cols = st.columns([0.2, 0.4, 0.2, 0.1, 0.1])
                    cols[0].markdown("**Data**")
                    cols[1].markdown("**Descrição**")
                    cols[2].markdown("**Valor**")
                    cols[3].markdown("**Editar**")
                    cols[4].markdown("**Excluir**")

                for _, row in df_trans.iterrows():
                    trans_id = row.get('original_id', row['id'])
                    data_formatada = row['data'].strftime('%d/%m/%Y')
                    
                    if type_name == "Despesas":
                        cols = st.columns([0.15, 0.3, 0.2, 0.2, 0.075, 0.075])
                        cols[0].write(data_formatada)
                        cols[1].write(row['descricao'])
                        cols[2].write(row['categoria'])
                        cols[3].write(format_currency(row['valor']))
                        edit_col, del_col = cols[4], cols[5]
                    else:
                        cols = st.columns([0.2, 0.4, 0.2, 0.1, 0.1])
                        cols[0].write(data_formatada)
                        cols[1].write(row['descricao'])
                        cols[2].write(format_currency(row['valor']))
                        edit_col, del_col = cols[3], cols[4]

                    if edit_col.button("✏️", key=f"edit_{trans_id}_{mes_num}_{row.name}", use_container_width=True):
                        st.session_state.editing_transaction_id = trans_id
                        st.rerun()

                    if del_col.button("❌", key=f"del_{trans_id}_{mes_num}_{row.name}", use_container_width=True):
                        st.session_state.transactions = [t for t in st.session_state.transactions if t['id'] != trans_id]
                        save_data(DATA_FILE, st.session_state.transactions)
                        st.rerun()
            
            display_transactions(df_month[df_month["tipo"] == "Receita"], "Receitas")
            st.markdown("---")
            display_transactions(df_month[df_month["tipo"] == "Despesa"], "Despesas")


# --- Lógica para Diálogos de Edição ---
if 'editing_transaction_id' in st.session_state and st.session_state.editing_transaction_id:
    transaction_id = st.session_state.editing_transaction_id
    transaction = next((t for t in st.session_state.transactions if t['id'] == transaction_id), None)
    
    if transaction:
        @st.dialog("Editar Transação")
        def edit_dialog():
            with st.form("edit_form"):
                st.subheader(f"Editando: {transaction['descricao']}")
                
                new_date = st.date_input("Data", value=datetime.strptime(transaction['data'], '%Y-%m-%d'))
                new_description = st.text_input("Descrição", value=transaction['descricao'])
                new_value = st.number_input("Valor", value=float(transaction['valor']), format="%.2f")
                
                if transaction['tipo'] == 'Despesa':
                    cat_index = st.session_state.categories.index(transaction['categoria']) if transaction['categoria'] in st.session_state.categories else 0
                    new_category = st.selectbox("Categoria", st.session_state.categories, index=cat_index)
                    new_is_recurring = st.checkbox("É recorrente?", value=transaction.get('recorrente', False))
                
                if st.form_submit_button("Salvar Alterações"):
                    for t in st.session_state.transactions:
                        if t['id'] == transaction_id:
                            t['data'] = str(new_date)
                            t['descricao'] = new_description
                            t['valor'] = new_value
                            if t['tipo'] == 'Despesa':
                                t['categoria'] = new_category
                                t['recorrente'] = new_is_recurring
                            break
                    save_data(DATA_FILE, st.session_state.transactions)
                    st.session_state.editing_transaction_id = None
                    st.rerun()
        
        edit_dialog()