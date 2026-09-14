# Security Policy

## Supported Versions

Only the latest release of VasukiSquare receives security updates and vulnerability patches.

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |
| < 0.1.0 | :x:                |

---

## Reporting Vulnerabilities

If you discover a security vulnerability in VasukiSquare, please report it responsibly:

- Open a confidential security advisory or contact the repository maintainers through the official repository contact channels.
- Please provide a detailed description of the vulnerability, reproduction steps, and potential impact.
- Do not create public GitHub issues for sensitive security vulnerabilities.

---

## Best Practices for Commercial Users & Developers

### 1. API Key & Secret Safety
- **Never commit `.env` or `.env.local` files to version control.** The `.gitignore` file is configured to exclude these files by default.
- Use environment variables or local `.env` files for `GROQ_API_KEY`, `TAVILY_API_KEY`, `SERPER_API_KEY`, and `MONGODB_URI`.
- If an API key is ever committed or exposed accidentally, rotate and invalidate it immediately via your provider console.

### 2. Local Model & Ollama Security
- When using Ollama (`LLM_PROVIDER=ollama`), ensure the Ollama API port (`11434`) is bound to `localhost` (`127.0.0.1`) and not exposed to the public internet without an authentication proxy.

### 3. Database Security
- When connecting to MongoDB instances in production environments, use TLS/SSL connection strings and ensure strong authentication is enforced.

