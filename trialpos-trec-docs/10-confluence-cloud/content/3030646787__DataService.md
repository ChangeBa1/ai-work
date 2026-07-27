---
confluence_id: 3030646787
title: "DataService"
parent_id: 3011970010
version: 1
version_at: 2024-11-18T08:57:48.895Z
status: current
source_url: https://retailai.atlassian.net/wiki/spaces/POSSYS/pages/3030646787
synced_at: 2026-07-07
---

# DataService

### ①**POS4U更新モジュールがあるか**

* **サービスURL：**[http://(ホスト名)/](#)DataService[.svc/](#)CheckExistUpdateModule/\[企業コード\]/\[店舗コード\]
* POST
* JSON
* リクエストパラメータ

| 名称 | 論理名 | 型 | 説明 | 設定例 |
| --- | --- | --- | --- | --- |
| アクセルコード | AccessCode | string |  | 012345 |
| 現在バージョン | CurrentVersion | string |  | 2024110501 |

* レスポンスパラメータ

| 名称 | 論理名 | 型 | 説明 | 設定例 |
| --- | --- | --- | --- | --- |
| 処理成功フラグ | IsSuccess | boolean | 処理成功時:true、処理失敗時:false | true |
| エラーコード | ErrorCode | string | エラー時のエラーコード | null |
| エラーメッセージ | ErrorMessage | string | エラー時のエラーメッセージ | null |
| エラーコード詳細 | ErrorCodeDetail | string | エラーコード詳細 | null |
| ワーニングコード | WarningCode | string | ワーニングコード。ワーニングがない場合はnull | null |
| ワーニングメッセージ | WarningMessage | string | ワーニングメッセージ。ワーニングがない場合はnull | null |
| ワーニングコード詳細 | WarningCodeDetail | string | ワーニング時の各サーバにおけるワーニング詳細 | null |
| 新バージョン | NewVersion | string |  | 2024121201 |
| Uri | Uri | string |  |  |
| 更新開始日時 | UpdateStartDateTime | string |  |  |

### ②**端末のモジュール更新情報登録**

* **サービスURL：**[http://(ホスト名)/DataService.svc/](#)NotifyModuleUpload/\[企業コード\]/\[店舗コード\]/\[端末番号\]
* POST
* JSON
* リクエストパラメータ

| 名称 | 論理名 | 型 | 説明 | 設定例 |
| --- | --- | --- | --- | --- |
| アクセルコード | AccessCode | string |  | 012345 |
| ダウンロードしたモジュールバージョン | DownloadVersion | string |  | 2024110501 |
| ダウンロードした日時 | DownloadDateTime | DateTime? |  |  |
| 更新完了したモジュールバージョン | CurrentVersion | string |  | 2024110501 |
| 更新完了した日時 | UpdateDateTime | DateTime? |  |  |

* レスポンスパラメータ

| 名称 | 論理名 | 型 | 説明 | 設定例 |
| --- | --- | --- | --- | --- |
| 処理成功フラグ | IsSuccess | boolean | 処理成功時:true、処理失敗時:false | true |
| エラーコード | ErrorCode | string | エラー時のエラーコード | null |
| エラーメッセージ | ErrorMessage | string | エラー時のエラーメッセージ | null |
| エラーコード詳細 | ErrorCodeDetail | string | エラーコード詳細 | null |
| ワーニングコード | WarningCode | string | ワーニングコード。ワーニングがない場合はnull | null |
| ワーニングメッセージ | WarningMessage | string | ワーニングメッセージ。ワーニングがない場合はnull | null |
| ワーニングコード詳細 | WarningCodeDetail | string | ワーニング時の各サーバにおけるワーニング詳細 | null |

### ③**マスタ配信ファイルのダウンロード情報取得**

* **サービスURL：**[http://(ホスト名)/DataService.svc/](#)**GetMasterDownloadInfo2**/\[企業コード\]/\[店舗コード\]/\[端末番号\]
* POST
* JSON
* リクエストパラメータ

| 名称 | 論理名 | 型 | 説明 | 設定例 |
| --- | --- | --- | --- | --- |
| アクセルコード | AccessCode | string |  | 012345 |
| 現在バージョン | CurrentVersion | string |  | 2024110501 |
| マイナーバージョン | CurrentMinorVersion | string |  | 2024110501-0001 |
| 全店舗フラグ | IsAllStore | bool |  | false |

* レスポンスパラメータ

| 名称 | 論理名 | 型 | 説明 | 設定例 |
| --- | --- | --- | --- | --- |
| 処理成功フラグ | IsSuccess | boolean | 処理成功時:true、処理失敗時:false | true |
| エラーコード | ErrorCode | string | エラー時のエラーコード | null |
| エラーメッセージ | ErrorMessage | string | エラー時のエラーメッセージ | null |
| エラーコード詳細 | ErrorCodeDetail | string | エラーコード詳細 | null |
| ワーニングコード | WarningCode | string | ワーニングコード。ワーニングがない場合はnull | null |
| ワーニングメッセージ | WarningMessage | string | ワーニングメッセージ。ワーニングがない場合はnull | null |
| ワーニングコード詳細 | WarningCodeDetail | string | ワーニング時の各サーバにおけるワーニング詳細 | null |
| マイナーバージョン | MinorVersion | string |  |  |
| URI | Uri | string |  |  |
| バージョン | Version | string |  |  |
| 更新開始時刻 | UpdateStartDateTime | string |  |  |

### ④**マスタダウンロードファイルのダウンロード**

* **サービスURL：**[http://(ホスト名)/DataService.svc/](#)**GetMasterDownloadFile**/\[企業コード\]
* POST
* JSON
* リクエストパラメータ

| 名称 | 論理名 | 型 | 説明 | 設定例 |
| --- | --- | --- | --- | --- |
| アクセルコード | AccessCode | string |  | 012345 |
| ダウンロード対象のURL | Uri | string |  |  |

* レスポンスパラメータ

　　HttpResponseMessage

### ⑤**マスタダウンロードの完了報告**

* **サービスURL：**[http://(ホスト名)/DataService.svc/](https://retailai.atlassian.net/wiki/pages/resumedraft.action?draftId=3030646787&draftShareId=9f274d97-c0b4-4347-b9ba-b1216a578d08)**NotifyMasterDownloadCompleted**/\[企業コード\]/\[店舗コード\]/\[端末番号\]
* POST
* JSON
* リクエストパラメータ

| 名称 | 論理名 | 型 | 説明 | 設定例 |
| --- | --- | --- | --- | --- |
| アクセルコード | AccessCode | string |  | 012345 |
| 現在バージョン | CurrentVersion | string |  | 2024110501 |
| マイナーバージョン | CurrentMinorVersion | string |  | 2024110501-0001 |
| 全店舗フラグ | IsAllStore | bool |  | false |

* レスポンスパラメータ

| 名称 | 論理名 | 型 | 説明 | 設定例 |
| --- | --- | --- | --- | --- |
| 処理成功フラグ | IsSuccess | boolean | 処理成功時:true、処理失敗時:false | true |
| エラーコード | ErrorCode | string | エラー時のエラーコード | null |
| エラーメッセージ | ErrorMessage | string | エラー時のエラーメッセージ | null |
| エラーコード詳細 | ErrorCodeDetail | string | エラーコード詳細 | null |
| ワーニングコード | WarningCode | string | ワーニングコード。ワーニングがない場合はnull | null |
| ワーニングメッセージ | WarningMessage | string | ワーニングメッセージ。ワーニングがない場合はnull | null |
| ワーニングコード詳細 | WarningCodeDetail | string | ワーニング時の各サーバにおけるワーニング詳細 | null |
| マイナーバージョン | MinorVersion | string |  |  |
| URI | Uri | string |  |  |
| バージョン | Version | string |  |  |
| 更新開始時刻 | UpdateStartDateTime | string |  |  |

 ⑥**マスタ配信ファイルの更新情報取得**

* **サービスURL：**[http://(ホスト名)/DataService.svc/](#)**GetMasterUpdateInfo2**/\[企業コード\]/\[店舗コード\]/\[端末番号\]
* POST
* JSON
* リクエストパラメータ

| 名称 | 論理名 | 型 | 説明 | 設定例 |
| --- | --- | --- | --- | --- |
| アクセルコード | AccessCode | string |  | 012345 |
| 現在バージョン | CurrentVersion | string |  | 2024110501 |
| マイナーバージョン | CurrentMinorVersion | string |  | 2024110501-0001 |
| 全店舗フラグ | IsAllStore | bool |  | false |

* レスポンスパラメータ

| 名称 | 論理名 | 型 | 説明 | 設定例 |
| --- | --- | --- | --- | --- |
| 処理成功フラグ | IsSuccess | boolean | 処理成功時:true、処理失敗時:false | true |
| エラーコード | ErrorCode | string | エラー時のエラーコード | null |
| エラーメッセージ | ErrorMessage | string | エラー時のエラーメッセージ | null |
| エラーコード詳細 | ErrorCodeDetail | string | エラーコード詳細 | null |
| ワーニングコード | WarningCode | string | ワーニングコード。ワーニングがない場合はnull | null |
| ワーニングメッセージ | WarningMessage | string | ワーニングメッセージ。ワーニングがない場合はnull | null |
| ワーニングコード詳細 | WarningCodeDetail | string | ワーニング時の各サーバにおけるワーニング詳細 | null |
| マイナーバージョン | MinorVersion | string |  |  |
| URI | Uri | string |  |  |
| バージョン | Version | string |  |  |
| 更新開始時刻 | UpdateStartDateTime | string |  |  |
