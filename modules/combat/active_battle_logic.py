import json, os, traceback
from .combat import calculate_battle
from dolphin_handler import ask_dolphin, classify_intent
from constants import EFFECTS, SKILLS, WEAPON_SKILLS
from utils import (
    calc_modifier,
    calculate_ac,
    roll_with_advantage_disadvantage,
    find_best_skill,
)
from data_storage import (
    get_all_active_battles,
    save_active_battle,
    remove_active_battle,
    get_player_data,
    save_player_data,
)
from vk_utils import get_user_name
from modules.progression.statistics import update_stats_for_player

def _get_battle(uid: int):
    for k, v in get_all_active_battles().items():
        if uid in v["players"]:
            return k, v
    return None, None

def _tick_effects(char: dict):
    """
    –1 к duration всем эффектам.
    Обработка периодического урона и других эффектов.
    """
    se = char.get("status_effects", {})
    log = []

    for name in list(se):
        eff = se[name]
        duration = eff.get("duration", 1)
        if duration <= 1:
            del se[name]
            log.append(f"эффект '{name}' закончился у {char['name']}.")
            continue

        eff["duration"] -= 1

        if eff.get("type") == "periodic":
            dmg_dice = eff.get("damage", "1d2")
            from .combat import roll
            dmg = roll(dmg_dice)
            char["hp"] -= dmg
            log.append(f"{char['name']} получает {dmg} урона от '{name}'.")

    char["status_effects"] = se
    return log

def _pass_turn(battle: dict, key: str):
    """Передаём ход другому игроку без атаки."""
    print(f"[DEBUG] _pass_turn: key={key}, battle={battle}") # <-- Отладка
    next_id = next(pid for pid in battle["players"] if pid != battle["turn"])
    battle["turn"]  = next_id
    battle["round"] += 1
    save_active_battle(key, battle)
    print(f"[DEBUG] _pass_turn: saved battle {key}") # <-- Отладка

def reset_player_on_death(player_data):
    """Сбрасывает статус игрока после смерти."""
    print(f"[DEBUG] reset_player_on_death: Resetting {player_data['name']}") # <-- Отладка
    player_data["hp"] = player_data.get("max_hp", 10)
    player_data["status_effects"] = {}
    player_data.pop("dead", None)
    print(f"[DEBUG] reset_player_on_death: {player_data['name']} reset: HP={player_data['hp']}, Status Effects={player_data['status_effects']}") # <-- Отладка

