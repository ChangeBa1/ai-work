---
confluence_id: 18783350
title: "SettingMaster"
parent_id: 18783346
version: 2
version_at: 2024-08-27T10:35:55.000+08:00
status: current
space: POSProduct
source_url: http://documents.trechina.cn/pages/viewpage.action?pageId=18783350
synced_at: 2026-07-12
---

# SettingMaster

\

<table class="fixed-table">
<tbody>
<tr>
<td rowspan="2" class="highlight-blue" data-highlight-colour="blue"><p>No.</p></td>
<td class="highlight-blue" data-highlight-colour="blue">企業コード</td>
<td class="highlight-blue" data-highlight-colour="blue">店舗コード</td>
<td class="highlight-blue" data-highlight-colour="blue">端末番号</td>
<td class="highlight-blue" data-highlight-colour="blue">キー</td>
<td class="highlight-blue" data-highlight-colour="blue">バリュー</td>
<td rowspan="2" class="highlight-blue" data-highlight-colour="blue"><br />
関連機能</td>
<td rowspan="2" class="highlight-blue" data-highlight-colour="blue"><br />
取得方法</td>
<td rowspan="2" class="highlight-blue" data-highlight-colour="blue"><br />
企業別</td>
<td rowspan="2" class="highlight-blue" data-highlight-colour="blue"><br />
店舗別</td>
<td rowspan="2" class="highlight-blue" data-highlight-colour="blue"><br />
端末別</td>
<td rowspan="2" class="highlight-blue" data-highlight-colour="blue"><br />
ディフォルト値</td>
<td rowspan="2" class="highlight-blue" data-highlight-colour="blue"><br />
取得失敗Log</td>
</tr>
<tr>
<td class="highlight-blue" data-highlight-colour="blue">CompanyCode</td>
<td class="highlight-blue" data-highlight-colour="blue">StoreCode</td>
<td class="highlight-blue" data-highlight-colour="blue">TerminalNo</td>
<td class="highlight-blue" data-highlight-colour="blue">Key</td>
<td class="highlight-blue" data-highlight-colour="blue">Value</td>
</tr>
<tr>
<td style="text-align: right;">1</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>AccessCode</td>
<td style="text-align: right;">12345</td>
<td>LogicService</td>
<td>ー</td>
<td><br />
</td>
<td><br />
</td>
<td><br />
</td>
<td style="text-align: center;">ー</td>
<td style="text-align: center;">ー</td>
</tr>
<tr>
<td style="text-align: right;">2</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>BestBeforeTimeHourInterval</td>
<td style="text-align: right;">0</td>
<td>26桁JAN</td>
<td>GetValue(企業コード,店舗コード,0)</td>
<td>〇</td>
<td>〇</td>
<td><br />
</td>
<td style="text-align: center;">2</td>
<td style="text-align: center;">INFO</td>
</tr>
<tr>
<td style="text-align: right;">3</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>BIReportLimitDaysInThePast</td>
<td style="text-align: right;">3</td>
<td>BIレポート</td>
<td>GetValue(企業コード,Empty,0)</td>
<td>〇</td>
<td><br />
</td>
<td><br />
</td>
<td style="text-align: center;">ー</td>
<td style="text-align: center;">ー</td>
</tr>
<tr>
<td style="text-align: right;">4</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>CashChangerDispenseChangeRetryCount</td>
<td style="text-align: right;">3</td>
<td>お釣り</td>
<td>GetValues(企業コード,Empty,0)</td>
<td>〇</td>
<td><br />
</td>
<td><br />
</td>
<td style="text-align: center;">3</td>
<td style="text-align: center;">ー</td>
</tr>
<tr>
<td style="text-align: right;">5</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>CashChangerDispenseChangeRetryTime</td>
<td style="text-align: right;">1000</td>
<td>お釣り</td>
<td>GetValues(企業コード,Empty,0)</td>
<td>〇</td>
<td><br />
</td>
<td><br />
</td>
<td style="text-align: center;">1000</td>
<td style="text-align: center;">ー</td>
</tr>
<tr>
<td style="text-align: right;">6</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>CashInSleepMillisecond</td>
<td style="text-align: right;">9000</td>
<td>未精算音声</td>
<td>GetValues(企業コード,店舗コード,0)</td>
<td>〇</td>
<td>〇</td>
<td><br />
</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">ー</td>
</tr>
<tr>
<td style="text-align: right;">7</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>CashInSleepMillisecondShort</td>
<td style="text-align: right;">2000</td>
<td>未精算音声</td>
<td>GetValues(企業コード,店舗コード,0)</td>
<td>〇</td>
<td>〇</td>
<td><br />
</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">ー</td>
</tr>
<tr>
<td style="text-align: right;">8</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>ChargePayment</td>
<td style="text-align: right;">1</td>
<td>チャージ</td>
<td>GetValue(企業コード,店舗コード,0)</td>
<td>〇</td>
<td>〇</td>
<td><br />
</td>
<td style="text-align: center;">NULL</td>
<td style="text-align: center;">ー</td>
</tr>
<tr>
<td style="text-align: right;">9</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>CRMBaseURL</td>
<td><span class="nolink">http://tcloud.trechina.cn</span></td>
<td>オーダー</td>
<td>GetValue(企業コード,店舗コード,端末Id)</td>
<td>〇</td>
<td><br />
</td>
<td>〇</td>
<td style="text-align: center;">ー</td>
<td style="text-align: center;">WARN</td>
</tr>
<tr>
<td style="text-align: right;">10</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>CRMPointServiceAccessToken</td>
<td>82b33ca1cdd8b7abe4d16795c0ccc3bd</td>
<td>チャージポイント</td>
<td>GetValues(企業コード,店舗コード,端末Id)</td>
<td>〇</td>
<td>〇</td>
<td>〇</td>
<td style="text-align: center;">ー</td>
<td style="text-align: center;">ー</td>
</tr>
<tr>
<td style="text-align: right;">11</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>CRMPointServiceURL</td>
<td>http://0.0.0.0/PPM/Service.asmx</td>
<td>チャージポイント</td>
<td>GetValues(企業コード,店舗コード,端末Id)</td>
<td>〇</td>
<td>〇</td>
<td>〇</td>
<td style="text-align: center;">ー</td>
<td style="text-align: center;">ー</td>
</tr>
<tr>
<td style="text-align: right;">12</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>CRMServiceRetryCount</td>
<td style="text-align: right;">5</td>
<td>オーダー</td>
<td>GetValue(企業コード,店舗コード,端末Id)</td>
<td>〇</td>
<td><br />
</td>
<td>〇</td>
<td style="text-align: center;">5</td>
<td style="text-align: center;">ー</td>
</tr>
<tr>
<td style="text-align: right;">13</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>CRMServiceRetryInterval</td>
<td style="text-align: right;">5000</td>
<td>オーダー</td>
<td>GetValue(企業コード,店舗コード,端末Id)</td>
<td>〇</td>
<td><br />
</td>
<td>〇</td>
<td style="text-align: center;">5000</td>
<td style="text-align: center;">ー</td>
</tr>
<tr>
<td style="text-align: right;">14</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>CRMServiceTimeout</td>
<td style="text-align: right;">5000</td>
<td>オーダー</td>
<td>GetValue(企業コード,店舗コード,端末Id)</td>
<td>〇</td>
<td><br />
</td>
<td>〇</td>
<td style="text-align: center;">30000</td>
<td style="text-align: center;">ー</td>
</tr>
<tr>
<td style="text-align: right;">15</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>DangoActivateEndPoint</td>
<td>card/activate</td>
<td>Dango</td>
<td>GetValues(企業コード,店舗コード,端末Id)</td>
<td>〇</td>
<td>〇</td>
<td>〇</td>
<td><br />
</td>
<td><br />
</td>
</tr>
<tr>
<td style="text-align: right;">16</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>DangoAzureToken</td>
<td>eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZXJtaW5hbF9pZCI6MTA5MDAxMDAxfQ.-VCRdx9p9ql3aIqzS5QfkuS9EVveDckhjjGnE9vzQP0</td>
<td>Dango</td>
<td>GetValues(企業コード,店舗コード,端末Id)</td>
<td>〇</td>
<td>〇</td>
<td>〇</td>
<td><br />
</td>
<td><br />
</td>
</tr>
<tr>
<td style="text-align: right;">17</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>DangoBalanceEndPoint</td>
<td>card/balance</td>
<td>Dango</td>
<td>GetValues(企業コード,店舗コード,端末Id)</td>
<td>〇</td>
<td>〇</td>
<td>〇</td>
<td><br />
</td>
<td><br />
</td>
</tr>
<tr>
<td style="text-align: right;">18</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>DangoChargeCancelEndPoint</td>
<td>card/charge/cancel</td>
<td>Dango</td>
<td>GetValues(企業コード,店舗コード,端末Id)</td>
<td>〇</td>
<td>〇</td>
<td>〇</td>
<td><br />
</td>
<td><br />
</td>
</tr>
<tr>
<td style="text-align: right;">19</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>DangoChargeEndPoint</td>
<td>card/charge</td>
<td>Dango</td>
<td>GetValues(企業コード,店舗コード,端末Id)</td>
<td>〇</td>
<td>〇</td>
<td>〇</td>
<td><br />
</td>
<td><br />
</td>
</tr>
<tr>
<td style="text-align: right;">20</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>DangoCompanyCode</td>
<td style="text-align: right;">1</td>
<td>Dango</td>
<td>GetValues(企業コード,店舗コード,端末Id)</td>
<td>〇</td>
<td>〇</td>
<td>〇</td>
<td><br />
</td>
<td><br />
</td>
</tr>
<tr>
<td style="text-align: right;">21</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>DangoForceCancelEndPoint</td>
<td>card/request/cancel</td>
<td>Dango</td>
<td>GetValues(企業コード,店舗コード,端末Id)</td>
<td>〇</td>
<td>〇</td>
<td>〇</td>
<td><br />
</td>
<td><br />
</td>
</tr>
<tr>
<td style="text-align: right;">22</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>DangoPurchaseEndPoint</td>
<td>card/purchase</td>
<td>Dango</td>
<td>GetValues(企業コード,店舗コード,端末Id)</td>
<td>〇</td>
<td>〇</td>
<td>〇</td>
<td><br />
</td>
<td><br />
</td>
</tr>
<tr>
<td style="text-align: right;">23</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>DangoTokenPrefix</td>
<td>Bearer</td>
<td>Dango</td>
<td>GetValues(企業コード,店舗コード,端末Id)</td>
<td>〇</td>
<td>〇</td>
<td>〇</td>
<td><br />
</td>
<td><br />
</td>
</tr>
<tr>
<td style="text-align: right;">24</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>DangoTrainingCardLeadString</td>
<td style="text-align: right;">299</td>
<td>Dango</td>
<td>GetValues(企業コード,店舗コード,端末Id)</td>
<td>〇</td>
<td>〇</td>
<td>〇</td>
<td><br />
</td>
<td><br />
</td>
</tr>
<tr>
<td style="text-align: right;">25</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>DiscountRoundDigits</td>
<td style="text-align: right;">0</td>
<td>値引き</td>
<td>GetValues(企業コード,店舗コード,端末Id)</td>
<td>〇</td>
<td>〇</td>
<td>〇</td>
<td style="text-align: center;">ー</td>
<td style="text-align: center;">ー</td>
</tr>
<tr>
<td style="text-align: right;">26</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>DiscountRoundType</td>
<td style="text-align: right;">2</td>
<td>値引き</td>
<td>GetValues(企業コード,店舗コード,端末Id)</td>
<td>〇</td>
<td>〇</td>
<td>〇</td>
<td style="text-align: center;">ー</td>
<td style="text-align: center;">ー</td>
</tr>
<tr>
<td style="text-align: right;">27</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>ElectronicMoneyDeviceId</td>
<td>ValueCard</td>
<td>Dango</td>
<td>GetValue(企業コード,店舗コード,0)</td>
<td>〇</td>
<td>〇</td>
<td><br />
</td>
<td><br />
</td>
<td><br />
</td>
</tr>
<tr>
<td style="text-align: right;">28</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>EmployeeCardServiceURL</td>
<td><span style="color: rgb(0,0,0);"><span class="nolink">http://0.0.0.0/EmployeeCard/Service.asmx/getEmployeeCard?card=</span>{0}&amp;Token={1}</span></td>
<td>給料天引き</td>
<td>GetValue(企業コード,店舗コード,0)</td>
<td>〇</td>
<td>〇</td>
<td><br />
</td>
<td style="text-align: center;">ー</td>
<td style="text-align: center;">ERROR</td>
</tr>
<tr>
<td style="text-align: right;">29</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>FaceMeHealthCheckRequestTimeout</td>
<td style="text-align: right;">10000</td>
<td>顔認証</td>
<td>GetValues(企業コード,店舗コード,端末Id)</td>
<td>〇</td>
<td>〇</td>
<td>〇</td>
<td style="text-align: center;">10000</td>
<td style="text-align: center;">ERROR</td>
</tr>
<tr>
<td style="text-align: right;">30</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>FaceMePinInputCount</td>
<td style="text-align: right;">5</td>
<td>顔認証</td>
<td>GetValues(企業コード,店舗コード,端末Id)</td>
<td>〇</td>
<td>〇</td>
<td>〇</td>
<td style="text-align: center;">5</td>
<td style="text-align: center;">ERROR</td>
</tr>
<tr>
<td style="text-align: right;">31</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>FaceMeSecondRequestTimeout</td>
<td style="text-align: right;">10000</td>
<td>顔認証</td>
<td>GetValues(企業コード,店舗コード,端末Id)</td>
<td>〇</td>
<td>〇</td>
<td>〇</td>
<td style="text-align: center;">10000</td>
<td style="text-align: center;">ERROR</td>
</tr>
<tr>
<td style="text-align: right;">32</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>FaceMeStartParamTimeout</td>
<td style="text-align: right;">30</td>
<td>顔認証</td>
<td>GetValues(企業コード,店舗コード,端末Id)</td>
<td>〇</td>
<td>〇</td>
<td>〇</td>
<td style="text-align: center;">10</td>
<td style="text-align: center;">ERROR</td>
</tr>
<tr>
<td style="text-align: right;">33</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>FaceMeStartRequestTimeout</td>
<td style="text-align: right;">30000</td>
<td>顔認証</td>
<td>GetValues(企業コード,店舗コード,端末Id)</td>
<td>〇</td>
<td>〇</td>
<td>〇</td>
<td style="text-align: center;">30000</td>
<td style="text-align: center;">ERROR</td>
</tr>
<tr>
<td style="text-align: right;">34</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>FaceMeStopRequestTimeout</td>
<td style="text-align: right;">30000</td>
<td>顔認証</td>
<td>GetValues(企業コード,店舗コード,端末Id)</td>
<td>〇</td>
<td>〇</td>
<td>〇</td>
<td style="text-align: center;">30000</td>
<td style="text-align: center;">ERROR</td>
</tr>
<tr>
<td style="text-align: right;">35</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>HomeOfficeQuickEmployeeServiceURL</td>
<td><span style="color: rgb(0,0,0);"><span class="nolink">http://0.0.0.0/EmployeeCard/Service.asmx/getEmployeeCard?card=</span>{0}&amp;Token={1}</span></td>
<td>給料天引き</td>
<td>GetValue(企業コード,店舗コード,0)</td>
<td>〇</td>
<td>〇</td>
<td><br />
</td>
<td style="text-align: center;">ー</td>
<td style="text-align: center;">ERROR</td>
</tr>
<tr>
<td style="text-align: right;">36</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>IsBestBeforeTarget</td>
<td style="text-align: center;">TRUE</td>
<td>26桁JAN</td>
<td>GetValue(企業コード,店舗コード,0)</td>
<td>〇</td>
<td>〇</td>
<td><br />
</td>
<td style="text-align: center;">FALSE</td>
<td style="text-align: center;">INFO</td>
</tr>
<tr>
<td style="text-align: right;">37</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>IsDynamicPricingTarget</td>
<td style="text-align: center;">TRUE</td>
<td>ダイナミックプライス</td>
<td>GetValue(企業コード,店舗コード,0)</td>
<td>〇</td>
<td>〇</td>
<td><br />
</td>
<td style="text-align: center;">FALSE</td>
<td style="text-align: center;">INFO</td>
</tr>
<tr>
<td style="text-align: right;">38</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>IsEJournalBackupTarget</td>
<td style="text-align: center;">FALSE</td>
<td>Azure</td>
<td>GetValue(企業コード,店舗コード,0)</td>
<td>〇</td>
<td>〇</td>
<td><br />
</td>
<td style="text-align: center;">ー</td>
<td style="text-align: center;">ー</td>
</tr>
<tr>
<td style="text-align: right;">39</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>IsFaceMe</td>
<td style="text-align: center;">FALSE</td>
<td>顔認証</td>
<td>GetValue(企業コード,店舗コード,0)</td>
<td>〇</td>
<td>〇</td>
<td><br />
</td>
<td style="text-align: center;">FALSE</td>
<td style="text-align: center;">WARN</td>
</tr>
<tr>
<td style="text-align: right;">40</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>IsHyBridMode</td>
<td style="text-align: center;">FALSE</td>
<td>ハイブリッド</td>
<td>GetValue(企業コード,店舗コード,0)</td>
<td>〇</td>
<td>〇</td>
<td><br />
</td>
<td style="text-align: center;">FALSE</td>
<td style="text-align: center;">ー</td>
</tr>
<tr>
<td style="text-align: right;">41</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>IsManjyuBarcodeNullItemTarget</td>
<td style="text-align: center;">FALSE</td>
<td>ISM</td>
<td>GetValue(企業コード,店舗コード,0)</td>
<td>〇</td>
<td>〇</td>
<td><br />
</td>
<td style="text-align: center;">FALSE</td>
<td style="text-align: center;">WARN</td>
</tr>
<tr>
<td style="text-align: right;">42</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>IsOfflineCreditDeviceCheck</td>
<td style="text-align: center;">FALSE</td>
<td>オフラインクレジット</td>
<td>GetValue(企業コード,店舗コード,0)</td>
<td>〇</td>
<td>〇</td>
<td><br />
</td>
<td style="text-align: center;">FALSE</td>
<td style="text-align: center;">WARN</td>
</tr>
<tr>
<td style="text-align: right;">43</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>IsOTCDrugSales</td>
<td style="text-align: center;">TRUE</td>
<td>医薬品</td>
<td>GetValues(企業コード,店舗コード,端末Id)</td>
<td>〇</td>
<td>〇</td>
<td>〇</td>
<td style="text-align: center;">FALSE</td>
<td style="text-align: center;">ー</td>
</tr>
<tr>
<td style="text-align: right;">44</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>IsPointCalcAmountWithNoTaxes</td>
<td style="text-align: center;">TRUE</td>
<td>ポイント</td>
<td>GetValues(企業コード,店舗コード,端末Id)</td>
<td>〇</td>
<td>〇</td>
<td>〇</td>
<td style="text-align: center;">ー</td>
<td style="text-align: center;">ー</td>
</tr>
<tr>
<td style="text-align: right;">45</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>IsPointCalcRateGroupCheck</td>
<td style="text-align: center;">FALSE</td>
<td>ポイント</td>
<td>GetValues(企業コード,店舗コード,端末Id)</td>
<td>〇</td>
<td>〇</td>
<td>〇</td>
<td style="text-align: center;">ー</td>
<td style="text-align: center;">ー</td>
</tr>
<tr>
<td style="text-align: right;">46</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>IsPointDetailRealShow</td>
<td style="text-align: center;">FALSE</td>
<td>Azure</td>
<td>GetValue(企業コード,店舗コード,0)</td>
<td>〇</td>
<td>〇</td>
<td><br />
</td>
<td style="text-align: center;">ー</td>
<td style="text-align: center;">ー</td>
</tr>
<tr>
<td style="text-align: right;">47</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>IsRemoteAgeConfirm</td>
<td style="text-align: center;">FALSE</td>
<td>リモート年齢確認</td>
<td>GetValue(企業コード,店舗コード,0)</td>
<td>〇</td>
<td>〇</td>
<td><br />
</td>
<td style="text-align: center;">FALSE</td>
<td style="text-align: center;">WARN</td>
</tr>
<tr>
<td style="text-align: right;">48</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>IsSalaryDeductionTarget</td>
<td style="text-align: center;">FALSE</td>
<td>給料天引き</td>
<td>GetValue(企業コード,店舗コード,0)</td>
<td>〇</td>
<td>〇</td>
<td><br />
</td>
<td style="text-align: center;">FALSE</td>
<td style="text-align: center;">ー</td>
</tr>
<tr>
<td style="text-align: right;">49</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>IsV2EJournalBackupAddress</td>
<td><br />
</td>
<td>Azure</td>
<td>GetValue(企業コード,店舗コード,0)</td>
<td>〇</td>
<td>〇</td>
<td><br />
</td>
<td style="text-align: center;">TRUE</td>
<td style="text-align: center;">ー</td>
</tr>
<tr>
<td style="text-align: right;">50</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>IsV2EJournalBackupTarget</td>
<td style="text-align: center;">TRUE</td>
<td>Azure</td>
<td>GetValue(企業コード,店舗コード,0)</td>
<td>〇</td>
<td>〇</td>
<td><br />
</td>
<td style="text-align: center;">ー</td>
<td style="text-align: center;">ー</td>
</tr>
<tr>
<td style="text-align: right;">51</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>ItemScanNoOperateSleepMillisecond</td>
<td style="text-align: right;">35000</td>
<td>未精算音声</td>
<td>GetValues(企業コード,店舗コード,0)</td>
<td>〇</td>
<td>〇</td>
<td><br />
</td>
<td style="text-align: center;">35000</td>
<td style="text-align: center;">ー</td>
</tr>
<tr>
<td style="text-align: right;">52</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>ItemScanNoOperateSleepMillisecondShort</td>
<td style="text-align: right;">30000</td>
<td>未精算音声</td>
<td>GetValues(企業コード,店舗コード,0)</td>
<td>〇</td>
<td>〇</td>
<td><br />
</td>
<td style="text-align: center;">30000</td>
<td style="text-align: center;">ー</td>
</tr>
<tr>
<td style="text-align: right;">53</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>ManjyuApiClientId</td>
<td>test_OLCMSof1uYvU6vmDX4IaODSJBIvd1sElqHIvBEbB8Up</td>
<td>Manjyu</td>
<td>GetValue(企業コード,店舗コード,0)</td>
<td>〇</td>
<td>〇</td>
<td><br />
</td>
<td style="text-align: center;">ー</td>
<td style="text-align: center;">WARN</td>
</tr>
<tr>
<td style="text-align: right;">54</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>ManjyuApiClientSecret</td>
<td>test_X4LZbCMGCLFeAgczFhTtmFXpY3cFvDvwKKqqofkNxfg</td>
<td>Manjyu</td>
<td>GetValue(企業コード,店舗コード,0)</td>
<td>〇</td>
<td>〇</td>
<td><br />
</td>
<td style="text-align: center;">ー</td>
<td style="text-align: center;">WARN</td>
</tr>
<tr>
<td style="text-align: right;">55</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>ManjyuApiServiceBaseURL</td>
<td>sandbox.raicart.io</td>
<td>Manjyu</td>
<td>GetValue(企業コード,店舗コード,0)</td>
<td>〇</td>
<td>〇</td>
<td><br />
</td>
<td style="text-align: center;">ー</td>
<td style="text-align: center;">WARN</td>
</tr>
<tr>
<td style="text-align: right;">56</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>ManjyuApiServiceHybridCancelURL</td>
<td>v1/user/hook/hybrid/cart/cancel</td>
<td>ハイブリッド・饅頭</td>
<td>GetValue(企業コード,店舗コード,0)</td>
<td>〇</td>
<td>〇</td>
<td><br />
</td>
<td style="text-align: center;">ー</td>
<td style="text-align: center;">ー</td>
</tr>
<tr>
<td style="text-align: right;">57</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>ManjyuApiServiceHybridPaymentURL</td>
<td>v1/user/hook/hybrid/payment/finalize</td>
<td>ハイブリッド・饅頭</td>
<td>GetValue(企業コード,店舗コード,0)</td>
<td>〇</td>
<td>〇</td>
<td><br />
</td>
<td style="text-align: center;">ー</td>
<td style="text-align: center;">ー</td>
</tr>
<tr>
<td style="text-align: right;">58</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>ManjyuApiServiceHybridTimeout</td>
<td style="text-align: right;">5000</td>
<td>ハイブリッドAzure・饅頭</td>
<td>GetValue(企業コード,店舗コード,0)</td>
<td>〇</td>
<td>〇</td>
<td><br />
</td>
<td style="text-align: center;">ー</td>
<td style="text-align: center;">ー</td>
</tr>
<tr>
<td style="text-align: right;">59</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>ManjyuApiUpdateBalanceTimes</td>
<td style="text-align: right;">1</td>
<td>Manjyu</td>
<td>GetValue(企業コード,店舗コード,0)</td>
<td>〇</td>
<td>〇</td>
<td><br />
</td>
<td style="text-align: center;">1</td>
<td style="text-align: center;">ー</td>
</tr>
<tr>
<td style="text-align: right;">60</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>MemberServiceValueStoreCode</td>
<td style="text-align: right;">9</td>
<td>MemberAPI</td>
<td>GetValues(企業コード,Empty,0)</td>
<td>〇</td>
<td><br />
</td>
<td><br />
</td>
<td style="text-align: center;">ー</td>
<td style="text-align: center;">ー</td>
</tr>
<tr>
<td style="text-align: right;">61</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>MemberServiceValueTerminalNo</td>
<td style="text-align: right;">9</td>
<td>MemberAPI</td>
<td>GetValues(企業コード,Empty,0)</td>
<td>〇</td>
<td><br />
</td>
<td><br />
</td>
<td style="text-align: center;">ー</td>
<td style="text-align: center;">ー</td>
</tr>
<tr>
<td style="text-align: right;">62</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>MMSplitRoundType</td>
<td style="text-align: right;">2</td>
<td>M&amp;M</td>
<td>GetValues(企業コード,店舗コード,端末Id)</td>
<td>〇</td>
<td>〇</td>
<td>〇</td>
<td style="text-align: center;">ー</td>
<td style="text-align: center;">ー</td>
</tr>
<tr>
<td style="text-align: right;">63</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>MSRReadNodeTypes</td>
<td>08,09,10,13</td>
<td>MSR</td>
<td>GetValue(企業コード,店舗コード,0)</td>
<td>〇</td>
<td>〇</td>
<td><br />
</td>
<td style="text-align: center;">ー</td>
<td style="text-align: center;">ー</td>
</tr>
<tr>
<td style="text-align: right;">64</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>OneTimeBarcodeBaseTime</td>
<td style="text-align: right;">2018-01-01 0:00:00</td>
<td>ワンタイムバーコード</td>
<td>GetValue(企業コード,Empty,0)<br />
GetValue(企業コード,店舗コード,端末Id)</td>
<td>〇</td>
<td><br />
</td>
<td>〇</td>
<td style="text-align: center;">ー</td>
<td style="text-align: center;">ー</td>
</tr>
<tr>
<td style="text-align: right;">65</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>OTCDrugNodeTypes</td>
<td>10,11</td>
<td>医薬品</td>
<td>GetValues(企業コード,店舗コード,端末Id)</td>
<td>〇</td>
<td>〇</td>
<td>〇</td>
<td style="text-align: center;">ー</td>
<td style="text-align: center;">WARN</td>
</tr>
<tr>
<td style="text-align: right;">66</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>PaymentConfirmSleepMillisecond</td>
<td style="text-align: right;">0</td>
<td>未精算音声</td>
<td>GetValues(企業コード,店舗コード,0)</td>
<td>〇</td>
<td>〇</td>
<td><br />
</td>
<td style="text-align: center;">4500</td>
<td style="text-align: center;">ー</td>
</tr>
<tr>
<td style="text-align: right;">67</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>PointBaseAmount</td>
<td style="text-align: right;">200</td>
<td>ポイント</td>
<td>GetValues(企業コード,店舗コード,端末Id)</td>
<td>〇</td>
<td>〇</td>
<td>〇</td>
<td style="text-align: center;">ー</td>
<td style="text-align: center;">ー</td>
</tr>
<tr>
<td style="text-align: right;">68</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>PointCalcRoundType</td>
<td style="text-align: right;">3</td>
<td>ポイント</td>
<td>GetValues(企業コード,店舗コード,端末Id)</td>
<td>〇</td>
<td>〇</td>
<td>〇</td>
<td style="text-align: center;">ー</td>
<td style="text-align: center;">ー</td>
</tr>
<tr>
<td style="text-align: right;">69</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>PointNormalRate</td>
<td style="text-align: right;">1</td>
<td>ポイント</td>
<td>GetValues(企業コード,店舗コード,端末Id)</td>
<td>〇</td>
<td>〇</td>
<td>〇</td>
<td style="text-align: center;">ー</td>
<td style="text-align: center;">ー</td>
</tr>
<tr>
<td style="text-align: right;">70</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>PointServiceIPAddress</td>
<td>10.2.10.110</td>
<td>PointService</td>
<td>GetValues(企業コード,店舗コード,端末Id)</td>
<td>〇</td>
<td>〇</td>
<td>〇</td>
<td style="text-align: center;">ー</td>
<td style="text-align: center;">ー</td>
</tr>
<tr>
<td style="text-align: right;">71</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>PointServicePortNo</td>
<td style="text-align: right;">51001</td>
<td>PointService</td>
<td>GetValues(企業コード,店舗コード,端末Id)</td>
<td>〇</td>
<td>〇</td>
<td>〇</td>
<td style="text-align: center;">ー</td>
<td style="text-align: center;">ー</td>
</tr>
<tr>
<td style="text-align: right;">72</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>PointServiceReadTimeout</td>
<td style="text-align: right;">5000</td>
<td>PointService</td>
<td>GetValues(企業コード,店舗コード,端末Id)</td>
<td>〇</td>
<td>〇</td>
<td>〇</td>
<td style="text-align: center;">ー</td>
<td style="text-align: center;">ー</td>
</tr>
<tr>
<td style="text-align: right;">73</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>PointServiceTcpConnectTimeout</td>
<td style="text-align: right;">5000</td>
<td>PointService</td>
<td>GetValues(企業コード,店舗コード,端末Id)</td>
<td>〇</td>
<td>〇</td>
<td>〇</td>
<td style="text-align: center;">ー</td>
<td style="text-align: center;">ー</td>
</tr>
<tr>
<td style="text-align: right;">74</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>PointServiceWriteTimeout</td>
<td style="text-align: right;">5000</td>
<td>PointService</td>
<td>GetValues(企業コード,店舗コード,端末Id)</td>
<td>〇</td>
<td>〇</td>
<td>〇</td>
<td style="text-align: center;">ー</td>
<td style="text-align: center;">ー</td>
</tr>
<tr>
<td style="text-align: right;">75</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>RecommendationCouponApplyAPI</td>
<td>/recommendation/coupon/apply</td>
<td>RM</td>
<td>GetValue(企業コード,店舗コード,端末Id)</td>
<td>〇</td>
<td><br />
</td>
<td>〇</td>
<td style="text-align: center;">ー</td>
<td style="text-align: center;">ー</td>
</tr>
<tr>
<td style="text-align: right;">76</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>RemoteAgeConfirmStartParamTimeout</td>
<td style="text-align: right;">180</td>
<td>リモート年齢確認</td>
<td>GetValues(企業コード,店舗コード,端末Id)</td>
<td>〇</td>
<td>〇</td>
<td>〇</td>
<td style="text-align: center;">180</td>
<td style="text-align: center;">ERROR</td>
</tr>
<tr>
<td style="text-align: right;">77</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>RemoteAgeConfirmStartRequestTimeout</td>
<td style="text-align: right;">180000</td>
<td>リモート年齢確認</td>
<td>GetValues(企業コード,店舗コード,端末Id)</td>
<td>〇</td>
<td>〇</td>
<td>〇</td>
<td style="text-align: center;">180000</td>
<td style="text-align: center;">ERROR</td>
</tr>
<tr>
<td style="text-align: right;">78</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>RemoteAgeConfirmStopRequestTimeout</td>
<td style="text-align: right;">30000</td>
<td>リモート年齢確認</td>
<td>GetValues(企業コード,店舗コード,端末Id)</td>
<td>〇</td>
<td>〇</td>
<td>〇</td>
<td style="text-align: center;">30000</td>
<td style="text-align: center;">ERROR</td>
</tr>
<tr>
<td style="text-align: right;">79</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>RetailMediaEnterpriseCode</td>
<td>company1</td>
<td>RM</td>
<td>GetValues(企業コード,店舗コード,端末Id)</td>
<td>〇</td>
<td>〇</td>
<td>〇</td>
<td style="text-align: center;">ー</td>
<td style="text-align: center;">ー</td>
</tr>
<tr>
<td style="text-align: right;">80</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>RetailMediaServiceAccessCode</td>
<td>hxG9rzPcEGuth8ND489jdw==</td>
<td>RM</td>
<td>GetValues(企業コード,店舗コード,端末Id)</td>
<td>〇</td>
<td>〇</td>
<td>〇</td>
<td style="text-align: center;">ー</td>
<td style="text-align: center;">ー</td>
</tr>
<tr>
<td style="text-align: right;">81</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>RetailMediaServiceBaseURL</td>
<td><br />
</td>
<td>RM</td>
<td>GetValue(企業コード,店舗コード,端末Id)</td>
<td>〇</td>
<td><br />
</td>
<td>〇</td>
<td style="text-align: center;">ー</td>
<td style="text-align: center;">WARN</td>
</tr>
<tr>
<td style="text-align: right;">82</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>RetailMediaServiceTimeout</td>
<td style="text-align: right;">30000</td>
<td>RM</td>
<td>GetValue(企業コード,店舗コード,端末Id)</td>
<td>〇</td>
<td><br />
</td>
<td>〇</td>
<td style="text-align: center;">30000</td>
<td style="text-align: center;">ー</td>
</tr>
<tr>
<td style="text-align: right;">83</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>SalesViewInitialDisplay</td>
<td style="text-align: right;">1</td>
<td>レーンレジ</td>
<td>GetValues(企業コード,店舗コード,端末Id)</td>
<td>〇</td>
<td>〇</td>
<td>〇</td>
<td style="text-align: center;">ー</td>
<td style="text-align: center;">ー</td>
</tr>
<tr>
<td style="text-align: right;">84</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>SaveOrderCallbackNodeTypes</td>
<td style="text-align: right;">5</td>
<td>オーダー</td>
<td>GetValue(企業コード,店舗コード,端末Id)</td>
<td>〇</td>
<td><br />
</td>
<td>〇</td>
<td style="text-align: center;">ー</td>
<td style="text-align: center;">ー</td>
</tr>
<tr>
<td style="text-align: right;">85</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>SavePayInfoRetryCounts</td>
<td style="text-align: right;">0</td>
<td>給料天引き</td>
<td>GetValue(企業コード,店舗コード,0)</td>
<td>〇</td>
<td>〇</td>
<td><br />
</td>
<td style="text-align: center;">0</td>
<td style="text-align: center;">ー</td>
</tr>
<tr>
<td style="text-align: right;">86</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>SelectPaymentSleepMillisecond</td>
<td style="text-align: right;">3500</td>
<td>未精算音声</td>
<td>GetValues(企業コード,店舗コード,0)</td>
<td>〇</td>
<td>〇</td>
<td><br />
</td>
<td style="text-align: center;">3500</td>
<td style="text-align: center;">ー</td>
</tr>
<tr>
<td style="text-align: right;">87</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>SelectPaymentSleepMillisecond4SemiSelf</td>
<td style="text-align: right;">3500</td>
<td>未精算音声</td>
<td>GetValues(企業コード,店舗コード,0)</td>
<td>〇</td>
<td>〇</td>
<td><br />
</td>
<td style="text-align: center;">3500</td>
<td style="text-align: center;">ー</td>
</tr>
<tr>
<td style="text-align: right;">88</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>SelfAddValueCardNodeTypes</td>
<td><br />
</td>
<td><br />
</td>
<td>GetValue(企業コード,店舗コード,0)</td>
<td>〇</td>
<td>〇</td>
<td><br />
</td>
<td style="text-align: center;">ー</td>
<td style="text-align: center;">ー</td>
</tr>
<tr>
<td style="text-align: right;">89</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>SelfFraudDetectionIPAddress</td>
<td><br />
</td>
<td>TEC</td>
<td>GetValues(企業コード,店舗コード,端末Id)</td>
<td>〇</td>
<td>〇</td>
<td>〇</td>
<td style="text-align: center;">ー</td>
<td style="text-align: center;">ー</td>
</tr>
<tr>
<td style="text-align: right;">90</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>SelfFraudDetectionPortNo</td>
<td><br />
</td>
<td>TEC</td>
<td>GetValues(企業コード,店舗コード,端末Id)</td>
<td>〇</td>
<td>〇</td>
<td>〇</td>
<td style="text-align: center;">ー</td>
<td style="text-align: center;">ー</td>
</tr>
<tr>
<td style="text-align: right;">91</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>SelfFraudDetectionTcpConnectTimeout</td>
<td><br />
</td>
<td>TEC</td>
<td>GetValues(企業コード,店舗コード,端末Id)</td>
<td>〇</td>
<td>〇</td>
<td>〇</td>
<td style="text-align: center;">ー</td>
<td style="text-align: center;">ー</td>
</tr>
<tr>
<td style="text-align: right;">92</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>SelfFraudDetectionReadTimeout</td>
<td><br />
</td>
<td>TEC</td>
<td>GetValues(企業コード,店舗コード,端末Id)</td>
<td>〇</td>
<td>〇</td>
<td>〇</td>
<td style="text-align: center;">ー</td>
<td style="text-align: center;">ー</td>
</tr>
<tr>
<td style="text-align: right;">93</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>SelfFraudDetectionWriteTimeout</td>
<td><br />
</td>
<td>TEC</td>
<td>GetValues(企業コード,店舗コード,端末Id)</td>
<td>〇</td>
<td>〇</td>
<td>〇</td>
<td style="text-align: center;">ー</td>
<td style="text-align: center;">ー</td>
</tr>
<tr>
<td style="text-align: right;">94</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>StamprallyApplyAPI</td>
<td>/campaigns/stamp</td>
<td>RM</td>
<td>GetValue(企業コード,店舗コード,端末Id)</td>
<td>〇</td>
<td><br />
</td>
<td>〇</td>
<td style="text-align: center;">ー</td>
<td style="text-align: center;">ー</td>
</tr>
<tr>
<td style="text-align: right;">95</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>StoreType</td>
<td>00</td>
<td>店舗タイプ</td>
<td>GetValue(企業コード,店舗コード,0)</td>
<td>〇</td>
<td>〇</td>
<td><br />
</td>
<td style="text-align: center;">ー</td>
<td style="text-align: center;">ー</td>
</tr>
<tr>
<td style="text-align: right;">96</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>TrialCouponApplyAPI</td>
<td>/trycoupon/apply</td>
<td>RM</td>
<td>GetValue(企業コード,店舗コード,端末Id)</td>
<td>〇</td>
<td><br />
</td>
<td>〇</td>
<td style="text-align: center;">ー</td>
<td style="text-align: center;">ー</td>
</tr>
<tr>
<td style="text-align: right;">97</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>ValueCardAccessKey</td>
<td>O5bp6rRWS9hfrh178T3ICHIvNOO2KSheRyVDBhJgAw0=</td>
<td>VD</td>
<td>GetValues(企業コード,店舗コード,端末Id)</td>
<td>〇</td>
<td>〇</td>
<td>〇</td>
<td style="text-align: center;">ー</td>
<td style="text-align: center;">ー</td>
</tr>
<tr>
<td style="text-align: right;">98</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>ValueCardDealServiceURL</td>
<td><span class="nolink">https://dev.valuecardservice.biz:443/soap/services/DealServiceWithPoint</span></td>
<td>VD</td>
<td>GetValues(企業コード,店舗コード,端末Id)</td>
<td>〇</td>
<td>〇</td>
<td>〇</td>
<td style="text-align: center;">ー</td>
<td style="text-align: center;">ー</td>
</tr>
<tr>
<td style="text-align: right;">99</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>ValueCardDealServiceURLWithDango</td>
<td>https://dango-stg.su-pay.jp/api/v3/</td>
<td>Dango</td>
<td>GetValues(企業コード,店舗コード,端末Id)</td>
<td>〇</td>
<td>〇</td>
<td>〇</td>
<td><br />
</td>
<td><br />
</td>
</tr>
<tr>
<td style="text-align: right;">100</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>ValueCardDepositTimeout</td>
<td style="text-align: right;">20000</td>
<td>VD</td>
<td>GetValues(企業コード,店舗コード,端末Id)</td>
<td>〇</td>
<td>〇</td>
<td>〇</td>
<td style="text-align: center;">ー</td>
<td style="text-align: center;">ー</td>
</tr>
<tr>
<td style="text-align: right;">101</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>ValueCardDepositTimeoutWithDango</td>
<td style="text-align: right;">25000</td>
<td>Dango</td>
<td>GetValues(企業コード,店舗コード,端末Id)</td>
<td>〇</td>
<td>〇</td>
<td>〇</td>
<td><br />
</td>
<td><br />
</td>
</tr>
<tr>
<td style="text-align: right;">102</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>ValueCardGetBalanceCheckWaitingTime</td>
<td style="text-align: right;">0</td>
<td>VD</td>
<td>GetValues(企業コード,店舗コード,端末Id)</td>
<td>〇</td>
<td>〇</td>
<td>〇</td>
<td style="text-align: center;">ー</td>
<td style="text-align: center;">ー</td>
</tr>
<tr>
<td style="text-align: right;">103</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>ValueCardGetBalanceCheckWaitingTimeDango</td>
<td style="text-align: right;">0</td>
<td>Dango</td>
<td>GetValues(企業コード,店舗コード,端末Id)</td>
<td>〇</td>
<td>〇</td>
<td>〇</td>
<td><br />
</td>
<td><br />
</td>
</tr>
<tr>
<td style="text-align: right;">104</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>ValueCardGetBalanceRetryCount</td>
<td style="text-align: right;">4</td>
<td>VD</td>
<td>GetValues(企業コード,店舗コード,端末Id)</td>
<td>〇</td>
<td>〇</td>
<td>〇</td>
<td style="text-align: center;">ー</td>
<td style="text-align: center;">ー</td>
</tr>
<tr>
<td style="text-align: right;">105</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>ValueCardGetBalanceRetryCountWithDango</td>
<td style="text-align: right;">4</td>
<td>Dango</td>
<td>GetValues(企業コード,店舗コード,端末Id)</td>
<td>〇</td>
<td>〇</td>
<td>〇</td>
<td><br />
</td>
<td><br />
</td>
</tr>
<tr>
<td style="text-align: right;">106</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>ValueCardGetBalanceTimeout</td>
<td style="text-align: right;">5000</td>
<td>VD</td>
<td>GetValues(企業コード,店舗コード,端末Id)</td>
<td>〇</td>
<td>〇</td>
<td>〇</td>
<td style="text-align: center;">ー</td>
<td style="text-align: center;">ー</td>
</tr>
<tr>
<td style="text-align: right;">107</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>ValueCardGetBalanceTimeoutWithDango</td>
<td style="text-align: right;">5000</td>
<td>Dango</td>
<td>GetValues(企業コード,店舗コード,端末Id)</td>
<td>〇</td>
<td>〇</td>
<td>〇</td>
<td><br />
</td>
<td><br />
</td>
</tr>
<tr>
<td style="text-align: right;">108</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>ValueCardLeadString</td>
<td style="text-align: right;">881</td>
<td>VD</td>
<td>GetValues(企業コード,店舗コード,端末Id)</td>
<td>〇</td>
<td>〇</td>
<td>〇</td>
<td style="text-align: center;">ー</td>
<td style="text-align: center;">ー</td>
</tr>
<tr>
<td style="text-align: right;">109</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>ValueCardLeadStringWithDango</td>
<td style="text-align: right;">881</td>
<td>Dango</td>
<td>GetValues(企業コード,店舗コード,端末Id)</td>
<td>〇</td>
<td>〇</td>
<td>〇</td>
<td><br />
</td>
<td><br />
</td>
</tr>
<tr>
<td style="text-align: right;">110</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>ValueCardTermIdPrefix</td>
<td style="text-align: right;">98129</td>
<td>VD</td>
<td>GetValues(企業コード,店舗コード,端末Id)</td>
<td>〇</td>
<td>〇</td>
<td>〇</td>
<td style="text-align: center;">ー</td>
<td style="text-align: center;">ー</td>
</tr>
<tr>
<td style="text-align: right;">111</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>ValueCardWithDrawTimeout</td>
<td style="text-align: right;">20000</td>
<td>VD</td>
<td>GetValues(企業コード,店舗コード,端末Id)</td>
<td>〇</td>
<td>〇</td>
<td>〇</td>
<td style="text-align: center;">ー</td>
<td style="text-align: center;">ー</td>
</tr>
<tr>
<td style="text-align: right;">112</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>ValueCardWithDrawTimeoutWithDango</td>
<td style="text-align: right;">25000</td>
<td>Dango</td>
<td>GetValues(企業コード,店舗コード,端末Id)</td>
<td>〇</td>
<td>〇</td>
<td>〇</td>
<td><br />
</td>
<td><br />
</td>
</tr>
<tr>
<td style="text-align: right;">113</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>ValueTrainingCardLeadString</td>
<td style="text-align: right;">299</td>
<td>VD</td>
<td>GetValues(企業コード,店舗コード,端末Id)</td>
<td>〇</td>
<td>〇</td>
<td>〇</td>
<td style="text-align: center;">ー</td>
<td style="text-align: center;">ー</td>
</tr>
<tr>
<td style="text-align: right;">114</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>ValueCardDealServiceV2URL</td>
<td><br />
</td>
<td>VD</td>
<td>GetValues(企業コード,店舗コード,端末Id)</td>
<td>〇</td>
<td>〇</td>
<td>〇</td>
<td style="text-align: center;">ー</td>
<td style="text-align: center;">WARN</td>
</tr>
<tr>
<td style="text-align: right;">115</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>ValueCardDealServiceV2URLStartTime</td>
<td><br />
</td>
<td>VD</td>
<td>GetValues(企業コード,店舗コード,端末Id)</td>
<td>〇</td>
<td>〇</td>
<td>〇</td>
<td style="text-align: center;">ー</td>
<td style="text-align: center;">WARN</td>
</tr>
<tr>
<td style="text-align: right;">116</td>
<td style="text-align: right;">1</td>
<td><br />
</td>
<td style="text-align: right;">0</td>
<td>IsCloseCountReceiptSimplePrint</td>
<td><br />
</td>
<td>精算</td>
<td>GetValues(企業コード,店舗コード,端末Id)</td>
<td>〇</td>
<td>〇</td>
<td>〇</td>
<td style="text-align: center;">FALSE</td>
<td style="text-align: center;">ー</td>
</tr>
<tr>
<td style="text-align: right;">117</td>
<td style="text-align: right;">1</td>
<td style="text-align: right;">900</td>
<td style="text-align: right;">0</td>
<td>AttendantServiceIPAddress</td>
<td>10.100.2.191</td>
<td>Attendant</td>
<td>GetValue(企業コード,店舗コード,0)</td>
<td>〇</td>
<td>〇</td>
<td><br />
</td>
<td style="text-align: center;">ー</td>
<td style="text-align: center;">WARN</td>
</tr>
<tr>
<td style="text-align: right;">118</td>
<td style="text-align: right;">1</td>
<td style="text-align: right;">900</td>
<td style="text-align: right;">0</td>
<td>ChargePayment</td>
<td style="text-align: right;">1</td>
<td>チャージ</td>
<td>GetValue(企業コード,店舗コード,0)</td>
<td>〇</td>
<td>〇</td>
<td><br />
</td>
<td style="text-align: center;">NULL</td>
<td style="text-align: center;">ー</td>
</tr>
<tr>
<td style="text-align: right;">119</td>
<td style="text-align: right;">1</td>
<td style="text-align: right;">900</td>
<td style="text-align: right;">0</td>
<td>IsCreditChargePoint</td>
<td style="text-align: center;">FALSE</td>
<td>クレジットチャージ</td>
<td>GetValue(企業コード,店舗コード,0)</td>
<td>〇</td>
<td>〇</td>
<td><br />
</td>
<td style="text-align: center;">FALSE</td>
<td style="text-align: center;">ー</td>
</tr>
<tr>
<td style="text-align: right;">120</td>
<td style="text-align: right;">1</td>
<td style="text-align: right;">900</td>
<td style="text-align: right;">2501</td>
<td>FaceMeServiceIPAddress</td>
<td>0.0.0.0</td>
<td>顔認証</td>
<td>GetValue(企業コード,店舗コード,端末Id)</td>
<td>〇</td>
<td><br />
</td>
<td>〇</td>
<td style="text-align: center;">ー</td>
<td style="text-align: center;">ー</td>
</tr>
</tbody>
</table>

\

GoogleDrive参照：<https://docs.google.com/spreadsheets/d/1CppWO4Gf7FsjpdxfWV3XYtLiQ8FqkD4g8IUYPcEMb3Q/edit?gid=0#gid=0>

\

最後更新日付：2024/6/18
