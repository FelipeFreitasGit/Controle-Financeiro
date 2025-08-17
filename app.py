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
DATA_FILE = "finance_data.json"
CATEGORIES_FILE = "finance_categories.json"
SUBCATEGORIES_FILE = "subcategories.json" # <-- ARQUIVO EXTERNO DE REGRAS

# --- FUNÇÕES: Lógica de Subcategoria ---
def clean_merchant_name(name: str) -> str:
    if not isinstance(name, str): return ''
    name = name.upper()
    name = re.sub(r'^[A-Z]{2,4}\*([A-Z0-9]+\*)?', '', name)
    name = re.sub(r'[^A-Z0-9\s]', '', name)
    return name.strip()

def get_subcategory(merchant_name: str, rules: dict) -> str:
    if not rules: return 'Diversos'
    cleaned_name = clean_merchant_name(merchant_name)
    sorted_keywords = sorted(rules.keys(), key=len, reverse=True)
    
    for keyword in sorted_keywords:
        if keyword in cleaned_name:
            return rules[keyword]
            
    return 'Diversos'

# --- Configurações da Página ---
st.set_page_config(page_title="Controle Financeiro Avançado", layout="wide")

# --- Funções de Persistência de Dados (Salvar/Carregar) ---
def save_data(filepath, data):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def load_data(filepath):
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {} if "subcategories" in filepath else []
    return {} if "subcategories" in filepath else []

# --- Lógica para gerar parcelas ---
def generate_installments(original_transaction):
    installments = []
    if isinstance(original_transaction.get('data'), (datetime, date)):
        original_transaction['data'] = original_transaction['data'].strftime('%Y-%m-%d')

    parcela_str = str(original_transaction.get('parcela', '')).strip()
    total_installments = 1
    if '/' in parcela_str:
        try: total_installments = int(parcela_str.split('/')[1])
        except (ValueError, IndexError): total_installments = 1
    elif parcela_str.isdigit() and int(parcela_str) > 1:
        total_installments = int(parcela_str)

    if total_installments <= 1:
        original_transaction.pop('parcela', None)
        original_transaction['id'] = str(uuid.uuid4())
        return [original_transaction]
    try:
        purchase_date = pd.to_datetime(original_transaction['data'])
    except Exception:
        st.error(f"Formato de data inválido para a transação: {original_transaction['descricao']}")
        return []
    base_description = re.sub(r'\s*\d+/\d+\s*$', '', original_transaction['descricao']).strip()
    for i in range(total_installments):
        payment_date = purchase_date + pd.DateOffset(months=i)
        installment_number = i + 1
        new_transaction = original_transaction.copy()
        new_transaction['data'] = payment_date.strftime('%Y-%m-%d')
        new_transaction['descricao'] = f"{base_description} ({installment_number}/{total_installments})"
        new_transaction['parcela'] = f"{installment_number}/{total_installments}"
        new_transaction['id'] = str(uuid.uuid4())
        installments.append(new_transaction)
    return installments

# --- Inicialização do Estado da Sessão ---
if "transactions" not in st.session_state:
    st.session_state.transactions = load_data(DATA_FILE)
    for t in st.session_state.transactions:
        if 'id' not in t: t['id'] = str(uuid.uuid4())

if "categories" not in st.session_state:
    default_categories = ["Cartão de Crédito", "Moradia", "Alimentação", "Transporte", "Lazer", "Saúde", "Educação", "Outros"]
    st.session_state.categories = load_data(CATEGORIES_FILE)
    if not st.session_state.categories: st.session_state.categories = default_categories

if "subcat_rules" not in st.session_state:
    st.session_state.subcat_rules = load_data(SUBCATEGORIES_FILE)
    if not st.session_state.subcat_rules:
        st.session_state.subcat_rules = {"AMAZON": "Varejo Online"}
        save_data(SUBCATEGORIES_FILE, st.session_state.subcat_rules)

