# STL Models Storage — план и эксплуатация

**Рабочее название проекта:** STL Models Storage.

## Важно: команды bash и Docker

Вся логика работы с **bash** (вводимые команды в терминале) в документации и примерах ниже рассматривается **в контексте управления Docker-контейнерами** проекта (`docker compose` из корня репозитория).

Примеры:

```bash
# Поднять стек
docker compose up -d --build

# Логи PHP/Symfony
docker compose logs -f symfony-php-apache

# Консоль Symfony внутри контейнера
docker compose exec symfony-php-apache php bin/console cache:clear

# CouchDB внутри контейнера (при необходимости)
docker compose exec couchdb curl -s -u admin:password http://127.0.0.1:5984/
```

Не запускайте `php bin/console` и прочие команды приложения на хосте, если зависимости установлены только в образе — используйте `docker compose exec <service> …`.

## Сервисы (docker-compose)

| Сервис             | Роль        | Порт (хост) |
|--------------------|------------|-------------|
| `symfony-php-apache` | API (Symfony) | 80       |
| `nodejs`           | Vite / React | 5173     |
| `couchdb`          | CouchDB    | 5984     |

## Загрузка файлов и лимиты PHP (Docker)

В образе `symfony-php-apache` файл `.infrastructure/php/99-uploads.ini` копируется в **`/etc/php/8.3/apache2/conf.d/`** и **`/etc/php/8.3/cli/conf.d/`** (`upload_max_filesize` / `post_max_size` 256M). Если при загрузке STL API отвечает, что файлов нет, а в ответе `debug.fileBagKeys: []` — часто сработал лимит `post_max_size` (PHP тогда обнуляет `$_FILES`). После правок ini **пересоберите** контейнер:

```bash
docker compose build symfony-php-apache --no-cache && docker compose up -d symfony-php-apache
```

Проверка: **`docker compose exec … php -i`** всегда показывает настройки **PHP CLI** (SAPI `cli`), а не Apache. Значения 2M/8M вы видели именно для CLI, пока в `cli/conf.d` не было `99-uploads.ini`. Для веб-загрузок важен **`apache2`**.

```bash
docker compose exec symfony-php-apache php -i | grep -E 'post_max_size|upload_max_filesize'
docker compose exec symfony-php-apache cat /etc/php/8.3/apache2/conf.d/99-uploads.ini
```

## Функционал загрузки STL

1. **Фронтенд:** форма multi-upload с проверкой MIME и расширения `.stl`.
2. **API:** `POST /api/stl/upload` — сохранение файлов в `public/stl_user_uploads/`, метаданные — документы CouchDB (та же БД `telegram_messages_2`, поле `source: user_upload`).
3. **Скачивание для превью:** существующий `POST /telegram-downloads/download` поддерживает и `telegram_downloads`, и `stl_user_uploads` (по префиксу `savedUrl`).

## Переменные фронтенда

- **`VITE_API_BASE`** — если **не задан** (пусто), в **dev** запросы к API идут на **тот же origin**, что и Vite (`/api/...`), и **проксируются** на Symfony (`vite.config.ts`). Так уходит ошибка CORS при `localhost:5173` → `localhost:80`. В **production** без переменной используется `http://localhost` (лучше задать явно или собирать с пустым base при общем домене).
- **`VITE_DEV_PROXY_TARGET`** — куда Vite проксирует `/api`, `/telegram*`, `/telegram-downloads` (только dev). В `docker-compose` для `nodejs` задано `http://symfony-php-apache`. Локально без Docker: `http://127.0.0.1:80`.
- `VITE_COUCHDB_URL`, `VITE_COUCHDB_DATABASE`, `VITE_COUCHDB_USER`, `VITE_COUCHDB_PASSWORD` — прямой доступ браузера к CouchDB (см. `app/src/couchdbConfig.ts`). По умолчанию `http://localhost:5984`, БД `telegram_messages_2`, `admin` / `password`.

## Дубликаты STL по содержимому

При загрузке считается **SHA-256** файла; в CouchDB в документе поле **`contentHash`**. Повторная загрузка того же файла отклоняется (в т.ч. дубликаты в одном multi-upload). Для быстрого поиска в CouchDB 3+ используется **`_find`** (Mango); при большой БД имеет смысл добавить индекс по `contentHash`.
