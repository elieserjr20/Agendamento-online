import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1.field_path import FieldPath
from datetime import datetime, timedelta
import time
import os
import json
from PIL import Image
import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException
import re
import unicodedata
import streamlit.components.v1 as components

# --- DEFINIÇÃO DE CAMINHOS SEGUROS (PARA O FAVICON) ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

# --- CARREGAR O ÍCONE DA PÁGINA ---
try:
    # Lembre-se que o ícone precisa estar na pasta 'static' do seu projeto no Render
    favicon_path = os.path.join(STATIC_DIR, "icon_any_192.png")
    favicon = Image.open(favicon_path)
except FileNotFoundError:
    st.warning("Arquivo 'icon_any_192.png' não encontrado na pasta 'static'. Usando emoji padrão.")
    favicon = "📅" # Um emoji de calendário como alternativa

# --- CONFIGURAÇÕES DA PÁGINA ---
st.set_page_config(
    page_title="Agendamento Interno",
    page_icon=favicon,
    layout="wide" # ou "wide", como preferir
)

# CSS customizado para colorir os botões da tabela e centralizar o texto
# CSS customizado para criar uma grade de agendamentos visual e responsiva
st.markdown("""
<style>
    /* --- CÓDIGO ADICIONADO PARA REMOVER O ESPAÇO NO TOPO --- */
    div.block-container {
        padding-top: 1.5rem; /* Ajuste este valor se necessário, ex: 0.5rem ou 0rem */
    }
    /* --------------------------------------------------------- */
    
    /* Define a célula base do agendamento */
    .schedule-cell {
        height: 50px;              /* Altura fixa para cada célula */
        border-radius: 8px;        /* Bordas arredondadas */
        display: flex;             /* Centraliza o conteúdo */
        align-items: center;
        justify-content: center;
        margin-bottom: 5px;        /* Espaço entre as linhas */
        padding: 5px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.12), 0 1px 2px rgba(0,0,0,0.24); /* Sombra sutil */
    }

    /* Cores de fundo baseadas no status */
    .schedule-cell.disponivel { background-color: #28a745; } /* Verde */
    .schedule-cell.ocupado    { background-color: #dc3545; } /* Vermelho */
    .schedule-cell.almoco     { background-color: #ffc107; color: black;} /* Laranja */
    .schedule-cell.indisponivel { background-color: #6c757d; } /* Cinza padrão para indisponível (SDJ, Descanso) */
    .schedule-cell.fechado { background-color: #A9A9A9; color: black; } /* Nova classe para "Fechado" */

    /* Estiliza o botão dentro da célula para ser "invisível" mas clicável */
    .schedule-cell button {
        background-color: transparent;
        color: white;
        border: none;
        width: 100%;
        height: 100%;
        font-weight: bold;
    }
    
    /* Para o texto do botão (que é um <p> dentro do botão do Streamlit) */
    .schedule-cell button p {
        color: white; /* Cor do texto para status verde e vermelho */
        margin: 0;
        white-space: nowrap;      /* Impede a quebra de linha */
        overflow: hidden;         /* Esconde o que passar do limite */
        text-overflow: ellipsis;  /* Adiciona "..." ao final de texto longo */
    }

    /* Cor do texto específica para a célula de almoço */
    .schedule-cell.almoco button p {
        color: black;
    }

    /* Remove o ponteiro de clique para horários não clicáveis */
    .schedule-cell.indisponivel {
        pointer-events: none;
    }

</style>
""", unsafe_allow_html=True)


# --- INICIALIZAÇÃO DO FIREBASE E E-MAIL (Mesmo do código original) ---

FIREBASE_CREDENTIALS = None
EMAIL = os.environ.get("EMAIL_CREDENCIADO")
SENHA = os.environ.get("EMAIL_SENHA")

# 2. Carrega o caminho para o ficheiro de credenciais do Firebase
#    (O Render coloca o caminho nesta variável de ambiente)
FIREBASE_SECRET_PATH = os.environ.get("FIREBASE_SECRET_PATH")

if FIREBASE_SECRET_PATH:
    try:
        # Abre e lê o ficheiro JSON a partir do caminho fornecido
        with open(FIREBASE_SECRET_PATH, 'r') as f:
            FIREBASE_CREDENTIALS = json.load(f)
    except FileNotFoundError:
        st.error(f"ERRO: O arquivo de credenciais não foi encontrado no caminho: {FIREBASE_SECRET_PATH}")
    except json.JSONDecodeError:
        st.error("ERRO: O conteúdo do arquivo de credenciais não é um JSON válido.")
    except Exception as e:
        st.error(f"ERRO ao ler o Secret File do Firebase: {e}")
else:
    st.error("ERRO CRÍTICO: A variável de ambiente 'FIREBASE_SECRET_PATH' não está definida. Verifique as suas configurações no Render.")

# --- Inicialização do Firebase ---
if FIREBASE_CREDENTIALS and not firebase_admin._apps:
    try:
        cred = credentials.Certificate(FIREBASE_CREDENTIALS)
        firebase_admin.initialize_app(cred)
    except Exception as e:
        st.error(f"Erro ao inicializar a aplicação Firebase: {e}")

db = firestore.client() if firebase_admin._apps else None


# --- DADOS BÁSICOS ---
servicos = ["Tradicional", "Social", "Degradê", "Pezim", "Navalhado", "Barba", "Abordagem de visagismo", "Consultoria de visagismo"]
barbeiros = ["Aluizio", "Lucas Borges"]


# --- FUNÇÕES DE BACKEND (Adaptadas e Novas) ---
# VERSÃO CORRETA DA FUNÇÃO
# COLOQUE ESTA VERSÃO NO LUGAR DA SUA FUNÇÃO enviar_email

