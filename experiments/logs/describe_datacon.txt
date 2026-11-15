# DataCon 2019 Stage1: первичное описание

Источник: `derived\datacon` (convert_datacon.py). raw — все записи песочницы, clean — без служебных. Метки: 0 = benign, 1 = malware.

## Сравнение с MalBehavD-V1

| датасет       |   строк | benign / malware   | уникальных трасс   | уникальных benign   | уникальных malware   |   строк с конфликтом меток | длина: медиана (min–max)   |   словарь API |
|:--------------|--------:|:-------------------|:-------------------|:--------------------|:---------------------|---------------------------:|:---------------------------|--------------:|
| MalBehavD-V1  |    2570 | 1285 / 1285        | 1601 (62.3%)       | 87.4%               | 37.3%                |                         12 | 37 (2–175)                 |           291 |
| DataCon raw   |   30000 | 20000 / 10000      | 11035 (36.8%)      | 26.7%               | 57.4%                |                        516 | 22 (2–61)                  |            93 |
| DataCon clean |   29999 | 19999 / 10000      | 9204 (30.7%)       | 22.7%               | 47.2%                |                       2010 | 15 (1–51)                  |            81 |

## Длина последовательности (уникальных API в порядке первого вызова)

| вариант   | класс   |   строк |   min |   25% |   медиана |   75% |   max |   среднее |
|:----------|:--------|--------:|------:|------:|----------:|------:|------:|----------:|
| raw       | benign  |   20000 |     2 |    11 |        17 |    26 |    61 |      19.1 |
| raw       | malware |   10000 |     6 |    24 |        33 |    37 |    55 |      30.2 |
| clean     | benign  |   19999 |     1 |     7 |        11 |    19 |    51 |      13.6 |
| clean     | malware |   10000 |     2 |    16 |        25 |    28 |    45 |      22   |

Выпало из clean (не осталось ни одного вызова после удаления служебных записей):
- `965ac9477480…`, benign, raw: AnalyzeStart → AnalyzeStop

## Размеры групп одинаковых трасс

Группа — строки одного класса с одинаковой последовательностью.

| вариант   | размер группы   |   групп benign |   строк benign |   групп malware |   строк malware |
|:----------|:----------------|---------------:|---------------:|----------------:|----------------:|
| raw       | 1               |           4040 |           4040 |            4808 |            4808 |
| raw       | 2–5             |            962 |           2590 |             747 |            1990 |
| raw       | 6–20            |            241 |           2310 |             144 |            1378 |
| raw       | 21–100          |             80 |           3345 |              34 |            1294 |
| raw       | больше 100      |             23 |           7715 |               2 |             530 |
| clean     | 1               |           3348 |           3348 |            3820 |            3820 |
| clean     | 2–5             |            862 |           2333 |             669 |            1810 |
| clean     | 6–20            |            230 |           2348 |             174 |            1611 |
| clean     | 21–100          |             81 |           3441 |              50 |            1882 |
| clean     | больше 100      |             22 |           8529 |               4 |             877 |

## Крупнейшие конфликтующие трассы (одна трасса с метками обоих классов)

| вариант   |   строк |   benign |   malware |   длина | начало трассы                                                               |
|:----------|--------:|---------:|----------:|--------:|:----------------------------------------------------------------------------|
| raw       |     194 |      193 |         1 |      10 | AnalyzeStart → Fake_BeCreatedEx → TryToAnalyze → LoadLibraryExW …           |
| raw       |      30 |       28 |         2 |      11 | AnalyzeStart → Fake_BeCreatedEx → TryToAnalyze → LoadLibraryExW …           |
| raw       |      27 |       26 |         1 |      33 | AnalyzeStart → Fake_BeCreatedEx → TryToAnalyze → LoadLibraryExW …           |
| raw       |      22 |       15 |         7 |      10 | AnalyzeStart → Fake_BeCreatedEx → TryToAnalyze → LoadLibraryExW …           |
| raw       |      21 |       20 |         1 |       9 | AnalyzeStart → Fake_BeCreatedEx → TryToAnalyze → LoadLibraryExW …           |
| clean     |     498 |      454 |        44 |       6 | LoadLibraryExW → NtQueryAttributesFile → NtReadFile → GetForegroundWindow … |
| clean     |     456 |      455 |         1 |      27 | LoadLibraryExW → NtQueryAttributesFile → GetComputerNameExW → NtDeleteKey … |
| clean     |     260 |      259 |         1 |       2 | LoadLibraryExW → NtQueryAttributesFile                                      |
| clean     |     113 |      105 |         8 |       5 | LoadLibraryExW → NtQueryAttributesFile → NtReadFile → NtCreateMutant …      |
| clean     |      83 |       15 |        68 |       6 | LoadLibraryExW → NtQueryAttributesFile → NtReadFile → NtCreateMutant …      |

## Признаки отчёта, не связанные со смыслом поведения

ROC-AUC — насколько один признак сам по себе разделяет классы (0.5 — никак, 1.0 — идеально; больше 0.5 — у malware значения выше).

| признак                     | benign   | malware     | что показано   |   ROC-AUC |
|:----------------------------|:---------|:------------|:---------------|----------:|
| размер XML, байт            | 39071.5  | 1.10155e+06 | медиана        |     0.896 |
| число вызовов (с повторами) | 112      | 2777        | медиана        |     0.895 |
| число процессов             | 1        | 20          | медиана        |     0.816 |
| длина raw (уникальных API)  | 17       | 33          | медиана        |     0.798 |
| длина clean                 | 11       | 25          | медиана        |     0.754 |
| есть раздел reboot          | 1.2%     | 39.0%       | доля файлов    |     0.689 |
| пометка TooManyBehavior     | 14.6%    | 76.4%       | доля файлов    |     0.809 |

