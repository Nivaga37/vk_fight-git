# data_storage.py
import sqlite3
import json
import os
from typing import Optional

DATABASE_FILE = "models.db" # <-- Единый файл базы данных

# --- Схема базы данных ---
# Таблицы:
# players: id (INTEGER PRIMARY KEY), data (JSON TEXT) -- содержит весь словарь игрока
# active_battles: id (TEXT PRIMARY KEY), data (JSON TEXT) -- содержит весь словарь боя
# pending_battles: defender_id (INTEGER PRIMARY KEY), data (JSON TEXT) -- содержит словарь запроса
# statistics: player_id (INTEGER PRIMARY KEY), data (JSON TEXT) -- содержит словарь статистики

def _get_connection():
    """Возвращает соединение с базой данных. Создаёт базу и таблицы при первом запуске."""
    conn = sqlite3.connect(DATABASE_FILE)
    # Включаем поддержку внешних ключей (опционально)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def _init_db():
    """Инициализирует таблицы в базе данных, если они не существуют."""
    conn = _get_connection()
    cursor = conn.cursor()

    # Таблица игроков
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS players (
            id INTEGER PRIMARY KEY,
            data TEXT NOT NULL -- JSON
        );
    """)

    # Таблица активных боёв
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS active_battles (
            battle_id TEXT PRIMARY KEY, -- например, "123456_789012"
            data TEXT NOT NULL -- JSON
        );
    """)

    # Таблица ожидающих боёв
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pending_battles (
            defender_id INTEGER PRIMARY KEY, -- id игрока, которому отправлен вызов
            data TEXT NOT NULL -- JSON (содержит from, chat)
        );
    """)

    # Таблица статистики
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS statistics (
            player_id INTEGER PRIMARY KEY,
            data TEXT NOT NULL -- JSON (содержит first_name, last_name, wins, losses)
        );
    """)

    conn.commit()
    conn.close()

# --- ИНИЦИАЛИЗАЦИЯ ПРИ ИМПОРТЕ ---
_init_db()
# --- КОНЕЦ ИНИЦИАЛИЗАЦИИ ---

# --- МИГРАЦИЯ ИЗ JSON ФАЙЛОВ (ОДНОРАЗОВО ПРИ ПУСТОЙ БАЗЕ) ---
def _is_table_empty(table_name: str) -> bool:
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT 1 FROM {table_name} LIMIT 1")
        row = cur.fetchone()
        return row is None
    finally:
        conn.close()

def _load_json_if_exists(path: str) -> Optional[dict]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except Exception:
        return None

def _migrate_from_json_if_needed():
    """Импортирует данные из json-файлов в БД, если соответствующие таблицы пусты."""
    # players
    if _is_table_empty("players"):
        data = _load_json_if_exists("players.json")
        if isinstance(data, dict):
            for key, player in data.items():
                try:
                    uid = int(key)
                    save_player_data(uid, player)
                except Exception:
                    continue

    # active battles
    if _is_table_empty("active_battles"):
        data = _load_json_if_exists("active_battles.json")
        if isinstance(data, dict):
            for battle_id, battle_data in data.items():
                try:
                    save_active_battle(battle_id, battle_data)
                except Exception:
                    continue

    # pending battles
    if _is_table_empty("pending_battles"):
        data = _load_json_if_exists("pending_battles.json")
        if isinstance(data, dict):
            for defender_id_str, entry in data.items():
                try:
                    defender_id = int(defender_id_str)
                    save_pending_battle(defender_id, entry)
                except Exception:
                    continue

    # statistics
    if _is_table_empty("statistics"):
        data = _load_json_if_exists("statistics.json")
        if isinstance(data, dict):
            for player_id_str, stats in data.items():
                try:
                    player_id = int(player_id_str)
                    save_player_stats(player_id, stats)
                except Exception:
                    continue

# Выполняем миграцию один раз при импорте, если таблицы пустые
_migrate_from_json_if_needed()

# --- ФУНКЦИИ ДЛЯ РАБОТЫ С ИГРОКАМИ ---
def get_player_data(user_id: int) -> dict | None:
    """Загружает данные игрока из базы."""
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT data FROM players WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return json.loads(row[0]) # Возвращает словарь
    return None # Игрок не найден

def save_player_data(user_id: int, player_data: dict):
    """Сохраняет (или обновляет) данные игрока в базе."""
    conn = _get_connection()
    cursor = conn.cursor()
    json_data = json.dumps(player_data, ensure_ascii=False)
    cursor.execute("INSERT OR REPLACE INTO players (id, data) VALUES (?, ?)", (user_id, json_data))
    conn.commit()
    conn.close()

def delete_player_data(user_id: int):
    """Удаляет данные игрока из базы."""
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM players WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()

def get_all_player_data() -> dict:
    """Загружает ВСЕ данные игроков. Полезно для массовых операций (редко)."""
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, data FROM players")
    rows = cursor.fetchall()
    conn.close()
    # Возвращает словарь {str(user_id): player_data_dict}
    return {str(row[0]): json.loads(row[1]) for row in rows}

