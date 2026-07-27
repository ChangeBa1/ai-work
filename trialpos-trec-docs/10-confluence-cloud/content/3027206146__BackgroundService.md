---
confluence_id: 3027206146
title: "BackgroundService"
parent_id: 3011970010
version: 3
version_at: 2024-11-18T06:55:15.645Z
status: current
source_url: https://retailai.atlassian.net/wiki/spaces/POSSYS/pages/3027206146
synced_at: 2026-07-07
---

# BackgroundService

### ①**取引ログ最終情報**

* **サービスURL：**[http://(ホスト名)/](#)BackgroundService[.svc/](#)GetLastTransactionLog/\[企業コード\]/\[店舗コード\]/\[端末番号\]
* POST
* JSON
* リクエストパラメータ

| 名称 | 論理名 | 型 | 説明 | 設定例 |
| --- | --- | --- | --- | --- |
| 企業コード | CompanyCode | string |  | 1 |
| 店舗コード | StoreCode | string |  | 00900 |
| 端末番号 | TerminalNo | int |  | 2501 |

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
| 企業コード | CompanyCode | string |  | 1 |
| 店舗コード | StoreCode | string |  | 00900 |
| 転送結果データ | TransferDatas |  |  |  |
| 　端末番号 | 　TerminalNo | int |  | 2501 |
| 　受信した最終番号のマネージ番号 | 　ReceivedLastManageNo | int |  |  |
| 　受信した最終番号 | 　ReceivedLastSeqNo | long |  | 9999 |
| 転送間隔 | IntervalsInSeconds | int | 単位：秒 | 1 |
| 送信データ件数 | TransferDataCount | int | 1度に送信するデータ件数 | 1000 |

### ②**電子ジャーナル最終情報**

* **サービスURL：**[http://(ホスト名)/BackgroundService.svc/](#)GetLastEJournal/\[企業コード\]/\[店舗コード\]/\[端末番号\]
* POST
* JSON
* リクエストパラメータ

| 名称 | 論理名 | 型 | 説明 | 設定例 |
| --- | --- | --- | --- | --- |
| 企業コード | CompanyCode | string |  | 1 |
| 店舗コード | StoreCode | string |  | 00900 |
| 端末番号 | TerminalNo | int |  | 2501 |

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
| 企業コード | CompanyCode | string |  | 1 |
| 店舗コード | StoreCode | string |  | 00900 |
| 転送結果データ | TransferDatas |  |  |  |
| 　端末番号 | 　TerminalNo | int |  | 2501 |
| 　受信した最終番号のマネージ番号 | 　ReceivedLastManageNo | int |  |  |
| 　受信した最終番号 | 　ReceivedLastSeqNo | long |  | 9999 |
| 転送間隔 | IntervalsInSeconds | int | 単位：秒 | 1 |
| 送信データ件数 | TransferDataCount | int | 1度に送信するデータ件数 | 1000 |

### ③**取引ログ送信**

* **サービスURL：**[http://(ホスト名)/BackgroundService.svc/](#)**PutTransactionLogList**/\[企業コード\]/\[店舗コード\]/\[端末番号\]
* POST
* JSON
* リクエストパラメータ

| 名称 | 論理名 | 型 | 説明 | 設定例 |
| --- | --- | --- | --- | --- |
| 企業コード | CompanyCode | string |  | 1 |
| 店舗コード | StoreCode | string |  | 00900 |
| 端末番号 | TerminalNo | int |  | 2501 |
| 受信した最終マネージ番号 | ReceivedLastManagedNo | int |  |  |
| 受信した最終シーケンス番号 | ReceivedLastSeqNo | long |  | 9999 |
| 取引ログデータリスト | TranLogDatas |  |  |  |
| 　管理番号 | 　ManagedNo | int |  |  |
| 　取引番号 | 　TransactionNo | long |  |  |
| 　PA連携取引番号 | 　PATransactionNo | long |  |  |
| 　営業回数 | 　BusinessCount | int |  |  |
| 　営業日 | 　BusinessDate | string |  |  |
| 　取引種別 | 　TransactionType | int |  |  |
| 　レシート番号 | 　ReceiptNo | long |  |  |
| 　取引XMLデータ | 　TransactionXmlData | string |  |  |
| 　取消したレシート番号 | 　VoidedReceiptNo | long |  |  |
| 　領収書発行レシート番号 | 　EvidenceReceiptIssuedReceiptNo | long |  |  |
| 　元取引の端末番号 | 　OriginalTerminalNo | int |  |  |
| 　元取引の営業日 | 　OriginalBusinessDate | string |  |  |
| 　元取引の取引種別 | 　OriginalTransactionType | int |  |  |
| 　取引中止 | 　IsCanceled | bool |  |  |
| 　生成時刻 | 　GenerateDateTime | string |  |  |

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
| 企業コード | CompanyCode | string |  | 1 |
| 店舗コード | StoreCode | string |  | 00900 |
| 転送結果データ | TransferDatas |  |  |  |
| 　端末番号 | 　TerminalNo | int |  | 2501 |
| 　受信した最終番号のマネージ番号 | 　ReceivedLastManageNo | int |  |  |
| 　受信した最終番号 | 　ReceivedLastSeqNo | long |  | 9999 |
| 転送間隔 | IntervalsInSeconds | int | 単位：秒 | 1 |
| 送信データ件数 | TransferDataCount | int | 1度に送信するデータ件数 | 1000 |

### ④**電子ジャーナル送信**

* **サービスURL：**[http://(ホスト名)/BackgroundService.svc/](https://retailai.atlassian.net/wiki/spaces/POSSYS/pages/3027206146)**PutEJournal**/\[企業コード\]/\[店舗コード\]/\[端末番号\]
* POST
* JSON
* リクエストパラメータ

| 名称 | 論理名 | 型 | 説明 | 設定例 |
| --- | --- | --- | --- | --- |
| 企業コード | CompanyCode | string |   | 1 |
| 店舗コード | StoreCode | string |   | 00900 |
| 端末番号 | TerminalNo | int |   | 2501 |
| 受信した最終マネージ番号 | ReceivedLastManagedNo | int |   |   |
| 受信した最終シーケンス番号 | ReceivedLastSeqNo | long |   | 9999 |
| ジャーナルデータリスト | EJournalDatas |   |   |   |
| 　管理番号 | 　ManagedNo | int |   |   |
| 　電子ジャーナルシーケンス番号 | 　EJournalSeqNo | long |   |   |
| 　電子ジャーナル番号 | 　EJournalNo | long |   |   |
| 　営業回数 | 　BusinessCount | int |   |   |
| 　営業日 | 　BusinessDate | string |   |   |
| 　電子ジャーナル種別 | 　EJournalType | int |   |   |
| 　担当者コード | 　OperatorCode | string |   |   |
| 　取引番号 | 　TransactionNo | long |   |   |
| 　レシート番号 | 　ReceiptNo | long |   |   |
| 　ジャーナルデータ | 　JournalData | string |   |   |
| 　レシートデータ | 　ReceiptData | string |   |   |
| 　再発行用レシートデータ | 　ReprintReceiptData | string |   |   |
| 　再発行用ジャーナルデータ | 　ReprintJournalData | string |   |   |
| 　お買物金額 | 　TotalAmountWithTaxes | decimal |   |   |
| 　外税額 | 　ExcludedTaxesAmount | decimal |   |   |
| 　内税額 | 　IncludedTaxesAmount | decimal |  |  |
| 　会員番号 | 　PointCardNo | string |  |  |
| 　ポイント処理結果区分 | 　PointProcResultType | int? |  |  |
| 　注文回数 | 　OrderNo | long? |  |  |
| 　収入印紙対象かどうか | 　IsRevenueStamp | bool |  |  |
| 　生成時刻 | 　GenerateDateTime | string |   |   |

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
| 企業コード | CompanyCode | string |  | 1 |
| 店舗コード | StoreCode | string |  | 00900 |
| 転送結果データ | TransferDatas |  |  |  |
| 　端末番号 | 　TerminalNo | int |  | 2501 |
| 　受信した最終番号のマネージ番号 | 　ReceivedLastManageNo | int |  |  |
| 　受信した最終番号 | 　ReceivedLastSeqNo | long |  | 9999 |
| 転送間隔 | IntervalsInSeconds | int | 単位：秒 | 1 |
| 送信データ件数 | TransferDataCount | int | 1度に送信するデータ件数 | 1000 |
