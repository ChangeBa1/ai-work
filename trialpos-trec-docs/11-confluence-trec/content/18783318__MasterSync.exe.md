---
confluence_id: 18783318
title: "MasterSync.exe"
parent_id: 18783306
version: 5
version_at: 2024-08-22T13:05:13.000+08:00
status: current
space: POSProduct
source_url: http://documents.trechina.cn/pages/viewpage.action?pageId=18783318
synced_at: 2026-07-12
---

# MasterSync.exe

### **1. 概要**

POSシステム起動する時、マスタ同期実行する。

### **2. マスタ同期処理**

#### 2.1 一括配信

#### 2.2 差分配信

### **3. マスタ同期フロー**

#### 3.1 一括配信フロー

![マスタ一括配信フロー.png](../attachments/18783318/%E3%83%9E%E3%82%B9%E3%82%BF%E4%B8%80%E6%8B%AC%E9%85%8D%E4%BF%A1%E3%83%95%E3%83%AD%E3%83%BC.png)

①運用監視システムのマスタ一括配信画面で店舗選択して登録ボタン押下すると、Azure側のAPIをコールしてパラメーターを作成してキューに入る

三つのVMから一つを選択してAzureのDB一括配信スケジュールを実行する、キューからパラメーターを取得\
②AzureDBから対象マスタリスト取得\
③ループで、マスタデータを出力してCSVファイル作成\
④CSVファイルを圧縮して、Zip一括配信ファイル作成\
⑤AzureDBに一括配信情報作成\
⑥POS側Launcher起動する時、AzureDB一括配信情報取得\
⑦POSからAzureのZip一括配信ファイル取得\
⑧Zip一括配信ファイルを解凍して、POSDB一括更新

※②～⑤ステップはスケジュール処理です\
※⑥～⑧ステップは端末Launcher起動中の処理です

GoogleDrive参照ファイル：<https://docs.google.com/spreadsheets/d/1ugv-oBLn8ZIV0uU60E9kvC_aYFOlvzWM/edit?gid=1915637992#gid=1915637992>

#### 3.2 差分配信フロー

![マスタ差分配信フロー.png](../attachments/18783318/%E3%83%9E%E3%82%B9%E3%82%BF%E5%B7%AE%E5%88%86%E9%85%8D%E4%BF%A1%E3%83%95%E3%83%AD%E3%83%BC.png)

①外部システムからIFファイル作成して、FTPサーバーへアップロード\
②AzureからFTPサーバー上のIFファイルを取得、AzureDBデータ更新\
③AzureDB更新データより、マスタ差分同期用CSVファイル作成\
④CSVファイルを圧縮してZip差分配信ファイル作成\
⑤AzureDBに差分配信情報作成\
⑥POSからAzureDB差分配信情報取得\
⑦POSからAzureのZip差分配信ファイル取得\
⑧Zip差分配信ファイルを解凍して、POSDB差分更新

GoogleDrive参照ファイル：<https://docs.google.com/spreadsheets/d/1sWS2qfOskNc2dbMSStbmuHyDjqJ6PqP7/edit?gid=1915637992#gid=1915637992>

\

最後更新日付：2024/08/20
