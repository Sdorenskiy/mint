# Попробовать MINT с открытыми моделями (Ollama)

[English](../OLLAMA.md) · **Русский**

Для знакомства с проектом без корпоративного шлюза: [Ollama](https://ollama.com) запускает открытые
модели на вашем компьютере, MINT подключается к нему через OpenAI-совместимый API.

> На работе используйте только модели и шлюзы, разрешённые компанией. Этот вариант — для тестов на
> открытых документах (например, опубликованных стандартах).

Модели по умолчанию:

- `qwen2.5:3b` — языковая модель, ≈ 2 ГБ, сносно отвечает по-русски и работает на процессоре.
- `bge-m3` — эмбеддинги, ≈ 1,2 ГБ, многоязычная.

Реранкера в Ollama нет: поиск работает без него, но точность ниже, чем с реранкером.

## Вариант 1: Docker

Нужен Docker с Compose.

```bash
git clone https://github.com/Sdorenskiy/mint.git && cd mint
docker compose up -d --build
docker compose logs -f ollama-pull     # дождитесь загрузки обеих моделей
```

Откройте `http://localhost:8501`. База знаний и логи хранятся в томе `mint-data` и переживают перезапуск.

Другие модели (сначала проверьте, что они есть в [библиотеке Ollama](https://ollama.com/library)):

```bash
MINT_LLM=qwen2.5:7b MINT_EMBED=bge-m3 docker compose up -d
```

Если сменить модель эмбеддингов, документы придётся переиндексировать: MINT предложит это в боковой
панели.

Остановить: `docker compose down`. Чтобы удалить и скачанные модели, и базу: `docker compose down -v`.

С видеокартой NVIDIA ответы в разы быстрее. Добавьте сервису `ollama` в `docker-compose.yml` блок
`deploy.resources.reservations.devices` (см. документацию Ollama и Docker).

## Вариант 2: Ollama на компьютере, MINT из исходников

1. Установите Ollama и скачайте модели:

   ```bash
   ollama pull qwen2.5:3b
   ollama pull bge-m3
   ```

2. Задайте окно контекста. У Ollama по умолчанию окно маленькое, и длинные запросы обрезаются:

   ```bash
   OLLAMA_CONTEXT_LENGTH=8192 ollama serve
   ```

   В Windows — переменная окружения `OLLAMA_CONTEXT_LENGTH=8192` и перезапуск Ollama.

3. Установите MINT по [docs/ru/INSTALL.md](INSTALL.md) и впишите в `.env`:

   ```ini
   LLM_API_URL=http://localhost:11434/v1
   EMBED_API_URL=http://localhost:11434/v1/embeddings
   LLM_API_KEY=
   LLM_MODEL=qwen2.5:3b
   EMBED_MODEL=bge-m3
   MINT_CONFIG=config.ollama.yaml
   ```

4. Проверьте `python check_install.py` и запускайте `run_mint.sh` / `run_mint.bat`.

## Чего ждать

- Небольшие модели заметно слабее корпоративных: аудит находит меньше и чаще ошибается. Для оценки
  интерфейса и поиска этого хватает, для выводов о качестве аудита — нет.
- На процессоре ответ занимает от десятков секунд до нескольких минут. Аудит большого документа — долго:
  для пробы возьмите документ на 5–10 страниц.
- Ollama не сообщает окна моделей. Они заданы в `config.ollama.yaml`; если меняете
  `OLLAMA_CONTEXT_LENGTH`, поменяйте и `llm_context_tokens`.
