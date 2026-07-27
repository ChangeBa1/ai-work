---
confluence_id: 3012624472
title: "POSLogicWebService"
parent_id: 3011970010
version: 2
version_at: 2024-11-04T08:06:53.410Z
status: current
source_url: https://retailai.atlassian.net/wiki/spaces/POSSYS/pages/3012624472
synced_at: 2026-07-07
---

# POSLogicWebService

### ①**システム時刻調整**

* **サービスURL：**[http://(ホスト名)/POSLogicWebService.svc/](#)**GetCurrentDateTime**/\[企業コード\]/\[店舗コード\]/\[端末番号\]
* POST
* JSON
* リクエストパラメータ

| 名称 | 論理名 | 型 | 説明 | 設定例 |
| --- | --- | --- | --- | --- |
| アクセスコード | AccessCode | string | 企業毎に固定値となります。 | 012345 |

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
| 現在時刻 | CurrentDateTime | string | 現在時刻値 | 2024/11/4 14:10:10.0000000 |

### ②**端末入替用採番情報取得**

* **サービスURL：**[http://(ホスト名)/POSLogicWebService.svc/](#)**GetBusinessCounterList**/\[企業コード\]/\[店舗コード\]/\[端末番号\]
* POST
* JSON
* リクエストパラメータ

| 名称 | 論理名 | 型 | 説明 | 設定例 |
| --- | --- | --- | --- | --- |
| アクセスコード | AccessCode | string | 企業毎に固定値となります。 | 012345 |

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
| 採番情報リスト | Result |  | 採番情報リスト |  |
| 　カウンターコード | 　CounterCode | string | カウンターコード | ReceiptNo |
| 　番号 | 　Number | long | 現在の番号 | 0 |
| 　開始番号 | 　StartNumber | long | 開始番号 | 1 |
| 　終了番号 | 　EndNumber | long | 終了番号 | 9999 |
| 　リセット後の番号 | 　ResetNumber | long | リセット後の番号 | 0 |

### ③**端末入替用採番情報アップロード**

* **サービスURL：**[http://(ホスト名)/POSLogicWebService.svc/](#)**PutBusinessCounterList**/\[企業コード\]/\[店舗コード\]/\[端末番号\]
* POST
* JSON
* リクエストパラメータ

| 名称 | 論理名 | 型 | 説明 | 設定例 |
| --- | --- | --- | --- | --- |
| アクセスコード | AccessCode | string | 企業毎に固定値となります。 | 012345 |
| 採番情報リスト | BusinessCounterDatas |  | 採番情報リスト |  |
| 　カウンターコード | 　CounterCode | string | カウンターコード | ReceiptNo |
| 　番号 | 　Number | long | 現在の番号 | 0 |
| 　開始番号 | 　StartNumber | long | 開始番号 | 1 |
| 　終了番号 | 　EndNumber | long | 終了番号 | 9999 |
| 　リセット後の番号 | 　ResetNumber | long | リセット後の番号 | 0 |

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

### ④**POS HW状況送信**

* **サービスURL：**[http://(ホスト名)/POSLogicWebService.svc/](#)**PutTerminalCapacity**/\[企業コード\]/\[店舗コード\]/\[端末番号\]
* POST
* JSON
* リクエストパラメータ

| 名称 | 論理名 | 型 | 説明 | 設定例 |
| --- | --- | --- | --- | --- |
| アクセスコード | AccessCode | string | 企業毎に固定値となります。 | 012345 |
| Cドライブ空き容量 | AvaiableSpaceInC | long | Cドライブ空き容量 | null |
| Cドライブ全容量 | TotalSizeInC | long | Cドライブ全容量 | null |
| Dドライブ空き容量 | AvaiableSpaceInD | long | Dドライブ空き容量 | null |
| Dドライブ全容量 | TotalSizeInD | long | Dドライブ全容量 | null |
| Logフォルダ総容量 | TotalFolderSizeInLog | long | Logフォルダ総容量 | null |
| DBBackUpフォルダ総容量 | TotalFolderSizeInDBBackUp | long | DBBackUpフォルダ総容量 | null |
| DBファイル容量 | DBFileSize | long | DBファイル容量 | null |
| DBログファイル容量 | DBLogFileSize | long | DBログファイル容量 | null |

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

### ⑤**釣銭機状態送信**

* **サービスURL：**[http://(ホスト名)/POSLogicWebService.svc/](#)**PutCashChangerStatus**/\[企業コード\]/\[店舗コード\]/\[端末番号\]
* POST
* JSON
* リクエストパラメータ

| 名称 | 論理名 | 型 | 説明 | 設定例 |
| --- | --- | --- | --- | --- |
| アクセスコード | AccessCode | string | 企業毎に固定値となります。 | 012345 |
| 釣銭機保有枚数 | RememberCashCount | string | 記録されている釣銭機保有枚数 |  |
| 釣銭機状態 | Status | long | 釣銭機の状態 | 0 |

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
