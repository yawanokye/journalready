# DeepSeek V4 Pro Article Topic Ideas Update

## Provider separation

- Article Topic Ideas now use DeepSeek V4 Pro only.
- The Article Writer continues to use OpenAI models.
- The topic-idea workflow does not silently fall back to OpenAI.
- If DeepSeek is unavailable, the existing structured local fallback is used and a warning is returned.

## Required Render environment variables

```text
DEEPSEEK_API_KEY=your_deepseek_api_key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_ARTICLE_IDEA_MODEL=deepseek-v4-pro
DEEPSEEK_ARTICLE_IDEA_THINKING=1
DEEPSEEK_ARTICLE_IDEA_REASONING_EFFORT=high
DEEPSEEK_ARTICLE_IDEA_MAX_TOKENS=12000
```

Keep `OPENAI_API_KEY` because the Article Writer still uses OpenAI.

## Main files changed

- `app/article_ideas_service.py`
- `.env.example`
- `render.yaml`
- `README.md`
- `tests/test_article_workflows.py`
