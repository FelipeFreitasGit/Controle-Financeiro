import streamlit as st
import pandas as pd
from datetime import date, datetime
import calendar
import io
import re
import json
import os
from dateutil.relativedelta import relativedelta

# Nome do arquivo onde os dados serão salvos
DATA_FILE = "finance_data.json"

# --- Configurações da Página ---
st.set_page_config(
    page_title="Controle Financeiro Pessoal",
    layout="wide"
)

# --- CSS para estilizar as tabelas e botões ---
st.markdown("""
<style>
/* Remove padding e margin padrão para criar um layout mais compacto */
.st-emotion-cache-1pxxpyh {
    padding: 0;
}
.st-emotion-cache-1wb35g {
    padding: 0;
    margin: 0;
}

/* Estilo para as colunas da tabela */
.st-emotion-cache-12110c3, .st-emotion-cache-s1h49 {
    padding-top: 0;
    padding-bottom: 0;
    margin-top: 0;
    margin-bottom: 0;
}

/* Estilo para o texto dentro das colunas */
.st-emotion-cache-k7vsyb, .st-emotion-cache-10q740q {
    margin-top: 0;
    margin-bottom: 0;
    padding-top: 0.2rem;
    padding-bottom: 0.2rem;
}

/* Estilo específico para o botão de excluir */
.st-emotion-cache-rn104 {
    margin-top: -0.2rem;
    margin-bottom: -0.2rem;
}
.st-emotion-cache-19kym45 {
    padding-top: 0.2rem;
    padding-bottom: 0.2rem;
    padding-left: 0.2rem;
    padding-right: 0.2rem;
    font-size: 1.2rem;
    color: #ff4b4b; /* Vermelho para o ícone de lixeira */
}
.st-emotion-cache-r44huj hr {
    margin: 1em 0px;
}
</style>
""", unsafe_allow_html=True)


# --- Funções para salvar e carregar dados em arquivo ---
def save_data_to_file(data):
    """Salva os dados da lista de transações em um arquivo JSON."""
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def load_data_from_file():
    """Carrega os dados de um arquivo JSON. Retorna uma lista vazia se o arquivo não existir."""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

# --- Inicializa o estado da sessão e carrega dados ---
if "transactions" not in st.session_state:
    st.session_state.transactions = load_data_from_file()

# --- Título e Descrição ---
st.title("💰 Controle Financeiro Pessoal")
if st.sidebar.button("Limpar todos os dados salvos"):
    st.session_state.transactions = []
    save_data_to_file(st.session_state.transactions)
    st.success("Dados do cache apagados com sucesso!")
    st.rerun()

# --- Funções de formatação ---
def format_currency(value):
    if pd.isna(value):
        return ""
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def generate_installments(original_transaction, current_year):
    """Gera transações para todas as parcelas de uma compra, limitadas ao ano atual."""
    installments = []
    
    parcela_match = re.match(r"(\d+)/(\d+)", str(original_transaction.get('parcela', '')))
    if not parcela_match:
        return [original_transaction]
    
    total_installments = int(parcela_match.group(2))
    
    try:
        original_date = pd.to_datetime(original_transaction['data'], dayfirst=True)
    except Exception:
        original_date = pd.to_datetime(original_transaction['data'])

    for i in range(1, total_installments + 1):
        new_transaction = original_transaction.copy()
        new_date = original_date + pd.DateOffset(months=i-1)
        
        if new_date.year > current_year:
            break
        
        new_transaction['data'] = new_date.strftime('%Y-%m-%d')
        new_transaction['descricao'] = f"{original_transaction['descricao']} ({i}/{total_installments})"
        new_transaction['parcela'] = f"{i}/{total_installments}"
        
        installments.append(new_transaction)
        
    return installments

# --- Formulários de Entrada em Abas na Barra Lateral ---
st.sidebar.header("Adicionar Transação")
tab1, tab2 = st.sidebar.tabs(["Receita", "Despesa"])

meses_nomes = [calendar.month_name[i] for i in range(1, 13)]
mes_atual = date.today().month
ano_atual = date.today().year

