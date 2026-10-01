# Разработка

## Проверки на Windows

Нужны Windows PowerShell 5.1 и Python 3.12 или новее. Пакеты Python для проверок лаунчера не нужны.

```powershell
$env:VM_SKIP_UPDATE_CHECK = '1'
powershell -NoProfile -ExecutionPolicy Bypass -File qa/test_updates.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File qa/test_connection.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File qa/test_gui.ps1
python qa/test_connection_launch.py
python qa/test_launcher.py
```

Проверки запуска используют подмены Steam, Porthole и Java. Они не запускают игру и не подключаются к чужому серверу. Проверка протокола работает с локальным тестовым сокетом. Проверки полной установки требуют отдельно распакованного релизного пакета и создают тестовые каталоги внутри `qa`.

## Собрать установщик

Распаковать опубликованный `VM-Setup.zip` в отдельный каталог. Его `payload.zip` и `runtime.zip` — база. Контрольные суммы проверяются по `package-manifest.json` из этого каталога. Манифест в `pack` сохраняет состав последней выпущенной версии.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools/build_icon.ps1
python tools/build_release.py --base C:\Build\VM-Setup --output dist
python qa/validate_package.py dist/VM-Setup.zip
```

Результат — `dist/VM-Setup.zip`, `dist/VM-Host-Tools.zip` и `dist/SHA256SUMS.txt`. Скрипт не включает личные настройки хозяина. Параметры пользователя сохраняются при установке поверх существующей версии.

Для отдельного личного пакета можно передать `--private --defaults C:\Private\server-defaults.json`. По умолчанию результат попадёт в `dist-private`; такой архив не публикуется. Файл defaults не должен попадать в Git. Обновление публичным пакетом сохраняет уже выбранный пользователем сервер.

## Модификации

`patches/java` содержит сохранённые исходники проекта MC Heli CE и Techguns, использованные при разработке, а также классы `WarfareFpv` и `WarfareQuickUav`. `patches/build` содержит инструменты подготовки звуков, патчей и игрового мира. Это материалы модификаций, а не полный checkout upstream-проектов: для полной пересборки модов нужны соответствующие upstream-исходники, Forge-зависимости, компилятор и подготовленные классы. Не следует считать отдельные сохранённые Java-файлы самодостаточным Gradle-проектом.

Сборка клиентского ZIP воспроизводима из опубликованной бинарной базы и файлов этого репозитория. Побайтовая воспроизводимость заново скомпилированных сторонних модов не заявляется.
