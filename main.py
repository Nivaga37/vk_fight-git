# main.py
import json
import random # <-- Оставил, так как используется в основном цикле
import time
import vk_api
from vk_api.bot_longpoll import VkBotEventType # <-- VkBotEventType нужно импортировать здесь
from vk_init import vk, longpoll # <-- Импортируем из нового файла
from constants import WEAPONS, ARMORS, BASE_STATS, VK_TOKEN, GROUP_ID, STAT_ALIASES
from modules.combat.battle import (
    is_battle_trigger, start_battle_request, handle_battle_response
)
from modules.combat.active_battle_logic import process_turn # <-- Импортируем функцию
from modules.character.character_creation import ( # <-- Импортируем функции создания
    create_character, choose_gender, choose_weapon, choose_offhand, choose_armor, distribute_stat, choose_race, choose_class,
    choose_race_page_2, choose_class_page_2, handle_class_confirmation
)
from modules.character.profile_view import show_profile, show_effects, main_keyboard, reset_character # <-- Импортируем функции просмотра
from data_storage import get_player_data, get_all_active_battles, get_all_pending_battles, remove_pending_battle, save_player_data
from vk_utils import send_message
import requests # For downloading photos
import os # Import os module

# Define a state for photo upload
UPLOAD_PHOTO_STATE = {} # {uid: True/False}

def check_pending_battles():
    """Проверяет и удаляет истекшие запросы на бой."""
    pending_battles = get_all_pending_battles()
    current_time = time.time()
    for defender_id_str, battle_info in pending_battles.items():
        if current_time - battle_info.get("timestamp", 0) > 60:  # 60 seconds timeout
            defender_id = int(defender_id_str)
            remove_pending_battle(defender_id)
            send_message(vk, battle_info["chat"], "Приглашение на бой истекло.")

def is_user_in_active_battle(user_id):
    """Проверяет, участвует ли пользователь в каком-либо активном бою."""
    active_battles = get_all_active_battles()
    for battle_info in active_battles.values():
        if user_id in battle_info.get("players", []):
            return True
    return False

def is_user_in_pending_battle(user_id):
    """Проверяет, ждёт ли пользователь какого-либо боя (в pending)."""
    pending_battles = get_all_pending_battles()
    return str(user_id) in pending_battles

