from functools import lru_cache
from pathlib import Path
from langchain_chroma import Chroma
from langchain_core.documents import Document
from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from agent.observabilidade import (
    buscar_cache_resposta,
    configurar_rastreamento_langfuse,
    enviar_logs_langfuse,
    salvar_cache_resposta,
)

load_dotenv()

CAMINHO_DB = str(Path(__file__).resolve().parent.parent / 'db')

MODELO_CHAT = 'gemini-3-flash-preview'
MODELO_EMBEDDING = 'models/gemini-embedding-001'

prompt_template =  """
Você é um Engenheiro de Software Sênior e assistente técnico especializado no Manual de Engenharia de Software da equipe.
Sua tarefa é responder à pergunta do usuário utilizando o histórico recente da conversa e a base de conhecimento fornecida abaixo.

Regras obrigatórias:
1. Se a mensagem for uma saudação, apresentação pessoal, agradecimento ou pergunta sobre o que você faz, responda de forma cordial, apresente-se como o Assistente Técnico do Manual de Engenharia de Software e explique resumidamente que pode ajudar com dúvidas sobre arquitetura, requisitos, modelagem e boas práticas do manual.
2. Se o usuário perguntar algo já mencionado no histórico da conversa (como o próprio nome), responda naturalmente usando o histórico.
3. Para perguntas técnicas ou sobre processos, baseie-se EXCLUSIVAMENTE na base de conhecimento fornecida abaixo. Não invente regras, padrões ou informações externas que não estejam no texto.
4. Se for uma pergunta técnica e a base de conhecimento estiver vazia ou não contiver a resposta, responda exatamente: "Não encontrei essa informação no Manual de Engenharia de Software."
5. Mantenha a resposta clara, objetiva e bem estruturada (use tópicos, checklists ou blocos de código quando ajudar na leitura).

Pergunta do usuário:
{pergunta}

Histórico recente da conversa:
{historico}

Base de conhecimento:
{base_conhecimento}
"""

@lru_cache(maxsize=1)
def obter_banco_vetorial() -> Chroma:
    funcao_embedding = GoogleGenerativeAIEmbeddings(model=MODELO_EMBEDDING)
    return Chroma(persist_directory=CAMINHO_DB, embedding_function=funcao_embedding)

def consultar_agente(
    pergunta: str,
    historico_texto: str = 'Nenhuma mensagem anterior.',
    session_id: str = 'terminal',
    origem: str = 'cli',
) -> dict:
    #verificar cache no redis
    chave_cache = ' '.join(pergunta.lower().strip().split())
    cache_encontrado = buscar_cache_resposta(chave_cache)
    if cache_encontrado:
        resultados_cache = [
            (Document(page_content=item['texto']), item['score'])
            for item in cache_encontrado.get('trechos', [])
        ]
        return {
            'resposta': cache_encontrado['resposta'],
            'usage_metadata': {},
            'cache_hit': True,
            'score_maximo': cache_encontrado['score_maximo'],
            'resultados': resultados_cache,
        }

    #carregar banco
    db = obter_banco_vetorial()

    #comparar pergunta do usuario (embedding) com banco
    resultados = db.similarity_search_with_relevance_scores(pergunta, k=5)
    score_max = resultados[0][1] if resultados else 0.0

    texto_resultados = []
    resultados_validos = []
    for resultado in resultados:
        if resultado[1] >= 0.5:
            texto = resultado[0].page_content
            texto_resultados.append(texto)
            resultados_validos.append(resultado)

    if len(texto_resultados) > 0:
        base_conhecimento = "\n\n----\n\n".join(texto_resultados)
        tag_tipo = 'rag'
    else:
        base_conhecimento = 'Nenhum trecho relevante encontrado no manual para esta mensagem.'
        tag_tipo = 'conversa'

    prompt = ChatPromptTemplate.from_template(prompt_template)
    prompt = prompt.invoke({
        'pergunta': pergunta,
        'historico': historico_texto,
        'base_conhecimento': base_conhecimento,
    })

    rastreador = configurar_rastreamento_langfuse()
    config_execucao = {
        'callbacks': [rastreador] if rastreador else [],
        'metadata': {
            'langfuse_session_id': session_id,
            'langfuse_tags': [tag_tipo, 'engenharia-software', origem],
        },
    }

    modelo = ChatGoogleGenerativeAI(model=MODELO_CHAT)
    resposta = modelo.invoke(prompt, config=config_execucao)
    enviar_logs_langfuse()
    usage_meta = getattr(resposta, 'usage_metadata', None) or {}

    #salvar no cache do redis se houve consulta valida ao manual
    if len(resultados_validos) > 0 and 'Não encontrei essa informação' not in resposta.text:
        salvar_cache_resposta(
            chave_cache,
            {
                'resposta': resposta.text,
                'score_maximo': score_max,
                'trechos': [
                    {'texto': item[0].page_content, 'score': float(item[1])}
                    for item in resultados_validos
                ],
            },
        )

    return {
        'resposta': resposta.text,
        'usage_metadata': usage_meta,
        'cache_hit': False,
        'score_maximo': score_max,
        'resultados': resultados_validos,
    }

def perguntar():
    pergunta = input("Escreva sua pergunta: ")
    retorno = consultar_agente(pergunta)
    print('\nResposta da IA:\n')
    print(retorno['resposta'])

if __name__ == '__main__':
    perguntar()