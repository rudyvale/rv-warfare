# Добавление техники / Adding vehicles

## Русский

RV Warfare использует MC Heli CE для части техники. В моде CE пользовательские наборы загружаются из папки `mcheli_addons`; формат и содержимое зависят от автора дополнения. В текущем репозитории есть собственные дополнения RV для FPV и самолётов, но нет подтверждённого набора с БТР. Поэтому конкретную модель, вооружение и характеристики БТР нужно проверять по самому дополнению и его автору.

### Установка набора MC Heli CE

1. Найди набор, явно совместимый с MC Heli CE для Minecraft 1.12.2. Скачивай его со страницы автора или официального проекта.
2. Прочитай лицензию. Не публикуй модель или текстуры в RV и не пересылай их другим игрокам, если автор не разрешил такое распространение.
3. Распакуй архив набора. Внутри должна быть структура ресурсов вида `assets/mcheli/...` (например, `assets/mcheli/tanks/...`). Не клади архив ZIP внутрь папки `mcheli_addons`.
4. В каталоге игры создай `mcheli_addons/<имя-набора>/` и помести туда папку `assets`. Итоговый путь к файлу техники должен начинаться с `mcheli_addons/<имя-набора>/assets/mcheli/`.
5. Для сетевой игры установи тот же набор и ту же версию на выделенный сервер и на компьютер каждого игрока, затем перезапусти игру и сервер. Сначала проверь набор в отдельном мире, прежде чем подключать его к сохранённому миру.

Официальное описание [MC Heli CE](https://www.curseforge.com/minecraft/mc-mods/mchce) документирует папку `mcheli_addons/<имя>/assets/mcheli/` для наборов техники. Отдельный набор не становится частью меню RV автоматически: способ получения техники (рецепт, творческий инвентарь или команда) определяет автор набора и настройки сервера. Не выдавай игрокам неизвестный ID предмета — сначала проверь его на установленной версии.

Если хочешь включить новую машину в стандартную сборку RV, потребуются совместимые файлы для сервера и клиентов, разрешение на распространение, подтверждённая загрузка модели и проверка посадки, управления, оружия и сохранения мира. До такой проверки машина не должна рекламироваться как часть стандартного набора.

## English

RV Warfare uses MC Heli CE for some vehicles. CE loads user content packs from `mcheli_addons`; supported files and behavior depend on the pack author. This repository contains RV add-ons for FPV aircraft, but it does not contain a verified BTR pack. Check a specific vehicle and its claimed features in the add-on itself and with its author.

### Install an MC Heli CE content pack

1. Find a pack explicitly compatible with MC Heli CE for Minecraft 1.12.2. Download it from the author or project's official page.
2. Read its license. Do not publish or redistribute its models or textures through RV unless the author allows it.
3. Extract the pack. It should contain a resource tree such as `assets/mcheli/...` (for example, `assets/mcheli/tanks/...`). Do not put the zipped archive inside `mcheli_addons`.
4. In the game directory, create `mcheli_addons/<pack-name>/` and place the `assets` folder there. Vehicle files should end up under `mcheli_addons/<pack-name>/assets/mcheli/`.
5. For multiplayer, install the same pack version on the dedicated server and every player's game, then restart the game and server. Test in a separate world before using it in an existing save.

The official [MC Heli CE description](https://www.curseforge.com/minecraft/mc-mods/mchce) documents the `mcheli_addons/<name>/assets/mcheli/` folder for content packs. An add-on does not automatically appear in RV's menus: the pack author and server configuration define how to obtain a vehicle (recipe, creative inventory or command). Do not give players an unverified item ID; confirm it with the installed version first.

Adding a vehicle to RV's standard build requires compatible server and client files, redistribution permission, confirmed loading, and checks for boarding, controls, weapons and world saving. Until those checks pass, do not advertise it as part of the standard pack.
