# combat.py
import random
from constants import WEAPONS, EFFECTS, SKILLS, WEAPON_SKILLS
from utils import calc_modifier, calculate_ac, roll_with_advantage_disadvantage # <-- Импортируем утилиты

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

def format_detailed_attack_log(attacker, defender, weapon, attack_roll_result, attack_mod, target_ac, hit, damage_roll_result, damage_mod, total_damage, is_crit, attacker_has_advantage, attacker_has_disadvantage):
    """Формирует подробный лог атаки."""
    log_lines = []
    # --- Информация о цели ---
    log_lines.append(f"{defender['name']}: КБ {target_ac}")

    # --- Информация об атаке ---
    advantage_str = " (Преимущество)" if attacker_has_advantage else ""
    disadvantage_str = " (Помеха)" if attacker_has_disadvantage else ""
    # Определим, какая характеристика использовалась для атаки
    attack_stat = weapon["stat"]
    if isinstance(attack_stat, list):
        used_stat = attack_stat[0] if calc_modifier(attacker[attack_stat[0]]) >= calc_modifier(attacker[attack_stat[1]]) else attack_stat[1]
    else:
        used_stat = attack_stat
    stat_mod = calc_modifier(attacker[used_stat])
    log_lines.append(f"Атака: {attack_roll_result}(1d20){advantage_str}{disadvantage_str}+{stat_mod}({used_stat}) = {attack_roll_result + stat_mod}")

    # --- Информация о попадании ---
    if hit:
        log_lines.append(f"Попадание! (результат {attack_roll_result + stat_mod} >= КБ {target_ac})")
        # --- Информация об уроне ---
        # Определим, какая характеристика использовалась для урона (обычно та же, что и для атаки, но может отличаться)
        damage_stat = weapon["stat"]
        if isinstance(damage_stat, list):
            # Выбираем характеристику для урона (обычно максимальная модификатора)
            used_damage_stat = damage_stat[0] if calc_modifier(attacker[damage_stat[0]]) >= calc_modifier(attacker[damage_stat[1]]) else damage_stat[1]
        else:
            used_damage_stat = damage_stat
        damage_stat_mod = calc_modifier(attacker[used_damage_stat])
        log_lines.append(f"Урон: {damage_roll_result}({weapon['damage_two'] if weapon['hands'] == 2 else weapon['damage_one']})+{damage_stat_mod}({used_damage_stat}) = {total_damage}")
        if is_crit:
             log_lines.append(f"Критический удар! Урон удвоен до {total_damage}.")
    else:
        log_lines.append(f"Промах! (результат {attack_roll_result + stat_mod} < КБ {target_ac})")

    return "\n".join(log_lines)

