from langchain_chroma.vectorstores import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI , GoogleGenerativeAIEmbeddings


load_dotenv()

CAMINHO_DB = 'db'

prompt_template = prompt_template = """
Você é um Engenheiro de Software Sênior e assistente técnico especializado no Manual de Engenharia de Software da equipe.
Sua tarefa é responder à pergunta do usuário utilizando EXCLUSIVAMENTE as informações fornecidas na base de conhecimento abaixo.

Regras obrigatórias:
1. Baseie-se estritamente no contexto fornecido. Não invente regras, padrões ou informações externas que não estejam no texto.
2. Se a resposta não estiver na base de conhecimento, responda exatamente: "Não encontrei essa informação no Manual de Engenharia de Software."
3. Mantenha a resposta clara, objetiva e bem estruturada (use tópicos, checklists ou blocos de código quando ajudar na leitura).

Pergunta do usuário:
{pergunta}

Base de conhecimento:
{base_conhecimento}
"""
def perguntar():
    pergunta = input("Escreva sua pergunta: ")

    #carregar banco 

    funcao_embedding = GoogleGenerativeAIEmbeddings(model='models/gemini-embedding-001')
    db = Chroma(persist_directory=CAMINHO_DB, embedding_function=funcao_embedding)

    #comparar pergunta do usuario (embedding) com banco
    resultados = db.similarity_search_with_relevance_scores(pergunta, k=5)
    if len(resultados) == 0 or resultados[0][1] < 0.5:
        print('Não conseguiu achar uma informação relevante')
        return
    texto_resultados = []
    for resultado in resultados:
        texto = resultado[0].page_content
        texto_resultados.append(texto)

    base_conhecimento = "\n\n----\n\n".join(texto_resultados)
    prompt = ChatPromptTemplate.from_template(prompt_template)
    prompt = prompt.invoke({'pergunta': pergunta, 'base_conhecimento': base_conhecimento})

    modelo = ChatGoogleGenerativeAI(model='gemini-3-flash-preview')
    resposta = modelo.invoke(prompt)
    print('\nResposta da IA:\n')
    print(resposta.text)

perguntar()