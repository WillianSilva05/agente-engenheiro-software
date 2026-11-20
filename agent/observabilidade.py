import hashlib
import json
import os
import redis
from langchain_community.chat_message_histories import RedisChatMessageHistory
from langfuse import get_client
from langfuse.langchain import CallbackHandler

# tabela de referencia de precos por milhao de tokens (USD)
PRECOS_POR_MILHAO = {
    'gemini-3-flash-preview': {'input': 0.15, 'output': 0.60, 'cache_read': 0.0375},
    'gemini-2.5-flash-lite': {'input': 0.075, 'output': 0.30, 'cache_read': 0.01875},
}


def obter_cliente_redis() -> redis.Redis:
    return redis.from_url(os.environ['REDIS_URL'], decode_responses=True)


def configurar_cache_llm() -> str:
    cliente = obter_cliente_redis()
    cliente.ping()
    return 'Redis cache ativo'


def obter_historico_sessao(session_id: str, ttl_segundos: int = 3600) -> RedisChatMessageHistory:
    return RedisChatMessageHistory(
        session_id=session_id,
        url=os.environ['REDIS_URL'],
        ttl=ttl_segundos,
    )


def configurar_rastreamento_langfuse() -> CallbackHandler | None:
    if os.getenv('LANGFUSE_PUBLIC_KEY') and os.getenv('LANGFUSE_SECRET_KEY'):
        return CallbackHandler()
    return None


def enviar_logs_langfuse() -> None:
    # descarrega a fila do langfuse imediatamente para aparecer no painel na hora
    if os.getenv('LANGFUSE_PUBLIC_KEY') and os.getenv('LANGFUSE_SECRET_KEY'):
        try:
            get_client().flush()
        except Exception:
            pass


def _gerar_chave_cache(pergunta_normalizada: str) -> str:
    hash_pergunta = hashlib.sha256(pergunta_normalizada.encode('utf-8')).hexdigest()
    return f"rag:resposta:{hash_pergunta}"


def buscar_cache_resposta(pergunta_normalizada: str) -> dict | None:
    cliente = obter_cliente_redis()
    dados_salvos = cliente.get(_gerar_chave_cache(pergunta_normalizada))
    if dados_salvos:
        return json.loads(dados_salvos)
    return None


def salvar_cache_resposta(pergunta_normalizada: str, dados: dict, ttl_segundos: int = 3600) -> None:
    cliente = obter_cliente_redis()
    cliente.setex(
        _gerar_chave_cache(pergunta_normalizada),
        ttl_segundos,
        json.dumps(dados, ensure_ascii=False),
    )


def extrair_metricas_turno(
    modelo: str,
    latencia_ms: float,
    score_maximo: float,
    usage_metadata: dict | None,
    cache_hit: bool,
) -> dict:
    usage = usage_metadata or {}
    input_tokens = 0 if cache_hit else usage.get('input_tokens', 0)
    output_tokens = 0 if cache_hit else usage.get('output_tokens', 0)
    total_tokens = 0 if cache_hit else usage.get('total_tokens', input_tokens + output_tokens)
    cache_read = usage.get('input_token_details', {}).get('cache_read', 0)
    reasoning_tokens = usage.get('output_token_details', {}).get('reasoning', 0)

    tabela = PRECOS_POR_MILHAO.get(modelo, {'input': 0.15, 'output': 0.60, 'cache_read': 0.0375})
    tokens_input_novos = max(0, input_tokens - cache_read)

    custo_usd = 0.0 if cache_hit else round(
        (tokens_input_novos / 1_000_000) * tabela['input']
        + (cache_read / 1_000_000) * tabela['cache_read']
        + (output_tokens / 1_000_000) * tabela['output'],
        6,
    )

    return {
        'latencia_ms': round(latencia_ms, 2),
        'score_relevancia': round(score_maximo, 4),
        'cache_hit': cache_hit,
        'custo_usd': custo_usd,
        'tokens': {
            'input': input_tokens,
            'output': output_tokens,
            'cache_read': cache_read,
            'reasoning': reasoning_tokens,
            'total': total_tokens,
        },
    }