## Служебные записи песочницы (доля файлов класса)

| api                          |   share_benign |   share_malware |
|:-----------------------------|---------------:|----------------:|
| AnalyzeStart                 |         1      |          1      |
| Fake_BeCreatedEx             |         1      |          1      |
| TryToAnalyze                 |         1      |          1      |
| AnalyzeStop                  |         1      |          0.9984 |
| Fake_DetectDebugger          |         0.7648 |          0.9526 |
| Fake_WritePEFile             |         0.175  |          0.8824 |
| TooManyBehavior              |         0.1458 |          0.7643 |
| Fake_SetFileHiddenOrReadOnly |         0.048  |          0.5245 |
| UnpackSelf                   |         0.202  |          0.3747 |
| Fake_TerminateRemoteProcess  |         0.1108 |          0.3304 |
| Fake_SetFileCreationTime     |         0.095  |          0.2366 |
| Fake_BeInjected              |         0.0003 |          0.1455 |

## 15 самых частых API (clean-словарь, доля файлов класса)

| api                     |   share_benign |   share_malware |   разница долей |   in_malbehavd |
|:------------------------|---------------:|----------------:|----------------:|---------------:|
| LoadLibraryExW          |         0.9995 |          0.9999 |           0     |              0 |
| NtQueryAttributesFile   |         0.982  |          0.999  |           0.017 |              1 |
| NtReadFile              |         0.954  |          0.9955 |           0.042 |              1 |
| NtCreateMutant          |         0.9022 |          0.9635 |           0.061 |              1 |
| NtTerminateProcess      |         0.8902 |          0.9059 |           0.016 |              1 |
| NtSetValueKey           |         0.5968 |          0.918  |           0.321 |              1 |
| NtWriteFile             |         0.5686 |          0.9218 |           0.353 |              1 |
| GetForegroundWindow     |         0.6862 |          0.6727 |          -0.014 |              1 |
| NtCreateFile            |         0.5284 |          0.8191 |           0.291 |              1 |
| GetComputerNameW        |         0.5223 |          0.8041 |           0.282 |              1 |
| DeleteFileW             |         0.443  |          0.7517 |           0.309 |              1 |
| GetComputerNameExW      |         0.4798 |          0.6977 |           0.218 |              0 |
| CreateProcessInternalW  |         0.4004 |          0.7305 |           0.33  |              1 |
| NtAdjustPrivilegesToken |         0.4168 |          0.7013 |           0.285 |              0 |
| NtQueryDirectoryFile    |         0.4009 |          0.6982 |           0.297 |              1 |

## 10 API, которые чаще встречаются у malware

| api                    |   share_benign |   share_malware |   разница долей |   in_malbehavd |
|:-----------------------|---------------:|----------------:|----------------:|---------------:|
| CopyFileExW            |         0.099  |          0.6425 |           0.544 |              1 |
| connect                |         0.1196 |          0.5646 |           0.445 |              1 |
| Process32FirstW        |         0.0605 |          0.5004 |           0.44  |              1 |
| WSASocketW             |         0.1924 |          0.6245 |           0.432 |              1 |
| AutoLogin              |         0.0107 |          0.3888 |           0.378 |              0 |
| FindFirstFileExW       |         0.174  |          0.5418 |           0.368 |              1 |
| gethostbyname          |         0.0453 |          0.4081 |           0.363 |              1 |
| NtWriteFile            |         0.5686 |          0.9218 |           0.353 |              1 |
| CreateProcessInternalW |         0.4004 |          0.7305 |           0.33  |              1 |
| NtSetValueKey          |         0.5968 |          0.918  |           0.321 |              1 |

## 10 API, которые чаще встречаются у benign

| api                       |   share_benign |   share_malware |   разница долей |   in_malbehavd |
|:--------------------------|---------------:|----------------:|----------------:|---------------:|
| NtSuspendThread           |         0.1167 |          0.0225 |          -0.094 |              1 |
| NtQueryFullAttributesFile |         0.1003 |          0.0466 |          -0.054 |              1 |
| NtSetContextThread        |         0.077  |          0.0412 |          -0.036 |              1 |
| EnumServicesStatusExW     |         0.0248 |          0.0022 |          -0.023 |              0 |
| WSASend                   |         0.0174 |          0.0029 |          -0.014 |              1 |
| GetForegroundWindow       |         0.6862 |          0.6727 |          -0.014 |              1 |
| CryptExportKey            |         0.0158 |          0.0031 |          -0.013 |              1 |
| Thread32First             |         0.1109 |          0.0994 |          -0.011 |              1 |
| recv                      |         0.058  |          0.0483 |          -0.01  |              1 |
| GetProcessAffinityMask    |         0.006  |          0.001  |          -0.005 |              0 |

## Словарь: где встречаются API (без служебных)

| где встречается     |   API |
|:--------------------|------:|
| только в malware    |     4 |
| только в benign     |     2 |
| в обоих классах     |    75 |
| есть в MalBehavD-V1 |    53 |
| нет в MalBehavD-V1  |    28 |

API DataCon, которых нет в MalBehavD-V1: AutoLogin, DeleteService, EnumServicesStatusExW, GetComputerNameExW, GetProcessAffinityMask, KeBugCheck2, KiGeneralProtectionFault, KiTrap0D, LoadLibraryExW, Login, NtAdjustPrivilegesToken, NtCreateThread, NtDeleteFile, NtSetSystemInformation, NtSetSystemTime, NtShutdownSystem, NtSuspendProcess, NtUnloadDriver, NtWriteVirtualMemory, PowerOn, SendARP, StrangeBehavior, VMDetect, WMIConnectServer, WMICreateInstanceEnum, WMIExecQuery, WSARecvFrom, WSASendTo
