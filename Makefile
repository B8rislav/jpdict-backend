.PHONY: dev migrate logs stop build import-jmdict import-kanjidic import-kradfile import-cedict import-hsk import-kanji-ru import-all

dev:
	docker compose up db cache -d
	uv run --env-file .env uvicorn app.main:app --reload

migrate:
	uv run --env-file .env alembic upgrade head

logs:
	docker compose logs -f db cache

stop:
	docker compose down

build:
	docker compose up --build

# Download and import JMdict (Japanese-English + Russian glosses, JLPT levels)
import-jmdict:
	uv run --env-file .env python scripts/import_jmdict.py

# Download and import KANJIDIC2 (kanji details: readings, stroke count, JLPT)
import-kanjidic:
	uv run --env-file .env python scripts/import_kanjidic2.py

# Download and import KRADFILE (kanji component decomposition)
# Run after import-kanjidic
import-kradfile:
	uv run --env-file .env python scripts/import_kradfile.py

# Download and import CC-CEDICT (Chinese-English dictionary)
import-cedict:
	uv run --env-file .env python scripts/import_cedict.py

# Populate hsk_level on cedict_entries from open HSK 1-6 wordlist
# Run after import-cedict
import-hsk:
	uv run --env-file .env python scripts/import_hsk.py

# Download Yarxi SQLite DB and populate kanjidic_entries.meanings_ru with Russian glosses
# Run after import-kanjidic
import-kanji-ru:
	uv run --env-file .env python scripts/import_kanji_ru.py

# Download Tatoeba per-language sentence dumps and import Japanese+Russian/English pairs into reibun_entries
import-reibun:
	uv run --env-file .env python scripts/import_tatoeba.py

# Run all imports in correct order
import-all: import-jmdict import-kanjidic import-kradfile import-cedict import-hsk import-kanji-ru import-reibun
