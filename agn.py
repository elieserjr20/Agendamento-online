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
def enviar_email(assunto, mensagem):
    """
    Função atualizada para enviar e-mails usando a API da Brevo.
    Lê a chave da API e o e-mail do remetente das variáveis de ambiente do Render.
    """
    # Passo 1: O código busca a chave secreta no "cofre" do Render.
    api_key = os.environ.get("BREVO_API_KEY")
    
    # Passo 2: O código busca o teu e-mail (que também está no "cofre").
    sender_email = os.environ.get("EMAIL_CREDENCIADO")

    # Se não encontrar as chaves no Render, avisa no log e para.
    if not api_key or not sender_email:
        print("AVISO: Credenciais da Brevo (BREVO_API_KEY ou EMAIL_CREDENCIADO) não configuradas. E-mail não enviado.")
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
        st.error("Ocorreu um erro ao tentar enviar o e-mail de notificação.")

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
def salvar_agendamento(data_obj, horario, nome, telefone, servicos, barbeiro):
    if not db: return False
    data_para_id = data_obj.strftime('%Y-%m-%d')
    chave_agendamento = f"{data_para_id}_{horario}_{barbeiro}"
    try:
        # CORREÇÃO: Converte o objeto 'date' para 'datetime' antes de salvar
        data_para_salvar = datetime.combine(data_obj, datetime.min.time())
        db.collection('agendamentos').document(chave_agendamento).set({
            'nome': nome, 'telefone': telefone, 'servicos': servicos,
            'barbeiro': barbeiro, 'data': data_para_salvar, 'horario': horario
        })
        return True
    except Exception as e:
        st.error(f"Erro ao salvar agendamento: {e}")
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

#
# SUBSTITUA A SUA FUNÇÃO 'verificar_disponibilidade_especifica' POR ESTA:
#
def verificar_disponibilidade_especifica(data_obj, horario, barbeiro):
    """
    Verifica de forma eficiente se um único horário está livre e, 
    se não estiver, retorna os detalhes de quem o ocupa.
    
    Esta é a versão CORRIGIDA que retorna um DICIONÁRIO.
    """
    if not db: 
        return {'status': 'indisponivel', 'cliente': 'DB Error'}
        
    data_para_id = data_obj.strftime('%Y-%m-%d')
    id_padrao = f"{data_para_id}_{horario}_{barbeiro}"
    id_bloqueado = f"{data_para_id}_{horario}_{barbeiro}_BLOQUEADO"
    
    try:
        # Tenta buscar o agendamento padrão
        doc_padrao_ref = db.collection('agendamentos').document(id_padrao)
        doc_padrao = doc_padrao_ref.get()
        if doc_padrao.exists:
            dados = doc_padrao.to_dict()
            nome_cliente = dados.get('nome', 'Ocupado')
            
            # Distingue bloqueios internos de clientes
            if nome_cliente == "Fechado":
                return {'status': 'fechado', 'cliente': 'Fechado'}
            if nome_cliente == "Almoço":
                return {'status': 'almoco', 'cliente': 'Almoço'}
                
            return {'status': 'ocupado', 'cliente': nome_cliente}

        # Tenta buscar o bloqueio de "Corte+Barba"
        doc_bloqueado_ref = db.collection('agendamentos').document(id_bloqueado)
        if doc_bloqueado_ref.get().exists:
            # Se for um bloqueio de Corte+Barba, também tratamos como ocupado
            return {'status': 'ocupado', 'cliente': 'BLOQUEADO'}
            
        # Se não achou nenhum dos dois, está livre
        return {'status': 'disponivel'}
        
    except Exception as e:
        print(f"Erro ao verificar disponibilidade: {e}")
        return {'status': 'indisponivel', 'cliente': 'Erro'}

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