def process_turn(vk_api_instance, user_id: int, msg: str, send_message_func) -> bool: # <-- Принимаем vk_api_instance
    print(f"[DEBUG] process_turn: user_id={user_id}, msg={msg}") # <-- Отладка
    key, battle = _get_battle(user_id)
    if not battle:
        print(f"[DEBUG] process_turn: No active battle found for user {user_id}") # <-- Отладка
        return False

    print(f"[DEBUG] process_turn: Found battle {key} for user {user_id}") # <-- Отладка

    if battle["turn"] != user_id:
        print(f"[DEBUG] process_turn: Not {user_id}'s turn. Current turn: {battle['turn']}") # <-- Отладка
        send_message_func(battle["chat"], "Сейчас не твой ход.")
        return True

    print(f"[DEBUG] process_turn: It's {user_id}'s turn. Proceeding with turn logic.") # <-- Отладка

    attacker     = get_player_data(user_id)
    if not attacker:
        print(f"[ERROR] process_turn: Player data for {user_id} not found in players.json") # <-- Ошибка
        return False
    defender_id  = next(pid for pid in battle["players"] if pid != user_id)
    defender     = get_player_data(defender_id)
    if not defender:
        print(f"[ERROR] process_turn: Player data for {defender_id} not found in players.json") # <-- Ошибка
        return False
    log: list[str] = []

    # ❶ проверяем оглушение / заморозку
    stunned = any(
        (name in ("stun", "freeze")) and (
            (isinstance(eff, dict)  and eff.get("duration", 0) > 0) or
            (isinstance(eff, int)   and eff > 0)
        )
        for name, eff in attacker.get("status_effects", {}).items()
    )
    if stunned:
        log.append(f"{attacker['name']} оглушён и пропускает ход!")
        _tick_effects(attacker)
        _pass_turn(battle, key)
        save_player_data(user_id, attacker)
        send_message_func(battle["chat"], "\n".join(log))
        return True

    # ❷ «Сдаюсь»
    if msg.strip().lower() == "сдаюсь":
        # Gemini для сдачи
        surrender_action = ask_dolphin(
            "сдаюсь", attacker, defender, defender.get("status_effects", {}), {"damage": 0, "crit": False, "effects": {}}
        )
        surrender_description = surrender_action.get("description", f"{attacker['name']} сдался! Побеждает {defender['name']}!")
        log.append(surrender_description)

        try:
            remove_active_battle(key)
        except Exception as e:
            print(f"[ERR] remove_active_battle on surrender: {e}")
        send_message_func(battle["chat"], "\n".join(log))

        reset_player_on_death(attacker)
        save_player_data(user_id, attacker)
        print(f"[DEBUG] process_turn: Reset player {user_id} after surrender")
        return True

    # ❸ Классифицируем намерение игрока
    intent = classify_intent(msg)
    print(f"[DEBUG] Player intent classified as: {intent}")

    if intent == "passive":
        print(f"[DEBUG] Processing passive action for {attacker['name']}.") # <-- Добавлен дебаг
        _tick_effects(attacker)
        _pass_turn(battle, key)
        save_player_data(user_id, attacker)
        
        # Генерируем описание пассивного действия
        passive_action_desc = ask_dolphin(
            msg, attacker, defender, defender.get("status_effects", {}), {"damage": 0, "crit": False, "effects": {}, "type": "pass"}
        )
        log.append(passive_action_desc.get("description", f"{attacker['name']} пропускает ход."))
        
        send_message_func(battle["chat"], "\n".join(log))
        return True

    # Если намерение не пассивное, продолжаем как атаку
    # ❹ Проверяем, есть ли у игрока скиллы и соответствует ли ввод одному из них
    equipped_weapon = attacker.get("equipment", {}).get("weapon")
    available_skill_names = []

    print(f"[DEBUG] Equipped weapon: {equipped_weapon}")

    if equipped_weapon and equipped_weapon in WEAPON_SKILLS:
        for skill_name in WEAPON_SKILLS[equipped_weapon]:
            if skill_name in SKILLS:
                available_skill_names.append(skill_name)
    
    print(f"[DEBUG] Available skill names for equipped weapon: {available_skill_names}")

    # Now, find the best skill from the collected skill names
    matched_skill = find_best_skill(msg, available_skill_names)

    # Проверяем баффы на урон у атакующего
    damage_bonus = 0
    for effect in attacker.get("status_effects", {}).values():
        if effect.get("type") == "damage_buff":
            damage_bonus += effect.get("damage_bonus", 0)

    if matched_skill:
        log.append(f"Активирована способность: {matched_skill}")
        skill_info = SKILLS[matched_skill]
        
        # Готовим "action" для calculate_battle на основе скилла
        skill_action = {
            "type": "skill",
            "skill_name": matched_skill,
            "effects": {effect: EFFECTS[effect] for effect in skill_info["effects"] if effect in EFFECTS}
        }
        result = calculate_battle(attacker, defender, skill_action, damage_bonus)

    else:
        # Если скилл не найден, выполняем стандартную атаку
        try:
            result = calculate_battle(attacker, defender, {"type": "attack"}, damage_bonus)
            print(f"[DEBUG] process_turn: Battle calculation result: {result}") # <-- Отладка
        except Exception as e:
            print(f"[ERR] calculate_battle: {e}")
            print(f"[ERR] calculate_battle traceback: {traceback.format_exc()}")
            return False

    try:
        action = ask_dolphin(
            msg, attacker, defender, defender.get("status_effects", {}), result
        )
        print(f"[DEBUG] process_turn: Gemini response: {action}") # <-- Отладка
    except Exception as e:
        print(f"[ERR] Gemini: {e}")
        print(f"[ERR] Gemini traceback: {traceback.format_exc()}")
        action = {"description": f"{attacker['name']} делает стандартную атаку по {defender['name']} (ошибка Gemini).", "type": "attack"}

    # --- Объединение описания Gemini и технического лога ---
    if desc := action.get("description"):
        log.append(desc)

    # 2. Добавляем технические сообщения из calculate_battle, но только важные
    # (например, не дублируем урон, если он уже в описании Gemini, но можно добавить)
    # Важно: calculate_battle возвращает log, который уже содержит "попадание/промах/урон/эффекты"
    # Мы можем использовать его содержимое, но аккуратно, чтобы не дублировать.
    # Пока добавим всё, но можно фильтровать.
    # Проверим, был ли урон или смерть в result, и добавим технический лог.
    # Убираем лог о смерти из result["log"], так как смерть обрабатывается отдельно.
    technical_log = result.get("log", [])
    # Фильтруем лог от calculate_battle, чтобы не дублировать смерть
    filtered_technical_log = [entry for entry in technical_log if "пал! Бой окончен." not in entry]
    log.extend(filtered_technical_log) # <-- Добавляем технические детали

    # Применяем урон и эффекты к defender (в локальной копии)
    if result["damage"]:
        print(f"[DEBUG] Defender HP before damage: {defender['hp']}") # <-- Добавлен дебаг
        defender["hp"] -= result["damage"]
        print(f"[DEBUG] Defender HP after damage: {defender['hp']} (applied {result['damage']} damage)") # <-- Добавлен дебаг
        # Не добавляем сообщение о уроне сюда, так как оно уже в result["log"] или в Gemini
        if defender["hp"] <= 0:
            defender["hp"] = 0
            defender["dead"] = True

    for name, eff in result.get("effects", {}).items():
        defender.setdefault("status_effects", {})[name] = eff.copy()

    # ❺ очередь следующего хода
    try:
        battles = get_all_active_battles()
        print(f"[DEBUG] process_turn: Loaded active battles before update: {battles}") # <-- Отладка
        if defender.get("dead"):
            remove_active_battle(key)
            print(f"[DEBUG] process_turn: Removed battle {key} from active (defender dead)") # <-- Отладка
            # --- Обновление статистики ---
            try:
                att_vk_info = vk_api_instance.users.get(user_ids=attacker["id"])[0]
                def_vk_info = vk_api_instance.users.get(user_ids=defender["id"])[0]
                update_stats_for_player(attacker["id"], att_vk_info["first_name"], att_vk_info["last_name"], win=True)
                update_stats_for_player(defender["id"], def_vk_info["first_name"], def_vk_info["last_name"], win=False)
            except Exception as e:
                print(f"[ERR] Не удалось обновить статистику при завершении боя: {e}")
                print(f"[ERR] traceback: {traceback.format_exc()}")

            death_message = f"{defender['name']} пал! Бой окончен." # <-- Можешь изменить текст
            log.append(death_message)

            reset_player_on_death(defender)
            print(f"[DEBUG] process_turn: Reset player {defender_id} after death")

            # Reset winner's status effects and HP
            reset_player_on_death(attacker)
            save_player_data(user_id, attacker)
            print(f"[DEBUG] process_turn: Reset winner {user_id} after battle")

        else:
            battle["turn"]  = defender_id
            battle["round"] += 1
            save_active_battle(key, battle)
            print(f"[DEBUG] process_turn: Updated battle {key} turn to {defender_id} and saved.")
    except Exception as e:
        print(f"[ERR] Saving active battle: {e}")
        print(f"[ERR] Saving active battle traceback: {traceback.format_exc()}")
        return False

    # ❻ сохраняем игроков
    try:
        save_player_data(defender_id, defender)
        save_player_data(user_id, attacker)
        _tick_effects(attacker)
        save_player_data(user_id, attacker)
        print(f"[DEBUG] process_turn: Saved player data")
    except Exception as e:
        print(f"[ERR] Saving player  {e}")
        print(f"[ERR] Saving player data traceback: {traceback.format_exc()}")
        return False

    send_message_func(battle["chat"], "\n".join(log))
    print(f"[DEBUG] process_turn: Turn completed successfully for {user_id}")
    return True
