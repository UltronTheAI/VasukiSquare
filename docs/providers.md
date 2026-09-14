# LLM & Search Providers Guide

VasukiSquare features a flexible backend architecture supporting both cloud and local LLMs alongside multi-provider web search backends.

---

## 1. Supported LLM Providers

VasukiSquare supports two primary LLM execution environments:
1. **Groq Cloud** (High-speed inference via Llama 3.3, GPT-OSS, and Qwen)
2. **Ollama** (100% offline, private local model execution)

Provider selection is configured via `LLM_PROVIDER` in `.env`:
- `LLM_PROVIDER=auto`: Automatically routes to Groq if `GROQ_API_KEY` is provided; otherwise routes to Ollama.
- `LLM_PROVIDER=groq`: Enforces Groq cloud execution (raises an error if `GROQ_API_KEY` is missing).
- `LLM_PROVIDER=ollama`: Enforces local Ollama execution.

---

## 2. Groq Cloud Setup & Model Pooling

Groq delivers ultra-fast generation speeds (often exceeding 200–500 tokens/second), allowing 60-page books to be researched, planned, and authored in minutes.

### 1. Account & API Key Setup
1. Create an account at [console.groq.com](https://console.groq.com/).
2. Navigate to **API Keys** and generate a new key (`gsk_...`).
3. Add the key to `.env`:
   ```env
   GROQ_API_KEY=gsk_your_groq_api_key_here
   ```

### 2. Multi-Key Rotation Pool
You can supply multiple Groq API keys separated by commas. VasukiSquare automatically pools and rotates keys to maximize throughput and seamlessly handle rate limits:

```env
GROQ_API_KEY=gsk_key1,gsk_key2,gsk_key3
GROQ_KEY_STRATEGY=preferred   # Options: "preferred", "round_robin", "rotate"
GROQ_KEY_COOLDOWN_SECONDS=60.0
```

### 3. Model Failover Pool
To protect against individual model downtime or token rate limits (HTTP 429), configure a model pool:

```env
GROQ_MODELS=openai/gpt-oss-120b,llama-3.3-70b-versatile,llama-3.1-8b-instant
GROQ_MODEL_STRATEGY=ordered
GROQ_MODEL_FALLBACK=true
GROQ_RETRIES_PER_MODEL=1
```

If a rate limit occurs during content generation, the engine immediately fails over to the next candidate model in the pool without interrupting the book build.

### 4. Task-Specific Pools (Optional)
You can assign specialized models to specific pipeline stages:

```env
GROQ_MODELS_PLANNING=openai/gpt-oss-120b
GROQ_MODELS_RESEARCH=llama-3.3-70b-versatile
GROQ_MODELS_WRITING=openai/gpt-oss-120b,llama-3.3-70b-versatile
```

---

## 3. Ollama Local LLM Setup (Zero-Cost & Offline)

Ollama allows VasukiSquare to run entirely on your local machine with zero external cloud dependencies or API fees.

### 1. Installing & Starting Ollama
1. Download Ollama from [ollama.com](https://ollama.com/) for Windows, macOS, or Linux.
2. Start the Ollama server:
   ```bash
   ollama serve
   ```

### 2. Pulling Recommended Models
Pull the recommended high-performance structured instruction models:

```bash
# Recommended default (High accuracy structured JSON output)
ollama pull qwen2.5:7b-instruct

# Alternative models
ollama pull llama3.1:8b
ollama pull mistral:7b
```

### 3. Configuring VasukiSquare for Ollama
In `.env`:
```env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:7b-instruct
OLLAMA_NUM_CTX=8192
```

---

## 4. Web Search & Research Providers

VasukiSquare grounds every chapter in real-world facts and verified citations using swappable search backends.

Configure via `SEARCH_PROVIDER` in `.env`:
- `auto`: Uses SearXNG if available, then Tavily/Serper/Brave if configured, then DuckDuckGo.
- `duckduckgo`: Free, no-key web search.
- `searxng`: Local, self-hosted metasearch engine.
- `tavily`: AI-optimized search API.
- `serper`: Google search API.
- `brave`: Brave Search API.
- `mock`: Built-in offline technical documentation corpus.

### DuckDuckGo (Default Free Online Provider)
Requires zero API keys:
```env
SEARCH_PROVIDER=duckduckgo
```

### SearXNG (Local Self-Hosted Metasearch)
Run a local privacy-respecting metasearch instance via Docker:
```bash
docker run -d -p 8080:8080 searxng/searxng
```
Configure in `.env`:
```env
SEARCH_PROVIDER=searxng
SEARXNG_URL=http://localhost:8080
SEARXNG_ENABLED=true
```

### Tavily Search API
```env
SEARCH_PROVIDER=tavily
TAVILY_API_KEY=tvly-your_key_here
```

### Serper Google Search API
```env
SEARCH_PROVIDER=serper
SERPER_API_KEY=your_serper_key_here
```

### Brave Search API
```env
SEARCH_PROVIDER=brave
BRAVE_SEARCH_API_KEY=your_brave_key_here
```

