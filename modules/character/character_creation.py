import json
from constants import WEAPONS, ARMORS, BASE_STATS, EFFECTS, STAT_ALIASES, CLASS_DESCRIPTIONS
from utils import calc_modifier
from data_storage import get_player_data, save_player_data
from vk_utils import send_message, get_user_name
from .character_image_generator import generate_character_image # Import for initial image generation
import os # Import os for path manipulation

def explain_weapon_choice():
    """Сообщение перед выбором оружия. Отредактируйте этот текст!"""
    return (
   "Боевой топор -  Кров"
   "отечение, Покалечено"
   " \r\n"
   "В одной руке: Наноси"
   "т 1d8  + модификатор"
   " силы\r\n"
   "В двух руках: Наноси"
   "т 1d10 + модификатор"
   " силы\r\n\r\n"
   "Длинный меч - Кровот"
   "ечение, Сбивание с н"
   "ог\r\n"
   "В одной руке: Наноси"
   "т 1d8 + (модификатор"
   " силы)\r\n"
   "В двух руках: Наноси"
   "т 1d10 + (модификато"
   "р силы) \r\n\r\n"
   "Булава 1d6 + (модифи"
   "катор силы)- Дезорие"
   "нтация\r\n"
   "Кинжал 1d4 + (модифи"
   "катор  ловкости) - К"
   "ровотечение\r\n"
   "Короткий меч 1d6 + 2"
   " + (модификатор  лов"
   "кости или  силы) - К"
   "ровотечение, сбивани"
   "е с ног\r\n"
   "Моргенштерн 1d8 + (м"
   "одификатор силы) - Р"
   "анение в грудь, Дезо"
   "риентация\r\n"
   "Рапира 1d8 + (модифи"
   "катор  силы или  лов"
   "кости) - Слабая хват"
   "ка, Кровотечение,  с"
   "бивание с ног"
    )

def explain_armor_choice():
    """Сообщение перед выбором брони. Отредектируйте этот текст!"""
    return (
        "🛡️ Броня защищает вас в бою.\n\n"
        "• Кожаный доспех — 11 КБ + модификатор ловкости.\n"
        "• Сыромятный — 12 КБ + модификатор ловкости (не больше +2).\n"
        "• Кольчатый — 15 КБ."
    )

def create_character(vk_api_instance, uid, peer_id):
    from .profile_view import main_keyboard
    existing = get_player_data(uid)
    if existing:
        send_message(vk_api_instance, peer_id, "Персонаж уже создан.", keyboard=main_keyboard())
        return

    name = get_user_name(vk_api_instance, uid)
    player = {
        "id": uid,
        "name": name,
        "level": 3,
        "allocated_points": {},
        "stat_points": 12,
        "is_setup_complete": False,
        "gender": None,
        "race": None, # <-- Добавлено поле расы
        "class": None,
        "skills": ["Разрыв тканей"], # Default skill, will be updated by class/weapon
        "inventory": [],
        "equipment": {"weapon": "боевой топор", "armor": None, "offhand": None}, # <-- Временно устанавливаем дефолтное оружие для отладки
        "hp": 0,
        "max_hp": 0,
        "setup_stage": "gender"
    }
    save_player_data(uid, player)
    print(f"[DEBUG] create_character: Player {name} created with equipment: {player['equipment']}") # <-- Добавлен дебаг

    kb = json.dumps({
        "inline": True,
        "buttons": [[
            {"action": {"type": "text", "label": "мальтик"}, "color": "primary"},
            {"action": {"type": "text", "label": "девотька"}, "color": "secondary"},
        ]]
    })
    send_message(vk_api_instance, peer_id, f"🎲 {name} создан. Выберите пол:", kb)

def choose_gender(vk_api_instance, uid, peer_id, gender):
    p = get_player_data(uid)
    if not p or p.get("setup_stage") != "gender":
        return
    if gender not in ("мальтик", "девотька"):
        send_message(vk_api_instance, peer_id, "Нажмите кнопку.")
        return
    p["gender"] = gender
    p["setup_stage"] = "race" # <-- Изменено: следующий этап - выбор расы
    save_player_data(uid, p)

    # --- НОВОЕ: Клавиатура с расами (Часть 1) ---
    kb = json.dumps({
        "inline": True,
        "buttons": [
            [
                {"action": {"type": "text", "label": "Человек"}, "color": "primary"},
                {"action": {"type": "text", "label": "Эльф"}, "color": "primary"},
                {"action": {"type": "text", "label": "Дварф"}, "color": "primary"},
            ],
            [
                {"action": {"type": "text", "label": "Полуэльф"}, "color": "primary"},
                {"action": {"type": "text", "label": "Полурослик"}, "color": "primary"},
            ],
            [
                {"action": {"type": "text", "label": "Далее (расы)"}, "color": "secondary"},
            ]
        ]
    })
    # --- КОНЕЦ НОВОГО ---

    send_message(vk_api_instance, peer_id, "Теперь выберите расу (пока не на что не влияет)(1/2):", kb)

