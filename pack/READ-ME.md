# VM

Распакуй архив и открой **УСТАНОВИТЬ.cmd**. Введи ник, нажми **Установить**, затем **Играть**. Игра, Java и моды установятся сами. Для установки нужен интернет. Steam требуется только для Porthole.

Открой **Настройки** и укажи код Porthole хозяина или прямой адрес. Для Porthole добавь хозяина в друзья Steam. Если Porthole ещё нет, лаунчер откроет его установку в Steam.

Если хозяин пришлёт другие данные, открой **Настройки**:

- **Porthole** — текущий код подключения и порт сервера. Нужен вход в Steam; установку Porthole откроет лаунчер.
- **Прямой адрес** — IP или домен и порт сервера.

Код, адрес и порт можно менять в этом окне без переустановки. При смене аккаунта хозяина тоже укажи новые данные. Сохрани их и нажми **Играть**. Сервер должен быть запущен.

VM тихо проверяет GitHub при запуске и установке. Проверку можно отключить в **Настройках**. Для новой версии нажми **Обновить** — архив проверяется по SHA-256. Можно также распаковать новый архив и открыть **УСТАНОВИТЬ.cmd**. Миры, настройки и данные подключения сохранятся. Заменённые файлы останутся в папке `backups`.

## В игре

- T — чат. Меню: `/trigger menu set 1`.
- ЛКМ — огонь, ПКМ — прицел, R — перезарядка.
- J — карта, E — инвентарь.
- Дрон: поставь на землю, возьми планшет или контроллер, нажми ПКМ по дрону.
- W/S — увеличить/уменьшить газ, A/D — поворот, мышь — наклон, Shift — выйти.
- Shift + ПКМ планшетом по свободному дрону на земле — выровнять его после переворота.
- F8 — настройка пульта, осей и режима полёта.

После подключения газ сброшен. У дрона есть инерция; газ с клавиатуры остаётся на выбранном уровне. В режиме «Стабилизация» корпус выравнивается при отпускании управления. В Acro наклон сохраняется, выравнивать нужно самому. Около 50% газа удерживает высоту при горизонтальном корпусе.

Для USB-пульта открой F8, выбери устройство и откалибруй оси. Перед подключением опусти газ. При потере связи с пультом или фокуса окна газ сбрасывается.

Если игра тормозит, уменьши дальность прорисовки или выключи шейдеры в настройках графики.

## English

Extract the archive and open **INSTALL.cmd**. Enter a nickname, click **Install**, then **Play**. The installer sets up Minecraft, Java and the mods. Installation requires internet access. Steam is needed only for Porthole.

Open **Settings** and enter the host’s Porthole code or direct address. Add the host as a Steam friend for Porthole. If Porthole is missing, the launcher opens its Steam installation.

If the host sends different connection details, open **Settings**:

- **Porthole** — the current connection code and server port. Sign in to Steam; the launcher opens the Porthole installation if needed.
- **Direct address** — the server IP or hostname and port.

The code, address and port can be changed here without reinstalling. Update the details if the host changes Steam accounts, too. Save and click **Play**. The server must be running.

VM checks GitHub quietly on startup and installation. You can disable automatic checks in **Settings**. Click **Update** to install a new version; the download is verified with SHA-256. You can also extract a new archive and open **INSTALL.cmd**. Your worlds, settings and connection details are kept. Replaced files are saved in `backups`.

T: chat; `/trigger menu set 1`: menu. Left click: fire, right click: aim, R: reload. J: map, E: inventory.

UAV: place it, hold the tablet or controller, then right-click the UAV. W/S adjusts throttle, A/D turns, the mouse tilts, Shift exits. Throttle resets when you connect. Shift + right-click with the tablet resets an unoccupied UAV on the ground after a flip.

Keyboard throttle stays where you leave it. Stabilized mode levels the UAV when you release the controls; Acro keeps the tilt until you correct it. About 50% throttle holds altitude when level. Press F8 to choose the flight mode or calibrate a USB controller. Lower the throttle before connecting. Loss of controller input or window focus cuts controller throttle.

For higher FPS, lower render distance or disable shaders in Video Settings.

## Авторы / Credits

MC Heli CE — Warfactory / EMB4: https://github.com/Warfactory-Official/McHeliCE
Techguns — pWn3d_1337: https://www.curseforge.com/minecraft/mc-mods/techguns
Forge: https://files.minecraftforge.net/
WorldEdit — EngineHub; WorldEdit CUI — Forge Edition 3.
JourneyMap — TeamJM; JEI — mezz.
BSL — CaptTatsu; OptiFine — sp614x: https://optifine.net/
Java — Eclipse Temurin. License and third-party notices are included.