def _normalizar_horario(texto):
    """Tenta converter '10 e meia', '10 horas', '10:30', '10' para '10:00' ou '10:30'."""
    texto = texto.lower().strip()
    
    # Converte "10 e meia" para "10:30"
    texto = re.sub(r'(\d+)\s*e\s*meia', r'\1:30', texto)
    # Converte "10 e 30" para "10:30"
    texto = re.sub(r'(\d+)\s*e\s*(\d+)', r'\1:\2', texto)
    # Converte "10 horas" para "10:00"
    texto = re.sub(r'(\d+)\s*horas?', r'\1:00', texto)
    
    # Encontra o padrão de hora (ex: "10:30" ou "10")
    match = re.search(r'(\d{1,2})(:(\d{2}))?', texto)
    if not match:
        return None

    hora = int(match.group(1))
    minutos_str = match.group(3)
    
    minutos = 0
    if minutos_str:
        minutos = int(minutos_str)
    
    # Arredonda os minutos para 00 ou 30 (ex: 10:05 -> 10:00, 10:40 -> 10:30)
    if minutos < 15:
        minutos = 0
    elif minutos >= 15 and minutos < 45:
        minutos = 30
    else: # se for > 45, arredonda para a próxima hora
        minutos = 0
        hora += 1
        
    # Validação final da hora
    if hora < 8 or hora > 22: # (Ajuste se necessário)
        return None 

    return f"{hora:02d}:{minutos:02d}"

