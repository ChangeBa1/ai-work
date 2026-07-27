---
confluence_id: 18783328
title: "CESettingTool.exe"
parent_id: 18783306
version: 11
version_at: 2024-08-29T13:12:41.000+08:00
status: current
space: POSProduct
source_url: http://documents.trechina.cn/pages/viewpage.action?pageId=18783328
synced_at: 2026-07-12
---

# CESettingTool.exe

## 1. 概要

CESettingToolを起動し、POSシステム必要な情報を設定する

## 2. 機能一覧

<table class="wrapped fixed-table" style="margin-left: 30.0px;">
<tbody style="margin-left: 60.0px;">
<tr style="margin-left: 60.0px;">
<td class="highlight-blue" style="margin-left: 60.0px" data-highlight-colour="blue">No.</td>
<td class="highlight-blue" style="margin-left: 60.0px" data-highlight-colour="blue">画面名</td>
<td class="highlight-blue" style="margin-left: 60.0px" data-highlight-colour="blue">サブ画面</td>
<td class="highlight-blue" style="margin-left: 60.0px" data-highlight-colour="blue"><p>画面タイプ</p></td>
<td class="highlight-blue" style="margin-left: 60.0px" data-highlight-colour="blue">機能分類</td>
<td class="highlight-blue" style="margin-left: 60.0px" data-highlight-colour="blue">機能概要</td>
<td class="highlight-blue" style="margin-left: 60.0px" data-highlight-colour="blue">備考</td>
</tr>
<tr style="margin-left: 60.0px;">
<td style="text-align: right; margin-left: 60.0px;">1</td>
<td style="margin-left: 60.0px">設定モード入力</td>
<td style="margin-left: 60.0px">-</td>
<td style="margin-left: 60.0px">選択</td>
<td style="margin-left: 60.0px">設定モード選択</td>
<td style="margin-left: 60.0px">設定の機種をリストから選択する</td>
<td style="margin-left: 60.0px"><span>端末の用途設定</span></td>
</tr>
<tr style="margin-left: 60.0px;">
<td style="text-align: right; margin-left: 60.0px;">2</td>
<td style="margin-left: 60.0px"><br />
</td>
<td style="margin-left: 60.0px"><br />
</td>
<td style="margin-left: 60.0px"><br />
</td>
<td style="margin-left: 60.0px">確定ボタン</td>
<td style="margin-left: 60.0px">端末情報設定へ遷移</td>
<td style="margin-left: 60.0px"><br />
</td>
</tr>
<tr style="margin-left: 60.0px;">
<td style="text-align: right; margin-left: 60.0px;">3</td>
<td style="margin-left: 60.0px"><br />
</td>
<td style="margin-left: 60.0px"><br />
</td>
<td style="margin-left: 60.0px"><br />
</td>
<td style="margin-left: 60.0px">閉じるボタン</td>
<td style="margin-left: 60.0px">Exe自体の終了</td>
<td style="margin-left: 60.0px"><br />
</td>
</tr>
<tr style="margin-left: 60.0px;">
<td style="text-align: right; margin-left: 60.0px;">4</td>
<td style="margin-left: 60.0px"><br />
</td>
<td style="margin-left: 60.0px"><br />
</td>
<td style="margin-left: 60.0px"><br />
</td>
<td style="margin-left: 60.0px">DB初期化</td>
<td style="margin-left: 60.0px">対象テーブルのデータをクリアする及び設定のManageNoを０に設定</td>
<td style="margin-left: 60.0px"><br />
</td>
</tr>
<tr style="margin-left: 60.0px;">
<td style="text-align: right; margin-left: 60.0px;">5</td>
<td style="margin-left: 60.0px">端末情報設定</td>
<td style="margin-left: 60.0px">環境選択</td>
<td style="margin-left: 60.0px">選択</td>
<td style="margin-left: 60.0px">環境リスト</td>
<td style="margin-left: 60.0px">リストから設定環境（教育／パイロット／メイン）を選択する</td>
<td style="margin-left: 60.0px"><p><span>環境選択によって、基幹サーバとの送受信先が決定されます</span></p></td>
</tr>
<tr style="margin-left: 60.0px;">
<td style="text-align: right; margin-left: 60.0px;">6</td>
<td style="margin-left: 60.0px"><br />
</td>
<td style="margin-left: 60.0px"><br />
</td>
<td style="margin-left: 60.0px"><br />
</td>
<td style="margin-left: 60.0px">テストモードOFF/ON</td>
<td style="margin-left: 60.0px"><p>本番環境（パイロット／メイン）に設定する場合、テストモード設定コントロール<br />
OFFに設定したら、本番環境のまま利用する<br />
ONに設定したら、本番環境の一部機能は無効にして、POS機で作成したデータはAzureに送信しない</p></td>
<td style="margin-left: 60.0px"><br />
</td>
</tr>
<tr style="margin-left: 60.0px;">
<td style="text-align: right; margin-left: 60.0px;">7</td>
<td style="margin-left: 60.0px"><br />
</td>
<td style="margin-left: 60.0px">基本情報</td>
<td style="margin-left: 60.0px">選択/入力</td>
<td style="margin-left: 60.0px">端末設定</td>
<td style="margin-left: 60.0px">設定POS機の企業コード、店舗コード及び端末番号を入力する</td>
<td style="margin-left: 60.0px"><span>店舗コード、端末番号、釣銭機設定</span></td>
</tr>
<tr style="margin-left: 60.0px;">
<td style="text-align: right; margin-left: 60.0px;">8</td>
<td style="margin-left: 60.0px"><br />
</td>
<td style="margin-left: 60.0px"><br />
</td>
<td style="margin-left: 60.0px"><br />
</td>
<td style="margin-left: 60.0px">初期化</td>
<td style="margin-left: 60.0px">マネージ番号（ManageNo）を０にする</td>
<td style="margin-left: 60.0px"><br />
</td>
</tr>
<tr style="margin-left: 60.0px;">
<td style="text-align: right; margin-left: 60.0px;">9</td>
<td style="margin-left: 60.0px"><br />
</td>
<td style="margin-left: 60.0px"><br />
</td>
<td style="margin-left: 60.0px"><br />
</td>
<td style="margin-left: 60.0px">釣銭機選択</td>
<td style="margin-left: 60.0px">釣銭機の種類を選択する</td>
<td style="margin-left: 60.0px"><br />
</td>
</tr>
<tr style="margin-left: 60.0px;">
<td style="text-align: right; margin-left: 60.0px;">10</td>
<td style="margin-left: 60.0px"><br />
</td>
<td style="margin-left: 60.0px"><br />
</td>
<td style="margin-left: 60.0px"><br />
</td>
<td style="margin-left: 60.0px">POS設定</td>
<td style="margin-left: 60.0px">基本は固定で、Settingsファイルから読み込んで画面に表示する</td>
<td style="margin-left: 60.0px"><br />
</td>
</tr>
<tr style="margin-left: 60.0px;">
<td style="text-align: right; margin-left: 60.0px;">11</td>
<td style="margin-left: 60.0px"><br />
</td>
<td style="margin-left: 60.0px">端末情報設定</td>
<td style="margin-left: 60.0px">選択/入力</td>
<td style="margin-left: 60.0px">メイン画面</td>
<td style="margin-left: 60.0px">POS機画面サイズを設定する</td>
<td style="margin-left: 60.0px"><br />
</td>
</tr>
<tr style="margin-left: 60.0px;">
<td style="text-align: right; margin-left: 60.0px;">12</td>
<td style="margin-left: 60.0px"><br />
</td>
<td style="margin-left: 60.0px"><br />
</td>
<td style="margin-left: 60.0px"><br />
</td>
<td style="margin-left: 60.0px">ＩＰアドレス</td>
<td style="margin-left: 60.0px">POS機のＩＰアドレスを表示する</td>
<td style="margin-left: 60.0px"><span>事前にヒアリングした情報をセット</span></td>
</tr>
<tr style="margin-left: 60.0px;">
<td style="text-align: right; margin-left: 60.0px;">13</td>
<td style="margin-left: 60.0px"><br />
</td>
<td style="margin-left: 60.0px"><br />
</td>
<td style="margin-left: 60.0px"><br />
</td>
<td style="margin-left: 60.0px">マシン名</td>
<td style="margin-left: 60.0px">POS機のマシン名を表示する</td>
<td style="margin-left: 60.0px"><span>手動で変更</span></td>
</tr>
<tr style="margin-left: 60.0px;">
<td style="text-align: right; margin-left: 60.0px;">14</td>
<td style="margin-left: 60.0px"><br />
</td>
<td style="margin-left: 60.0px"><br />
</td>
<td style="margin-left: 60.0px"><br />
</td>
<td style="margin-left: 60.0px">ロゴファイル選択</td>
<td style="margin-left: 60.0px">レシートを印字する時頭部のログファイルを設定する</td>
<td style="margin-left: 60.0px"><br />
</td>
</tr>
<tr style="margin-left: 60.0px;">
<td style="text-align: right; margin-left: 60.0px;">15</td>
<td style="margin-left: 60.0px"><br />
</td>
<td style="margin-left: 60.0px"><br />
</td>
<td style="margin-left: 60.0px"><br />
</td>
<td style="margin-left: 60.0px">客面</td>
<td style="margin-left: 60.0px">客面ディスプレイのサイズ設定</td>
<td style="margin-left: 60.0px"><span>環境選択内容で自動セット</span></td>
</tr>
<tr style="margin-left: 60.0px;">
<td style="text-align: right; margin-left: 60.0px;">16</td>
<td style="margin-left: 60.0px"><br />
</td>
<td style="margin-left: 60.0px"><br />
</td>
<td style="margin-left: 60.0px"><br />
</td>
<td style="margin-left: 60.0px">客面位置</td>
<td style="margin-left: 60.0px">客面ディスプレイに情報表示の開始位置を設定する</td>
<td style="margin-left: 60.0px"><span>環境選択内容で自動セット</span></td>
</tr>
<tr style="margin-left: 60.0px;">
<td style="text-align: right; margin-left: 60.0px;">17</td>
<td style="margin-left: 60.0px"><br />
</td>
<td style="margin-left: 60.0px"><br />
</td>
<td style="margin-left: 60.0px"><br />
</td>
<td style="margin-left: 60.0px">画像タイプ</td>
<td style="margin-left: 60.0px">画像タイプ設定</td>
<td style="margin-left: 60.0px"><span>環境選択内容で自動セット</span></td>
</tr>
<tr style="margin-left: 60.0px;">
<td style="text-align: right; margin-left: 60.0px;">18</td>
<td style="margin-left: 60.0px"><br />
</td>
<td style="margin-left: 60.0px"><br />
</td>
<td style="margin-left: 60.0px"><br />
</td>
<td style="margin-left: 60.0px">音声タイプ</td>
<td style="margin-left: 60.0px">音声タイプ設定</td>
<td style="margin-left: 60.0px"><span>環境選択内容で自動セット</span></td>
</tr>
<tr style="margin-left: 60.0px;">
<td style="text-align: right; margin-left: 60.0px;">19</td>
<td style="margin-left: 60.0px"><br />
</td>
<td style="margin-left: 60.0px">周辺機器設定</td>
<td style="margin-left: 60.0px">選択/入力</td>
<td style="margin-left: 60.0px">設定モードPlugins</td>
<td style="margin-left: 60.0px">デビットとクレジットの有無設定</td>
<td style="margin-left: 60.0px"><br />
</td>
</tr>
<tr style="margin-left: 60.0px;">
<td style="text-align: right; margin-left: 60.0px;">20</td>
<td style="margin-left: 60.0px"><br />
</td>
<td style="margin-left: 60.0px"><br />
</td>
<td style="margin-left: 60.0px"><br />
</td>
<td style="margin-left: 60.0px">SettingDevice</td>
<td style="margin-left: 60.0px">デビットとクレジットの接続COMとボーレート設定</td>
<td style="margin-left: 60.0px"><br />
</td>
</tr>
<tr style="margin-left: 60.0px;">
<td style="text-align: right; margin-left: 60.0px;">21</td>
<td style="margin-left: 60.0px"><br />
</td>
<td style="margin-left: 60.0px">外部サービス設定</td>
<td style="margin-left: 60.0px">表示</td>
<td style="margin-left: 60.0px">-</td>
<td style="margin-left: 60.0px">外部サービスのURLとかの設定情報表示（VD,PA,CRM、RetailMedia）</td>
<td style="margin-left: 60.0px"><br />
</td>
</tr>
<tr style="margin-left: 60.0px;">
<td style="text-align: right; margin-left: 60.0px;">22</td>
<td style="margin-left: 60.0px"><br />
</td>
<td style="margin-left: 60.0px"><br />
</td>
<td style="margin-left: 60.0px"><br />
</td>
<td style="margin-left: 60.0px">接続確認ボタン</td>
<td style="margin-left: 60.0px">外部サービスへ接続できる可否を確認する</td>
<td style="margin-left: 60.0px"><br />
</td>
</tr>
<tr style="margin-left: 60.0px;">
<td style="text-align: right; margin-left: 60.0px;">23</td>
<td style="margin-left: 60.0px"><br />
</td>
<td style="margin-left: 60.0px">DB操作</td>
<td style="margin-left: 60.0px">更新</td>
<td style="margin-left: 60.0px">初期化</td>
<td style="margin-left: 60.0px">対象テーブルのデータをクリアする及び設定のManageNoを０に設定</td>
<td style="margin-left: 60.0px"><br />
</td>
</tr>
<tr style="margin-left: 60.0px;">
<td style="text-align: right; margin-left: 60.0px;">24</td>
<td style="margin-left: 60.0px"><br />
</td>
<td style="margin-left: 60.0px"><br />
</td>
<td style="margin-left: 60.0px"><br />
</td>
<td style="margin-left: 60.0px">チャージポイントGrid</td>
<td style="margin-left: 60.0px">チャージポイントの情報表示、メンテ可</td>
<td style="margin-left: 60.0px"><br />
</td>
</tr>
<tr style="margin-left: 60.0px;">
<td style="text-align: right; margin-left: 60.0px;">25</td>
<td style="margin-left: 60.0px"><br />
</td>
<td style="margin-left: 60.0px"><br />
</td>
<td style="margin-left: 60.0px"><br />
</td>
<td style="margin-left: 60.0px">チャージポイント計算マスタ更新ボタン</td>
<td style="margin-left: 60.0px">Gridに表示（メンテ）したデータをDBのテーブルに反映する</td>
<td style="margin-left: 60.0px"><br />
</td>
</tr>
<tr style="margin-left: 60.0px;">
<td style="text-align: right; margin-left: 60.0px;">26</td>
<td style="margin-left: 60.0px"><br />
</td>
<td style="margin-left: 60.0px"><br />
</td>
<td style="margin-left: 60.0px"><br />
</td>
<td style="margin-left: 60.0px">戻るボタン</td>
<td style="margin-left: 60.0px">環境選択画面に戻る、初期データを再ロードする</td>
<td style="margin-left: 60.0px"><br />
</td>
</tr>
<tr style="margin-left: 60.0px;">
<td style="text-align: right; margin-left: 60.0px;">27</td>
<td style="margin-left: 60.0px"><br />
</td>
<td style="margin-left: 60.0px">-</td>
<td style="margin-left: 60.0px">更新</td>
<td style="margin-left: 60.0px">確定ボタン</td>
<td style="margin-left: 60.0px">ツールに設定した情報をSettingsファイルに更新する</td>
<td style="margin-left: 60.0px"><br />
</td>
</tr>
<tr style="margin-left: 60.0px;">
<td style="text-align: right; margin-left: 60.0px;">28</td>
<td style="margin-left: 60.0px"><br />
</td>
<td style="margin-left: 60.0px"><br />
</td>
<td style="margin-left: 60.0px"><br />
</td>
<td style="margin-left: 60.0px">閉じるボタン</td>
<td style="margin-left: 60.0px">Exe自体の終了</td>
<td style="margin-left: 60.0px"><br />
</td>
</tr>
</tbody>
</table>

\

GoogleDrive参照：<https://docs.google.com/spreadsheets/d/1C3-AW9KIJNRkJG6dXSysQVKG2XIpzWimE77kUZ5-FnY/edit?gid=2062669387#gid=2062669387>

\

最後更新日付：2024/08/20