def enviar_email(assunto, mensagem):
    """
    Função atualizada para enviar e-mails usando a API da Brevo.
    Lê a chave da API e o e-mail do remetente das variáveis de ambiente do Render.
    MOSTRA AVISOS NA TELA se as chaves falharem.
    """
    # Passo 1: O código busca a chave secreta no "cofre" do Render.
    api_key = os.environ.get("BREVO_API_KEY")
    
    # Passo 2: O código busca o teu e-mail (que também está no "cofre").
    sender_email = os.environ.get("EMAIL_CREDENCIADO")

    # Se não encontrar as chaves no Render, avisa no log E NA TELA.
    if not api_key or not sender_email:
        print("AVISO: Credenciais da Brevo (BREVO_API_KEY ou EMAIL_CREDENCIADO) não configuradas. E-mail não enviado.")
        # --- MELHORIA ADICIONADA ---
        st.warning("AVISO: Credenciais de E-mail não configuradas no servidor. A notificação não foi enviada.")
        # ---------------------------
        return

    # Passo 3: Configura a comunicação com a Brevo.
    configuration = sib_api_v3_sdk.Configuration()
    configuration.api_key['api-key'] = api_key
    api_instance = sib_api_v3_sdk.TransactionalEmailsApi(sib_api_v3_sdk.ApiClient(configuration))

    # Passo 4: Monta o e-mail.
    send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
        to=[{"email": sender_email}],
        sender={"name": "Painel Interno Barbearia", "email": sender_email},
        subject=assunto,
        text_content=mensagem
    )

    try:
        # Passo 5: Envia o e-mail.
        api_instance.send_transac_email(send_smtp_email)
        print(f"E-mail de notificação ('{assunto}') enviado com sucesso pela Brevo.")
    except ApiException as e:
        print(f"ERRO ao enviar e-mail com a Brevo: {e}")
        # --- MELHORIA ADICIONADA ---
        st.error(f"Ocorreu um erro ao tentar enviar o e-mail de notificação: {e}")
        # ---------------------------

def buscar_agendamentos_do_dia(data_obj):
    """
    Busca todos os agendamentos do dia em UMA ÚNICA CONSULTA e retorna um dicionário.
    A chave é o ID do documento, e o valor são os dados do agendamento.
    """
    if not db:
        st.error("Firestore não inicializado.")
        return {}
    
    ocupados_map = {}
    prefixo_id = data_obj.strftime('%Y-%m-%d')
    try:
        docs = db.collection('agendamentos') \
                 .order_by(FieldPath.document_id()) \
                 .start_at([prefixo_id]) \
                 .end_at([prefixo_id + '\uf8ff']) \
                 .stream()
        for doc in docs:
            ocupados_map[doc.id] = doc.to_dict()
    except Exception as e:
        st.error(f"Erro ao buscar agendamentos do dia: {e}")
    return ocupados_map

# FUNÇÕES DE ESCRITA (JÁ CORRIGIDAS NA NOSSA CONVERSA)
def salvar_agendamento(data_obj, horario, nome, telefone, servicos, barbeiro, is_bloqueio=False):
    if not db: return False
    data_para_id = data_obj.strftime('%Y-%m-%d')
    chave_base = f"{data_para_id}_{horario}_{barbeiro}"
    
    # Lógica de Bloqueio
    if is_bloqueio:
        chave_agendamento = f"{chave_base}_BLOQUEADO"
        nome = "Bloqueado"
    else:
        chave_agendamento = chave_base

    try:
        data_para_salvar = datetime.combine(data_obj, datetime.min.time())
        db.collection('agendamentos').document(chave_agendamento).set({
            'nome': nome, 'telefone': telefone, 'servicos': servicos, 'barbeiro': barbeiro,
            'data': data_para_salvar, 'horario': horario, 'status': "Confirmado",
            'data_agendamento': firestore.SERVER_TIMESTAMP
        })
        return True
    except Exception as e:
        print(f"Erro ao salvar: {e}")
        return False

def bloquear_horario(data_obj, horario, barbeiro, motivo="BLOQUEADO"):
    if not db: return False
    data_para_id = data_obj.strftime('%Y-%m-%d')
    chave_bloqueio = f"{data_para_id}_{horario}_{barbeiro}_BLOQUEADO" if motivo == "BLOQUEADO" else f"{data_para_id}_{horario}_{barbeiro}"
    try:
        # CORREÇÃO: Converte o objeto 'date' para 'datetime' antes de salvar
        data_para_salvar = datetime.combine(data_obj, datetime.min.time())
        db.collection('agendamentos').document(chave_bloqueio).set({
            'nome': motivo, 'telefone': "INTERNO", 'servicos': [], 
            'barbeiro': barbeiro, 'data': data_para_salvar, 'horario': horario
        })
        return True
    except Exception as e:
        st.error(f"Erro ao bloquear horário: {e}")
        return False
        
# ADICIONE ESTA FUNÇÃO JUNTO COM AS OUTRAS FUNÇÕES DE BACKEND

def desbloquear_horario(data_obj, horario_agendado, barbeiro):
    """
    Remove o documento de bloqueio (_BLOQUEADO) referente a um agendamento de Corte+Barba.
    """
    if not db: return
    try:
        # Calcula o horário seguinte que foi bloqueado
        horario_dt = datetime.strptime(horario_agendado, '%H:%M') + timedelta(minutes=30)
        horario_seguinte_str = horario_dt.strftime('%H:%M')
        
        # Cria o ID do documento de bloqueio no formato correto
        data_para_id = data_obj.strftime('%Y-%m-%d')
        chave_bloqueio = f"{data_para_id}_{horario_seguinte_str}_{barbeiro}_BLOQUEADO"
        
        # Deleta o documento
        bloqueio_ref = db.collection('agendamentos').document(chave_bloqueio)
        if bloqueio_ref.get().exists:
            bloqueio_ref.delete()
    except Exception as e:
        # Apenas avisa no console, não precisa mostrar erro para o usuário
        print(f"Aviso: Não foi possível desbloquear o horário seguinte. {e}")