with tab1:
    st.subheader("Nova Receita")
    with st.form(key="revenue_form", clear_on_submit=True):
        col1_form, col2_form = st.columns(2)
        with col1_form:
            selected_month_name = st.selectbox("Mês", meses_nomes, index=mes_atual - 1, key='receita_mes')
        with col2_form:
            selected_year = st.number_input("Ano", min_value=1900, max_value=2100, value=ano_atual, step=1, key='receita_ano')

        description = st.text_input("Descrição", key='receita_descricao')
        value = st.number_input("Valor (R$)", min_value=0.01, format="%.2f", key='receita_valor')
        submit_button = st.form_submit_button("Adicionar Receita")

        if submit_button:
            if description and value:
                mes_numero = meses_nomes.index(selected_month_name) + 1
                nova_data = date(selected_year, mes_numero, 1)
                new_transaction = {
                    "data": str(nova_data),
                    "descricao": description,
                    "valor": float(value),
                    "tipo": "Receita",
                    "categoria": "N/A"
                }
                st.session_state.transactions.append(new_transaction)
                st.success("Receita adicionada com sucesso!")
                save_data_to_file(st.session_state.transactions)
                st.rerun()

with tab2:
    st.subheader("Nova Despesa")
    expense_category = st.selectbox("Categoria de Despesa", ["Fixa", "Variável", "Cartão de Crédito"])

    if expense_category == "Cartão de Crédito":
        uploaded_file = st.file_uploader("Faça upload da fatura (CSV)", type=["csv"])
        if uploaded_file is not None:
            try:
                df_cc = pd.read_csv(uploaded_file, sep=None, engine='python', encoding='utf-8-sig')
                
                expected_columns = {'data', 'lançamento', 'valor'}
                if not expected_columns.issubset(df_cc.columns):
                    st.error(f"Seu arquivo CSV deve conter as colunas: {', '.join(expected_columns)}. Colunas encontradas: {', '.join(df_cc.columns)}")
                else:
                    df_cc.rename(columns={'lançamento': 'descricao'}, inplace=True)
                    df_cc['valor'] = df_cc['valor'].astype(str).str.replace(',', '.').astype(float)
                    
                    if 'parcela' not in df_cc.columns:
                        df_cc['parcela'] = ''
                    
                    # Converte a coluna 'data' para datetime
                    df_cc['data'] = pd.to_datetime(df_cc['data'], dayfirst=True)
                    
                    def check_and_advance_date(dt):
                        """Verifica se a data é o último dia do mês e avança para o próximo."""
                        if dt.day == (dt + relativedelta(months=1, day=1) - relativedelta(days=1)).day:
                            return dt + relativedelta(months=1, day=1)
                        return dt
                    
                    df_cc['data'] = df_cc['data'].apply(check_and_advance_date)

                    # Filtra o DataFrame para manter apenas as colunas relevantes
                    expected_columns_list = ['data', 'descricao', 'valor', 'parcela']
                    # Garante que 'parcela' exista antes de filtrar
                    if 'parcela' not in df_cc.columns:
                        df_cc['parcela'] = ''
                    df_cc = df_cc[expected_columns_list]

                    cc_transactions_list = df_cc.to_dict('records')
                    
                    st.session_state.transactions = [t for t in st.session_state.transactions if t.get('categoria') != 'Cartão de Crédito']
                    
                    for transaction in cc_transactions_list:
                        transaction['tipo'] = 'Despesa'
                        transaction['categoria'] = 'Cartão de Crédito'
                        
                        installments = generate_installments(transaction, ano_atual)
                        for inst in installments:
                            st.session_state.transactions.append(inst)
                            
                    st.success("Fatura do cartão de crédito carregada e parcelas distribuídas com sucesso!")
                    st.info("As transações do cartão de crédito aparecerão nos meses correspondentes.")
                    save_data_to_file(st.session_state.transactions)
                    st.rerun()
            except Exception as e:
                st.error(f"Erro ao ler o arquivo: {e}")

    else:
        with st.form(key="expense_form", clear_on_submit=True):
            col1_form, col2_form = st.columns(2)
            with col1_form:
                selected_month_name = st.selectbox("Mês", meses_nomes, index=mes_atual - 1, key='despesa_mes')
            with col2_form:
                selected_year = st.number_input("Ano", min_value=1900, max_value=2100, value=ano_atual, step=1, key='despesa_ano')
            
            description = st.text_input("Descrição")
            value = st.number_input("Valor (R$)", min_value=0.01, format="%.2f")
            submit_button = st.form_submit_button("Adicionar Despesa")

            if submit_button:
                if description and value:
                    mes_numero = meses_nomes.index(selected_month_name) + 1
                    nova_data = date(selected_year, mes_numero, 1)
                    new_transaction = {
                        "data": str(nova_data),
                        "descricao": description,
                        "valor": float(value),
                        "tipo": "Despesa",
                        "categoria": expense_category
                    }
                    st.session_state.transactions.append(new_transaction)
                    st.success("Despesa adicionada com sucesso!")
                    save_data_to_file(st.session_state.transactions)
                    st.rerun()