# --- ФУНКЦИИ ДЛЯ РАБОТЫ С АКТИВНЫМИ БОЯМИ ---
def get_active_battle(battle_id: str) -> dict | None:
    """Загружает данные активного боя по ID."""
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT data FROM active_battles WHERE battle_id = ?", (battle_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return json.loads(row[0])
    return None

def get_active_battle_for_player(user_id: int) -> tuple[str, dict] | None:
    """Находит активный бой, в котором участвует игрок. Возвращает (battle_id, battle_data)."""
    all_battles = get_all_active_battles()
    for battle_id, battle_data in all_battles.items():
        if user_id in battle_data.get("players", []):
            return battle_id, battle_data
    return None

def get_all_active_battles() -> dict:
    """Загружает ВСЕ активные бои."""
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT battle_id, data FROM active_battles")
    rows = cursor.fetchall()
    conn.close()
    return {row[0]: json.loads(row[1]) for row in rows}

def save_active_battle(battle_id: str, battle_data: dict):
    """Сохраняет (или обновляет) активный бой."""
    conn = _get_connection()
    cursor = conn.cursor()
    json_data = json.dumps(battle_data, ensure_ascii=False)
    cursor.execute("INSERT OR REPLACE INTO active_battles (battle_id, data) VALUES (?, ?)", (battle_id, json_data))
    conn.commit()
    conn.close()

def remove_active_battle(battle_id: str):
    """Удаляет активный бой из базы."""
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM active_battles WHERE battle_id = ?", (battle_id,))
    conn.commit()
    conn.close()

# --- ФУНКЦИИ ДЛЯ РАБОТЫ С ОЖИДАЮЩИМИ БОЯМИ ---
def get_pending_battle(defender_id: int) -> dict | None:
    """Загружает данные ожидающего боя для игрока."""
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT data FROM pending_battles WHERE defender_id = ?", (defender_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return json.loads(row[0])
    return None

def save_pending_battle(defender_id: int, battle_request_data: dict):
    """Сохраняет запрос на бой."""
    conn = _get_connection()
    cursor = conn.cursor()
    json_data = json.dumps(battle_request_data, ensure_ascii=False)
    cursor.execute("INSERT OR REPLACE INTO pending_battles (defender_id, data) VALUES (?, ?)", (defender_id, json_data))
    conn.commit()
    conn.close()

def remove_pending_battle(defender_id: int):
    """Удаляет запрос на бой."""
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM pending_battles WHERE defender_id = ?", (defender_id,))
    conn.commit()
    conn.close()

def get_all_pending_battles() -> dict:
    """Загружает ВСЕ ожидающие бои."""
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT defender_id, data FROM pending_battles")
    rows = cursor.fetchall()
    conn.close()
    return {str(row[0]): json.loads(row[1]) for row in rows}

# --- ФУНКЦИИ ДЛЯ РАБОТЫ СО СТАТИСТИКОЙ ---
def get_player_stats(player_id: int) -> dict | None:
    """Загружает статистику игрока."""
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT data FROM statistics WHERE player_id = ?", (player_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return json.loads(row[0])
    return None

def save_player_stats(player_id: int, stats_data: dict):
    """Сохраняет (или обновляет) статистику игрока."""
    conn = _get_connection()
    cursor = conn.cursor()
    json_data = json.dumps(stats_data, ensure_ascii=False)
    cursor.execute("INSERT OR REPLACE INTO statistics (player_id, data) VALUES (?, ?)", (player_id, json_data))
    conn.commit()
    conn.close()

def get_top_stats(limit: int = 10) -> list[tuple[str, dict]]: # Возвращает [(player_id, stats_dict), ...]
    """Загружает топ статистики."""
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT player_id, data FROM statistics")
    rows = cursor.fetchall()
    conn.close()
    all_stats = [(int(row[0]), json.loads(row[1])) for row in rows]
    # Сортируем по wins, потом по losses (убывающе)
    sorted_stats = sorted(all_stats, key=lambda item: (item[1]["wins"], -item[1]["losses"]), reverse=True)
    return sorted_stats[:limit]

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def reset_player_on_death_in_db(player_data: dict):
    """Сбрасывает статус игрока после смерти *внутри переданного словаря*. Не сохраняет в базу!"""
    # Восстанавливаем HP до максимального
    player_data["hp"] = player_data.get("max_hp", 10)
    # Очищаем статус-эффекты
    player_data["status_effects"] = {}
    # Убираем флаг смерти, если он был
    player_data.pop("dead", None)
    # Можно сбросить и другие поля, связанные с боем, если они есть
    # player_data.pop("current_weapon", None) # <-- Пример

# Пример использования:
# player = get_player_data(123456)
# if player:
#     reset_player_on_death_in_db(player)
#     save_player_data(123456, player)