def verificar_disponibilidade_especifica(data_obj, horario, barbeiro):
    """ Verifica de forma eficiente se um único horário está livre. """
    if not db: return False
    data_para_id = data_obj.strftime('%Y-%m-%d')
    id_padrao = f"{data_para_id}_{horario}_{barbeiro}"
    id_bloqueado = f"{data_para_id}_{horario}_{barbeiro}_BLOQUEADO"
    try:
        doc_padrao_ref = db.collection('agendamentos').document(id_padrao)
        doc_bloqueado_ref = db.collection('agendamentos').document(id_bloqueado)
        
        # Se qualquer um dos dois documentos existir, o horário não está livre.
        if doc_padrao_ref.get().exists or doc_bloqueado_ref.get().exists:
            return False # Indisponível
        return True # Disponível
    except Exception:
        return False

def cancelar_agendamento(data_obj, horario, barbeiro):
    if not db: return None
    data_para_id = data_obj.strftime('%Y-%m-%d')
    chave_agendamento = f"{data_para_id}_{horario}_{barbeiro}"
    agendamento_ref = db.collection('agendamentos').document(chave_agendamento)
    try:
        doc = agendamento_ref.get()
        if doc.exists:
            agendamento_data = doc.to_dict()
            agendamento_ref.delete()
            return agendamento_data
        return None
    except Exception as e:
        st.error(f"Erro ao cancelar agendamento: {e}")
        return None

def fechar_horario(data_obj, horario, barbeiro):
    if not db: return False
    data_para_id = data_obj.strftime('%Y-%m-%d')
    chave_bloqueio = f"{data_para_id}_{horario}_{barbeiro}"
    try:
        # CORREÇÃO: Converte o objeto 'date' para 'datetime' antes de salvar
        data_para_salvar = datetime.combine(data_obj, datetime.min.time())
        db.collection('agendamentos').document(chave_bloqueio).set({
            'nome': "Fechado", 'telefone': "INTERNO", 'servicos': [],
            'barbeiro': barbeiro, 'data': data_para_salvar, 'horario': horario
        })
        return True
    except Exception as e:
        st.error(f"Erro ao fechar horário: {e}")
        return False
    # ADICIONE ESTA NOVA FUNÇÃO NO SEU BLOCO DE FUNÇÕES DE BACKEND

# NO SEU ARQUIVO agn.py, SUBSTITUA ESTA FUNÇÃO:

def desbloquear_horario_especifico(data_obj, horario, barbeiro):
    """
    Remove um agendamento/bloqueio específico, tentando apagar tanto o ID
    padrão quanto o ID com sufixo _BLOQUEADO para garantir a limpeza.
    """
    if not db: return False
    
    data_para_id = data_obj.strftime('%Y-%m-%d')
    
    # Define os dois possíveis nomes de documento que podem estar ocupando o horário
    chave_padrao = f"{data_para_id}_{horario}_{barbeiro}"
    chave_bloqueado = f"{data_para_id}_{horario}_{barbeiro}_BLOQUEADO"
    
    ref_padrao = db.collection('agendamentos').document(chave_padrao)
    ref_bloqueado = db.collection('agendamentos').document(chave_bloqueado)
    
    try:
        # Tenta apagar os dois documentos. O Firestore não gera erro se o documento não existir.
        # Isso garante que tanto um agendamento normal quanto um bloqueio órfão sejam removidos.
        ref_padrao.delete()
        ref_bloqueado.delete()
        
        return True # Retorna sucesso, pois a intenção é deixar o horário livre.
        
    except Exception as e:
        st.error(f"Erro ao tentar desbloquear horário: {e}")
        return False
        
