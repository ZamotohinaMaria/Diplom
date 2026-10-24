# Самостоятельная сборка benign-набора трасс Windows (CAPEv2), согласованного с WinMET / Avast-CTU

Метки достоверности: [V] = проверено по загруженной странице/PDF в этой сессии; [U] = не удалось проверить (источник недоступен или не содержит); [E] = моя оценка/вывод, не факт из источника. Дата: 2026-10.

## 1. Легальные источники benign-исполняемых файлов Windows

### Takeaway
Наиболее практичный массовый источник - манифесты winget-pkgs (MIT, ~10-13 тыс. пакетов, прямые URL + SHA256 установщиков) плюс Chocolatey (12 027 пакетов, но жёсткие rate limits). NSRL RDS - это только хэши/метаданные, не файлы. Sysinternals - легально использовать, но нельзя публиковать сами бинарники; для диплома публиковать нужно только хэши и трассы.

### Cited Findings
- microsoft/winget-pkgs - "манифесты Windows Package Manager default source", лицензия MIT; поддерживаемые типы установщиков: MSIX, MSI, APPX, MSIXBundle, APPXBundle, .exe; script-based установщики не поддерживаются [V] — [GitHub winget-pkgs](https://github.com/microsoft/winget-pkgs). Сами установщики лежат на сайтах вендоров (в репозитории только YAML), поэтому лицензия MIT относится к манифестам, а не к бинарникам [E].
- Число пакетов winget: официального счётчика на странице репо нет [V]. Разнородные оценки: 9 000 пакетов (май 2025) и 12 850 (май 2026) по Wikipedia, ">10 000" по блогу; это разные источники и не официальные [V как наличие цифр, U как точность] — [Wikipedia: Windows Package Manager](https://en.wikipedia.org/wiki/Windows_Package_Manager). Счёт файлов манифестов (много версий на пакет) значительно больше числа пакетов [E].
- `winget download` скачивает установщик без установки; параметры `--id`, `--version`, `--architecture`, `--installer-type`, `--download-directory`, `--accept-package-agreements`, `--disable-interactivity`; для Microsoft Store (msix/appx) нужна Entra ID аутентификация, если не указать `--skip-license` [V] — [Microsoft Learn: winget download](https://learn.microsoft.com/en-us/windows/package-manager/winget/download). Массовая загрузка = цикл по списку id [E].
- Chocolatey community repository: сейчас 12 027 stable-пакетов [V] — [community.chocolatey.org/packages](https://community.chocolatey.org/packages). Многие пакеты не содержат бинарники, а скачивают их с официальных сайтов при установке [V] — [Chocolatey: Community Packages Disclaimer](https://docs.chocolatey.org/en-us/community-repository/community-packages-disclaimer/). Rate limit: ~5 загрузок/мин на IP для самого Chocolatey, ~20/мин для остальных пакетов; устойчивая нагрузка >~100 установок/час может считаться злоупотреблением и приводить к блокировке без автоснятия; рекомендуют внутренний прокси/кэш [V] (та же страница). Отдельных условий на API/bulk на странице нет [V].
- NSRL RDS: страница описывает данные как хэш-ориентированные (представления FILE, MFG, OS, PKG), формат RDSv3 SQLite; самих файлов в базе нет (вывод из описания "minimal database ... equivalent to old RDS 2.XX text files") [V частично] — [NIST NSRL current RDS](https://www.nist.gov/itl/ssd/software-quality-group/national-software-reference-library-nsrl/nsrl-download/current-rds). Политика редистрибуции - отдельная страница, к ней доступа не получено (URL вернул 404) [U]. Использование: сопоставлять SHA-256/MD5 своих benign с RDS для подтверждения "known software", не как источник бинарников [E].
- Sysinternals: лицензия разрешает установку и использование любого числа копий, но запрещает "publish the software for others to copy"; предупреждает, что файлы, сохраняемые утилитами, могут содержать имена пользователей и пути [V] — [Sysinternals Software License Terms](https://learn.microsoft.com/en-us/sysinternals/license-terms). Т.е. запускать можно, перераспространять бинарники нельзя - публиковать только хэши и трассы [E].
- PortableApps.com: страница legal вернула 403, условия и бульк-ограничения не проверены [U]. NirSoft, Scoop, GitHub Releases: не исследовались в рамках сессии [U].
- Влияние типа на разнообразие: `exe` package в CAPE запускает файл напрямую, `msi` - через msiexec.exe [V] — [CAPE packages](https://capev2.readthedocs.io/en/latest/usage/packages.html). Portable-программы (zip/portable) дают поведение "запущенного приложения"; инсталляторы дают поведение "установки" (запись файлов, реестр, службы) [E]. Для устранения shortcut "benign = installer" нужно запускать установленное приложение, а не установщик, либо в обоих классах иметь и то и то (в malware-корпусах это обычно сам исполняемый файл-дроппер) [E].

### Inferences
- Рекомендуемая смесь [E]: ~60-70% portable/zip-приложений и приложений, установленных заранее и запускаемых из snapshot'а (или установленных в одном шаге, затем запускаемых отдельной задачей), ~10-20% системные бинарники и Sysinternals, остальное - инсталляторы с silent-флагами. Silent-флаги брать из поля `InstallerSwitches` манифеста winget (`Silent`, `SilentWithProgress`) [E, поле существует в схеме winget, но в сессии не проверялось].
- Публиковать: список winget id + версию + SHA-256 + трассы (с анонимизацией); не публиковать бинарники [E].

### Gaps
- Точное число пакетов/манифестов winget-pkgs (нужен `git clone` + подсчёт `manifests/**/*.installer.yaml`).
- Условия PortableApps, NirSoft, Scoop, лицензирование отдельных вендоров для исследовательского использования - не проверены.
- Содержимое Redistribution Policy NSRL.
- Какая доля winget-пакетов - portable/zip (требует парсинга InstallerType).

## 2. Как WinMET/MALVADA и Avast-CTU запускали образцы; как воспроизвести для benign

### Takeaway
WinMET: CAPEv2 с расширенным capemon (больше хуков, сгенерированных CAPE Hook Generator), KVM, 4 VM Windows 10 x64 на хосте Ubuntu 22. MALVADA сама образцы не запускает - только обрабатывает JSON-отчёты CAPE; benign-режима в репо нет, но входной формат - любой CAPE-отчёт, поэтому benign-отчёты, снятые тем же CAPE+capemon, можно пропустить через неё. Avast-CTU: Windows 7 с MS Office, июль-август 2021.

### Cited Findings
- MALVADA: "enhanced version of CAPE Sandbox", увеличено число перехватываемых API (сеть, файлы/реестр, память); CAPE Hook Generator публично доступен; KVM; четыре VM на хосте Ubuntu 22, каждая Windows 10 x64; проанализировано >20 000 образцов, неудачные (ошибки, падения, проблемы связности) отброшены [V] — [SoftwareX preprint, PDF](https://webdiis.unizar.es/~ricardo/files/papers/RaducuVRA-SoftwareX-25.pdf).
- В статье нет упоминаний таймаута, симуляции пользователя, anti-evasion настроек в извлечённом тексте [V как отсутствие] — тот же PDF. Это критично: параметры нужно извлечь из `capemon`/конфигов в репо [U].
- Структура трассы: `behavior.processes[].calls[]` с полями `category`, `api`, `return`, `arguments[{name,value}]`; `processtree`; `summary` (files, keys, mutexes, executed_commands и т.д.); `target.file` хэши, `virustotal` и т.д. [V] — тот же PDF.
- Репозиторий MALVADA: https://github.com/reverseame/MALVADA существует [V] — [GitHub MALVADA](https://github.com/reverseame/malvada). Этапы: детект некорректных отчётов, дедупликация по SHA512, санитизация/анонимизация по `terms_to_anonymize.txt`, AVClass по VirusTotal, статистика; запуск `python3 malvada.py directory`; предупреждение, что инструмент изменяет отчёты в директории; README: "can be extended to other sandboxing engines" [V]. Структура репо: `src`, `doc`, `test_reports` (200 отчётов), `capemon` (скомпилированная версия), `cape-hook-generator`, `WinMET` [V] — PDF выше.
- Фильтр по VirusTotal (`-vt`, по умолчанию 10 positives "considered malicious") и AVClass относятся к malware-метке; для benign нужно отключить/заменить этот этап [V про параметр; E про необходимость адаптации] — [GitHub MALVADA](https://github.com/reverseame/malvada).
- CAPE Hook Generator: https://github.com/reverseame/cape-hook-generator существует, GPL-3.0; генерирует скелеты hookdefs для capemon (`extended_hooks.c/.h`, `extended_hook_misc.c`), требует ручной доработки; опционально использует Google CSE [V] — [GitHub cape-hook-generator](https://github.com/reverseame/cape-hook-generator).
- WinMET v3 на Zenodo: 31 844 JSON-трасс, ~13 GB сжато / ~750 GB распаковано, 5 архивов 7z (пароль "infected"), лицензия GPL-3.0+; указаны mapping-файлы меток; ОС и таймаут на странице не указаны [V] — [Zenodo 16414116](https://zenodo.org/records/16414116). Условие "Windows 10 x64" берётся из SoftwareX, не из Zenodo [V].
- Средний размер ~750 GB / 31 844 ≈ 23.6 MB на трассу [E, арифметика по [V] цифрам].
- Avast-CTU: Windows 7 с MS Office; запуск июль-август 2021 на CAPEv2 того времени; три физические машины по четыре гостевых VM, настроены как "обычный ПК" (браузеры, приложения, ключ, сохранённый пароль Chrome, документы, картинки, доступ в интернет); все образцы malware; 48 976 образцов; некоторые полные отчёты >800 MB; таймаут и human-interaction не указаны [V] — [ar5iv 2209.03188](https://ar5iv.labs.arxiv.org/html/2209.03188). GitHub: 48 976 файлов, полные отчёты 13 GB, сокращённые 566 MB; файл Licences.txt, содержимое не проверено [V/U] — [avast/avast-ctu-cape-dataset](https://github.com/avast/avast-ctu-cape-dataset). Сам arXiv: образцы в основном 2017-2019 [V] — [arXiv 2209.03188](https://arxiv.org/abs/2209.03188v1).

### Inferences
- Воспроизвести "то же окружение" полностью для обоих корпусов невозможно: они различаются по ОС (Win7 vs Win10) и по набору хуков. Поэтому benign нужно делать отдельно под каждый корпус (Win10 + расширенный capemon для WinMET; Win7 для Avast-CTU) либо ограничиться WinMET [E]. Для диплома разумнее сфокусироваться на WinMET (Win10 x64), что и совпадает с современной системой.
- Берите готовый скомпилированный `capemon` из папки `capemon` репо MALVADA, чтобы набор хуков был идентичным [E; соответствие версии CAPE Python-анализатору не проверено].

### Gaps
- Таймаут, human/nohuman и anti-evasion конфигурация WinMET: не найдены. Нужно написать авторам (reverseame@unizar.es, указан в статье) или изучить папку `WinMET` репо.
- Версия CAPE и Python/анализатора, под которую собран их capemon.
- Условия лицензии Avast-CTU (Licences.txt).
- Data in Brief статья про WinMET (PMC) не найдена поисковиком в этой сессии.

## 3. Практическая настройка CAPEv2

### Takeaway
Хост - Linux (Ubuntu) с KVM, установка скриптами `kvm-qemu.sh` и `cape2.sh`; гость - Windows с агентом, snapshot; модуль `human` имитирует мышь/клики и автоматически жмёт кнопки Next/Install/Accept, что помогает инсталляторам, но создаёт и свой шум.

### Cited Findings
- Любой гипервизор можно использовать, но KVM рекомендован; `kvm-qemu.sh` вместо apt (скрытнее, лучше производительность); установка `sudo ./cape2.sh base cape`/`all cape`; сервисы cape, cape-processor, cape-web, cape-rooter; CAPE - rolling release без версий [V] — [CAPE host installation](https://capev2.readthedocs.io/en/latest/installation/host/installation.html). Не обновлять через apt пакеты, установленные скриптами [V].
- Руководство по гостю: отдельные инструкции для Windows до 10 и 10+, установка агента, сохранение snapshot (KVM/virt-manager, VirtualBox, VMware, Xen, Azure), debloat, отключение Defender/Store, шумных сетевых служб [V по оглавлению] — [CAPE guest installation](https://capev2.readthedocs.io/en/latest/installation/guest/index.html).
- Пакеты анализа: `exe` (опции appdata, arguments, runasx86), `dll`, `msi` через msiexec.exe; `free` отключает мониторинг [V] — [CAPE packages](https://capev2.readthedocs.io/en/latest/usage/packages.html).
- Submit: `--timeout`, `--enforce-timeout` (принудительный полный срок), `--clock` (дата-время гостя), `--options`; опция `interactive` (интерактивный рабочий стол) указана в разделе Monitor & Evasion; значение таймаута по умолчанию для CLI на странице не указано [V] — [CAPE submit](https://capev2.readthedocs.io/en/latest/usage/submit.html).
- Модуль `human.py` (исходный код): включается через `config.human_windows`; отключается опцией `nohuman`; реалистичные движения мыши по кривым Безье, случайные клики, раз в 15+rand(0-10) c смена окна на передний план; нажимает кнопки из `CLICK_BUTTONS` (install, next, accept, save, finish, allow и др.) и игнорирует `DONT_CLICK_BUTTONS` (cancel, don't run, restart now); для документов Office/PDF начиная с 45 с и далее каждые 30 с; заполняет буфер обмена случайным текстом 10-1000 символов; документированный баг с `RESOLUTION["X"]` в ветке документов (KeyError глушится) [V] — [human.py (raw)](https://raw.githubusercontent.com/kevoreilly/CAPEv2/master/analyzer/windows/modules/auxiliary/human.py).
- Требования лицензии Windows 10: страница Evaluation Center перенаправлена на блог Microsoft об окончании поддержки Windows 10 [V]; доступность eval ISO и срок лицензии не подтверждены [U]. Windows 10 вышла из основной поддержки в октябре 2025 [U - не проверено в сессии, из общих знаний].
- Hardware/throughput/parallelism: в источниках только факты "четыре VM на хосте" (WinMET) и "три хоста по четыре VM" (Avast-CTU) [V].

### Inferences
- Для GUI-баланса: запускать benign и malware с одинаковыми `human`-настройками (включено у обоих); не делать `nohuman` для benign и не делать его для malware [E].
- Оценки [E, не из источников]: одна машина с 16-32 GB RAM, 4 VM по 2 vCPU / 4 GB; на образец ~ timeout (например 120-300 с) + ~30-60 с revert snapshot + обработка; ~4 VM * 8-12 образцов/ч ≈ 30-50 образцов/ч, т.е. 5 000 образцов ≈ 100-170 ч (4-7 суток непрерывной работы). Хранилище: WinMET ~24 MB/трасса -> ~120 GB несжатых на 5 000 [E; арифметика с [V] чисел]; сжатие 7z ~57x (13 GB / 750 GB) -> ~2 GB [E]; но benign GUI-приложения могут давать больше или меньше вызовов, чем malware.
- Docker/Windows host не поддерживаются как основной сценарий CAPE; dual-boot Ubuntu корректен [E; не проверялось в сессии]. GPU не нужен для сэндбокса; нужна VT-x/AMD-V [E].

### Gaps
- Минимальные требования к железу, пропускная способность и Ubuntu-версия (на странице установки не указаны).
- Точные значения по умолчанию для timeout/human в актуальном `conf/` (нужно смотреть `conf/default/auxiliary.conf.default`, `cuckoo.conf.default` в репо).
- Лицензия/eval-ISO Windows 10 и Windows 7 для гостя.
- Альтернативы (Cuckoo3, DRAKVUF Sandbox, Qiling/Speakeasy, Sysmon/ETW): в сессии не исследованы; в рамках таймбокса данные не собраны. Вывод [E]: для "того же формата отчётов, что у WinMET" нужен именно CAPEv2 + тот же capemon; эмуляторы (Qiling/Speakeasy) не дадут сопоставимых ordered API с аргументами и таймстемпами в формате CAPE; ETW/Sysmon - другой уровень (события ОС, а не API user-mode).

## 4. Контроль shortcut learning

### Takeaway
Arp et al. (2022) формально определяют P1 sampling bias и P4 spurious correlations и прямо рекомендуют не смешивать данные из несовместимых источников; benign и malware надо собирать на одной и той же инфраструктуре и проверять классификатором источника.

### Cited Findings
- P1: "The collected data does not sufficiently represent the true data distribution"; рекомендация: "mixing of data from incompatible sources should be avoided, as it is a common cause of additional bias" [V] — [Arp et al., arXiv 2010.09470](https://arxiv.org/pdf/2010.09470).
- P4: "Artifacts unrelated to the security problem create shortcut patterns"; рекомендуется использовать explanation techniques и заранее задать цель; в Android-эксперименте классификатор определил URL play.google.com как один из пяти наиболее дискриминативных признаков benign-класса, т.е. выучил источник приложений, а не вредоносность [V] — тот же PDF.
- Контрольный эксперимент в статье: обучение на данных из одного рынка (GooglePlay, Anzhi, AppChina) по отдельности дало F1 0.807-0.879 против 0.885 при случайной смеси - признак sampling bias [V] — тот же PDF.
- Survivorship bias: если оставлять только образцы, успешно обработанные динамическим анализом, это тоже вносит смещение [V] — тот же PDF (Appendix).
- Распространённость: P1 присутствует (хотя бы частично) в 90% рассмотренных работ, P3 - в 73% [V] — тот же PDF.
- MALVADA уже содержит механизм анонимизации по списку терминов (`terms_to_anonymize.txt`) и фильтр "incorrect reports" [V] — [GitHub MALVADA](https://github.com/reverseame/malvada).

### Inferences
Контрольный список [E]:
1. Один и тот же образ VM/snapshot, версия CAPE, capemon, `human`, timeout, `enforce_timeout`, `clock` (одна и та же дата гостя для malware и benign), сеть и маршрутизация (одинаковый доступ в интернет). Если malware отработан в 2021 на Win7 - это разные домены; matching возможен только по свежему Win10-корпусу (WinMET).
2. Длина: сравнить распределение числа вызовов и длительности; либо усечь трассы до N вызовов / T секунд у обоих классов; выровнять долю "пустых" и "упавших" запусков (применять к обоим один и тот же фильтр MALVADA).
3. GUI: ввести признак "создал окно" и сбалансировать по нему (стратификация) либо включить в тест.
4. Артефакты: нормализовать пути (имя пользователя, `C:\Users\<name>`, имя компьютера, имя файла образца, путь запуска, случайные tmp-имена), хэши, даты, хост-специфичные значения; применить одну и ту же функцию к обоим классам (расширить `terms_to_anonymize.txt`).
5. Тест источника: обучить простой классификатор (n-gram по API, TF-IDF по аргументам) на задаче "WinMET-malware vs мой-benign"; затем обучить его же на подвыборке "malware, снятый мной vs malware из WinMET" (если снять ~200 повторных запусков известных malware на своей инфраструктуре) - если эти различимы, то отличия связаны с инфраструктурой, а не с классом. Метод [E], не взят из статьи.
6. Объяснимость (SHAP/Integrated Gradients) для проверки, что топ-признаки - не пути и не инфраструктурные вызовы (рекомендация P4 [V]).
7. Временное разделение (P3): benign по дате выпуска версий и malware по дате первого появления [E].

### Gaps
- Другие работы (помимо Arp et al.), цитируемые в списке "и др." - Rossow et al. и Botacin et al. упомянуты в тексте PDF только как отсылки; сами статьи не читались [V как упоминание в Arp / MALVADA].
- Нет эмпирических данных о том, насколько sandbox-инфраструктура сама по себе отделяет benign от malware в CAPE-отчётах.

## 5. Минимальный план (время/стоимость)

### Takeaway
Реалистичный минимум - один ПК с Ubuntu, 1 хост CAPE и 3-4 VM Windows 10 x64, ~3 000-5 000 benign (portable + preinstalled + installers), 1-2 недели календарного времени. Деньги в основном нулевые (открытое ПО, бесплатные источники) при условии доступности лицензионного/ eval-образа Windows.

### Cited Findings
- Окружение-прототип WinMET: KVM, Ubuntu 22 host, 4 VM Win10 x64, расширенный capemon [V] — [SoftwareX preprint](https://webdiis.unizar.es/~ricardo/files/papers/RaducuVRA-SoftwareX-25.pdf).
- CAPE устанавливается скриптами `kvm-qemu.sh` и `cape2.sh` [V] — [CAPE host installation](https://capev2.readthedocs.io/en/latest/installation/host/installation.html).
- Загрузка: `winget download --id ... --architecture x64 --download-directory ...` [V] — [winget download](https://learn.microsoft.com/en-us/windows/package-manager/winget/download); Chocolatey limits ~5-20 загрузок/мин [V] — [Chocolatey disclaimer](https://docs.chocolatey.org/en-us/community-repository/community-packages-disclaimer/).

### Inferences
План и оценки [все E, не проверены]:
| Шаг | Что делать | Время |
|---|---|---|
| 1 | Dual-boot Ubuntu 22.04, установка KVM+CAPE по документации; GPU не нужен | 1-2 дня |
| 2 | Подготовка Win10 x64 гостя (агент, Python, debloat, отключить Defender, snapshot), взять capemon из репо MALVADA; задать `clock`, `human`, timeout, как у WinMET (после запроса авторам) | 1-3 дня |
| 3 | Скрипт: парсинг winget-pkgs (git clone), фильтр по InstallerType (zip/portable/exe/msi), `winget download` с задержкой; dedupe по SHA-256; сверка с NSRL RDS по хэшу | 2-3 дня |
| 4 | Pilot 100 образцов: проверить долю успешных запусков, длину трасс, GUI-признак, размер | 1 день |
| 5 | Основной прогон 5 000 (до 7 суток при ~30-50/ч) + повтор неудач | 4-8 суток |
| 6 | MALVADA (адаптировать VT-фильтр под benign), анонимизация, source-классификатор | 2-4 дня |
Стоимость: ПО бесплатно; электричество/диск ~0.5-1 TB SSD (~100-250 USD, если нужен новый); лицензия Windows - eval или уже имеющаяся (проверить условия).

### Gaps
- Конкретные цифры пропускной способности, доля успешных запусков, размер benign-трасс - только после пилота.
- Юридическая консультация: условия лицензий вендоров на анализ исполняемых файлов в песочнице, публикация трасс (хэш + трассы, без бинарников) - вне охвата; стоит согласовать с научным руководителем/университетом.
