import random 
from constants import ARMORS, SKILLS
from sentence_transformers import SentenceTransformer, util

# Загружаем модель один раз при старте
# Добавляем кэширование, чтобы избежать повторной загрузки, но убеждаемся, что она чистая.
_model_instance = None
def get_sentence_transformer_model():
    global _model_instance
    if _model_instance is None:
        _model_instance = SentenceTransformer('all-MiniLM-L6-v2')
    return _model_instance

model = get_sentence_transformer_model()

def calc_modifier(score):
    return (score - 10) // 2

def calculate_ac(player_data):
    """Рассчитывает КБ игрока на основе брони, ловкости и эффектов."""
    equip = player_data.get("equipment", {})
    armor_name = equip.get("armor")
    ac = 10 # Базовый КБ без брони

    if armor_name and armor_name in ARMORS:
        armor_data = ARMORS[armor_name]
        if armor_data["type"] == "броня":
            ac = armor_data["ac_base"]
            # Проверяем, есть ли эффект, отключающий бонус ловкости к КБ
            is_debuffed = any(
                name == "дезориентация" and isinstance(eff, dict) and eff.get("duration", 0) > 0
                for name, eff in player_data.get("status_effects", {}).items()
            )
            if armor_data["dex_mod"] and not is_debuffed:
                dex_mod = calc_modifier(player_data["dexterity"])
                if armor_data["max_dex"] is not None:
                    dex_mod = min(dex_mod, armor_data["max_dex"])
                ac += dex_mod

    # Проверяем щит
    offhand = equip.get("offhand")
    if offhand == "щит":
        ac += ARMORS.get("щит", {}).get("ac_bonus", 0)

    return ac

def roll_with_advantage_disadvantage(dice_base, modifier, advantage=False, disadvantage=False):
    """Бросает 1d20 + modifier, с учётом advantage/disadvantage."""
    if advantage and disadvantage:
        advantage = disadvantage = False

    if advantage:
        roll1 = random.randint(1, 20)
        roll2 = random.randint(1, 20)
        roll_result = max(roll1, roll2)
    elif disadvantage:
        roll1 = random.randint(1, 20)
        roll2 = random.randint(1, 20)
        roll_result = min(roll1, roll2)
    else:
        roll_result = random.randint(1, 20)

    return roll_result + modifier

## VK-specific helpers moved to vk_utils.py

def find_best_skill(player_input: str, available_skill_names: list, threshold=0.6):
    """
    Находит наиболее подходящий скилл на основе семантического сходства.
    Принимает список названий скиллов, доступных игроку.
    """
    if not available_skill_names:
        print(f"[DEBUG] find_best_skill: No available skill names provided.")
        return None

    all_triggers = []
    trigger_to_skill_name_map = {} # Для обратного поиска скилла по триггеру

    for skill_name in available_skill_names:
        if skill_name in SKILLS:
            for trigger in SKILLS[skill_name]["triggers"]:
                all_triggers.append(trigger)
                trigger_to_skill_name_map[trigger] = skill_name
        else:
            print(f"[DEBUG] find_best_skill: Skill '{skill_name}' not found in SKILLS dictionary.")

    if not all_triggers:
        print(f"[DEBUG] find_best_skill: No triggers found for available skills.")
        return None

    # Кодируем ввод игрока и все триггеры
    input_embedding = model.encode(player_input, convert_to_tensor=True)
    trigger_embeddings = model.encode(all_triggers, convert_to_tensor=True)

    # Вычисляем косинусное сходство
    cosine_scores = util.pytorch_cos_sim(input_embedding, trigger_embeddings)

    # Находим лучший результат
    best_score, best_idx = cosine_scores[0].max(dim=0)
    
    print(f"[DEBUG] find_best_skill: Input: '{player_input}'")
    print(f"[DEBUG] find_best_skill: All collected triggers: {all_triggers}")
    print(f"[DEBUG] find_best_skill: Cosine scores: {cosine_scores[0].tolist()}")
    print(f"[DEBUG] find_best_skill: Best score: {best_score.item()}, Best trigger index: {best_idx}")

    if best_score.item() > threshold:
        best_trigger = all_triggers[best_idx]
        matched_skill_name = trigger_to_skill_name_map[best_trigger]
        print(f"[DEBUG] find_best_skill: Matched skill: '{matched_skill_name}' with score {best_score.item()} (trigger: '{best_trigger}')")
        return matched_skill_name
    
    print(f"[DEBUG] find_best_skill: No skill matched above threshold {threshold}")
    return None