def parsear_comando(texto):
    texto_original = texto
    barbeiro = None
    horario_normalizado = None

    # --- ETAPA DE NORMALIZAÇÃO PRÉVIA ---
    # Remove acentos do texto de entrada para facilitar o match
    texto_sem_acento = texto
    if isinstance(texto, str):
        try:
            # Tenta normalizar, se falhar, usa o original
            texto_sem_acento = ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn')
        except:
            pass # Mantém o texto original se a normalização falhar
    
    # 1. Encontrar o Barbeiro (com RegEx "Fuzzy")
    # Usamos o texto_sem_acento e re.IGNORECASE para máxima flexibilidade
    
    # Procura por "lucas borges" OU "lucas"
    if re.search(r'lucas\s*borges|lucas', texto_sem_acento, re.IGNORECASE):
        barbeiro = "Lucas Borges"
        # Remove a(s) palavra(s) que encontrou (do texto original)
        texto = re.sub(r'lucas\s*borges|lucas', '', texto, flags=re.IGNORECASE)
        
    # ESTA É A LINHA QUE APANHA O "ALUIZIO" (agora no texto_sem_acento):
    # Procura por "Aluisio", "Aloisio" ou "Alu"
    elif re.search(r'aluisio|aloisio|alu', texto_sem_acento, re.IGNORECASE):
        barbeiro = "Aluizio"
        # Remove a(s) palavra(s) que encontrou (do texto original)
        texto = re.sub(r'alu[ií]sio|alo[ií]sio|alu', '', texto, flags=re.IGNORECASE)
    
    else:
        return None # Barbeiro é obrigatório

    # 2. Encontrar o Horário (A sua lógica de _normalizar_horario era melhor, vamos usá-la)
    match_horario = re.search(r'(?:às|para\s*às|pelas)?\s*([\d\s:e]+(?:meia|horas?)?)', texto, re.IGNORECASE)
    if match_horario:
        horario_str = match_horario.group(1)
        horario_normalizado = _normalizar_horario(horario_str) # <-- Esta é a sua função 'def _normalizar_horario()'
        if horario_normalizado:
            texto = texto.replace(match_horario.group(0), '')
        else:
            return None 
    else:
        return None 

    # 3. O que sobrar é o Nome do Cliente
    texto = re.sub(r'\s*(com|para|o|a)\s*', ' ', texto, flags=re.IGNORECASE)
    nome_cliente = texto.strip()
    
    if not nome_cliente or not horario_normalizado or not barbeiro:
        print(f"Parse falhou: N={nome_cliente}, H={horario_normalizado}, B={barbeiro}")
        return None

    return {
        'nome': nome_cliente.title(),
        'horario': horario_normalizado,
        'barbeiro': barbeiro
    }

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
                        # Sua lógica de bloquear o próximo horário (mantida e corrigida)
                        precisa_bloquear_proximo = False
                        if "Barba" in servicos_selecionados and any(c in servicos_selecionados for c in ["Tradicional", "Social", "Degradê", "Navalhado"]):
                            horario_seguinte_dt = datetime.strptime(horario, '%H:%M') + timedelta(minutes=30)
                            horario_seguinte_str = horario_seguinte_dt.strftime('%H:%M')
                            if verificar_disponibilidade_especifica(data_obj, horario_seguinte_str, barbeiro):
                                precisa_bloquear_proximo = True
                            else:
                                st.error("Não é possível agendar Corte+Barba. O horário seguinte não está disponível.")
                                st.stop()

                        # Chamada da função de salvar com a variável correta (data_obj)
                        if salvar_agendamento(data_obj, horario, nome_cliente, "INTERNO", servicos_selecionados, barbeiro):
                            if precisa_bloquear_proximo:
                                bloquear_horario(data_obj, horario_seguinte_str, barbeiro, "BLOQUEADO")

                            st.success(f"Agendamento para {nome_cliente} confirmado!")
                            
                            # E-mail enviado com a data formatada corretamente
                            assunto_email = f"Novo Agendamento: {nome_cliente} em {data_str_display}"
                            mensagem_email = (
                                f"Agendamento interno:\n\nCliente: {nome_cliente}\nData: {data_str_display}\n"
                                f"Horário: {horario}\nBarbeiro: {barbeiro}\n"
                                f"Serviços: {', '.join(servicos_selecionados) if servicos_selecionados else 'Nenhum'}"
                            )
                            enviar_email(assunto_email, mensagem_email)
                            
                            st.cache_data.clear()
                            st.session_state.view = 'main'
                            time.sleep(2)
                            st.rerun()
                        else:
                            st.error("Falha ao salvar. Tente novamente.")
    
    # Botão de voltar, também indentado corretamente
    if st.button("⬅️ Voltar para a Agenda"):
        st.session_state.view = 'main'
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
                st.session_state.view = 'main'
                time.sleep(2)
                st.rerun()
            else:
                st.error("Não foi possível liberar. O horário pode já ter sido removido.")

    # Botão para voltar para a agenda
    if cols[1].button("⬅️ Voltar para a Agenda", use_container_width=True):
        st.session_state.view = 'main'
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
        st.session_state.view = 'main'
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
                            st.session_state.view = 'main' # <-- Corrigido para 'agenda'
                            time.sleep(2)
                            st.rerun()
                        else:
                            st.error("Ocorreu um erro ao fechar um ou mais horários.")
            except ValueError:
                st.error("Horário selecionado inválido.")

        if btn_cols[1].button("⬅️ Voltar", use_container_width=True):
            st.session_state.view = 'main' # <-- Corrigido para 'agenda'
            st.rerun()
            