# --- Funções de Formatação e Utilitários ---
def format_currency(value):
    if pd.isna(value): return ""
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def display_transactions(df_trans, type_name):
    st.subheader(type_name)
    df_sorted = df_trans.sort_values(by="data")
    if df_sorted.empty:
        st.info(f"Nenhuma transação do tipo '{type_name}' neste mês.")
        return

    # --- MODIFICADO: Coluna Subcategoria removida da exibição ---
    if type_name == "Despesas":
        cols = st.columns([0.15, 0.5, 0.2, 0.15])
        cols[0].markdown("**Data**")
        cols[1].markdown("**Descrição**")
        cols[2].markdown("**Categoria**")
        cols[3].markdown("**Valor**")
    else:
        cols = st.columns([0.2, 0.6, 0.2])
        cols[0].markdown("**Data**")
        cols[1].markdown("**Descrição**")
        cols[2].markdown("**Valor**")

    for _, row in df_sorted.iterrows():
        data_formatada = row['data'].strftime('%d/%m/%Y')
        if type_name == "Despesas":
            cols = st.columns([0.15, 0.5, 0.2, 0.15])
            cols[0].write(data_formatada)
            cols[1].write(row['descricao'])
            cols[2].write(row['categoria'])
            cols[3].write(format_currency(row['valor']))
        else:
            cols = st.columns([0.2, 0.6, 0.2])
            cols[0].write(data_formatada)
            cols[1].write(row['descricao'])
            cols[2].write(format_currency(row['valor']))