def choose_race_page_2(vk_api_instance, uid, peer_id):
    p = get_player_data(uid)
    if not p or p.get("setup_stage") != "race":
        return
    kb = json.dumps({
        "inline": True,
        "buttons": [
            [
                {"action": {"type": "text", "label": "Гном"}, "color": "primary"},
                {"action": {"type": "text", "label": "Дроу"}, "color": "primary"},
                {"action": {"type": "text", "label": "Тифлинг"}, "color": "primary"},
            ],
            [
                {"action": {"type": "text", "label": "Полуорк"}, "color": "primary"},
                {"action": {"type": "text", "label": "Гитянка"}, "color": "primary"},
            ],
            [
                {"action": {"type": "text", "label": "Драконорожденный"}, "color": "primary"},
            ]
        ]
    })
    send_message(vk_api_instance, peer_id, "Выберите расу (пока не на что не влияет)(2/2):", kb)

# --- НОВОЕ: Обработчик выбора расы ---
def choose_race(vk_api_instance, uid, peer_id, race_name):
    p = get_player_data(uid)
    if not p or p.get("setup_stage") != "race":
        return

    # Список допустимых рас
    valid_races = [
        "Гитянка", "Гном", "Дварф", "Дроу", "Полуорк", "Полурослик",
        "Полуэльф", "Тифлинг", "Человек", "Эльф", "Драконорожденный"
    ]

    if race_name not in valid_races:
        send_message(vk_api_instance, peer_id, "Нет такой расы.")
        return

    p["race"] = race_name
    p["setup_stage"] = "class"
    save_player_data(uid, p)

    kb = json.dumps({
        "inline": True,
        "buttons": [
            [
                {"action": {"type": "text", "label": "Варвар"}, "color": "primary"},
                {"action": {"type": "text", "label": "Бард"}, "color": "primary"},
                {"action": {"type": "text", "label": "Жрец"}, "color": "primary"},
            ],
            [
                {"action": {"type": "text", "label": "Друид"}, "color": "primary"},
                {"action": {"type": "text", "label": "Воин"}, "color": "primary"},
                {"action": {"type": "text", "label": "Монах"}, "color": "primary"},
            ],
            [
                {"action": {"type": "text", "label": "Далее (классы)"}, "color": "secondary"},
            ]
        ]
    })

    send_message(vk_api_instance, peer_id, "Теперь выберите класс (пока не на что не влияет)(1/2):", kb)

def choose_class_page_2(vk_api_instance, uid, peer_id):
    p = get_player_data(uid)
    if not p or p.get("setup_stage") != "class":
        return
    kb = json.dumps({
        "inline": True,
        "buttons": [
            [
                {"action": {"type": "text", "label": "Паладин"}, "color": "primary"},
                {"action": {"type": "text", "label": "Следопыт"}, "color": "primary"},
                {"action": {"type": "text", "label": "Плут"}, "color": "primary"},
            ],
            [
                {"action": {"type": "text", "label": "Чародей"}, "color": "primary"},
                {"action": {"type": "text", "label": "Колдун"}, "color": "primary"},
                {"action": {"type": "text", "label": "Волшебник"}, "color": "primary"},
            ]
        ]
    })
    send_message(vk_api_instance, peer_id, "Выберите класс (пока не на что не влияет)(2/2):", kb)

def choose_class(vk_api_instance, uid, peer_id, class_name):
    p = get_player_data(uid)
    if not p or p.get("setup_stage") != "class":
        return

    valid_classes = list(CLASS_DESCRIPTIONS.keys())
    if class_name not in valid_classes:
        send_message(vk_api_instance, peer_id, "Нет такого класса.")
        return

    p["temp_class"] = class_name
    p["setup_stage"] = "class_confirm"
    save_player_data(uid, p)

    description = CLASS_DESCRIPTIONS.get(class_name, "Описание не найдено.")
    
    kb = json.dumps({
        "inline": True,
        "buttons": [
            [
                {"action": {"type": "text", "label": "Принять"}, "color": "positive"},
                {"action": {"type": "text", "label": "Выбрать другой"}, "color": "negative"},
            ]
        ]
    })
    
    send_message(vk_api_instance, peer_id, f"**{class_name}**\n\n{description}", kb)

