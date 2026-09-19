# VibeForge

Опиши сайт звичайними словами → AI генерує повний HTML/CSS/JS → живий прев'ю в браузері → уточнюй далі в чаті → завантаж готовий файл.

## Архітектура

```
vibeforge/
  backend/    FastAPI-сервер: приймає промпт, викликає генератор, зберігає проєкти
    app/generation/   інтерфейс SiteGenerator + реалізації (mock зараз, Gemini — реальна)
    app/projects.py   історія проєктів (JSON-файл, поки без справжньої БД)
  frontend/   React: чат зліва, live-прев'ю в iframe справа
```

Генератор схований за інтерфейсом `SiteGenerator` (`backend/app/generation/base.py`),
вибір через змінну середовища `GENERATOR`:

- `mock` (за замовчуванням) — заглушка, повертає просту сторінку з текстом промпту, для перевірки пайплайну без API-ключа
- `gemini` — реальна генерація через безкоштовний рівень Google Gemini API

Кожна генерація повертає **повний самодостатній HTML-документ** (стилі й скрипти
інлайн, без окремих файлів) — це і рендериться в `<iframe sandbox>` для прев'ю,
і віддається як файл для завантаження.

## Запуск локально (macOS)

### Бекенд

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

За замовчуванням працює в mock-режимі (без API-ключа).

### Увімкнути реальну генерацію (Gemini)

1. Отримай безкоштовний ключ на **aistudio.google.com/apikey**
2. Створи файл `backend/.env` (не комітиться, вже в `.gitignore`):
   ```
   GEMINI_API_KEY=твій_ключ
   ```
3. Запусти бекенд з `GENERATOR=gemini`:
   ```bash
   GENERATOR=gemini uvicorn app.main:app --reload --port 8000
   ```

### Фронтенд

```bash
cd frontend
npm install
npm run dev
```

Відкрити http://localhost:5173 — опиши сайт у чаті зліва, прев'ю з'явиться справа.
Уточнюй наступними повідомленнями ("зроби кнопку синьою") — модель редагує
попередній HTML, а не починає з нуля.

## Публікація в інтернет

Бекенд і фронтенд деплояться окремо — бекенду потрібен хостинг, що тримає
процес постійно запущеним (не просто статичні файли).

### Бекенд (наприклад, Render.com)

1. Створи новий "Web Service", підключи цей GitHub-репозиторій
2. Root Directory: `backend`
3. Build Command: `pip install -r requirements.txt`
4. Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. Environment Variables:
   - `GENERATOR=gemini`
   - `GEMINI_API_KEY=твій_ключ`
   - `FRONTEND_ORIGIN=` (адреса фронтенду з наступного кроку — можна додати пізніше й передеплоїти)
6. Після деплою запиши публічну адресу (напр. `https://vibeforge-backend.onrender.com`)

### Фронтенд (наприклад, Vercel)

1. Імпортуй репозиторій у Vercel
2. Root Directory: `frontend`
3. Vercel сам розпізнає Vite-проєкт (Build Command `npm run build`, Output `dist`)
4. Environment Variables:
   - `VITE_API_URL=` (адреса бекенду з попереднього кроку, без слеша в кінці)
5. Deploy

Локально (`npm run dev`) `VITE_API_URL` не задається — фронтенд тоді йде через
відносний шлях `/api/...`, який Vite сам перенаправляє на `localhost:8000`.

## Наступні кроки

1. Кращий промпт-інжиніринг для стабільніших результатів
2. Монетизація