# --- O "DEF PERARDO 2.0" (O TRADUTOR DE TEXTO) ---
# --- (Esta é a sua função, que começa na linha 92) ---
def parsear_comando(comando):
    # Normalização (remover acentos e converter para minúsculas)
    comando_normalizado = remover_acentos(comando.lower())
    
    # --- "IMPLANTE TRIPLO" (A CURA DOS 3 BUGS DE VOZ) ---
    # (Adicionado na linha 95 - ANTES do Regex)
    
    # 1. Cura o "Bug do Juni r" (Erro do Microfone)
    comando_normalizado = comando_normalizado.replace("juni r", "junior")
    
    # 2. Cura o "Bug do Aloísio" (Erro de Ortografia)
    # (Transforma a "voz" (Aloísio) no "código" (Aluizio))
    comando_normalizado = comando_normalizado.replace("aloisio", "aluizio")
    comando_normalizado = comando_normalizado.replace("aloísio", "aluizio") # (Garantia)
    comando_normalizado = comando_normalizado.replace("alu", "aluizio") # (Garante o "Alu")
    
    # --- FIM DO IMPLANTE ---

    # Lista de barbeiros conhecidos (normalizada)
    barbeiros_conhecidos = [remover_acentos(b.lower()) for b in BARBEIROS]

    # --- TENTATIVA 1: Regex Padrão (Nome às HH:MM com Barbeiro) ---
    padrao_completo = re.compile(r"(.+?)\s+(?:as|às|a|no|na)\s+(\d{1,2}:\d{2})\s+(?:com|como|cm|c|co)\s+(.+)", re.IGNORECASE)
    match = padrao_completo.search(comando_normalizado)
    if match:
        nome_cliente = match.group(1).strip()
        horario = match.group(2).strip()
        nome_barbeiro = match.group(3).strip()
        
        try:
            horario_obj = datetime.strptime(horario, "%H:%M")
            horario_formatado = horario_obj.strftime("%H:%M")
        except ValueError:
            return None 

        # --- "IMPLANTE ANTI-O" (A CURA GERAL) ---
        # (Cura o Bug 1 DEPOIS do Regex)
        if nome_cliente.lower().startswith(('o ', 'a ', 'os ', 'as ')):
            nome_cliente = nome_cliente.split(' ', 1)[1] 
        if nome_barbeiro.lower().startswith(('o ', 'a ', 'os ', 'as ')):
            nome_barbeiro = nome_barbeiro.split(' ', 1)[1]
        # --- FIM DO IMPLANTE ---

        if nome_barbeiro in barbeiros_conhecidos:
            idx = barbeiros_conhecidos.index(nome_barbeiro)
            nome_barbeiro_original = BARBEIROS[idx]
            return {'nome': nome_cliente.title(), 'horário': horario_formatado, 'barbeiro': nome_barbeiro_original}

    # --- TENTATIVA 2: Regex (Nome às HH com Barbeiro) ---
    padrao_hora_cheia = re.compile(r"(.+?)\s+(?:as|às|a|no|na)\s+(\d{1,2})\s*(?:h|horas)?\s+(?:com|como|cm|c|co)\s+(.+)", re.IGNORECASE)
    match = padrao_hora_cheia.search(comando_normalizado)
    if match:
        nome_cliente = match.group(1).strip()
        horario = match.group(2).strip()
        nome_barbeiro = match.group(3).strip()
        
        horario_formatado = f"{int(horario):02d}:00"

        # --- "IMPLANTE ANTI-O" (A CURA GERAL) ---
        if nome_cliente.lower().startswith(('o ', 'a ', 'os ', 'as ')):
            nome_cliente = nome_cliente.split(' ', 1)[1] 
        if nome_barbeiro.lower().startswith(('o ', 'a ', 'os ', 'as ')):
            nome_barbeiro = nome_barbeiro.split(' ', 1)[1]
        # --- FIM DO IMPLANTE ---
        
        if nome_barbeiro in barbeiros_conhecidos:
            idx = barbeiros_conhecidos.index(nome_barbeiro)
            nome_barbeiro_original = BARBEIROS[idx]
            return {'nome': nome_cliente.title(), 'horário': horario_formatado, 'barbeiro': nome_barbeiro_original}

    # --- TENTATIVA 3: Regex (Nome, Barbeiro às HH:MM) ---
    padrao_barbeiro_antes = re.compile(r"(.+?)\s*,\s*(.+?)\s+(?:as|às|a|no|na)\s+(\d{1,2}:\d{2})", re.IGNORECASE)
    match = padrao_barbeiro_antes.search(comando_normalizado)
    if match:
        nome_cliente = match.group(1).strip()
        nome_barbeiro = match.group(2).strip()
        horario = match.group(3).strip()

        try:
            horario_obj = datetime.strptime(horario, "%H:%M")
            horario_formatado = horario_obj.strftime("%H:%M")
        except ValueError:
            return None

        # --- "IMPLANTE ANTI-O" (A CURA GERAL) ---
        if nome_cliente.lower().startswith(('o ', 'a ', 'os ', 'as ')):
            nome_cliente = nome_cliente.split(' ', 1)[1] 
        if nome_barbeiro.lower().startswith(('o ', 'a ', 'os ', 'as ')):
            nome_barbeiro = nome_barbeiro.split(' ', 1)[1]
        # --- FIM DO IMPLANTE ---

        if nome_barbeiro in barbeiros_conhecidos:
            idx = barbeiros_conhecidos.index(nome_barbeiro)
            nome_barbeiro_original = BARBEIROS[idx]
            return {'nome': nome_cliente.title(), 'horário': horario_formatado, 'barbeiro': nome_barbeiro_original}

    # --- TENTATIVA 4: Regex (Nome, Barbeiro às HH) ---
    padrao_barbeiro_antes_hora_cheia = re.compile(r"(.+?)\s*,\s*(.+?)\s+(?:as|às|a|no|na)\s+(\d{1,2})\s*(?:h|horas)?", re.IGNORECASE)
    match = padrao_barbeiro_antes_hora_cheia.search(comando_normalizado)
    if match:
        nome_cliente = match.group(1).strip()
        nome_barbeiro = match.group(2).strip()
        horario = match.group(3).strip()
        
        horario_formatado = f"{int(horario):02d}:00"

        # --- "IMPLANTE ANTI-O" (A CURA GERAL) ---
        if nome_cliente.lower().startswith(('o ', 'a ', 'os ', 'as ')):
            nome_cliente = nome_cliente.split(' ', 1)[1] 
        if nome_barbeiro.lower().startswith(('o ', 'a ', 'os ', 'as ')):
            nome_barbeiro = nome_barbeiro.split(' ', 1)[1]
        # --- FIM DO IMPLANTE ---
        
        if nome_barbeiro in barbeiros_conhecidos:
            idx = barbeiros_conhecidos.index(nome_barbeiro)
            nome_barbeiro_original = BARBEIROS[idx]
            return {'nome': nome_cliente.title(), 'horário': horario_formatado, 'barbeiro': nome_barbeiro_original}

    # --- TENTATIVA 5: Regex (Barbeiro às HH:MM com Nome) ---
    padrao_invertido = re.compile(r"(.+?)\s+(?:as|às|a|no|na)\s+(\d{1,2}:\d{2})\s+(?:com|como|cm|c|co)\s+(.+)", re.IGNORECASE)
    match = padrao_invertido.search(comando_normalizado)
    if match:
        nome_barbeiro = match.group(1).strip()
        horario = match.group(2).strip()
        nome_cliente = match.group(3).strip()

        try:
            horario_obj = datetime.strptime(horario, "%H:%M")
            horario_formatado = horario_obj.strftime("%H:%M")
        except ValueError:
            None

        # --- "IMPLANTE ANTI-O" (A CURA GERAL) ---
        if nome_cliente.lower().startswith(('o ', 'a ', 'os ', 'as ')):
            nome_cliente = nome_cliente.split(' ', 1)[1] 
        if nome_barbeiro.lower().startswith(('o ', 'a ', 'os ', 'as ')):
            nome_barbeiro = nome_barbeiro.split(' ', 1)[1]
        # --- FIM DO IMPLANTE ---

        if nome_barbeiro in barbeiros_conhecidos:
            idx = barbeiros_conhecidos.index(nome_barbeiro)
            nome_barbeiro_original = BARBEIROS[idx]
            return {'nome': nome_cliente.title(), 'horário': horario_formatado, 'barbeiro': nome_barbeiro_original}

    return None
# --- (Esta é o fim da sua função, linha 205) ---

# --- INICIALIZAÇÃO DO ESTADO DA SESSÃO ---
if 'view' not in st.session_state:
    st.session_state.view = 'main' # 'main', 'agendar', 'cancelar'
    st.session_state.selected_data = None
    st.session_state.agendamento_info = {}
