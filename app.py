import os
import time
import uuid
import streamlit as st
from dotenv import load_dotenv
from agent.main import MODELO_CHAT, consultar_agente
from agent.observabilidade import (
    configurar_cache_llm,
    extrair_metricas_turno,
    obter_historico_sessao,
)

load_dotenv()

# configurar pagina e estilo compacto da barra lateral
st.set_page_config(
    page_title='Agente Engenharia de Software',
    page_icon='🤖',
    layout='wide',
)

st.markdown(
    """
    <style>
    [data-testid="stSidebar"] [data-testid="stMetricValue"] {
        font-size: 1.2rem;
    }
    .metricas-turno {
        display: flex;
        flex-wrap: wrap;
        justify-content: space-between;
        gap: 12px;
        padding: 8px 14px;
        margin-top: 6px;
        margin-bottom: 8px;
        border-radius: 8px;
        background-color: rgba(128, 128, 128, 0.08);
        border: 1px solid rgba(128, 128, 128, 0.2);
        font-size: 0.82rem;
    }
    .metrica-item {
        display: flex;
        flex-direction: column;
    }
    .metrica-titulo {
        opacity: 0.65;
        font-size: 0.72rem;
    }
    .metrica-valor {
        font-weight: 600;
    }
    .metrica-sub {
        opacity: 0.6;
        font-size: 0.7rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

status_cache = configurar_cache_llm()

# inicializar estado da sessao
if 'session_id' not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())[:8]

if 'metricas_sessao' not in st.session_state:
    st.session_state.metricas_sessao = []


def formatar_historico_texto(mensagens) -> str:
    if not mensagens:
        return 'Nenhuma mensagem anterior.'
    ultimas = mensagens[-6:]
    linhas = []
    for msg in ultimas:
        autor = 'Usuário' if msg.type == 'human' else 'Assistente'
        linhas.append(f"{autor}: {msg.content}")
    return '\n'.join(linhas)


def renderizar_card_metricas(m: dict):
    tempo_seg = m['latencia_ms'] / 1000
    relevancia_pct = int(m['score_relevancia'] * 100)
    total_tokens_turno = f"{m['tokens']['total']:,}".replace(',', '.')
    detalhe_tokens = f"{m['tokens']['input']} in · {m['tokens']['output']} out"

    if m['cache_hit']:
        origem = '⚡ Cache Redis'
        sub_custo = 'Custo zero'
    elif m['tokens']['total'] == 0:
        origem = 'Filtro local'
        sub_custo = 'Sem chamada API'
    else:
        origem = 'API Gemini'
        sub_custo = f"Cache read: {m['tokens']['cache_read']}"

    html_card = (
        f'<div class="metricas-turno">'
        f'<div class="metrica-item"><span class="metrica-titulo">⏱️ Tempo</span><span class="metrica-valor">{tempo_seg:.2f} s</span><span class="metrica-sub">{origem}</span></div>'
        f'<div class="metrica-item"><span class="metrica-titulo">🪙 Tokens</span><span class="metrica-valor">{total_tokens_turno}</span><span class="metrica-sub">{detalhe_tokens}</span></div>'
        f'<div class="metrica-item"><span class="metrica-titulo">💰 Custo</span><span class="metrica-valor">$ {m["custo_usd"]:.5f}</span><span class="metrica-sub">{sub_custo}</span></div>'
        f'<div class="metrica-item"><span class="metrica-titulo">🎯 Relevância</span><span class="metrica-valor">{relevancia_pct}%</span><span class="metrica-sub">Busca RAG</span></div>'
        f'</div>'
    )
    st.markdown(html_card, unsafe_allow_html=True)

    if m.get('resultados'):
        with st.expander(f"📚 Trechos consultados no manual ({len(m['resultados'])})"):
            for i, (doc, score) in enumerate(m['resultados'], 1):
                st.markdown(f"**Trecho {i} ({int(score * 100)}%):**\n\n{doc.page_content}")


# barra lateral com resumo da sessao e status
with st.sidebar:
    st.subheader('📊 Resumo da Sessão')

    metricas = st.session_state.metricas_sessao
    total_tokens = sum(m['tokens']['total'] for m in metricas)
    total_custo = sum(m['custo_usd'] for m in metricas)
    cache_hits = sum(1 for m in metricas if m['cache_hit'])
    latencia_media_seg = (
        (sum(m['latencia_ms'] for m in metricas) / len(metricas)) / 1000
        if metricas
        else 0.0
    )

    with st.container(border=True):
        col1, col2 = st.columns(2)
        col1.metric('Tempo Médio', f"{latencia_media_seg:.2f} s")
        col2.metric('Tokens Totais', f"{total_tokens:,}".replace(',', '.'))

        col3, col4 = st.columns(2)
        col3.metric('Custo Total', f"$ {total_custo:.5f}")
        col4.metric('Cache Hits', f"{cache_hits} / {len(metricas)}")

    st.subheader('🔌 Infraestrutura')
    langfuse_ativo = bool(os.getenv('LANGFUSE_PUBLIC_KEY') and os.getenv('LANGFUSE_SECRET_KEY'))
    st.caption(
        f"🟢 **{status_cache}**  \n"
        f"{'🟢 **Langfuse conectado**' if langfuse_ativo else '🟡 **Langfuse sem chaves**'}  \n"
        f"🤖 `{MODELO_CHAT}` · Sessão `{st.session_state.session_id}`"
    )

    st.divider()
    if st.button('🗑️ Nova Conversa', use_container_width=True):
        obter_historico_sessao(st.session_state.session_id).clear()
        st.session_state.metricas_sessao = []
        st.rerun()

# area principal do chat
st.title('🤖 Agente de Engenharia de Software')
st.caption('Tire dúvidas com base no Manual de Engenharia de Software da equipe.')

historico_chat = obter_historico_sessao(st.session_state.session_id)

# renderizar historico da conversa
for idx, msg in enumerate(historico_chat.messages):
    role = 'user' if msg.type == 'human' else 'assistant'
    with st.chat_message(role):
        st.markdown(msg.content)

        if role == 'assistant':
            idx_metrica = idx // 2
            if idx_metrica < len(st.session_state.metricas_sessao):
                renderizar_card_metricas(st.session_state.metricas_sessao[idx_metrica])

# processar nova pergunta
if pergunta := st.chat_input('Pergunte algo sobre o Manual de Engenharia de Software...'):
    with st.chat_message('user'):
        st.markdown(pergunta)

    with st.chat_message('assistant'):
        with st.spinner('Consultando manual e gerando resposta...'):
            inicio = time.perf_counter()
            historico_texto = formatar_historico_texto(historico_chat.messages)

            retorno = consultar_agente(
                pergunta=pergunta,
                historico_texto=historico_texto,
                session_id=st.session_state.session_id,
                origem='streamlit',
            )
            latencia_ms = (time.perf_counter() - inicio) * 1000

            texto_resposta = retorno['resposta']
            historico_chat.add_user_message(pergunta)
            historico_chat.add_ai_message(texto_resposta)

            metrica = extrair_metricas_turno(
                modelo=MODELO_CHAT,
                latencia_ms=latencia_ms,
                score_maximo=retorno['score_maximo'],
                usage_metadata=retorno['usage_metadata'],
                cache_hit=retorno['cache_hit'],
            )
            metrica['resultados'] = retorno['resultados']
            st.session_state.metricas_sessao.append(metrica)

            st.rerun()