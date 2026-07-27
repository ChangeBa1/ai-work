---
confluence_id: 2971697419
title: "SettingDataType"
parent_id: 2971500956
version: 4
version_at: 2024-11-04T08:23:18.903Z
status: current
source_url: https://retailai.atlassian.net/wiki/spaces/POSSYS/pages/2971697419
synced_at: 2026-07-07
---

# SettingDataType

EventGroupDetailMaster

イベント実行時に設定するデータタイプ

| **SettingDataType** | **Name** | **Description** |
| --- | --- | --- |
| 1 | EventSettingData | EventGroupDetailMasterのSettingDataを使用する |
| 2 | InputData | InputDataを使用する |
| 3 | InputDataNotNull | InputDataを使用する InputDataなし時はイベントを追加しない |
| 4 | PresetSettingData | PresetMenuButtonMasterのSettingDataを使用する |
| 5 | EventSettingDataWithInputData | EventGroupDetailMasterのSettingDataを使用する InputDataが存在する場合は、「SettingData+’,’+InputData」を入力値とする |
| 6 | PresetSettingDataWithInputData | PresetMenuButtonMasterのSettingDataを使用する InputDataが存在する場合は、「SettingData+’,’+InputData」を入力値とする |
