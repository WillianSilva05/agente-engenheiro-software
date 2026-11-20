# Assistente RAG - Manual de Engenharia de Software

Assistente de consulta para o Manual de Engenharia de Software da equipe. Permite buscar normas, padrões de arquitetura, requisitos e processos internos diretamente pelo PDF, reduzindo alucinações e controlando custo e latência.

## Como funciona

Em vez de usar Tool Calling ou roteadores estáticos em regex, o fluxo usa um prompt unificado com busca vetorial condicional:

1. **Cache no Upstash Redis:** Antes de consultar o banco vetorial, a pergunta é normalizada e convertida em hash (`SHA-256`). Se já tiver sido respondida na última hora (TTL de 3600s), retorna direto do Redis em ~0.15s sem gastar tokens.
2. **Busca no ChromaDB:** Para perguntas novas, busca os 5 trechos mais próximos usando `models/gemini-embedding-001` e descarta qualquer resultado com relevância abaixo de `0.5`.
3. **Resposta com Gemini (`gemini-3-flash-preview`):** Se houver trechos válidos, o modelo responde estritamente com base neles. Se a busca voltar vazia, o próprio prompt trata saudações e histórico da sessão ou bloqueia perguntas técnicas fora do escopo do manual.
4. **Observabilidade (Langfuse + Streamlit):** Cada turno envia os traces de forma síncrona (`flush`) para o Langfuse com tags (`rag` ou `conversa`) e exibe tempo, tokens, custo estimado e fontes consultadas na interface.

## Stack

- **Python 3.11+**
- **LangChain** (`langchain`, `langchain-core`, `langchain-chroma`, `langchain-google-genai`, `langchain-community`)
- **Google Gemini** (`gemini-3-flash-preview` e `models/gemini-embedding-001`)
- **ChromaDB** (persistência local em `db/`)
- **Upstash Redis** (histórico de conversa e cache de respostas)
- **Langfuse** (rastreamento e métricas)
- **Streamlit** (interface web)

## Estrutura

```text
├── agent/
│   ├── criar_db.py          # Leitura dos PDFs em base/, chunking e criação do banco ChromaDB
│   ├── main.py              # Fluxo do agente, busca vetorial e prompt
│   └── observabilidade.py   # Redis (cache e histórico), Langfuse e cálculo de custo
├── base/                    # PDF do Manual de Engenharia de Software
├── db/                      # Índice vetorial gerado pelo ChromaDB
├── app.py                   # Interface Streamlit
├── .env.example             # Exemplo de variáveis de ambiente
└── requirements.txt         # Dependências do projeto
```

## Rodando localmente

1. Clone o repositório e crie o ambiente virtual:

```bash
git clone <URL_DO_SEU_REPOSITORIO>
cd <NOME_DA_PASTA>

python -m venv venv
# Windows
venv\Scripts\activate
# Linux/macOS
source venv/bin/activate
```

2. Instale as dependências:

```bash
pip install -r requirements.txt
```

3. Crie um arquivo `.env` na raiz baseado no `.env.example`:

```env
GOOGLE_API_KEY="sua_chave_google_gemini"
REDIS_URL="rediss://default:sua_senha@seu-endpoint.upstash.io:6379"

# Opcional (observabilidade)
LANGFUSE_PUBLIC_KEY="pk-lf-..."
LANGFUSE_SECRET_KEY="sk-lf-..."
LANGFUSE_HOST="https://cloud.langfuse.com"
```

4. Coloque o PDF do manual na pasta `data/` e gere o banco vetorial:

```bash
python ingest.py
```

5. Inicie a aplicação:

```bash
# Interface web
streamlit run app.py

# Ou direto pelo terminal
python -m agent.main
```