def handle_class_confirmation(vk_api_instance, uid, peer_id, choice):
    p = get_player_data(uid)
    if not p or p.get("setup_stage") != "class_confirm":
        return

    if choice == "принять":
        p["class"] = p.pop("temp_class", None)
        p["setup_stage"] = "weapon"
        save_player_data(uid, p)

        send_message(vk_api_instance, peer_id, explain_weapon_choice())

        kb = json.dumps({
            "inline": True,
            "buttons": [
                [{"action": {"type": "text", "label": "кинжал"}, "color": "primary"}],
                [{"action": {"type": "text", "label": "короткий меч"}, "color": "primary"}],
                [{"action": {"type": "text", "label": "длинный меч"}, "color": "primary"}],
                [{"action": {"type": "text", "label": "боевой топор"}, "color": "primary"}],
                [{"action": {"type": "text", "label": "булава"}, "color": "primary"}],
                [{"action": {"type": "text", "label": "рапира"}, "color": "primary"}],
            ]
        })
        send_message(vk_api_instance, peer_id, "Класс принят! Теперь выберите начальное оружие:", kb)
    
    elif choice == "выбрать другой":
        p.pop("temp_class", None)
        p["setup_stage"] = "class"
        save_player_data(uid, p)
        
        # Повторно отправляем первую страницу выбора класса
        kb = json.dumps({
            "inline": True,
            "buttons": [
                [
                    {"action": {"type": "text", "label": "Варвар"}, "color": "primary"},
                    {"action": {"type": "text", "label": "Бард"}, "color": "primary"},
                    {"action": {"type": "text", "label": "Жрец"}, "color": "primary"},
                ],
                [
                    {"action": {"type": "text", "label": "Друид"}, "color": "primary"},
                    {"action": {"type": "text", "label": "Воин"}, "color": "primary"},
                    {"action": {"type": "text", "label": "Монах"}, "color": "primary"},
                ],
                [
                    {"action": {"type": "text", "label": "Далее (классы)"}, "color": "secondary"},
                ]
            ]
        })
        send_message(vk_api_instance, peer_id, "Выберите класс (пока не на что не влияет)(1/2):", kb)
    else:
        send_message(vk_api_instance, peer_id, "Нажмите 'Принять' или 'Выбрать другой'.")

def choose_weapon(vk_api_instance, uid, peer_id, weapon_name):
    p = get_player_data(uid)
    if not p or p.get("setup_stage") != "weapon":
        return
    if weapon_name not in WEAPONS:
        send_message(vk_api_instance, peer_id, "Нет такого оружия.")
        return

    p["equipment"]["weapon"] = weapon_name
    p["inventory"].append(weapon_name)
    wp = WEAPONS[weapon_name]

    if wp["hands"] == 2:
        p["equipment"]["offhand"] = "ничего"
        p["setup_stage"] = "armor"
        save_player_data(uid, p)

        send_message(vk_api_instance, peer_id, explain_armor_choice())

        kb = json.dumps({
            "inline": True,
            "buttons": [
                [{"action": {"type": "text", "label": "кожаный доспех"}, "color": "primary"}],
                [{"action": {"type": "text", "label": "сыромятный доспех"}, "color": "primary"}],
                [{"action": {"type": "text", "label": "кольчужный доспех"}, "color": "primary"}],
            ]
        })
        send_message(vk_api_instance, peer_id, f"Оружие выбрано: {weapon_name}. Теперь выберите броню:", kb)
    else:
        p["equipment"]["offhand"] = None
        p["setup_stage"] = "offhand"
        save_player_data(uid, p)
        kb = json.dumps({
            "inline": True,
            "buttons": [
                [{"action": {"type": "text", "label": "ничего"}, "color": "default"}],
                [{"action": {"type": "text", "label": "щит"}, "color": "primary"}],
                [{"action": {"type": "text", "label": "короткий меч"}, "color": "primary"}],
                [{"action": {"type": "text", "label": "кинжал"}, "color": "primary"}],
            ]
        })
        send_message(vk_api_instance, peer_id, f"Оружие выбрано: {weapon_name}. Что во второй руке?", kb)

