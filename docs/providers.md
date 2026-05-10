# Providers

Both generation and embeddings are provider-agnostic.

## LLM providers

Supported values:

- `LLM_PROVIDER=openai`
- `LLM_PROVIDER=openrouter`
- `LLM_PROVIDER=ollama`

### OpenAI-compatible configuration

```env
LLM_PROVIDER=openai
LLM_API_KEY=...
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
```

Use the same shape for any OpenAI-compatible gateway by changing `LLM_BASE_URL`.

### OpenRouter configuration

```env
LLM_PROVIDER=openrouter
LLM_API_KEY=...
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_MODEL=qwen/qwen3-14b
```

### Ollama configuration

```env
LLM_PROVIDER=ollama
OLLAMA_HOST=http://ollama:11434
LLM_MODEL=qwen3:8b
```

## Embedding providers

Supported values:

- `EMBEDDING_PROVIDER=openai`
- `EMBEDDING_PROVIDER=openrouter`
- `EMBEDDING_PROVIDER=ollama`

### Examples

```env
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-small
```

```env
EMBEDDING_PROVIDER=openrouter
EMBEDDING_BASE_URL=https://openrouter.ai/api/v1
EMBEDDING_MODEL=text-embedding-3-small
```

```env
EMBEDDING_PROVIDER=ollama
OLLAMA_HOST=http://ollama:11434
EMBEDDING_MODEL=nomic-embed-text
```