# --- Exibição do Dashboard ---
#st.markdown("---")

meses = [calendar.month_name[i] for i in range(1, 13)]
meses_num = [f"{datetime.now().year}-{str(i).zfill(2)}" for i in range(1, 13)]
meses_e_abrev = list(zip(meses_num, meses))

tabs = st.tabs(meses)

if st.session_state.transactions:
    df_completo = pd.DataFrame(st.session_state.transactions)
    df_completo["data"] = pd.to_datetime(df_completo["data"]).dt.date
    df_completo["mes_ano"] = pd.to_datetime(df_completo["data"]).dt.strftime("%Y-%m")
    
    df_completo.sort_values(by="data", ascending=False, inplace=True)
    
    for i, (mes_num, mes_nome) in enumerate(meses_e_abrev):
        with tabs[i]:
            df_filtered = df_completo[df_completo["mes_ano"] == mes_num]
            
            if not df_filtered.empty:
                total_revenue = df_filtered[df_filtered["tipo"] == "Receita"]["valor"].sum()
                total_expenses = df_filtered[df_filtered["tipo"] == "Despesa"]["valor"].sum()
                current_balance = total_revenue - total_expenses

                st.subheader(f"Resumo de {mes_nome}")
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric(label="Saldo Atual", value=format_currency(current_balance))
                with col2:
                    st.metric(label="Total de Receitas", value=format_currency(total_revenue))
                with col3:
                    st.metric(label="Total de Despesas", value=format_currency(total_expenses))

                st.markdown("---")

                # Tabela de Receitas
                st.subheader("Receitas")
                df_revenue = df_filtered[df_filtered["tipo"] == "Receita"]
                if not df_revenue.empty:
                    cols = st.columns([0.2, 0.5, 0.2, 0.1])
                    with cols[0]: st.markdown("**Data**")
                    with cols[1]: st.markdown("**Descrição**")
                    with cols[2]: st.markdown("**Valor**")
                    with cols[3]: st.markdown("**Ações**")
                    st.markdown("---")
                    
                    for index, row in df_revenue.iterrows():
                        cols = st.columns([0.2, 0.5, 0.2, 0.1])
                        with cols[0]: st.write(row["data"])
                        with cols[1]: st.write(row["descricao"])
                        with cols[2]: st.write(format_currency(row["valor"]))
                        with cols[3]: 
                            if st.button("🗑️", key=f"del_receita_{index}"):
                                # A forma mais segura é reconstruir a lista sem o item
                                st.session_state.transactions = [t for i, t in enumerate(st.session_state.transactions) if i != index]
                                save_data_to_file(st.session_state.transactions)
                                st.rerun()
                else:
                    st.info("Nenhuma receita registrada ainda.")

                # Tabela de Despesas Fixas
                st.subheader("Despesas Fixas")
                df_fixed_expenses = df_filtered[(df_filtered["tipo"] == "Despesa") & (df_filtered["categoria"] == "Fixa")]
                if not df_fixed_expenses.empty:
                    cols = st.columns([0.2, 0.5, 0.2, 0.1])
                    with cols[0]: st.markdown("**Data**")
                    with cols[1]: st.markdown("**Descrição**")
                    with cols[2]: st.markdown("**Valor**")
                    with cols[3]: st.markdown("**Ações**")
                    st.markdown("---")
                    
                    for index, row in df_fixed_expenses.iterrows():
                        cols = st.columns([0.2, 0.5, 0.2, 0.1])
                        with cols[0]: st.write(row["data"])
                        with cols[1]: st.write(row["descricao"])
                        with cols[2]: st.write(format_currency(row["valor"]))
                        with cols[3]: 
                            if st.button("🗑️", key=f"del_fixa_{index}"):
                                st.session_state.transactions = [t for i, t in enumerate(st.session_state.transactions) if i != index]
                                save_data_to_file(st.session_state.transactions)
                                st.rerun()

                    st.markdown("---")
                    total_fixed = df_fixed_expenses["valor"].sum()
                    cols = st.columns([0.2, 0.5, 0.2, 0.1])
                    with cols[1]: st.write("**Total**")
                    with cols[2]: st.write(format_currency(total_fixed))
                else:
                    st.info("Nenhuma despesa fixa registrada ainda.")

                # Tabela de Despesas Variáveis
                st.subheader("Despesas Variáveis")
                df_variable_expenses = df_filtered[(df_filtered["tipo"] == "Despesa") & (df_filtered["categoria"] == "Variável")]
                if not df_variable_expenses.empty:
                    cols = st.columns([0.2, 0.5, 0.2, 0.1])
                    with cols[0]: st.markdown("**Data**")
                    with cols[1]: st.markdown("**Descrição**")
                    with cols[2]: st.markdown("**Valor**")
                    with cols[3]: st.markdown("**Ações**")
                    st.markdown("---")
                    
                    for index, row in df_variable_expenses.iterrows():
                        cols = st.columns([0.2, 0.5, 0.2, 0.1])
                        with cols[0]: st.write(row["data"])
                        with cols[1]: st.write(row["descricao"])
                        with cols[2]: st.write(format_currency(row["valor"]))
                        with cols[3]: 
                            if st.button("🗑️", key=f"del_var_{index}"):
                                st.session_state.transactions = [t for i, t in enumerate(st.session_state.transactions) if i != index]
                                save_data_to_file(st.session_state.transactions)
                                st.rerun()
                    
                    st.markdown("---")
                    total_variable = df_variable_expenses["valor"].sum()
                    cols = st.columns([0.2, 0.5, 0.2, 0.1])
                    with cols[1]: st.write("**Total**")
                    with cols[2]: st.write(format_currency(total_variable))

                else:
                    st.info("Nenhuma despesa variável registrada ainda.")

                # Tabela de Despesas Cartão de Crédito
                st.subheader("Despesas de Cartão de Crédito")
                df_cc_expenses = df_filtered[df_filtered["categoria"] == "Cartão de Crédito"]
                if not df_cc_expenses.empty:
                    total_cc = df_cc_expenses["valor"].sum()
                    
                    df_cc_expenses_display = df_cc_expenses[['data', 'descricao', 'parcela', 'valor']].copy()
                    df_cc_expenses_display["valor"] = df_cc_expenses_display["valor"].apply(format_currency)
                    st.dataframe(df_cc_expenses_display, use_container_width=True, hide_index=True)
                    
                    st.markdown(f"**Total:** {format_currency(total_cc)}")
                
                else:
                    st.info("Nenhuma despesa de cartão de crédito registrada ainda.")
            else:
                st.subheader(f"Resumo de {mes_nome}")
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric(label="Saldo Atual", value="R$ 0,00")
                with col2:
                    st.metric(label="Total de Receitas", value="R$ 0,00")
                with col3:
                    st.metric(label="Total de Despesas", value="R$ 0,00")
                st.markdown("---")
                st.info("Nenhuma transação registrada para este mês.")
else:
    st.info("Nenhuma transação registrada ainda.")