def choose_offhand(vk_api_instance, uid, peer_id, item):
    p = get_player_data(uid)
    if not p or p.get("setup_stage") != "offhand":
        return

    if item == "ничего":
        p["equipment"]["offhand"] = "ничего"
    elif item in ["щит", "короткий меч", "кинжал"]:
        weapon = p["equipment"]["weapon"]
        wp = WEAPONS.get(weapon)
        if wp and wp["hands"] == 2:
            send_message(vk_api_instance, peer_id, f"Нельзя использовать {item}, потому что {weapon} — двуручное оружие.")
            return
        p["equipment"]["offhand"] = item
        p["inventory"].append(item)
    else:
        send_message(vk_api_instance, peer_id, "Нет такого предмета.")
        return

    p["setup_stage"] = "armor"
    save_player_data(uid, p)

    send_message(vk_api_instance, peer_id, explain_armor_choice())

    kb = json.dumps({
        "inline": True,
        "buttons": [
            [{"action": {"type": "text", "label": "кожаный доспех"}, "color": "primary"}],
            [{"action": {"type": "text", "label": "сыромятный доспех"}, "color": "primary"}],
            [{"action": {"type": "text", "label": "кольчужный доспех"}, "color": "primary"}],
        ]
    })
    send_message(vk_api_instance, peer_id, f"Во второй руке: {item}. Теперь выберите броню:", kb)

def choose_armor(vk_api_instance, uid, peer_id, armor_name):
    from .profile_view import main_keyboard
    p = get_player_data(uid)
    if not p or p.get("setup_stage") != "armor":
        return
    if armor_name not in ARMORS or ARMORS[armor_name]["type"] != "броня":
        send_message(vk_api_instance, peer_id, "Нет такой брони.")
        return

    p["equipment"]["armor"] = armor_name
    p["inventory"].append(armor_name)
    p["setup_stage"] = "stats"
    save_player_data(uid, p)

    stat_info = (
        f"Теперь распределите 12 очков по характеристикам.\n\n"
        "📊 Характеристики:\n"
        "• Сила (СИЛ): Влияет на атаки и урон оружием, зависящим от силы (например, топор, меч).\n"
        "• Ловкость (ЛВК): Влияет на атаки и урон оружием, зависящим от ловкости (например, кинжал, рапира).\n"
        "Также влияет на ваш Класс Брони (КБ) при ношении лёгкой брони.\n"
        "• Выносливость (ВЫН): Влияет на ваше максимальное здоровье (HP).\n"
        "• Интеллект (пока не на что не влияет)(ИНТ): Влияет на магические способности и знание.\n"
        "• Мудрость (пока не на что не влияет)(МДР): Влияет на восприятие и силу воли.\n"
        "• Харизма (пока не на что не влияет)(ХАР): Влияет на социальные взаимодействия и лидерство.\n"
        "📈 Модификаторы:\n"
        "Изначально каждая характеристика равняется 8. Каждая характеристика имеет модификатор\n"
        "Например, характеристика 12 даёт модификатор +1, характеристика 8 даёт модификатор -1.\n"
        "Эти модификаторы добавляются к броскам атаки, урону, спасброскам и КБ.\n\n"
        "📝 Пример команды: 'сил 3' — добавит 3 очка к Силе (итоговая Сила будет 8+3=11, модификатор +0).\n"
        "У вас 12 очков для распределения между этими 6 характеристиками."
        )

    send_message(vk_api_instance, peer_id, stat_info, keyboard=main_keyboard())

