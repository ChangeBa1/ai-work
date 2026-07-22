---
confluence_id: 2970550556
title: "POSアプリ Release note"
parent_id: 2976415820
version: 16
version_at: 2024-12-11T02:34:44.093Z
status: current
source_url: https://retailai.atlassian.net/wiki/spaces/POSSYS/pages/2970550556
synced_at: 2026-07-07
---

# POSアプリ Release note

‌

## TRIAL

### 全店版\_ver2024110501<custom data-type="status" data-id="id-0">全店展開</custom>  

* リリース日：
* リリース対象店舗：全店
* 現時点の展開範囲店舗：
* ベースバージョン：2024100301
* 改善ポイント：

    * [#6775](https://my.redmine.jp/retail-shift/issues/6775)【保守】釣銭機　紙幣硬貨のお釣り排出時、硬貨抜き取りのみでレシートが印字		
    * [#6741](https://my.redmine.jp/retail-shift/issues/6741)【保守/コール削減】プリンター　エラーメッセージ追記
    * [#6546](https://my.redmine.jp/retail-shift/issues/6546)【TEC関連】スキャナ明滅モードコントロール
    * [#6266](https://my.redmine.jp/retail-shift/issues/6266)【顔認証関連】ミラ・マモル機能実装
    * [#6220](https://my.redmine.jp/retail-shift/issues/6220)【開発課題】：従業員バーコードの代わりにキーコマンドで従業員確認
    * [#5901](https://my.redmine.jp/retail-shift/issues/5901)【保守／コール削減】画面表示が固まる　お釣り抜き取りから画面遷移しない	
    * [#5883](https://my.redmine.jp/retail-shift/issues/5883)【領収証発行】アイテム指定発行の期間変更
    * [#5741](https://my.redmine.jp/retail-shift/issues/5741)【業務課題】：オーダーPOSに顔認証機能を連動させる
    * [#6815](https://my.redmine.jp/retail-shift/issues/6815) TLS1.2バッチリリース							
    
* 導入後の問題発見：

　新決済Win10テスト段階に、マルチチャンク問題が発生した

　原因：モジュール作成する時、ローカルで編集したソースをビルドしまいました

‌

### イオンテナント\_ver2024020601

・リリース日：2024/02/06

・リリース対象店舗：635イオンモール下田店

・現時点の展開範囲店舗：

・ベースバージョン：2023102301

・改善ポイント：イオンテナント決済

導入後の問題発見：

‌

### NEXMART01GO店\_ver2024092781

リリース日：2024/09/27

リリース対象店舗：639NEXMART01GO

現時点の展開範囲店舗：

ベースバージョン：2023121281

改善ポイント：202410最新+QR決済

導入後の問題発見：

‌

### フードパーク店\_ver2024110501ベースの差分

リリース日：2024/11/11

リリース対象店舗：フードパーク店(950,951,952,953,954)

現時点の展開範囲店舗：

ベースバージョン：2024110501

改善ポイント：202411最新+フードパーク

導入後の問題発見：

‌

### CT6100クレジットチャージ\_ver2024110501ベースの差分

リリース日：2024/11/11

リリース対象店舗：

現時点の展開範囲店舗：[クレジットチャージ対象](https://docs.google.com/spreadsheets/d/1idSQSh63cFFJTDOaav8OubKEDq6gZ8qW/edit?gid=1802767571#gid=1802767571)

ベースバージョン：2024110501

改善ポイント：202411最新+CT6100

導入後の問題発見：

　[#6923](https://my.redmine.jp/retail-shift/issues/6923) 【保守】CT6100クレジットチャージ　釣銭機預かり中止で操作不能になる

## FC

### FC版\_ver2024091761

リリース日：2024/09/19

リリース対象店舗：7本渡店,24リンドマール店,142牛深店

現時点の展開範囲店舗：

ベースバージョン：2021120801

改善ポイント：202406までのTrial最新+VDのTLS1.2対応

導入後の問題発見：

‌

履歴：

全店版\_ver2024100301  

* リリース日：2024/10/03
* リリース対象店舗：
* 展開範囲店舗：全店舗(2024/10/2時点)
* ベースバージョン：2024090401
* 改善ポイント：

    * [#6712](https://my.redmine.jp/retail-shift/issues/6712)　【CESettongTool改修】VD接続先固定値変更
    * [#6707](https://my.redmine.jp/retail-shift/issues/6707)　【店舗サポート部案件】レシートメッセージ変更
    * [#6202](https://my.redmine.jp/retail-shift/issues/6202)　【保守】お釣りを抜き取らずにレシートが排出される
    * [#6619](https://my.redmine.jp/retail-shift/issues/6619)　【保守】富士通　横領収証　フッターメッセージ出ない不具合
    * 指定領収書発行問題(NonPLU値下復元でエラーPOP)対応
    
* 導入後の問題発見：

‌

PoC版\_ver2024100471

リリース日：2024/10/03

リリース対象店舗：

現時点の展開範囲店舗：

ベースバージョン：2024090571

改善ポイント：同上

導入後の問題発見：

‌
