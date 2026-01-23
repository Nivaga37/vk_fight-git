from PIL import Image, ImageDraw, ImageFont
import os
import sys

# Add the project root to the sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE_DIR)

from constants import IMAGE_MAPPING, WEAPONS # Import the mapping and WEAPONS

# Пути (относительно корня проекта)
# BASE_DIR is already defined above
IMG_DIR = os.path.join(BASE_DIR, "img")
PORTRAITS_DIR = os.path.join(IMG_DIR, "portraits")

# Убедимся, что папка для портретов существует
os.makedirs(PORTRAITS_DIR, exist_ok=True)

input_image_path = os.path.join(IMG_DIR, "form.png") #начальное
# overlay_image_path будет динамическим
portrait_image_path_template = os.path.join(PORTRAITS_DIR, "{uid}.jpg") #фото игрока

# Цвета
white = (255, 255, 255)
beige = (189, 154, 112)

# Кэш шрифтов
font_cache = {}
font_name = os.path.join(IMG_DIR, "FF Quadraat Pro Regular.ttf")

def get_font(size):
    if size not in font_cache:
        try:
            font_cache[size] = ImageFont.truetype(font_name, size)
        except OSError:
            print(f"⚠️ Шрифт '{font_name}' не найден. Используется стандартный для размера {size}.")
            font_cache[size] = ImageFont.load_default()
    return font_cache[size]