def distribute_stat(vk_api_instance, uid, peer_id, stat_input, amount): # <-- Изменён параметр
    from .profile_view import main_keyboard
    try:
        amount = int(amount)
    except ValueError:
        send_message(vk_api_instance, peer_id, "Количество очков должно быть числом.")
        return

    # --- ПОЛУЧАЕМ ПОЛНОЕ ИМЯ СТАТА ---
    full_stat_name = STAT_ALIASES.get(stat_input.lower(), stat_input.lower()) # <-- НОВОЕ
    # --- КОНЕЦ ПОЛУЧЕНИЯ ---

    if full_stat_name not in BASE_STATS[:-2]: # Exclude "жизни" from the check
        available_aliases = ', '.join([alias for alias, stat in STAT_ALIASES.items() if stat != "жизни"])
        send_message(vk_api_instance, peer_id, f"Нет такой характеристики. Доступны сокращения: {available_aliases}")
        return
    if amount <= 0:
        send_message(vk_api_instance, peer_id, "Введите положительное число.")
        return

    p = get_player_data(uid)
    if not p or p.get("setup_stage") != "stats":
        return

    if p["stat_points"] < amount:
        send_message(vk_api_instance, peer_id, f"У вас недостаточно очков. Осталось: {p['stat_points']}")
        return

    # Calculate current total for the stat (base 8 + already allocated points)
    current_stat_value = 8 + p["allocated_points"].get(full_stat_name, 0)
    
    # Check if adding 'amount' would exceed the limit of 16
    if current_stat_value + amount > 16:
        max_addable = 16 - current_stat_value
        if max_addable <= 0:
            send_message(vk_api_instance, peer_id, f"Характеристика '{full_stat_name}' уже достигла максимального значения (16).")
            return
        else:
            send_message(vk_api_instance, peer_id, f"Вы можете добавить только {max_addable} очков к '{full_stat_name}', чтобы не превысить лимит 16.")
            amount = max_addable # Adjust amount to only reach the limit

    # --- ИСПОЛЬЗУЕМ full_stat_name ---
    p["allocated_points"][full_stat_name] = p["allocated_points"].get(full_stat_name, 0) + amount
    # --- КОНЕЦ ИСПОЛЬЗОВАНИЯ ---

    p["stat_points"] -= amount

    if p["stat_points"] == 0:
        s = p["allocated_points"]
        base_stat_value = 8
        base_hp = 22

        final_strength = base_stat_value + s.get("сила", 0)
        final_dexterity = base_stat_value + s.get("ловкость", 0)
        final_constitution = base_stat_value + s.get("выносливость", 0)
        final_intelligence = base_stat_value + s.get("интеллект", 0)
        final_wisdom = base_stat_value + s.get("мудрость", 0)
        final_charism = base_stat_value + s.get("харизма", 0)

        str_mod = calc_modifier(final_strength) # Calculate strength modifier
        hp_total = base_hp + str_mod * 3 # New HP calculation: 22 + strength_modifier * 3

        p.update(
            strength=final_strength,
            dexterity=final_dexterity,
            constitution=final_constitution,
            intelligence=final_intelligence,
            wisdom=final_wisdom,
            charism=final_charism,
            hp=hp_total,
            max_hp=hp_total,
            exp=0,
            status_effects={},
            is_setup_complete=True,
            setup_stage="done"
        )

        # Calculate AC
        final_ac = 0
        armor_name = p["equipment"].get("armor")
        offhand_name = p["equipment"].get("offhand")

        if armor_name and armor_name in ARMORS:
            armor_data = ARMORS[armor_name]
            base_ac = armor_data.get("ac_base", 10)
            dex_mod_applies = armor_data.get("dex_mod", False)
            max_dex_bonus = armor_data.get("max_dex")

            final_ac = base_ac
            if dex_mod_applies:
                dex_mod = calc_modifier(final_dexterity)
                if max_dex_bonus is not None:
                    final_ac += min(dex_mod, max_dex_bonus)
                else:
                    final_ac += dex_mod
        else:
            # Default AC if no armor or unknown armor
            final_ac = 10 + calc_modifier(final_dexterity) # Base AC 10 + Dex modifier

        if offhand_name == "щит" and offhand_name in ARMORS:
            shield_data = ARMORS[offhand_name]
            final_ac += shield_data.get("ac_bonus", 0)
        
        p["ac"] = final_ac # Store the calculated AC
        print(f"[DEBUG character_creation] Calculated AC: {final_ac}") # Debug print

        txt = "✅ Все очки распределены! Персонаж готов."

        # Generate initial profile image after setup is complete
        output_image_name = f"profile_{uid}.png"
        print(f"[DEBUG character_creation] Generating initial profile image for {uid}")
        generate_character_image(uid, p, output_image_name)

    else:
        # --- ИСПОЛЬЗУЕМ full_stat_name ---
        txt = f"✅ {amount} в «{full_stat_name}». Осталось {p['stat_points']}." # <-- ЗАМЕНЕНО
        # --- КОНЕЦ ИСПОЛЬЗОВАНИЯ ---

    save_player_data(uid, p)
    send_message(vk_api_instance, peer_id, txt, keyboard=main_keyboard())