if 'dados_voz' not in st.session_state:
    st.session_state.dados_voz = None

# --- LÓGICA DE NAVEGAÇÃO E EXIBIÇÃO (MODAIS) ---

# ---- MODAL DE AGENDAMENTO ----
if st.session_state.view == 'agendar':
    # Todo o código abaixo está corretamente indentado ("dentro" do if)
    info = st.session_state.agendamento_info
    
    # Pegamos o objeto de data para as funções
    data_obj = info['data_obj']
    # Criamos a string de data para mostrar na tela
    data_str_display = data_obj.strftime('%d/%m/%Y')
    
    horario = info['horario']
    barbeiro = info['barbeiro']
    
    st.header("Confirmar Agendamento")
    st.subheader(f"🗓️ {data_str_display} às {horario} com {barbeiro}")

    with st.container(border=True):
        nome_cliente = st.text_input("Nome do Cliente*", key="cliente_nome")
        
        # Sua lista de serviços original
        servicos = ["Tradicional", "Social", "Degradê", "Pezim", "Navalhado", "Barba", "Abordagem de visagismo", "Consultoria de visagismo"]
        servicos_selecionados = st.multiselect("Serviços", servicos, key="servicos_selecionados")

        # Sua validação de Visagismo (mantida)
        is_visagismo = any(s in servicos_selecionados for s in ["Abordagem de visagismo", "Consultoria de visagismo"])
        if is_visagismo and barbeiro == 'Aluizio':
            st.error("Serviços de visagismo são apenas com Lucas Borges.")
        else:
            cols = st.columns(3)
            if cols[0].button("✅ Confirmar Agendamento", type="primary", use_container_width=True):
                if not nome_cliente:
                    st.error("O nome do cliente é obrigatório!")
                else:
                    with st.spinner("Processando..."):
                        
                        is_bloqueio = nome_cliente.strip().lower() == 'bloqueado'
                        
                        # 2. Lógica de Corte+Barba (SÓ corre se NÃO for bloqueio)
                        precisa_bloquear_proximo = False
                        if "Barba" in servicos_selecionados and any(c in servicos_selecionados for c in ["Tradicional", "Social", "Degradê", "Navalhado"]) and not is_bloqueio:
                            horario_seguinte_dt = datetime.strptime(horario, '%H:%M') + timedelta(minutes=30)
                            horario_seguinte_str = horario_seguinte_dt.strftime('%H:%M')
                            
                            # (Assumindo que você tem esta função 'verificar_disponibilidade_especifica' no seu código)
                            if verificar_disponibilidade_especifica(data_obj, horario_seguinte_str, barbeiro):
                                precisa_bloquear_proximo = True
                            else:
                                st.error("Não é possível agendar Corte+Barba. O horário seguinte não está disponível.")
                                st.stop() # Pára a execução

                        # 3. Chamada de salvar (AGORA COM 'is_bloqueio')
                        if salvar_agendamento(data_obj, horario, nome_cliente, "INTERNO", servicos_selecionados, barbeiro, is_bloqueio=is_bloqueio):
                            
                            if precisa_bloquear_proximo:
                                # (Assumindo que você tem esta função 'bloquear_horario' no seu código)
                                bloquear_horario(data_obj, horario_seguinte_str, barbeiro, "BLOQUEADO")

                            # 4. Mensagem de sucesso "inteligente"
                            st.success("Horário bloqueado com sucesso!" if is_bloqueio else f"Agendamento para {nome_cliente} confirmado!")
                            
                            # 5. Só envia e-mail se NÃO for um bloqueio
                            if not is_bloqueio:
                                assunto_email = f"Novo Agendamento: {nome_cliente} em {data_str_display}"
                                mensagem_email = (
                                    f"Agendamento interno:\n\nCliente: {nome_cliente}\nData: {data_str_display}\n"
                                    f"Horário: {horario}\nBarbeiro: {barbeiro}\n"
                                    f"Serviços: {', '.join(servicos_selecionados) if servicos_selecionados else 'Nenhum'}"
                                )
                                # (Assumindo que você tem esta função 'enviar_email' no seu código)
                                enviar_email(assunto_email, mensagem_email)
                            
                            # --- FIM DA "INTEGRAÇÃO" ---

                            st.cache_data.clear()
                            st.session_state.view = 'agenda' # (O seu código usa 'agenda', mantive)
                            time.sleep(2)
                            st.rerun()
                        else:
                            st.error("Falha ao salvar. Tente novamente.")
    
    # Botão de voltar, também indentado corretamente
    if st.button("⬅️ Voltar para a Agenda"):
        st.session_state.view = 'agenda'
        st.rerun()


# ---- MODAL DE CANCELAMENTO ----
# SUBSTITUA TODA A SUA SEÇÃO 'cancelar' POR ESTA:

elif st.session_state.view == 'cancelar':
    info = st.session_state.agendamento_info
    
    # --- LÓGICA CORRIGIDA PARA PEGAR OS DADOS ---
    # Pegamos o OBJETO de data para usar nas funções
    data_obj = info['data_obj']
    # Criamos a STRING de data formatada apenas para mostrar na tela
    data_str_display = data_obj.strftime('%d/%m/%Y')
    
    horario = info['horario']
    barbeiro = info['barbeiro']
    
    # Acessamos os dados de forma segura com .get() para evitar qualquer erro
    dados = info.get('dados', {})
    nome = dados.get('nome', 'Ocupado')

    # --- INTERFACE DO MODAL DE GERENCIAMENTO ---
    st.header("Gerenciar Horário")
    st.subheader(f"🗓️ {data_str_display} às {horario} com {barbeiro}")
    st.markdown("---")

    # Mostra os detalhes do horário de forma inteligente
    if nome not in ["Fechado", "BLOQUEADO"]:
        # Se for um agendamento de cliente, mostramos todos os detalhes
        st.write(f"**Cliente:** {nome}")
        st.write(f"**Telefone:** {dados.get('telefone', 'N/A')}")
        st.write(f"**Serviços:** {', '.join(dados.get('servicos', []))}")
    else:
        # Se for um bloqueio interno ("Fechado" ou "BLOQUEADO"), apenas informamos o status
        st.info(f"O horário está marcado como: **{nome}**")

    st.markdown("---")
    st.warning("Tem certeza de que deseja liberar este horário?")

    cols = st.columns(2)
    # Botão para confirmar o cancelamento/liberação
    if cols[0].button("✅ Sim, Liberar Horário", type="primary", use_container_width=True):
        with st.spinner("Processando..."):
            
            # Chamamos a função de backend com os dados corretos (data_obj)
            dados_cancelados = cancelar_agendamento(data_obj, horario, barbeiro)
            
            if dados_cancelados:
                # Se o horário foi liberado com sucesso, verificamos se precisa desbloquear o seguinte
                servicos = dados_cancelados.get('servicos', [])
                if "Barba" in servicos and any(c in servicos for c in ["Tradicional", "Social", "Degradê", "Navalhado"]):
                    desbloquear_horario(data_obj, horario, barbeiro)

                st.success("Horário liberado com sucesso!")
                
                assunto_email = f"Cancelamento/Liberação: {nome} em {data_str_display}"
                mensagem_email = f"O agendamento para {nome} às {horario} com {barbeiro} foi cancelado/liberado."
                
                # Enviamos o e-mail com os dados corretos
                enviar_email(assunto_email, mensagem_email)
                
                # Voltamos para a tela da agenda
                st.session_state.view = 'agenda'
                time.sleep(2)
                st.rerun()
            else:
                st.error("Não foi possível liberar. O horário pode já ter sido removido.")

    # Botão para voltar para a agenda
    if cols[1].button("⬅️ Voltar para a Agenda", use_container_width=True):
        st.session_state.view = 'agenda'
        st.rerun()

# ---- NOVO MODAL PARA FECHAR HORÁRIOS ----
elif st.session_state.view == 'fechar':
    st.header("🔒 Fechar Horários em Lote")

    # --- CORREÇÃO PRINCIPAL AQUI ---
    # Pegamos o OBJETO de data que foi salvo na sessão
    data_obj_para_fechar = st.session_state.get('data_obj_selecionada')
    
    # Se, por algum motivo, o objeto de data não estiver na sessão, voltamos para a agenda
    if not data_obj_para_fechar:
        st.error("Data não selecionada. Voltando para a agenda.")
        st.session_state.view = 'agenda'
        time.sleep(2)
        st.rerun()

    # Criamos a string de data APENAS para mostrar na tela
    data_str_display = data_obj_para_fechar.strftime('%d/%m/%Y')
    st.subheader(f"Data selecionada: {data_str_display}")

    # Lista de horários para os seletores
    horarios_tabela = [f"{h:02d}:{m:02d}" for h in range(8, 20) for m in (0, 30)]

    with st.container(border=True):
        col1, col2 = st.columns(2)
        with col1:
            horario_inicio = st.selectbox("Horário de Início", options=horarios_tabela, key="fecha_inicio")
        with col2:
            horario_fim = st.selectbox("Horário Final", options=horarios_tabela, key="fecha_fim", index=len(horarios_tabela)-1)

        barbeiro_fechar = st.selectbox("Selecione o Barbeiro", options=barbeiros, key="fecha_barbeiro")

        st.warning("Atenção: Esta ação irá sobrescrever quaisquer agendamentos existentes no intervalo selecionado.", icon="⚠️")

        btn_cols = st.columns(2)
        if btn_cols[0].button("✔️ Confirmar Fechamento", type="primary", use_container_width=True):
            try:
                start_index = horarios_tabela.index(horario_inicio)
                end_index = horarios_tabela.index(horario_fim)

                if start_index > end_index:
                    st.error("O horário de início deve ser anterior ao horário final.")
                else:
                    with st.spinner(f"Fechando horários para {barbeiro_fechar}..."):
                        horarios_para_fechar = horarios_tabela[start_index:end_index+1]
                        sucesso_total = True
                        for horario in horarios_para_fechar:
                            # --- USAMOS data_obj_para_fechar AQUI ---
                            if not fechar_horario(data_obj_para_fechar, horario, barbeiro_fechar):
                                sucesso_total = False
                                break
                        
                        if sucesso_total:
                            st.success("Horários fechados com sucesso!")
                            st.cache_data.clear()
                            st.session_state.view = 'agenda' # <-- Corrigido para 'agenda'
                            time.sleep(2)
                            st.rerun()
                        else:
                            st.error("Ocorreu um erro ao fechar um ou mais horários.")
            except ValueError:
                st.error("Horário selecionado inválido.")

        if btn_cols[1].button("⬅️ Voltar", use_container_width=True):
            st.session_state.view = 'agenda' # <-- Corrigido para 'agenda'
            st.rerun()
            
