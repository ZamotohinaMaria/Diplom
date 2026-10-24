# Публичные наборы benign-поведения Windows-программ (для пары к Avast-CTU CAPEv2 / WinMET)

Условные пометки: [VERIFIED] — проверено по странице хостинга/тексту статьи, открытому в этой сессии; [UNVERIFIED] — только из сниппета поиска или не удалось открыть. Дата исследования: 2026-10. Файлы не скачивались и не запускались (PDF-страницы статей сохранялись WebFetch'ем и читались только как текст).

## 1. Новые наборы с benign-поведением (динамика, sandbox-отчёты, телеметрия)

### Takeaway
Идеального «готового» benign-набора, сопоставимого по формату с CAPE-отчётами Avast-CTU (Windows 7, 2021) или WinMET (Windows 10), не найдено. Единственный найденный публичный набор с настоящими CAPEv2-JSON на Windows 10 — Thcrull (762 benign, уже известен). Из новых: MLRan (Cuckoo, Windows 7, ~2 550 goodware — но проверить наличие сырых отчётов не удалось), OpTC и LANL (хостовая телеметрия, а не трассы отдельных программ), ATLASv2 (нет ссылки на данные). Остальные «benign»-наборы — статические (IAT, хэши, признаки).

### Cited Findings

**A. Dynamic sandbox/API-трассы**

- MLRan (2025): >4 800 образцов, 64 семейства ransomware + «сбалансированный» набор goodware; код и метаданные на GitHub (лицензия MIT), полный датасет «на Zenodo» (по README); ссылка на конкретную Zenodo-запись и число/размер goodware в README не указаны — [GitHub faithfulco/mlran](https://github.com/faithfulco/mlran) [VERIFIED README, Zenodo-запись НЕ проверена]; в статье: goodware скачаны скриптом с Software Informer (5 010 → 3 837 уникальных → 2 696 с 0 детектов на VirusTotal → 2 550 успешно обработаны Cuckoo), 11 категорий; Cuckoo 2.0.7 на Windows 7 VM (VMCloak, Internet Explorer 11, vcredist), таймаут 120 с, 4 CPU/4 GB RAM, антиVM-маскировка — [arXiv 2505.18613](https://arxiv.org/pdf/2505.18613) [VERIFIED по тексту PDF]. Фичи: бинарное наличие API-вызовов, по описанию в статье — признаки из Cuckoo (6,4 млн сырых → 483 отобранных) [VERIFIED], порядок вызовов, скорее всего, не сохранён [UNVERIFIED].
- Ilić et al., Electronics 13(17):3553 (2024): 22 200 образцов (11 735 benign, 10 465 malware), полный отчёт Cuckoo на каждый; диссертация Ilić: 969 GB, >25 млн динамических признаков — [MDPI](https://www.mdpi.com/2079-9292/13/17/3553) (страница отдала 403), [dissertation PDF](https://kpu.edu.rs/cms/data/studenti/ujavnosti/disertacija_ilic_slavisa.pdf). Заявление о доступности данных найти не удалось [UNVERIFIED, доступность неизвестна — по-прежнему].
- Oliveira, «Malware Analysis Datasets: API Call Sequences» (IEEE DataPort, DOI 10.21227/tqqm-aq14): 1 079 goodware + 42 797 malware последовательностей; архив 2,02 MB; создан 24.10.2019, обновлён 12.12.2019; лицензия не указана, доступ — только для залогиненных; ОС песочницы на странице не указана — [IEEE DataPort](https://ieee-dataport.org/open-access/malware-analysis-datasets-api-call-sequences) [VERIFIED]. Сообщается, что формат — первые 100 непрерывных неповторяющихся вызовов родительского процесса, goodware с portableapps.com и каталогов Windows 7 x86 — [поиск/сниппет](https://ieee-dataport.org/node/1777) [частично UNVERIFIED].
- APIMDS (IEEE DataPort): API-последовательности (Microsoft Detours, Windows XP SP3 VM, 26 категорий API), 23 080 malware; число benign на странице не указано; zip 18,04 MB; лицензия не указана — [IEEE DataPort](https://ieee-dataport.org/documents/apimds-api-call-sequence-based-malware-detection-dataset) [VERIFIED]. Для Win7/Win10 не подходит (XP, benign-доля неизвестна).
- Упоминаемые в обзоре MLRan: EldeRAN (2016; 582 ransomware + 942 goodware, Cuckoo на Windows XP 32-bit) и ISOT ransomware dataset (666 ransomware + 103 goodware, Cuckoo, Windows 7) — [arXiv 2505.18613](https://arxiv.org/pdf/2505.18613) [VERIFIED только как цитата из обзора; сами наборы не открывались]. Слишком малы/устарели.
- Thcrull/win-exe-malware-analysis (HF; уже известен, уточнения): 1 844 образца всего (762 benign: PortableApps 328, PortableApps installers 100, Sysinternals Suite 149, Benign-NET NetWindows 185; 1 082 malware из MalwareBazaar), 57,4 GB, лицензия MIT, Windows 10 Pro detonation VM в CAPEv2, версия CAPE и способ запуска не указаны; сырые JSON-отчёты + «reduced» (process tree, домены, DNS, сигнатуры, MITRE, MBC) — [HF card](https://huggingface.co/datasets/Thcrull/win-exe-malware-analysis) [VERIFIED]. Замечание: подитоги источников (328+149+185=662) не сходятся с 762, а 100 installers — отдельная строка; на странице видна непоследовательность. Наличие API-вызовов в сырых отчётах на странице не заявлено [UNVERIFIED]. Сырые CAPE-отчёты обычно содержат `behavior.processes[].calls`, но для этого набора это нужно проверить по файлам.

**B. Хостовая телеметрия / провенанс (не «трассы программ», а фон нормальной активности)**

- DARPA OpTC (IEEE DataPort, DOI 10.21227/edq8-nk52): OpTC.tar.gz 287,59 GB + OpTC-data-release.md 18,88 KB; eCAR-JSON по клиентам; 500–1 000 Windows-хостов; 3 дня атак (23–25.09.2019); набор «23Sep19-night» без угроз — бейзлайн; требуется логин IEEE (бесплатный аккаунт, на странице есть противоречивая фраза про подписку); лицензия не указана, «public domain / Distribution A»; создан 30.03.2021, обновлён 08.08.2022 — [IEEE DataPort](https://ieee-dataport.org/node/3910) [VERIFIED]. Benign-часть: 16–22.09 (по сниппету поиска), активность генерируется скриптами; критика документированности — [поиск: IEEE DataPort OpTC / CSET'25 слайды](https://cset25.isi.edu/slides/cset2025-slides-optc.pdf) [UNVERIFIED, не открывалось]. Формат: события (process/file/flow/registry/…), не поток API-вызовов.
- LANL Unified Host and Network Dataset: ~90 дней, по файлу в сутки; host-логи Windows (wls_day-XX.bz2, JSON, события 4624, 4688 и др.) + netflow; лицензия CC0 1.0; перед скачиванием форма с email и целью; размер и разметка red-team на странице не указаны — [csr.lanl.gov/data/2017](https://csr.lanl.gov/data/2017/) [VERIFIED]. Только process-start и logon события корпоративной сети, глубины API нет.
- ATLASv2 (Riddle, Westfall, Bates, 2023, arXiv 2401.01341): Windows-VM, Security Auditing + Sysmon + VMware Carbon Black Cloud + Firefox + DNS, 4 дня реальной работы двух исследователей на виртуалках («benign») + 1 день с 10 атаками. Ссылка на репозиторий данных, размер, версия Windows на странице arXiv не указаны — [arXiv abs](https://arxiv.org/abs/2401.01341) [VERIFIED, но доступность данных НЕ подтверждена].
- Altinisik et al. (QCRI), arXiv 2206.05679: ETW+Sysmon, 46 серверов, 10 недель, 18 админов и 1 580 пользователей; ссылка на публикацию данных не найдена — [arXiv](https://arxiv.org/pdf/2206.05679) [датасет, вероятно, непубличный — UNVERIFIED].
- IEEE DataPort «System logs … RPC … ETW» — ETW-логи симуляций атак, benign-фона не заявлено — [IEEE DataPort](https://ieee-dataport.org/documents/system-logs-remote-procedure-call-rpc-information-collected-event-tracing-windows-etw) [UNVERIFIED, по сниппету].

**C. Статические наборы (benign-файлы/признаки; динамики нет)**

- WinAPI-AdvMal (Zenodo 20208958, v2.0.0, 18.05.2026, CC BY 4.0): единственный CSV 21,0 MB (md5 b17d331abedf743cf852884e0914efd0); 3 799 образцов = 3 121 benign (office 667, dev tools 746, multimedia 623, security tools 519, admin tools 566) + 678 malware (MalwareBazaar); бинарные признаки IAT (2 713 функций), имена PE анонимизированы. Динамики нет, сырых бинарников нет — [Zenodo](https://zenodo.org/records/20208958) [VERIFIED]. Полезно только как пример категоризации benign по типам ПО.
- SOREL-20M: ~10 M benign + ~10 M malware PE, метаданные и EMBER-v2 признаки; обезвреженные бинарники — только для malware; доступ через AWS S3 `sorel-20m` — [AWS registry](https://registry.opendata.aws/sorel-20m), [arXiv 2012.07634](https://arxiv.org/pdf/2012.07634) [частично VERIFIED по сниппетам]. Benign — только признаки/хэши, перезапустить нельзя.
- BODMAS: ~134K образцов (57 293 malware / 77 142 benign), 29.08.2019–30.09.2020, 581 семейство (по сниппету); доступность raw benign-файлов не подтверждена — [arXiv 2603.26632 / поиск](https://arxiv.org/pdf/2603.26632) [UNVERIFIED]. По памяти (не проверено в сессии): BODMAS распространяет benign как только хэши/признаки, бинарники — по запросу.
- EMBER / EMBER2024 benign: из результатов подтверждены только признаки (2 381-мерные векторы у оригинала) — [SOREL/EMBER обзор](https://arxiv.org/pdf/2012.07634); детали EMBER2024 не проверены [UNVERIFIED].
- NSRL RDS: только хэши и метаданные (RDSv3, SQLite; «minimal database» только FILE-хэши); NIST подчёркивает, что RDS показывает «известный», а не «безопасный» файл — [NIST NSRL](https://www.nist.gov/itl/csd/secure-systems-and-applications/national-software-reference-library-nsrl/about-nsrl/nsrl-0), [forensics.wiki](https://forensics.wiki/national_software_reference_library/) [VERIFIED по сниппетам]. Файлов нет — годится лишь как whitelist для фильтрации/проверки «известности» собранного benign-корпуса.
- Не проверено (в сессии не искалось/не открывалось): Chocolatey/winget/PortableApps как источники файлов — лишь косвенно: PortableApps использован в Thcrull и Oliveira (см. выше), Software Informer — в MLRan. Юридические условия редистрибуции этих программ не изучались [UNVERIFIED].

### Inferences
- Для CAPEv2-формата, максимально близкого к Avast-CTU, реалистичные варианты: (1) Thcrull (CAPE, Win10 — совпадает по ОС с WinMET, но не с Win7 Avast-CTU; мало образцов и PortableApps/Sysinternals/.NET смещены к не-GUI/утилитам), (2) собственный прогон benign-файлов в том же CAPEv2 (самый чистый вариант по OS/версии/таймауту), для чего источники файлов — PortableApps, Software Informer (как MLRan) с фильтрацией через VirusTotal 0 детектов и NSRL-проверкой.
- MLRan — наиболее близкий по методике (Cuckoo, Win7, 120 с) публичный источник «широкого» goodware, но формат и наличие порядка API-вызовов нужно проверить на Zenodo.
- OpTC/LANL/ATLASv2 решают другую задачу (аномалии хоста), не парные «benign-трассы программ»; для Avast-CTU/WinMET непосредственно не годятся.

### Gaps
- Zenodo-запись MLRan (DOI/размер/содержимое: сырые отчёты или только признаки) не найдена в сессии.
- Доступность данных Ilić et al. (11 735 benign) — заявление о доступности не удалось прочитать (MDPI 403).
- Наличие `calls` в сырых отчётах Thcrull — не проверено по файлам (на карточке только суммарный размер 57,4 GB).
- ATLASv2: репозиторий данных не найден; OpTC: фактический объём benign-части по хостам не подтверждён; точные условия лицензий DataPort не указаны.
- Не искались и не проверялись: Mendeley Data, OSF, Figshare и Kaggle напрямую (поиск общего вида не выдал benign-наборов; Kaggle-набор Greimas уже известен); StreamSpot/Unicorn/ProvDetector (в основном Linux — по сниппету, не подтверждено).

## 2. Крупные коллекции benign-исполняемых для повторного запуска

### Takeaway
Реально перезапускаемых публичных benign-бинарников с хэшами в проверенных источниках почти нет: SOREL, EMBER, NSRL, BODMAS (по найденному) дают хэши/признаки, а файлы приходится собирать самостоятельно (PortableApps, Software Informer, Sysinternals и т.п.) с перепроверкой «benign».

### Cited Findings
- SOREL-20M: обезвреженные бинарники только для malware — [AWS registry](https://registry.opendata.aws/sorel-20m) [VERIFIED по сниппету].
- NSRL: хэши, не файлы — [NIST](https://www.nist.gov/itl/csd/secure-systems-and-applications/national-software-reference-library-nsrl/about-nsrl/nsrl-0) [VERIFIED по сниппету].
- В MLRan цитируется Botacin et al. (2021): типичная ошибка — считать краулнутые приложения априори benign без валидации; MLRan сократил 3 837 → 2 696 по VirusTotal — [arXiv 2505.18613](https://arxiv.org/pdf/2505.18613) [VERIFIED].
- WinAPI-AdvMal собрал benign установкой стандартных Windows-приложений и извлечением .exe/.dll — [Zenodo](https://zenodo.org/records/20208958) [по сниппету поиска; на странице записи прямо не подтверждено].

### Inferences
- Сопоставимость по версии CAPE и Windows достижима только при собственном исполнении; публичные хэш-списки используются для проверки, а не как источник поведения.

### Gaps
- Лицензии и условия редистрибуции отчётов, полученных из чужого ПО (PortableApps, Software Informer, Sysinternals), не проверялись.
- Не проверены: G DATA/Microsoft whitelists, Chocolatey/winget, EMBER2024, BODMAS README.

## 3. Литература: как формировать benign и какие возникают смещения

### Takeaway
Arp et al. (USENIX Sec 2022) прямо относят к главным ловушкам sampling bias (P1), spurious correlations (P4) и временное смещение; для пары Avast-CTU (Win7, июль–август 2021, MS Office и популярные приложения в VM, Интернет разрешён) + benign из другого источника/ОС/года главный риск — классификатор научится различать происхождение/окружение, а не вредоносность.

### Cited Findings
- Arp et al. «Dos and Don'ts of ML in Computer Security», USENIX Security 2022: 10 pitfalls (P1 Sampling Bias, P3 Data Snooping, P4 Spurious Correlations, …), анализ 30 статей; пример на AndroZoo: benign-приложения в основном из Google Play, malware — из китайских магазинов, `play.google.com` оказался одним из топ-5 дискриминативных признаков benign-класса, т.е. модель различает источник, а не вредоносность; рекомендация учитывать распределение данных и временные зависимости — [USENIX PDF (прочитан локально)](https://www.usenix.org/system/files/sec22-arp.pdf), [страница](https://usenix.org/conference/usenixsecurity22/presentation/arp) [VERIFIED].
- Пространственно-временное смещение и ограничения TESSERACT (Pendlebury et al., USENIX Sec 2019): обучающие данные должны предшествовать тестовым, реалистичная доля malware в тесте — [слайды Arp](https://www.usenix.net/system/files/sec22_slides-arp.pdf); последующая работа подтверждает, что эти ограничения приняты сообществом — [arXiv 2506.23814](https://arxiv.org/html/2506.23814v1) [VERIFIED по сниппетам; полный текст TESSERACT не открывался].
- Avast-CTU CAPE: выполнение в CTU Prague в июле–августе 2021 на CAPEv2, 3 физические машины × 4 гостевых VM, Windows 7 + MS Office, установлены Chrome, Firefox, Adobe Reader, Spotify, сохранён пароль в Chrome, приватный ключ, документы/изображения, Интернет разрешён; в статье подчёркивается важность низкой FPR (10^-4) на «чистых» файлах — [arXiv 2209.03188](https://arxiv.org/pdf/2209.03188) [VERIFIED по тексту PDF]. Benign-образцов в наборе не обнаружено при чтении выдержек [UNVERIFIED полностью].
- WinMET: CAPEv2 на Windows 10 VM, 31 844 JSON-трассы, пайплайн MALVADA, только malware; Zenodo 10.5281/zenodo.12647555 — [Data in Brief / Zaguán](https://zaguan.unizar.es/record/165301?ln=en), [PDF](https://webdiis.unizar.es/~ricardo/files/papers/RaducuVRA-DIB-25.pdf) [VERIFIED по сниппетам поиска].
- Обзор MLRan: большинство ransomware-датасетов используют Windows 7 и Windows 10; goodware часто мало и не разнообразно; 120 с — типичный таймаут — [arXiv 2505.18613](https://arxiv.org/pdf/2505.18613) [VERIFIED].
- OpTC: бенигн-активность в основном генерируется скриптами (например, Firefox по фиксированному списку сайтов) — критика, цитируемая в поиске — [поиск OpTC](https://paperswithcode.com/dataset/darpa-optc) [UNVERIFIED].
- В имеющихся benign-источниках (из карточек): Sysinternals, PortableApps, .NET-утилиты (Thcrull) — смещение к консольным/портативным/утилитным программам без GUI-сценариев; Software Informer (MLRan) — 11 категорий, шире. Это наблюдение по составу источников, не количественно измеренное.

### Inferences
- Рекомендации применительно к Avast-CTU (Win7, 2021): прогонять benign в той же конфигурации CAPEv2/VM (Win7, Office, те же приложения, тот же таймаут, Интернет), чтобы убрать артефакты окружения (P4); либо — только признаки, инвариантные к ОС; не смешивать Win10-benign (Thcrull) с Win7-malware.
- Для WinMET (Win10): Thcrull ближе по ОС, но стоит перепрогнать на той же VM, чтобы совпала версия CAPE и формат отчёта; проверять дату первого появления benign-файлов относительно malware (временное смещение, TESSERACT).
- Проверять на «утечку источника»: простой классификатор по метаданным (размер отчёта, длина трассы, наличие определённых DLL/путей, сигнатуры CAPE, число процессов) не должен разделять классы; делать ablation (Arp P4).
- Контролировать долю GUI/установщиков и успешность запуска (процент образцов, где процесс реально выполнился), т.к. часть benign завершается сразу без поведения.
- One-class вариант: обучать на benign-только трассах (OpTC-подобный бейзлайн или собственный) и оценивать на Avast-CTU/WinMET — снимает проблему подбора malware-источника, но не снимает смещения окружения.

### Gaps
- Полный текст TESSERACT и точные формулировки Arp для P1/P3 recommendations из PDF не цитировались дословно (текст PDF прочитан частично через pdftotext).
- Работа Botacin et al. (2021) о «краулнутых = benign» только упомянута через MLRan, первоисточник не открывался.
- Количественных исследований GUI vs non-GUI benign для sandbox-трасс в этой сессии не найдено.

## Ранжирование кандидатов (по пригодности как benign-пара)

1. Собственный прогон benign в том же CAPEv2 (источники: PortableApps, Software Informer + VT-0 + NSRL-проверка) — лучшее соответствие; не публичный набор, а рекомендация (по итогам выше).
2. Thcrull/win-exe-malware-analysis (CAPEv2, Win10, MIT, 762 benign) — [HF](https://huggingface.co/datasets/Thcrull/win-exe-malware-analysis) — формат CAPE, но малый и смещённый; наличие API-вызовов не подтверждено.
3. MLRan (Cuckoo 2.0.7, Win7, ~2 550 goodware; GitHub MIT, Zenodo не проверен) — ближайший по ОС к Avast-CTU, формат отчётов не подтверждён.
4. Ilić et al. 2024 (11 735 benign Cuckoo) — размер идеальный, доступность не подтверждена.
5. Oliveira (1 079, API-последовательности, 2019) — доступен, но короток (100 вызовов), мало.
6. OpTC (benign-бейзлайн Windows 10 хостов, 287 GB, eCAR) — для one-class на уровне хоста, не на уровне программы.
7. LANL (CC0, 4688/4624 события) — для process-start аномалий, без API.
8. ATLASv2 — данные не найдены.
9. APIMDS (XP), WinAPI-AdvMal (статика), SOREL/EMBER/BODMAS/NSRL (хэши/признаки) — вспомогательные.