def calculate_battle(attacker: dict, defender: dict, action: dict, damage_bonus: int = 0):
    log = []
    applied_effects = {}
    is_skill_attack = False

    if action.get("valid") is False or action["type"] in ("invalid", "nsfw", "pass"):
        return {"damage": 0, "log": log, "effects": {}}

    if action["type"] == "skill":
        skill_name = action.get("skill_name")
        weapon_name = attacker.get("equipment", {}).get("weapon")
        
        if weapon_name and skill_name in WEAPON_SKILLS.get(weapon_name, []):
            is_skill_attack = True
            log.append(f"{attacker['name']} использует умение '{skill_name}'!")
        else:
            log.append(f"{attacker['name']} не может использовать умение '{skill_name}' с оружием {weapon_name}.")
            return {"damage": 0, "log": log, "effects": {}}

    if action["type"] in ("heal", "buff", "debuff"):
        return {"damage": 0, "log": log, "effects": action.get("effects", {})}

    weapon_name = attacker.get("equipment", {}).get("weapon")
    weapon = WEAPONS.get(weapon_name)
    if not weapon:
        log.append("Нет оружия — наносится 1 урон.")
        return {"damage": 1, "log": log, "effects": {}}

    is_two_handed = weapon["hands"] == 2
    damage_dice = weapon["damage_two"] if is_two_handed else weapon["damage_one"]

    stat = weapon["stat"]
    if isinstance(stat, list):
        mod1 = calc_modifier(attacker[stat[0]])
        mod2 = calc_modifier(attacker[stat[1]])
        attack_mod = max(mod1, mod2)
        # Для упрощения, используем модификатор атаки для урона, если он из списка
        # (в реальности может быть сложнее)
        damage_mod = attack_mod
    else:
        attack_mod = calc_modifier(attacker[stat])
        damage_mod = attack_mod # <-- В простом случае модификатор атаки = модификатор урона

    target_ac = calculate_ac(defender) # <-- Используем импортированную функцию

    # Определяем, есть ли преимущество/помеха для атаки
    attacker_has_advantage = any(
        name == "prone" and isinstance(eff, dict) and eff.get("duration", 0) > 0
        for name, eff in defender.get("status_effects", {}).items()
    )
    # Помеха не реализована в текущем calculate_battle, но можно добавить логику
    attacker_has_disadvantage = False # <-- Пример места для будущей логики помехи

    attack_roll_result = roll_with_advantage_disadvantage_base("1d20", advantage=attacker_has_advantage, disadvantage=attacker_has_disadvantage) # <-- Новая вспомогательная функция
    attack_roll_total = attack_roll_result + attack_mod

    hit = attack_roll_total >= target_ac

    # --- ФОРМИРОВАНИЕ ПОДРОБНОГО ЛОГА АТАКИ ---
    detailed_attack_log = format_detailed_attack_log(
        attacker, defender, weapon,
        attack_roll_result, attack_mod, target_ac, hit,
        # Нужно будет вычислить damage_roll_result до его сложения с модификатором
        0, 0, 0, False, # <-- Эти 3 значения пока неизвестны, нужно изменить логику
        attacker_has_advantage, attacker_has_disadvantage
    )
    # --- КОНЕЦ ФОРМИРОВАНИЯ ЛОГА ---

    if hit:
        # Вычисляем урон *после* определения попадания
        damage_roll_result = roll(damage_dice)
        is_crit = attack_roll_result >= 20 # <-- Крит на 20
        if is_crit:
            crit_damage_roll = roll(damage_dice)
            log.append(f"Критический удар! Дополнительный бросок урона: {crit_damage_roll}.")
            damage_roll_result += crit_damage_roll

        total_damage = damage_roll_result + damage_mod + damage_bonus
        if damage_bonus > 0:
            log.append(f"Бонусный урон от эффектов: +{damage_bonus}.")

        if is_skill_attack:
            skill_name = action.get("skill_name")
            skill_info = SKILLS.get(skill_name, {})
            skill_effects = skill_info.get("effects", [])
            for effect_name in skill_effects:
                if effect_name in EFFECTS:
                    applied_effects[effect_name] = EFFECTS[effect_name]
                    log.append(f"Умение '{skill_name}' накладывает эффект '{effect_name}'.")

        offhand_weapon_name = attacker.get("equipment", {}).get("offhand")
        if offhand_weapon_name and offhand_weapon_name != "щит" and offhand_weapon_name != "ничего":
            offhand_weapon = WEAPONS.get(offhand_weapon_name)
            if offhand_weapon:
                offhand_damage = roll(offhand_weapon["damage_one"])
                total_damage += offhand_damage
                log.append(f"{attacker['name']} также наносит {offhand_damage} урона оружием в левой руке.")

        # --- ОБНОВЛЯЕМ ПОДРОБНЫЙ ЛОГ С УЧЁТОМ ВЫЧИСЛЕННОГО УРОНА ---
        # Пересчитываем лог, передав вычисленные значения
        detailed_attack_log = format_detailed_attack_log(
            attacker, defender, weapon,
            attack_roll_result, attack_mod, target_ac, hit,
            damage_roll_result, damage_mod, total_damage, is_crit,
            attacker_has_advantage, attacker_has_disadvantage
        )
        # --- КОНЕЦ ОБНОВЛЕНИЯ ЛОГА ---

        # log.append(f"{attacker['name']} попадает по {defender['name']} и наносит {total_damage} урона.") # <-- УБРАНО
        log.append(detailed_attack_log) # <-- ДОБАВЛЕН ПОДРОБНЫЙ ЛОГ
    else:
        # log.append(f"{attacker['name']} промахивается по {defender['name']} (бросок {attack_roll_total}, КБ {target_ac}).") # <-- УБРАНО
        detailed_attack_log = format_detailed_attack_log(
            attacker, defender, weapon,
            attack_roll_result, attack_mod, target_ac, hit,
            0, 0, 0, False, # <-- Значения для урона не применимы
            attacker_has_advantage, attacker_has_disadvantage
        )
        log.append(detailed_attack_log) # <-- ДОБАВЛЕН ПОДРОБНЫЙ ЛОГ
        return {"damage": 0, "log": log, "crit": False, "effects": {}} # <-- Если промах, выходим

    # ... (обработка эффектов остается без изменений, но можно добавить подробности и тут) ...

    return {
        "damage": total_damage, # <-- Возвращаем вычисленное значение
        "log": log,
        "crit": is_crit,
        "effects": applied_effects
    }

# --- ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ ДЛЯ ОТДЕЛЬНОГО БРОСКА D20 ---
def roll_with_advantage_disadvantage_base(dice_base, advantage=False, disadvantage=False):
    """Бросает 1d20, с учётом advantage/disadvantage, возвращает результат броска."""
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

    return roll_result
# --- КОНЕЦ ВСПОМОГАТЕЛЬНОЙ ФУНКЦИИ ---
