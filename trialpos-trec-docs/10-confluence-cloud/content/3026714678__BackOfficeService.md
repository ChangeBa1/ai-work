---
confluence_id: 3026714678
title: "BackOfficeService"
parent_id: 3011970010
version: 2
version_at: 2024-11-14T08:02:49.376Z
status: current
source_url: https://retailai.atlassian.net/wiki/spaces/POSSYS/pages/3026714678
synced_at: 2026-07-07
---

# BackOfficeService

### ①マネージメントサービスの初期データ取得

* URL：[http://(ホスト名)/](https://retailai.atlassian.net/wiki/spaces/POSSYS/pages/3012624472)BackOfficeService.svc/GetManagementInitialData/\[企業コード\]/\[店舗コード\]/\[端末番号\]
* POST
* JSON
* リクエストパラメータ

| 名称 | 論理名 | 型 | 説明 | 設定例 |
| --- | --- | --- | --- | --- |
| 管理種別 | ManagementType | int | 1:店舗状態一覧取得 2:店舗状態取得 3:店舗閉店回数取得 4:タスクスケジュールログ取得 5:電子ジャーナル検索 6:端末状態一覧取得 7:ポイント倍率一覧取得 8:設定マスタ一覧取得 9:釣銭機状態一覧取得 10:ジャーナル検索の再印字データ取得 11:バーコード無しそのた商品マスタデータ取得 12:M＆M／セット・グループセット値引情報データ取得 | 1 |
| ユーザーID | UserId | string | ログインしたユーザーID |  |
| アクセスコード | AccessCode | string | 企業毎に固定値となります。 | 012345 |
| 言語コード | LangCode | string |  |  |
| BOからのアクセスかどうか | IsBOAccess | bool |  | true |

* レスポンス

| 名称 | 論理名 | 型 | 説明 | 設定例 |
| --- | --- | --- | --- | --- |
| 処理成功フラグ | IsSuccess | boolean | 処理成功時:true、処理失敗時:false | true |
| エラーコード | ErrorCode | string | エラー時のエラーコード | null |
| エラーメッセージ | ErrorMessage | string | エラー時のエラーメッセージ | null |
| エラーコード詳細 | ErrorCodeDetail | string | エラーコード詳細 | null |
| ワーニングコード | WarningCode | string | ワーニングコード。ワーニングがない場合はnull | null |
| ワーニングメッセージ | WarningMessage | string | ワーニングメッセージ。ワーニングがない場合はnull | null |
| ワーニングコード詳細 | WarningCodeDetail | string | ワーニング時の各サーバにおけるワーニング詳細 | null |
| 管理種別 | ManagementType | int |  | 1 |
| 初期データ | Datas | string | JSON形 | {} |

### ②マネージメントサービスのデータ取得

* URL：[http://(ホスト名)/](https://retailai.atlassian.net/wiki/spaces/POSSYS/pages/3012624472)BackOfficeService.svc/GetManagementData/\[企業コード\]/\[店舗コード\]/\[端末番号\]
* POST
* JSON
* リクエストパラメータ

| 名称 | 論理名 | 型 | 説明 | 設定例 |
| --- | --- | --- | --- | --- |
| 管理種別 | ManagementType | int | 1:店舗状態一覧取得 2:店舗状態取得 3:店舗閉店回数取得 4:タスクスケジュールログ取得 5:電子ジャーナル検索 6:端末状態一覧取得 7:ポイント倍率一覧取得 8:設定マスタ一覧取得 9:釣銭機状態一覧取得 10:ジャーナル検索の再印字データ取得 11:バーコード無しそのた商品マスタデータ取得 12:M＆M／セット・グループセット値引情報データ取得 | 7 |
| ユーザーID | UserId | string | ログインしたユーザーID |  |
| アクセスコード | AccessCode | string | 企業毎に固定値となります。 | 012345 |
| 言語コード | LangCode | string |  |  |
| BOからのアクセスかどうか | IsBOAccess | bool |  | true |
| 検索条件 | SearchCondition | string | JSON | {} |

* レスポンス

| 名称 | 論理名 | 型 | 説明 | 設定例 |
| --- | --- | --- | --- | --- |
| 処理成功フラグ | IsSuccess | boolean | 処理成功時:true、処理失敗時:false | true |
| エラーコード | ErrorCode | string | エラー時のエラーコード | null |
| エラーメッセージ | ErrorMessage | string | エラー時のエラーメッセージ | null |
| エラーコード詳細 | ErrorCodeDetail | string | エラーコード詳細 | null |
| ワーニングコード | WarningCode | string | ワーニングコード。ワーニングがない場合はnull | null |
| ワーニングメッセージ | WarningMessage | string | ワーニングメッセージ。ワーニングがない場合はnull | null |
| ワーニングコード詳細 | WarningCodeDetail | string | ワーニング時の各サーバにおけるワーニング詳細 | null |
| 管理種別 | ManagementType | int |  | 7 |
| データ取得結果 | Datas | string | JSON形 | {} |

### ③再印字のデータ取得

* URL：[http://(ホスト名)/](https://retailai.atlassian.net/wiki/spaces/POSSYS/pages/3012624472)BackOfficeService.svc/GetReprintReceiptData/\[企業コード\]/\[店舗コード\]/\[端末番号\]
* POST
* JSON
* リクエストパラメータ

| 名称 | 論理名 | 型 | 説明 | 設定例 |
| --- | --- | --- | --- | --- |
| 管理種別 | ManagementType | int | 10:ジャーナル検索の再印字データ取得 | 10 |
| ユーザーID | UserId | string | ログインしたユーザーID |  |
| アクセスコード | AccessCode | string | 企業毎に固定値となります。 | 012345 |
| 言語コード | LangCode | string |  |  |
| BOからのアクセスかどうか | IsBOAccess | bool |  | true |
| 検索条件 | SearchCondition | string | JSON | {} |

* レスポンス

| 名称 | 論理名 | 型 | 説明 | 設定例 |
| --- | --- | --- | --- | --- |
| 処理成功フラグ | IsSuccess | boolean | 処理成功時:true、処理失敗時:false | true |
| エラーコード | ErrorCode | string | エラー時のエラーコード | null |
| エラーメッセージ | ErrorMessage | string | エラー時のエラーメッセージ | null |
| エラーコード詳細 | ErrorCodeDetail | string | エラーコード詳細 | null |
| ワーニングコード | WarningCode | string | ワーニングコード。ワーニングがない場合はnull | null |
| ワーニングメッセージ | WarningMessage | string | ワーニングメッセージ。ワーニングがない場合はnull | null |
| ワーニングコード詳細 | WarningCodeDetail | string | ワーニング時の各サーバにおけるワーニング詳細 | null |
| 管理種別 | ManagementType | int |  | 10 |
| データ取得結果 | Datas | string | JSON形 | {} |