# --- Основной цикл ---
last_check = 0
for ev in longpoll.listen():
    if time.time() - last_check > 10: # Check every 10 seconds
        check_pending_battles()
        last_check = time.time()

    if ev.type != VkBotEventType.MESSAGE_NEW:
        continue

    m = ev.object["message"]
    raw_text = m.get("text", "")
    text = raw_text.strip().lower()
    uid = m["from_id"]
    peer_id = m["peer_id"]
    payload = m.get("payload")
    print(f"[DBG] {uid}@{peer_id}: {text!r} payload={payload}")

    if payload:
        try:
            lbl = json.loads(payload).get("label", "").lower()
            if not text:
                text = lbl
        except Exception:
            pass

    is_private = peer_id == uid

    if is_private:
        # --- НОВОЕ: Обработка загрузки фото (перенесено выше) ---
        if uid in UPLOAD_PHOTO_STATE and UPLOAD_PHOTO_STATE[uid]:
            attachments = m.get("attachments")
            if attachments:
                # Check for photo attachment
                photo_attachment = next((att for att in attachments if att["type"] == "photo"), None)
                # Check for document attachment that is an image
                doc_attachment = next((att for att in attachments if att["type"] == "doc" and att["doc"]["ext"] in ["jpg", "jpeg", "png"]), None)

                target_attachment = None
                if photo_attachment:
                    photo_sizes = photo_attachment["photo"]["sizes"]
                    target_url = max(photo_sizes, key=lambda s: s["width"] * s["height"])["url"]
                    target_attachment = "photo"
                elif doc_attachment:
                    target_url = doc_attachment["doc"]["url"]
                    target_attachment = "doc"

                if target_attachment:
                    from modules.character.character_image_generator import PORTRAITS_DIR
                    portrait_filename = os.path.join(PORTRAITS_DIR, f"{uid}.jpg")
                    print(f"[DEBUG main] Saving portrait to: {portrait_filename} from {target_attachment}") # Debug print

                    try:
                        response = requests.get(target_url, stream=True)
                        response.raise_for_status()
                        with open(portrait_filename, 'wb') as f:
                            for chunk in response.iter_content(1024):
                                f.write(chunk)
                        send_message(vk, peer_id, "Фотография успешно загружена и сохранена! Теперь вы можете посмотреть свой профиль.", keyboard=main_keyboard())
                        UPLOAD_PHOTO_STATE[uid] = False # Reset state
                        
                        # Regenerate profile image after new photo upload
                        p = get_player_data(uid)
                        if p and p.get("is_setup_complete"):
                            output_image_name = f"profile_{uid}.png"
                            print(f"[DEBUG main] Regenerating profile image after photo upload for {uid}")
                            from modules.character.character_image_generator import generate_character_image
                            generate_character_image(uid, p, output_image_name)

                    except requests.exceptions.RequestException as e:
                        send_message(vk, peer_id, f"Ошибка при загрузке фотографии: {e}", keyboard=main_keyboard())
                        UPLOAD_PHOTO_STATE[uid] = False # Reset state
                    continue
                else:
                    send_message(vk, peer_id, "Пожалуйста, отправьте именно фотографию или изображение в формате PNG/JPG.", keyboard=main_keyboard())
                    continue
            else:
                send_message(vk, peer_id, "Пожалуйста, отправьте именно фотографию или изображение в формате PNG/JPG.", keyboard=main_keyboard())
                continue

        if handle_battle_response(vk, uid, text, lambda pid, msg, keyboard=None: send_message(vk, pid, msg, keyboard)):
            continue

        p = get_player_data(uid)
        is_setup_done = p and p.get("is_setup_complete")

        if text in ("создать", "начать", "создать персонажа"):
            create_character(vk, uid, peer_id)
        elif not is_setup_done and p and p.get("setup_stage") == "gender" and text in ("мальтик", "девотька"):
            choose_gender(vk, uid, peer_id, text)
        elif not is_setup_done and p and p.get("setup_stage") == "race" and text == "далее (расы)":
            choose_race_page_2(vk, uid, peer_id)
        elif not is_setup_done and p and p.get("setup_stage") == "race":
            choose_race(vk, uid, peer_id, text.capitalize())
        elif not is_setup_done and p and p.get("setup_stage") == "class" and text == "далее (классы)":
            choose_class_page_2(vk, uid, peer_id)
        elif not is_setup_done and p and p.get("setup_stage") == "class":
            choose_class(vk, uid, peer_id, text.capitalize())
        elif not is_setup_done and p and p.get("setup_stage") == "class_confirm" and text in ("принять", "выбрать другой"):
            handle_class_confirmation(vk, uid, peer_id, text)
        elif not is_setup_done and p and p.get("setup_stage") == "weapon" and text in WEAPONS:
            choose_weapon(vk, uid, peer_id, text)
        elif not is_setup_done and p and p.get("setup_stage") == "offhand" and text in ("ничего", "щит", "короткий меч", "кинжал"):
            choose_offhand(vk, uid, peer_id, text)
        elif not is_setup_done and p and p.get("setup_stage") == "armor" and text in [a for a in ARMORS if ARMORS[a]["type"] == "броня"]:
            choose_armor(vk, uid, peer_id, text)

        elif not is_setup_done and p and p.get("setup_stage") == "stats":
            print(f"[DEBUG main] Received text: '{text}' for uid {uid}") # <-- Отладка

            # --- НОВОЕ: Проверка на ввод нескольких статов через запятую ---
            if ',' in text:
                print(f"[DEBUG main] Detected comma, processing multi-stat input: '{text}'") # <-- Отладка
                # Разбиваем по запятой
                stat_parts = text.split(',')
                all_valid = True
                processed_stats = []

                for part in stat_parts:
                    part = part.strip() # Убираем пробелы вокруг
                    if not part:
                        continue # Пропускаем пустые части
                    sub_parts = part.split()
                    print(f"[DEBUG main] Processing sub-part: '{part}', split into: {sub_parts}") # <-- Отладка

                    if len(sub_parts) == 2:
                        stat_input = sub_parts[0].lower()
                        amount_str = sub_parts[1]
                        print(f"[DEBUG main] stat_input: '{stat_input}', amount_str: '{amount_str}'") # <-- Отладка
                        full_stat_name = STAT_ALIASES.get(stat_input)
                        print(f"[DEBUG main] full_stat_name from alias: {full_stat_name}") # <-- Отладка

                        if full_stat_name and full_stat_name in BASE_STATS[:-1]:
                            try:
                                amount = int(amount_str)
                                print(f"[DEBUG main] Parsed amount: {amount}") # <-- Отладка
                                # Вместо немедленного вызова distribute_stat, собираем данные
                                processed_stats.append((full_stat_name, amount))
                            except ValueError:
                                print(f"[DEBUG main] ValueError on int(amount_str): '{amount_str}'") # <-- Отладка
                                send_message(vk, peer_id, f"Количество очков для '{stat_input}' должно быть числом.")
                                all_valid = False
                                break # <-- Прерываем обработку при ошибке
                        else:
                            print(f"[DEBUG main] full_stat_name '{full_stat_name}' not in BASE_STATS or alias not found for '{stat_input}'") # <-- Отладка
                            send_message(vk, peer_id, f"Неверный формат для '{part}'. Неверное сокращение статистики. Доступны: сил, лвк, вын.")
                            all_valid = False
                            break # <-- Прерываем обработку при ошибке
                    else:
                         print(f"[DEBUG main] len(sub_parts) != 2 for '{part}', got {len(sub_parts)}") # <-- Отладка
                         send_message(vk, peer_id, f"Неверный формат для '{part}'. Используйте: <сокращение> <число>.")
                         all_valid = False
                         break # <-- Прерываем обработку при ошибке

                # Если все части корректны, вызываем distribute_stat для каждой
                if all_valid and processed_stats:
                    print(f"[DEBUG main] All parts valid, distributing stats: {processed_stats}") # <-- Отладка
                    for stat_name, stat_amount in processed_stats:
                         distribute_stat(vk, uid, peer_id, stat_name, stat_amount)
                elif all_valid and not processed_stats:
                    send_message(vk, peer_id, "Не найдено корректных пар 'стат число' для распределения.")
                continue

            else:
                parts = text.split()
                print(f"[DEBUG main] No comma, processing single stat input. Split into parts: {parts}") # <-- Отладка
                if len(parts) == 2:
                    stat_input = parts[0].lower()
                    amount_str = parts[1]
                    print(f"[DEBUG main] stat_input: '{stat_input}', amount_str: '{amount_str}'") # <-- Отладка
                    full_stat_name = STAT_ALIASES.get(stat_input)
                    print(f"[DEBUG main] full_stat_name from alias: {full_stat_name}") # <-- Отладка
                    if full_stat_name and full_stat_name in BASE_STATS[:-1]:
                        try:
                            amount = int(amount_str)
                            print(f"[DEBUG main] Parsed amount: {amount}") # <-- Отладка
                            distribute_stat(vk, uid, peer_id, full_stat_name, amount)
                        except ValueError:
                            print(f"[DEBUG main] ValueError on int(amount_str): '{amount_str}'") # <-- Отладка
                            send_message(vk, peer_id, "Количество очков должно быть числом.")
                    else:
                        print(f"[DEBUG main] full_stat_name '{full_stat_name}' not in BASE_STATS or alias not found") # <-- Отладка
                        send_message(vk, peer_id, f"Неверный формат. Используйте: <сокращение> <число>. Доступны: сил, лвк, вын")
                else:
                     print(f"[DEBUG main] len(parts) != 2, got {len(parts)}") # <-- Отладка
                     send_message(vk, peer_id, f"Неверный формат. Используйте: <сокращение> <число>. Доступны: сил, лвк, вын")
            # --- КОНЕЦ СТАРОГО ---

        elif text == "профиль":
            show_profile(vk, uid, peer_id)
        elif text == "сбросить персонажа":
            reset_character(vk, uid, peer_id)
        elif text == "/эффекты":
            show_effects(vk, uid, peer_id)
        elif text == "/статистика":
            from modules.progression.statistics import get_player_stats, format_stats_message
            stats = get_player_stats(uid)
            message = format_stats_message(stats)
            send_message(vk, peer_id, message, keyboard=main_keyboard())
        elif text == "/топ":
            from modules.progression.statistics import get_top_stats, format_top_stats_message
            top_list = get_top_stats(limit=10)
            message = format_top_stats_message(top_list)
            send_message(vk, peer_id, message, keyboard=main_keyboard())
        elif text == "загрузить фото":
            UPLOAD_PHOTO_STATE[uid] = True
            send_message(vk, peer_id, "Отправьте мне фотографию для вашего персонажа. Она будет изменена по размеру, чтобы соответствовать рамке профиля.", keyboard=main_keyboard())
        else:
            if not is_setup_done:
                send_message(vk, peer_id, "Следуйте инструкциям бота. Используйте кнопки, команды или команду 'создать' если у вас нет персонажа.")
            else:
                send_message(vk, peer_id, "Команды: профиль, /эффекты, Загрузить фото", keyboard=main_keyboard())
        continue

    # Обработка в беседе
    # Проверим, является ли сообщение триггером боя
    battle_triggered = False
    # Игнорируем пересылки: не запускаем бой на пересланных сообщениях
    if m.get("fwd_messages"):
        pass
    elif m.get("conversation_message_id") and is_battle_trigger(text):
        # Если у отправителя уже идёт бой — не триггерим новый
        if is_user_in_active_battle(uid):
            send_message(vk, peer_id, "У тебя уже идёт бой.")
            battle_triggered = True
        else:
            reply = m.get("reply_message")
            if reply and not battle_triggered:
                defender_id = reply.get("from_id")
                if defender_id != uid:
                    # Проверим, не участвует ли уже кто-то из них в активном или pending бое
                    if is_user_in_active_battle(uid) or is_user_in_active_battle(defender_id):
                        send_message(vk, peer_id, "У кого-то из вас уже идёт бой.")
                        battle_triggered = True
                    elif is_user_in_pending_battle(defender_id):
                        send_message(vk, peer_id, "Игроку уже предложили бой.")
                        battle_triggered = True
                    else:
                        # Только если никто не занят, создаём новый запрос
                        start_battle_request(vk, uid, defender_id, peer_id, lambda pid, msg, keyboard=None: send_message(vk, pid, msg, keyboard))
                        battle_triggered = True
                else:
                    # Сообщение-ответ отправителю самого себе, не бой
                    pass
            else:
                # Нет reply, не бой
                pass

    if not battle_triggered:
        # Проверки для handle_battle_response и process_turn
        # handle_battle_response должен быть первым, так как он обрабатывает ответы на запросы боя
        if handle_battle_response(vk, uid, text, lambda pid, msg, keyboard=None: send_message(vk, pid, msg, keyboard)):
            continue
        
        # process_turn обрабатывает активные ходы в бою
        if process_turn(vk, uid, text, lambda pid, msg, keyboard=None: send_message(vk, pid, msg, keyboard)):
            continue

        # --- НОВОЕ: Обработка команд статистики в беседе ---
        # Проверяем, начинается ли сообщение с "тренер "
        if text.startswith("тренер "):
            # Извлекаем команду после "тренер "
            command = text[len("тренер "):].strip()

            if command == "статистика":
                from modules.progression.statistics import get_player_stats, format_stats_message
                stats = get_player_stats(uid)
                message = format_stats_message(stats)
                send_message(vk, peer_id, message)
                continue

            elif command == "топ":
                from modules.progression.statistics import get_top_stats, format_top_stats_message
                top_list = get_top_stats(limit=10)
                message = format_top_stats_message(top_list)
                send_message(vk, peer_id, message)
                continue