# --- Barra Lateral (Sidebar) ---
with st.sidebar:
    st.title("💰 Controle Financeiro")
    
    st.header("Adicionar Lançamento Manual", divider='rainbow')
    tab1, tab2 = st.tabs(["Receita", "Despesa"])

    with tab1:
        with st.form(key="revenue_form", clear_on_submit=True):
            revenue_description = st.text_input("Descrição", key='receita_descricao')
            revenue_value = st.number_input("Valor (R$)", min_value=0.01, format="%.2f", key='receita_valor')
            revenue_date = st.date_input("Data", date.today(), key='receita_data')
            if st.form_submit_button("Adicionar Receita", use_container_width=True):
                if revenue_description and revenue_value:
                    new_transaction = {
                        "id": str(uuid.uuid4()), "data": str(revenue_date), "descricao": revenue_description.strip(),
                        "valor": float(revenue_value), "tipo": "Receita", "categoria": "N/A"
                    }
                    st.session_state.transactions.append(new_transaction)
                    save_data(DATA_FILE, st.session_state.transactions)
                    st.success("Receita adicionada!")
                    # --- MODIFICADO: st.rerun() removido para corrigir o bug ---

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
                        "id": str(uuid.uuid4()), "data": str(expense_date), "descricao": expense_description.strip(),
                        "valor": float(expense_value), "tipo": "Despesa", "categoria": expense_category,
                        "recorrente": is_recurring
                    }
                    st.session_state.transactions.append(new_transaction)
                    save_data(DATA_FILE, st.session_state.transactions)
                    st.success("Despesa adicionada!")
                    # --- MODIFICADO: st.rerun() removido para corrigir o bug ---
    
    st.header("Importar Arquivos", divider='rainbow')

    with st.expander("📤 Importar Extrato da Conta Corrente (CSV)"):
        uploaded_extrato_file = st.file_uploader("Selecione o arquivo CSV do extrato", type=["csv"], key="extrato_uploader")
        if uploaded_extrato_file is not None:
            try:
                df_extrato = pd.read_csv(uploaded_extrato_file, sep=';', dtype=str, encoding='utf-8-sig').fillna('')
                df_extrato.columns = df_extrato.columns.str.strip()
                required_cols = {'data', 'lançamento', 'categoria', 'valor', 'recorrente'}
                if not required_cols.issubset(df_extrato.columns):
                    st.error(f"Arquivo inválido! Colunas necessárias: {', '.join(required_cols)}")
                else:
                    if st.button("Importar Novos Lançamentos", use_container_width=True, key="confirm_extrato"):
                        existing_transactions = {(t['data'], t['descricao'].strip()) for t in st.session_state.transactions}
                        new_transactions_to_add = []
                        for _, row in df_extrato.iterrows():
                            try:
                                data = pd.to_datetime(row['data'], dayfirst=True).strftime('%Y-%m-%d')
                                descricao = row['lançamento'].strip()
                                if not descricao: continue
                                if (data, descricao) in existing_transactions: continue
                                valor = float(str(row['valor']).replace('.', '').replace(',', '.'))
                                if valor >= 0:
                                    new_transaction = {"id": str(uuid.uuid4()), "data": data, "descricao": descricao, "valor": valor, "tipo": "Receita", "categoria": "N/A", "recorrente": False}
                                else:
                                    new_transaction = {"id": str(uuid.uuid4()), "data": data, "descricao": descricao, "valor": abs(valor), "tipo": "Despesa", "categoria": row['categoria'].strip(), "recorrente": str(row['recorrente']).strip().lower() == 'true'}
                                new_transactions_to_add.append(new_transaction)
                                existing_transactions.add((data, descricao))
                            except (ValueError, TypeError): continue
                        if new_transactions_to_add:
                            st.session_state.transactions.extend(new_transactions_to_add)
                            save_data(DATA_FILE, st.session_state.transactions)
                            st.success(f"{len(new_transactions_to_add)} novos lançamentos foram adicionados.")
                            st.rerun()
                        else:
                            st.info("Nenhum lançamento novo para importar.")
            except Exception as e:
                st.error(f"Ocorreu um erro ao processar o arquivo de extrato: {e}")

    with st.expander("💳 Importar Fatura de Cartão de Crédito (CSV)"):
        uploaded_file = st.file_uploader("Selecione o arquivo CSV da fatura", type=["csv"], key="fatura_uploader")
        if uploaded_file is not None:
            try:
                df = pd.read_csv(uploaded_file, sep=';', dtype=str, encoding='utf-8-sig').fillna('')
                df.columns = df.columns.str.strip()
                required_cols = {'data', 'lançamento', 'parcela', 'valor'}
                if not required_cols.issubset(df.columns):
                    st.error(f"Arquivo inválido! Colunas necessárias: {', '.join(required_cols)}")
                else:
                    if st.button("Importar Novas Despesas da Fatura", use_container_width=True):
                        classification_rules = st.session_state.subcat_rules
                        existing_transactions = {(t['data'], t['descricao'].strip()) for t in st.session_state.transactions}
                        new_transactions_to_add = []
                        df.rename(columns={'lançamento': 'descricao'}, inplace=True)
                        
                        for _, row in df.iterrows():
                            try:
                                # --- INÍCIO DA LÓGICA DE AJUSTE DE DATA ---
                                
                                # 1. Converte a data da compra para um objeto datetime
                                purchase_date = pd.to_datetime(row['data'], dayfirst=True)

                                # 2. Descobre qual é o último dia do mês da compra
                                _, last_day_of_month = calendar.monthrange(purchase_date.year, purchase_date.month)

                                # 3. Se a compra foi no último dia do mês...
                                if purchase_date.day == last_day_of_month:
                                    # ...ajusta a data para o primeiro dia do mês seguinte
                                    purchase_date = (purchase_date + relativedelta(months=1)).replace(day=1)

                                # --- FIM DA LÓGICA DE AJUSTE DE DATA ---
                                subcategory = get_subcategory(row['descricao'], classification_rules)
                                base_transaction = {
                                    "tipo": "Despesa", "categoria": "Cartão de Crédito",
                                    "subcategoria": subcategory, "recorrente": False, "data": purchase_date,
                                    "descricao": row['descricao'].strip(),
                                    "valor": float(str(row['valor']).replace('.', '').replace(',', '.')),
                                    "parcela": row['parcela'].strip()
                                }
                                if not base_transaction["descricao"]: continue
                                potential_installments = generate_installments(base_transaction.copy())
                                for trans in potential_installments:
                                    key = (trans['data'], trans['descricao'].strip())
                                    if key not in existing_transactions:
                                        new_transactions_to_add.append(trans)
                                        existing_transactions.add(key)
                            except (ValueError, TypeError): continue
                        
                        if new_transactions_to_add:
                            st.session_state.transactions.extend(new_transactions_to_add)
                            save_data(DATA_FILE, st.session_state.transactions)
                            st.success(f"{len(new_transactions_to_add)} novas despesas foram adicionadas.")
                            st.rerun()
                        else:
                            st.info("Nenhuma despesa nova para importar.")
            except Exception as e:
                st.error(f"Ocorreu um erro ao processar o arquivo da fatura: {e}")
    
    st.header("Gerenciamento", divider='rainbow')
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
    if st.session_state.transactions:
        df_export = pd.DataFrame(st.session_state.transactions)
        csv = df_export.to_csv(index=False, sep=';', encoding='utf-8-sig').encode('utf-8')
        st.download_button(label="📥 Exportar Dados para CSV", data=csv, file_name='dados_financeiros.csv', mime='text/csv', use_container_width=True)
    if st.button("🗑️ Limpar Todos os Dados", type="primary", use_container_width=True):
        st.session_state.transactions = []
        save_data(DATA_FILE, st.session_state.transactions)
        st.success("Todos os dados foram apagados.")
        st.rerun()