# --- TELA PRINCIPAL (GRID DE AGENDAMENTOS) ---
else:
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

    # --- PLANO D: O MICROFONE DO TECLADO (A SOLUÇÃO LIMPA) ---
    
    with st.expander("🎙️ Agendamento Rápido por Voz (para Hoje)", expanded=True):
        
        st.info("Clique na caixa abaixo e use o **microfone do seu teclado** para falar.")

        # --- ETAPA 1: OUVIR (Via Teclado) ---
        
        # Usamos um 'form' para que 'Enter' também funcione
        with st.form(key="form_voz"):
            texto_falado = st.text_input(
                "Comando de Voz:", 
                key="voz_text_input", 
                placeholder="Ex: Júnior às 10 com Lucas"
            )
            
            # O "estímulo" agora é um botão de Python normal!
            submitted = st.form_submit_button("Processar Comando", type="primary", use_container_width=True)

        if submitted and texto_falado:
            st.info(f"Comando recebido: \"{texto_falado}\"")
            
            # 2. Tenta traduzir
            dados = parsear_comando(texto_falado)
            
            if dados:
                # 3. SUCESSO! Armazena na sessão
                st.session_state.dados_voz = {
                    'nome': dados['nome'],
                    'horario': dados['horario'],
                    'barbeiro': dados['barbeiro'],
                    'data_obj': datetime.today().date()
                }
            else:
                # 4. FALHA.
                st.session_state.dados_voz = None
                st.error("Não entendi o comando. Tente 'Nome às XX horas com Barbeiro'.")
            
            # Força o rerun para mostrar a Etapa 2
            st.rerun() 

        # --- ETAPA 2: CONFIRMAR ---
        # Esta é a sua lógica de confirmação, que já está correta.
        # Ela é acionada pelo st.session_state.dados_voz (preenchido acima)
        if st.session_state.dados_voz:
            try:
                dados_para_confirmar = st.session_state.dados_voz
                nome = dados_para_confirmar['nome']
                horario = dados_para_confirmar['horario']
                barbeiro = dados_para_confirmar['barbeiro']
                data_obj = dados_para_confirmar['data_obj']

                st.markdown("---")
                st.subheader("Confirmar Agendamento por Voz?")
                st.write(f"**Cliente:** `{nome}`")
                st.write(f"**Horário:** `{horario}`")
                st.write(f"**Barbeiro:** `{barbeiro}`")
                
                col_confirm, col_cancel = st.columns(2)
                
                # ... (O seu código de 'col_confirm.button' e 'col_cancel.button' 
                #      (linhas 890-946 do seu agn(15).py) 
                #      ENTRA EXATAMENTE AQUI, SEM MUDANÇAS) ...
                
                # (Vou colar por segurança, mas o seu já estava certo)
                if col_confirm.button("✅ Confirmar Agendamento", key="btn_confirm_voz", type="primary", use_container_width=True):
                    
                    disponibilidade = verificar_disponibilidade_especifica(data_obj, horario, barbeiro)

                    if disponibilidade['status'] == 'disponivel':
                        with st.spinner("Agendando..."):
                            if salvar_agendamento(data_obj, horario, nome, "INTERNO (Voz)", ["(Voz)"], barbeiro):
                                st.success(f"Agendado! {nome} às {horario} com {barbeiro}.")
                                st.balloons()
                                
                                data_str_display = data_obj.strftime('%d/%m/%Y')
                                assunto_email = f"Novo Agendamento (VOZ): {nome} em {data_str_display}"
                                mensagem_email = (f"Agendamento rápido por VOZ:\n\nCliente: {nome}\nData: {data_str_display}\n"
                                                  f"Horário: {horario}\nBarbeiro: {barbeiro}")
                                enviar_email(assunto_email, mensagem_email)
                                
                                st.cache_data.clear()
                                st.session_state.dados_voz = None
                                time.sleep(2)
                                st.rerun()
                            else:
                                st.error("Falha inesperada ao salvar no banco de dados.")
                    
                    elif disponibilidade['status'] in ['ocupado', 'almoco', 'fechado']:
                        cliente_existente = disponibilidade.get('cliente', 'um compromisso')
                        st.error(f"❌ HORÁRIO BLOQUEADO! O horário das {horario} com {barbeiro} já está ocupado por {cliente_existente}.")
                        st.session_state.dados_voz = None
                    
                    else:
                        st.error("Erro desconhecido ao verificar disponibilidade.")
                        st.session_state.dados_voz = None

                if col_cancel.button("❌ Cancelar", key="btn_cancel_voz", use_container_width=True):
                    st.session_state.dados_voz = None
                    st.rerun()

            except KeyError:
                st.error("Erro nos dados da sessão. Por favor, fale novamente.")
                st.session_state.dados_voz = None

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
                        






























