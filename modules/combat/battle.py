import os, json, random, time
import vk_api # <-- Возможно, не нужен напрямую
from constants import EFFECTS, WEAPONS
from utils import calc_modifier, roll_with_advantage_disadvantage
from data_storage import (
    get_pending_battle,
    save_pending_battle,
    remove_pending_battle,
    get_all_pending_battles,
    get_all_active_battles,
    save_active_battle,
)
from vk_utils import get_user_name

def is_battle_trigger(text: str) -> bool:
    tr  = ("битва", "бой", "сражайся", "атакую", "удар", "защищайся")
    low = text.lower()
    return low in tr

def _clear_pending_for(user_id: int):
    """Удаляет все pending-запросы, адресованные user_id (safety sweep)."""
    pending = get_all_pending_battles()
    if str(user_id) in pending:
        remove_pending_battle(user_id)

def _clear_pending_between(attacker_id: int, defender_id: int):
    _clear_pending_for(attacker_id)
    _clear_pending_for(defender_id)

def start_battle_request(vk_api_instance, attacker_id: int, defender_id: int, peer_id: int, send_message_func):
    pending = get_all_pending_battles()
    active  = get_all_active_battles()

    if any(str(pid) in k for pid in (attacker_id, defender_id) for k in active):
        send_message_func(peer_id, "У кого-то из вас уже идёт бой.")
        return

    # Safety: очищаем старые pending между участниками
    _clear_pending_between(attacker_id, defender_id)
    pending = get_all_pending_battles()
    if str(defender_id) in pending:
        send_message_func(peer_id, "Игроку уже предложили бой.")
        return

    save_pending_battle(defender_id, {"from": attacker_id, "chat": peer_id, "timestamp": time.time()})

    keyboard = json.dumps({
        "inline": True,
        "buttons": [[
            {"action": {"type": "text", "label": "Начать"},  "color": "positive"},
            {"action": {"type": "text", "label": "Отказать"}, "color": "negative"}
        ]]
    })

    att_name = get_user_name(vk_api_instance, attacker_id)
    def_name = get_user_name(vk_api_instance, defender_id)
    send_message_func(
        peer_id,
        f"⚔️ {att_name} вызывает {def_name} на бой! {def_name}, принять вызов?",
        keyboard=keyboard,
    )

def handle_battle_response(vk_api_instance, user_id: int, text: str, send_message_func) -> bool:
    print(f"[DEBUG] handle_battle_response: user_id={user_id}, text={text}") # <-- Отладка
    pending = get_all_pending_battles()
    uid_str = str(user_id)

    print(f"[DEBUG] handle_battle_response: pending={pending}, uid_str={uid_str}") # <-- Отладка
    if uid_str not in pending:
        print(f"[DEBUG] handle_battle_response: uid_str {uid_str} NOT in pending") # <-- Отладка
        return False

    print(f"[DEBUG] handle_battle_response: uid_str {uid_str} FOUND in pending") # <-- Отладка
    offer      = pending[uid_str]
    attacker   = offer["from"]
    chat_id    = offer["chat"]
    text_low   = text.lower()

    print(f"[DEBUG] handle_battle_response: offer={offer}, attacker={attacker}, text_low={text_low}") # <-- Отладка

    # --- ИСПРАВЛЕНО: проверка на конец строки ---
    if text_low.endswith("отказать") or text_low == "отказать": # <-- Проверяем и полное слово, и окончание
        print(f"[DEBUG] handle_battle_response: user {user_id} refused battle") # <-- Отладка
        def_name = get_user_name(vk_api_instance, user_id)
        send_message_func(chat_id, f"{def_name} отказался от боя.")
        remove_pending_battle(user_id)
        print(f"[DEBUG] handle_battle_response: refused battle, removed from pending and saved") # <-- Отладка
        return True

    # --- ИСПРАВЛЕНО: проверка на конец строки ---
    if text_low.endswith("начать") or text_low == "начать": # <-- Проверяем и полное слово, и окончание
        print(f"[DEBUG] handle_battle_response: user {user_id} accepted battle") # <-- Отладка
        # --- ОПРЕДЕЛЯЕМ active И key ДО ИСПОЛЬЗОВАНИЯ ---
        active = get_all_active_battles()
        key    = f"{attacker}_{user_id}"
        print(f"[DEBUG] handle_battle_response: active loaded, key={key}") # <-- Отладка
        # --- КОНЕЦ ОПРЕДЕЛЕНИЯ ---

        from data_storage import get_player_data
        att_data = get_player_data(attacker)
        def_data = get_player_data(user_id) # <-- Убедитесь, что это так

        # --- ИСПРАВЛЕНО: def_ на def_data ---
        if not att_data or not def_data: # <-- ИСПРАВЛЕНО: def_ на def_data
             print(f"[DEBUG] handle_battle_response: Error loading player data for {attacker} or {user_id}") # <-- Отладка
             att_name = get_user_name(vk_api_instance, attacker)
             def_name = get_user_name(vk_api_instance, user_id)
             send_message_func(chat_id, f"Ошибка: данные одного из игроков ({att_name} или {def_name}) не найдены. Бой не начат.")
             # Удаляем из pending, если была ошибка загрузки
             remove_pending_battle(user_id)
             print(f"[DEBUG] handle_battle_response: error occurred, removed from pending and saved") # <-- Отладка
             return True

        # Бросаем инициативу
        att_init = roll_with_advantage_disadvantage("1d20", calc_modifier(att_data["dexterity"]), advantage=False, disadvantage=False)
        def_init = roll_with_advantage_disadvantage("1d20", calc_modifier(def_data["dexterity"]), advantage=False, disadvantage=False)
        first = attacker if att_init >= def_init else user_id

        # --- ТЕПЕРЬ МОЖНО ИСПОЛЬЗОВАТЬ active И key ---
        # Создаём запись боя
        active[key] = {
            "players": [attacker, user_id],
            "turn": first,
            "round": 1,
            "log":   [],
            "chat":  chat_id,
            "initiative": {str(attacker): att_init, str(user_id): def_init}
        }
        print(f"[DEBUG] handle_battle_response: active[{key}] created") # <-- Отладка
        # --- КОНЕЦ ИСПОЛЬЗОВАНИЯ ---

        save_active_battle(key, active[key])
        print(f"[DEBUG] handle_battle_response: active battles saved") # <-- Отладка
        # Safety: очищаем pending для обоих участников
        _clear_pending_between(attacker, user_id)
        print(f"[DEBUG] handle_battle_response: removed {uid_str} from pending in DB") # <-- Отладка
        print(f"[DEBUG] handle_battle_response: pending battles saved") # <-- Отладка

        att_name = get_user_name(vk_api_instance, attacker)
        def_name = get_user_name(vk_api_instance, user_id)
        send_message_func(
            chat_id,
            f"⚔️ Бой начинается! Инициатива: {att_name}={att_init}, {def_name}={def_init}. Ходит {get_user_name(vk_api_instance, first)}.",
        )
        print(f"[DEBUG] handle_battle_response: battle started message sent") # <-- Отладка
        return True

    print(f"[DEBUG] handle_battle_response: text '{text}' is not 'начать' or 'отказать'") # <-- Отладка
    return False

def roll(dice):
    if '+' in dice:
        parts = dice.split('+')
        base = parts[0]
        bonus = int(parts[1])
    else:
        base = dice
        bonus = 0

    if 'd' not in base:
        return int(base) + bonus

    count, size = map(int, base.lower().split('d'))
    return sum(random.randint(1, size) for _ in range(count)) + bonus