# --- Lógica de Processamento Anual (Cache) ---
@st.cache_data
def process_transactions_for_year(transactions_list, selected_year):
    df_completo = pd.DataFrame(transactions_list)
    if df_completo.empty: return pd.DataFrame()
    df_completo['data'] = pd.to_datetime(df_completo['data'])
    expanded_transactions = []
    for _, t in df_completo.iterrows():
        if t.get('recorrente'):
            start_date = t['data']
            if start_date.year <= selected_year:
                for month in range(1, 13):
                    if (start_date.year < selected_year) or (start_date.year == selected_year and start_date.month <= month):
                        new_t = t.to_dict(); valid_day = min(start_date.day, calendar.monthrange(selected_year, month)[1])
                        new_t['data'] = datetime(selected_year, month, valid_day); new_t['original_id'] = new_t['id']
                        expanded_transactions.append(new_t)
        elif t['data'].year == selected_year:
            expanded_transactions.append(t.to_dict())
    if not expanded_transactions: return pd.DataFrame()
    df_display = pd.DataFrame(expanded_transactions); df_display["mes"] = df_display["data"].dt.month
    return df_display

# --- Página Principal ---
st.title("Dashboard Financeiro")
if not st.session_state.transactions:
    st.info("Nenhuma transação registrada. Adicione uma receita ou despesa na barra lateral para começar.")
else:
    df_completo_base = pd.DataFrame(st.session_state.transactions)
    df_completo_base['data'] = pd.to_datetime(df_completo_base['data'])
    available_years = sorted(list(set(df_completo_base['data'].dt.year)), reverse=True)
    if not available_years: available_years.append(date.today().year)
    selected_year = st.selectbox("Selecione o Ano para visualizar:", available_years)
    
    df_display = process_transactions_for_year(tuple(st.session_state.transactions), selected_year)

    if df_display.empty:
        st.warning(f"Nenhuma transação encontrada para o ano de {selected_year}.")
    else:
        meses_nomes = [calendar.month_name[i] for i in range(1, 13)]
        tab_list = ["Resumo Anual"] + meses_nomes
        tabs = st.tabs(tab_list)

        with tabs[0]: # Resumo Anual
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
            st.subheader("Despesas por Categoria no Ano")
            expenses_by_cat_year = df_year[df_year['tipo'] == 'Despesa'].groupby('categoria')['valor'].sum()
            if not expenses_by_cat_year.empty: st.bar_chart(expenses_by_cat_year)
            
            st.subheader("Análise Anual do Cartão de Crédito")
            df_card_year = df_year[df_year['categoria'] == 'Cartão de Crédito']
            if not df_card_year.empty:
                expenses_by_subcat_year = df_card_year.groupby('subcategoria')['valor'].sum().sort_values(ascending=False)
                st.bar_chart(expenses_by_subcat_year)
            else:
                st.info("Nenhuma despesa de Cartão de Crédito registrada neste ano.")
            
            st.subheader("Evolução Mensal (Receitas vs. Despesas)")
            monthly_summary = df_year.groupby(['mes', 'tipo'])['valor'].sum().unstack(fill_value=0)
            if 'Receita' not in monthly_summary: monthly_summary['Receita'] = 0
            if 'Despesa' not in monthly_summary: monthly_summary['Despesa'] = 0
            st.bar_chart(monthly_summary)

        for i, mes_nome in enumerate(meses_nomes):
            with tabs[i+1]:
                mes_num = i + 1
                df_month = df_display[df_display["mes"] == mes_num]
                if df_month.empty:
                    st.info(f"Nenhuma transação registrada para {mes_nome} de {selected_year}.")
                    continue
                
                st.subheader(f"Resumo de {mes_nome}")
                total_revenue = df_month[df_month["tipo"] == "Receita"]["valor"].sum()
                total_expenses = df_month[df_month["tipo"] == "Despesa"]["valor"].sum()
                current_balance = total_revenue - total_expenses
                m_col1, m_col2, m_col3 = st.columns(3)
                m_col1.metric("Saldo do Mês", format_currency(current_balance))
                m_col2.metric("Total de Receitas", format_currency(total_revenue))
                m_col3.metric("Total de Despesas", format_currency(total_expenses))
                
                expenses_by_cat_month = df_month[df_month['tipo'] == 'Despesa'].groupby('categoria')['valor'].sum()
                if not expenses_by_cat_month.empty: st.bar_chart(expenses_by_cat_month)
                
                st.subheader("Análise do Cartão de Crédito no Mês")
                df_card_month = df_month[df_month['categoria'] == 'Cartão de Crédito']
                if not df_card_month.empty:
                    expenses_by_subcat_month = df_card_month.groupby('subcategoria')['valor'].sum().sort_values(ascending=False)
                    st.bar_chart(expenses_by_subcat_month)
                else:
                    st.info("Nenhuma despesa de Cartão de Crédito registrada neste mês.")

                st.markdown("---")
                display_transactions(df_month[df_month["tipo"] == "Receita"], "Receitas")
                st.markdown("---")
                display_transactions(df_month[df_month["tipo"] == "Despesa"], "Despesas")