def generate_character_image(uid, player_data, output_filename="output.png"):
    char_class_ru = player_data.get("class", "Воин") # Default to Воин if class not found
    char_race = player_data.get("race", "Неизвестная раса")
    char_name = player_data.get("name", "Имя Фамилия")
    strength = player_data.get("strength", 8)
    dexterity = player_data.get("dexterity", 8)
    constitution = player_data.get("constitution", 8)
    intelligence = player_data.get("intelligence", 8) # Assuming 'intelligence' for интеллект
    wisdom = player_data.get("wisdom", 8)
    charism = player_data.get("charism", 8)
    hp = player_data.get("hp", 20)
    max_hp = player_data.get("max_hp", 20)
    ac = player_data.get("ac", 10) # Armor Class
    print(f"[DEBUG image_generator] Received AC: {ac}") # Debug print
    
    # Equipment
    equipment = player_data.get("equipment", {})
    weapon_name_ru = equipment.get("weapon", "булава") # Default weapon in Russian
    offhand_name_ru = equipment.get("offhand", "щит") # Default offhand in Russian
    armor_name_ru = equipment.get("armor", "сыромятный доспех") # Default armor in Russian

    # Paths for dynamic images
    overlay_image_filename = IMAGE_MAPPING.get(char_class_ru, "Fighter") # Default to Fighter if class not in mapping
    overlay_image_path = os.path.join(IMG_DIR, f"{overlay_image_filename}.png")

    portrait_path = portrait_image_path_template.format(uid=uid)
    
    shield_image_filename = IMAGE_MAPPING.get(offhand_name_ru, "Shield")
    shield_path = os.path.join(IMG_DIR, f"{shield_image_filename}.png")
    print(f"[DEBUG image_generator] Offhand name: {offhand_name_ru}, Shield path: {shield_path}") # Debug print
    
    armor_image_filename = IMAGE_MAPPING.get(armor_name_ru, "Scale_Mail")
    scale_mail_path = os.path.join(IMG_DIR, f"{armor_image_filename}.png")
    
    weapon_image_filename = IMAGE_MAPPING.get(weapon_name_ru, "Morningstar")
    morningstar_path = os.path.join(IMG_DIR, f"{weapon_image_filename}.png")

    # Проверка файлов
    required_files = [
        (input_image_path, "фон"), # "фон" is a descriptive name, not a filename
        (overlay_image_path, overlay_image_filename),
        (scale_mail_path, armor_image_filename),
        (morningstar_path, weapon_image_filename),
    ]
    # Always add shield path, even if it's "ничего" (which maps to Empty_Hand.png)
    required_files.append((shield_path, shield_image_filename))

    for path, name in required_files:
        if not os.path.exists(path):
            print(f"⚠️ Файл {name}.png не найден: {path}. Используется заглушка или пропуск.")
            # Fallback logic for missing images
            if name == overlay_image_filename:
                overlay_image_path = os.path.join(IMG_DIR, "Fighter.png") # Fallback to Fighter
            elif name == shield_image_filename:
                shield_path = os.path.join(IMG_DIR, "Shield.png") # Fallback
            elif name == armor_image_filename:
                scale_mail_path = os.path.join(IMG_DIR, "Scale_Mail.png") # Fallback
            elif name == weapon_image_filename:
                morningstar_path = os.path.join(IMG_DIR, "Morningstar.png") # Fallback
            else:
                raise FileNotFoundError(f"Критический файл {name} не найден: {path}")

    print(f"[DEBUG image_generator] Looking for portrait at: {portrait_path}") # Debug print
    if not os.path.exists(portrait_path):
        print(f"⚠️ Портрет игрока не найден: {portrait_path}. Используется заглушка.")
        # Создать пустой портрет или использовать дефолтный
        portrait = Image.new("RGBA", (100, 100), (0, 0, 0, 0)) # Прозрачная заглушка
    else:
        portrait = Image.open(portrait_path).convert("RGBA")

    # Открываем фон
    background = Image.open(input_image_path).convert("RGBA")

    # === 1. class.png — увеличен на 30% (scale=1.3), центр в (693, 607) ===
    overlay = Image.open(overlay_image_path).convert("RGBA")
    scale = 1.3
    new_ow = int(overlay.width * scale)
    new_oh = int(overlay.height * scale)
    overlay_scaled = overlay.resize((new_ow, new_oh), Image.LANCZOS)

    center_x, center_y = 693, 607
    paste_x = center_x - new_ow // 2
    paste_y = center_y - new_oh // 2
    background.paste(overlay_scaled, (paste_x, paste_y), overlay_scaled)

    # === 2. Портрет в рамку (1453,385)-(2630,2000) ===
    x1, y1 = 1453, 385
    x2, y2 = 2630, 2000
    frame_width = x2 - x1
    frame_height = y2 - y1

    portrait_ratio = portrait.width / portrait.height
    frame_ratio = frame_width / frame_height

    if portrait_ratio > frame_ratio:
        new_width = frame_width
        new_height = int(frame_width / portrait_ratio)
    else:
        new_height = frame_height
        new_width = int(frame_height * portrait_ratio)

    portrait_resized = portrait.resize((new_width, new_height), Image.LANCZOS)
    offset_x = x1 + (frame_width - new_width) // 2
    offset_y = y1 + (frame_height - new_height) // 2
    background.paste(portrait_resized, (offset_x, offset_y), portrait_resized)

    # === 3. Создаём непрозрачную копию фона для иконок и текста ===
    background_rgb = background.convert("RGB")

    # === 4. Иконки — вставляем на background_rgb ===
    EQUIP_SCALE = 0.41

    def paste_equipment_icon(image_bg, icon_path, pos_x, pos_y, scale=EQUIP_SCALE):
        if icon_path is None: # Handle "ничего" case
            return
        if not os.path.exists(icon_path):
            print(f"⚠️ Иконка не найдена: {icon_path}. Пропускается.")
            return
        icon = Image.open(icon_path).convert("RGBA")
        
        if scale != 1.0:
            new_w = int(icon.width * scale)
            new_h = int(icon.height * scale)
            icon = icon.resize((new_w, new_h), Image.LANCZOS)
        
        paste_x = pos_x - icon.width // 2
        paste_y = pos_y - icon.height // 2
        image_bg.paste(icon, (paste_x, paste_y), icon)

    # Вставляем иконки
    paste_equipment_icon(background_rgb, shield_path, 1711, 2442)
    paste_equipment_icon(background_rgb, scale_mail_path, 1533, 2170)
    paste_equipment_icon(background_rgb, morningstar_path, 1533, 2442)

    # Helper function to get weapon damage string
    def get_weapon_damage_string(equipment):
        weapon_name = equipment.get("weapon")
        offhand_name = equipment.get("offhand")
        
        damage_parts = []

        if weapon_name and weapon_name in WEAPONS:
            weapon_data = WEAPONS[weapon_name]
            if weapon_data["hands"] == 2:
                damage_parts.append(weapon_data.get("damage_two", ""))
            else:
                damage_parts.append(weapon_data.get("damage_one", ""))
        
        if offhand_name and offhand_name in WEAPONS and offhand_name != "ничего":
            offhand_data = WEAPONS[offhand_name]
            damage_parts.append(offhand_data.get("damage_one", ""))
        
        # Filter out empty strings and join with '+'
        return "+".join(filter(None, damage_parts)) if damage_parts else "N/A"

    weapon_damage_text = get_weapon_damage_string(equipment)

    # === 5. Текст — тоже на background_rgb ===
    draw = ImageDraw.Draw(background_rgb)
    elements = [
        (str(strength), 271, 1175, white, 72), # сила
        (str(dexterity), 439, 1175, white, 72), # ловкость
        (str(constitution), 607, 1175, white, 72), # выносливость
        (str(intelligence), 775, 1175, white, 72), # интелект
        (str(wisdom), 943, 1175, white, 72), # мудрость
        (str(charism), 1111, 1175, white, 72), # харизма
        (f"Уровень 3 {char_class_ru}", 691, 915, beige, 72), # класс(всегда писать с 3 уровнем)
        (char_race, 691, 380, beige, 60), # расса
        (weapon_damage_text, 1622, 2580, white, 55), # урон оружия (dynamic)
        (str(ac), 2176, 2433, white, 92), # класс брони
        (f"{hp}", 1938, 2433, white, 92), # здоровье (current hp)
        (char_name, 2025, 299, beige, 72), # имя игрока из Vk
    ]

    for text, x, y, color, font_size in elements:
        font = get_font(font_size)
        draw.text((x, y), text, fill=color, font=font, anchor="mm")

    final = background_rgb.copy()

    # Вставляем overlay и portrait на final (как в background)
    final.paste(overlay_scaled, (paste_x, paste_y), overlay_scaled)
    final.paste(portrait_resized, (offset_x, offset_y), portrait_resized)

    output_image_full_path = os.path.join(IMG_DIR, output_filename)
    final.save(output_image_full_path)
    print(f"✅ Изображение сохранено как {output_image_full_path}")
    return output_image_full_path

if __name__ == "__main__":
    # Пример использования для тестирования
    sample_player_data = {
        "uid": 12345,
        "name": "Тестовый Игрок",
        "gender": "Мужской",
        "class": "Монах",
        "race": "Человек",
        "strength": 10,
        "dexterity": 12,
        "constitution": 14,
        "intelligence": 16,
        "wisdom": 13,
        "charism": 15,
        "hp": 25,
        "max_hp": 30,
        "ac": 12,
        "equipment": {
            "weapon": "рапира",
            "offhand": "ничего",
            "armor": "кожаный доспех"
        }
    }
    # Создайте тестовый портрет в img/portraits/12345.jpg для проверки
    # from PIL import Image
    # Image.new('RGB', (600, 800), color = 'red').save(os.path.join(PORTRAITS_DIR, "12345.jpg"))
    generate_character_image(sample_player_data["uid"], sample_player_data, "test_output.png")