# --- TELA PRINCIPAL (GRID DE AGENDAMENTOS) ---
else:
    components.html(
        """
        <script>
            setTimeout(function() {
                try {
                    // 1. Tenta focar no elemento H1 (o st.title)
                    // (Usamos o window.parent para "escapar" o iframe do componente)
                    var titleElement = window.parent.document.querySelector('h1');
                    
                    if (titleElement) {
                        // "Rouba" o foco para o título
                        titleElement.focus();
                    } else {
                        // Se falhar, foca no "corpo" da página
                        window.parent.document.body.focus();
                    }
                } catch (e) {
                    // Ignora erros de permissão de iframe (se houver)
                }
                
                // 2. Força o scroll para o topo (DE NOVO)
                window.scrollTo(0, 0);
                
            }, 100); // Aumentamos o tempo para 100ms (desespero)
        </script>
        """,
        height=0 # Invisível
    )
    
    st.title("Barbearia Lucas Borges - Agendamentos Internos")
    # Centraliza a logo
    cols_logo = st.columns([1, 2, 1])
    with cols_logo[1]:
        st.image("https://i.imgur.com/XVOXz8F.png", width=350)

    data_selecionada = st.date_input(
        "Selecione a data para visualizar",
        value=datetime.today(),
        min_value=datetime.today().date(),
        key="data_input"
    )

    # --- PLANO D 2.0 (A "Melhor Experiência" com Microfone do Teclado) ---
    # Esta barra de chat fica "colada" no rodapé da página.
    prompt = st.chat_input("Diga seu comando (Ex: Cliente às 10 com Lucas)")

    if prompt:
        # O 'prompt' é o texto que o utilizador enviou (falado ou digitado)
        with st.spinner("Processando comando... 🧠"):
            dados = parsear_comando(prompt)
        
        if dados:
            # SUCESSO! Envia para o Modal de Confirmação
            st.session_state.dados_voz = {
                'nome': dados['nome'],
                'horario': dados['horario'],
                'barbeiro': dados['barbeiro'],
                'data_obj': datetime.today().date() # Agenda sempre para HOJE
            }
            st.rerun() # Força o rerun para mostrar o modal
        else:
            # O "Def Perardo" falhou
            st.error("Não entendi o comando. Tente 'Nome às XX horas com Barbeiro'.")

    # --- MODAL DE CONFIRMAÇÃO DA VOZ (Do Plano D) ---
    if st.session_state.dados_voz:
        try:
            dados = st.session_state.dados_voz
            nome = dados['nome']
            horario = dados['horario']
            barbeiro = dados['barbeiro']
            data_obj = dados['data_obj']

            st.markdown("---")
            st.subheader("Confirmar Agendamento por Voz?")
            st.write(f"**Cliente:** `{nome}`")
            st.write(f"**Horário:** `{horario}`")
            st.write(f"**Barbeiro:** `{barbeiro}`")
            st.write(f"**Data:** `{data_obj.strftime('%d/%m/%Y')}`")
            
            col_confirm, col_cancel = st.columns(2)
            
            if col_confirm.button("✅ Confirmar", key="btn_confirm_voz", type="primary", use_container_width=True):
                # (Lógica de verificação de disponibilidade)
                if salvar_agendamento(data_obj, horario, nome, "INTERNO (Voz)", ["(Voz)"], barbeiro, is_bloqueio=False):
                    st.success(f"Agendado! {nome} às {horario} com {barbeiro}.")
                    st.balloons()
                    st.cache_data.clear()
                    st.session_state.dados_voz = None
                    time.sleep(2)
                    st.rerun()
                else:
                    st.error("Falha ao salvar no banco de dados.")

            if col_cancel.button("❌ Cancelar", key="btn_cancel_voz", use_container_width=True):
                st.session_state.dados_voz = None
                st.rerun()

        except KeyError:
            st.error("Erro nos dados da sessão. Por favor, fale novamente.")
            st.session_state.dados_voz = None
            
    # --- VARIÁVEIS DE DATA ---
    # Usamos 'data_selecionada' como o nosso objeto de data principal
    data_obj = data_selecionada
    # Criamos a string 'DD/MM/AAAA' para usar nas chaves dos botões e exibição
    data_str = data_obj.strftime('%d/%m/%Y')

    # Botão para ir para a tela de fechar horários em lote
    with st.expander("🔒 Fechar um Intervalo de Horários"):
        with st.form("form_fechar_horario", clear_on_submit=True):
            horarios_tabela = [f"{h:02d}:{m:02d}" for h in range(8, 20) for m in (0, 30)]
        
            col1, col2, col3 = st.columns(3)
            with col1:
                horario_inicio = st.selectbox("Início", options=horarios_tabela, key="fecha_inicio")
            with col2:
                horario_fim = st.selectbox("Fim", options=horarios_tabela, key="fecha_fim", index=len(horarios_tabela)-1)
            with col3:
                barbeiro_fechar = st.selectbox("Barbeiro", options=barbeiros, key="fecha_barbeiro")

            if st.form_submit_button("Confirmar Fechamento", use_container_width=True):
                try:
                    start_index = horarios_tabela.index(horario_inicio)
                    end_index = horarios_tabela.index(horario_fim)
                    if start_index > end_index:
                        st.error("O horário de início deve ser anterior ao final.")
                    else:
                        horarios_para_fechar = horarios_tabela[start_index:end_index+1]
                        for horario in horarios_para_fechar:
                            fechar_horario(data_obj, horario, barbeiro_fechar)
                        st.success("Horários fechados com sucesso!")
                        time.sleep(1)
                        st.rerun()
                except Exception as e:
                    st.error(f"Erro ao fechar horários: {e}")

    with st.expander("🔓 Desbloquear um Intervalo de Horários"):
        with st.form("form_desbloquear_horario", clear_on_submit=True):
            horarios_tabela = [f"{h:02d}:{m:02d}" for h in range(8, 20) for m in (0, 30)]
        
            col1, col2, col3 = st.columns(3)
            with col1:
                horario_inicio_desbloq = st.selectbox("Início", options=horarios_tabela, key="desbloq_inicio")
            with col2:
                horario_fim_desbloq = st.selectbox("Fim", options=horarios_tabela, key="desbloq_fim", index=len(horarios_tabela)-1)
            with col3:
                barbeiro_desbloquear = st.selectbox("Barbeiro", options=barbeiros, key="desbloq_barbeiro")

            if st.form_submit_button("Confirmar Desbloqueio", use_container_width=True):
                horarios_para_desbloquear = horarios_tabela[horarios_tabela.index(horario_inicio_desbloq):horarios_tabela.index(horario_fim_desbloq)+1]
                for horario in horarios_para_desbloquear:
                    desbloquear_horario_especifico(data_obj, horario, barbeiro_desbloquear)
                st.success("Horários desbloqueados com sucesso!")
                time.sleep(1)
                st.rerun()

    # --- OTIMIZAÇÃO DE CARREGAMENTO ---
    # 1. Busca todos os dados do dia de uma só vez, antes de desenhar a tabela
    ocupados_map = buscar_agendamentos_do_dia(data_obj)
    data_para_id = data_obj.strftime('%Y-%m-%d') # Formato AAAA-MM-DD para checar os IDs

    # Header da Tabela
    header_cols = st.columns([1.5, 3, 3])
    header_cols[0].markdown("**Horário**")
    for i, barbeiro in enumerate(barbeiros):
        header_cols[i+1].markdown(f"### {barbeiro}")
    
    # Geração do Grid Interativo
    horarios_tabela = [f"{h:02d}:{m:02d}" for h in range(8, 20) for m in (0, 30)]

    for horario in horarios_tabela:
        grid_cols = st.columns([1.5, 3, 3])
        grid_cols[0].markdown(f"#### {horario}")

        for i, barbeiro in enumerate(barbeiros):
            status = "disponivel"
            texto_botao = "Disponível"
            dados_agendamento = {}
            is_clicavel = True

            # --- LÓGICA SDJ ADICIONADA AQUI ---
            dia_mes = data_obj.day
            mes_ano = data_obj.month
            dia_semana = data_obj.weekday() # 0=Segunda, 6=Domingo
            is_intervalo_especial = (mes_ano == 7 and 10 <= dia_mes <= 19)
            
            hora_int = int(horario.split(':')[0])

            # REGRA 0: DURANTE O INTERVALO ESPECIAL, QUASE TUDO É LIBERADO
            if is_intervalo_especial:
                # Durante o intervalo, a única regra é verificar agendamentos no banco
                id_padrao = f"{data_para_id}_{horario}_{barbeiro}"
                id_bloqueado = f"{data_para_id}_{horario}_{barbeiro}_BLOQUEADO"
                if id_padrao in ocupados_map:
                    dados_agendamento = ocupados_map[id_padrao]
                    nome = dados_agendamento.get("nome", "Ocupado")
                    status, texto_botao = ("fechado" if nome == "Fechado" else "ocupado"), nome
                elif id_bloqueado in ocupados_map:
                    status, texto_botao, dados_agendamento = "ocupado", "Bloqueado", {"nome": "BLOQUEADO"}

            # REGRAS PARA DIAS NORMAIS (FORA DO INTERVALO ESPECIAL)
            else:
                # REGRA 1: Horários das 7h (SDJ)
                id_padrao = f"{data_para_id}_{horario}_{barbeiro}"
                id_bloqueado = f"{data_para_id}_{horario}_{barbeiro}_BLOQUEADO"

                if id_padrao in ocupados_map:
                    dados_agendamento = ocupados_map[id_padrao]
                    nome = dados_agendamento.get("nome", "Ocupado")
                    # A verificação de "Fechado" agora acontece ANTES da regra de almoço.
                    if nome == "Fechado":
                        status, texto_botao, is_clicavel = "fechado", "Fechado", False
                    elif nome == "Almoço": # Mantém a possibilidade de fechar como almoço em dias especiais
                        status, texto_botao, is_clicavel = "almoco", "Almoço", False
                    else: # Se for qualquer outro nome, é um agendamento normal
                        status, texto_botao = "ocupado", nome

                elif id_bloqueado in ocupados_map:
                    status, texto_botao, dados_agendamento = "ocupado", "Bloqueado", {"nome": "BLOQUEADO"}

                # 2. SE NÃO HOUVER NADA NO BANCO para este horário, aplicamos as regras fixas do sistema.
                elif horario in ["07:00", "07:30"]:
                    status, texto_botao, is_clicavel = "indisponivel", "SDJ", False
                
                elif horario == "08:00" and barbeiro == "Lucas Borges":
                    status, texto_botao, is_clicavel = "indisponivel", "Indisponível", False
                
                elif dia_semana == 6: # Domingo
                    status, texto_botao, is_clicavel = "fechado", "Fechado", False

                elif dia_semana < 5 and hora_int in [12, 13]: # Almoço
                     status, texto_botao, is_clicavel = "almoco", "Almoço", False

            # --- SEU CÓDIGO ORIGINAL DE BOTÕES RESTAURADO E ADAPTADO ---
            key = f"btn_{data_str}_{horario}_{barbeiro}"
            with grid_cols[i+1]:
                if status == 'disponivel':
                    cor_fundo = '#28a745'  # Verde
                    # O 'texto_botao' e 'is_clicavel' já foram definidos antes, mas aqui garantimos o padrão
                elif status == 'ocupado':
                    cor_fundo = '#dc3545'  # Vermelho
                elif status == 'almoco':
                    cor_fundo = '#ffc107'  # Laranja/Amarelo
                    is_clicavel = False # Garante que não é clicável
                elif status == 'indisponivel':
                    cor_fundo = '#808080'  # Cinza
                    is_clicavel = False # Garante que não é clicável
                elif status == 'fechado':
                     cor_fundo = '#A9A9A9' # Cinza claro
                     is_clicavel = False
                else: # Caso padrão
                    cor_fundo = '#6c757d'
                    is_clicavel = False
                
                cor_texto = "black" if status == "almoco" or status == "fechado" else "white"
                
                botao_html = f"""
                    <button style='
                        background-color: {cor_fundo}; color: {cor_texto}; border: none;
                        border-radius: 6px; padding: 4px 8px; width: 100%; font-size: 12px;
                        font-weight: bold; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
                    ' onclick="document.getElementById('{key}').click()">{texto_botao}</button>
                """
                st.markdown(botao_html, unsafe_allow_html=True)
                st.markdown(f"<div style='text-align: center; font-size: 12px; color: #AAA;'>{barbeiro}</div>", unsafe_allow_html=True)

                # O botão invisível que aciona a lógica, com as chamadas CORRIGIDAS
                if st.button("", key=key, disabled=not is_clicavel):
                    if status == 'disponivel':
                        st.session_state.view = 'agendar'
                        st.session_state.agendamento_info = {
                            'data_obj': data_obj, # Passa o objeto de data
                            'horario': horario,
                            'barbeiro': barbeiro
                        }
                        st.rerun()
                    elif status in ['ocupado', 'almoco', 'fechado']:
                        st.session_state.view = 'cancelar'
                        st.session_state.agendamento_info = {
                            'data_obj': data_obj, # Passa o objeto de data
                            'horario': horario,
                            'barbeiro': barbeiro,
                            'dados': dados_agendamento
                        }
                        st.rerun()
                        














