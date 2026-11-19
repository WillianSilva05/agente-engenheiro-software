from langchain_community.document_loaders import PyPDFDirectoryLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma.vectorstores import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from dotenv import load_dotenv

load_dotenv()

PASTA_BASE = 'base'

def criar_db():
    documentos = carregar_documentos()
    chunks = dividir_chunks(documentos)
    vetorizar_chunks(chunks)

    #carregar documentos
def carregar_documentos():
    carregador = PyPDFDirectoryLoader(PASTA_BASE)
    documentos = carregador.load()
    return documentos

    #dividir documento em chunks 
def dividir_chunks(documentos):
    separador_documentos = RecursiveCharacterTextSplitter(
        chunk_size=1200,
        chunk_overlap=200,
        length_function=len,
        add_start_index=True,
        separators=["\n\n", "\n", ". ", " ", ""]
    )
    chunks = separador_documentos.split_documents(documentos)
    print(len(chunks))
    return chunks

    #vetorizar os chunks em emedding
def vetorizar_chunks(chunks):
    embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")
    db = Chroma.from_documents(chunks, embeddings, persist_directory="db")
    print("Banco de dados criado")
    print("Banco de dados criado com sucesso!")
criar_db()