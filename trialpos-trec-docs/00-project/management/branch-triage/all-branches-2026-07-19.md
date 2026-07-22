# aipos 正本全分支快照（2026-07-19）

> 本文件为 [branch-triage-2026-07-19.md](./branch-triage-2026-07-19.md) 的附属全量快照，由 `git ls-remote --heads origin` + 本地对象库生成（origin = 内网 GitLab `https://74.226.74.29/git/trial.git`）。
> 列说明：**并入基线** = 该分支 tip 是否为基线 `release20260728_Local`（202607，当前已发布最新版）的祖先。`BASE`＝基线自身。tip 作者＝末次提交作者。

## 主线定期发布（release`*_Local`，60 支）

| 分支 | tip | 末次提交日 | 并入基线 | tip 作者 |
|---|---|---|---|---|
| `release20260818_Local` | b0a59a391 | 2026-07-17 | N | 中川 憲抄 |
| `release20260728_Local` | a1a8beb8e | 2026-07-03 | BASE | q.qin |
| `release20260701_FixForScannerHang_Local` | 63430020e | 2026-07-08 | N | 中川 憲抄 |
| `release20260630_AddLogForScannerHang_Local` | f8494a7be | 2026-06-30 | N | 中川 憲抄 |
| `release20260624_PointInfinitySimulatorFix_Local` | b2ffd4067 | 2026-06-24 | Y | 中川 憲抄 |
| `release20260610_FixSendMTranDialog_Local` | 7e4a03769 | 2026-06-10 | Y | 中川 憲抄 |
| `release20260609_StabilityFix_Local` | 39c5781b4 | 2026-06-12 | Y | 中川 憲抄 |
| `release20260609_FixDeleteMTran_Local` | e4140c24b | 2026-06-09 | Y | 中川 憲抄 |
| `release20260512_Local` | 5778a3454 | 2026-04-28 | Y | q.li |
| `release20260512_AutoDiscount_Local` | bc10af9d2 | 2026-05-26 | Y | p.shi |
| `release20260422_Local` | d7b4768c9 | 2026-04-14 | Y | qu_jian |
| `release20260422_LaneSelf_Local` | bc0941b73 | 2026-04-03 | N | q.qin |
| `release20260414_Local` | 21e4e2b30 | 2026-04-08 | Y | q.li |
| `release20260414_LaneSelf_Local` | cb1b7161b | 2026-04-03 | N | q.qin |
| `release2026041001_LaneSelf_Local` | d5b1b67f8 | 2026-04-16 | Y | q.qin |
| `release20260407_Local` | 9100becc0 | 2026-03-25 | Y | q.qin |
| `release20260310_Local` | 3f50b4de3 | 2026-02-17 | N | q.qin |
| `release20260209_Local` | f2a2fe146 | 2026-01-29 | Y | k.nakagawa |
| `release20260106_Local` | 2260001ff | 2026-01-07 | Y | q.qin |
| `release20251201_hanakoganei_Local` | 1c243cd6e | 2025-12-01 | Y | q.li |
| `release20251111_Local` | 1fa00124c | 2025-10-28 | Y | n.hu |
| `release20251104_Local` | f22542f3b | 2025-10-31 | Y | k.nakagawa |
| `release20251104_Local_rev3` | 8d14dab8d | 2026-01-08 | Y | q.qin |
| `release20251104_Local_rev2` | d69804c46 | 2025-11-07 | Y | k.nakagawa |
| `release20251007_Local` | 70495ac84 | 2025-09-25 | Y | q.qin |
| `release20250923_Local` | e68f0d2b0 | 2025-09-12 | Y | q.li |
| `release20250826_Local` | 0756eee5d | 2025-08-13 | Y | n.hu |
| `release20250826_CESettingTool_Local` | 85317f97e | 2026-04-23 | N | q.qin |
| `release20250814_SelfCreditPayment_Local` | 0dedf33bf | 2025-12-01 | Y | q.li |
| `release20250807_MultiLanguage_Local` | ae57826ed | 2026-01-30 | Y | k.nakagawa |
| `release20250715_Local` | ad1dd9735 | 2025-07-07 | Y | q.qin |
| `release20250630_Local` | 20472316b | 2025-06-23 | Y | q.qin |
| `release20250624_Local` | 1e7b3362f | 2025-06-13 | Y | q.li |
| `release20250611_Local` | 3ca91e409 | 2025-05-21 | Y | n.hu |
| `release20250514_Local` | f383b1cf3 | 2025-04-30 | Y | n.hu |
| `release20250415_Local` | 7457d84d4 | 2025-04-08 | Y | q.li |
| `release20250331_Local` | fffe40daf | 2025-04-09 | Y | q.qin |
| `release20250218_Local` | c688009f2 | 2025-02-19 | Y | q.li |
| `release20250121_Local` | 0c73afb50 | 2024-12-25 | Y | q.li |
| `release20241111_FoodPark_Local` | 0e604ab03 | 2024-11-29 | Y | m.liu |
| `release20241105_Local` | 04915dd0b | 2024-10-28 | Y | p.shi |
| `release20240924_Local` | c0c159202 | 2024-09-18 | Y | q.li |
| `release20240820_Local` | bdada651e | 2024-08-08 | Y | n.hu |
| `release20240710_Local` | 754eaf0f8 | 2024-07-02 | Y | q.li |
| `release20240611_Local` | 6bddc15f5 | 2024-05-28 | Y | q.li |
| `release20240528_Local` | 25c32c78e | 2024-05-24 | Y | p.shi |
| `release20240206_Local` | 78f5644e4 | 2024-01-24 | Y | q.li |
| `release20231127_Local` | 3113547b9 | 2023-12-25 | Y | p.shi |
| `release20231010_Local` | d930d63e8 | 2023-10-11 | Y | p.shi |
| `release20230829_Local` | a23f12a57 | 2023-09-04 | Y | p.shi |
| `release20230821_Local` | 4bd9e5b94 | 2023-08-14 | Y | q.li |
| `release20230717_Local` | 3ee422577 | 2023-07-10 | Y | p.shi |
| `release20230522_Local` | d819e6bbe | 2023-07-20 | Y | p.shi |
| `release20230418_Local` | a92437c77 | 2023-06-06 | Y | p.shi |
| `release20200629_local` | 86f589746 | 2020-08-18 | Y | p.shi |
| `release20200219_local` | 0d16d9891 | 2020-05-15 | Y | s.watarai |
| `release20191127_local` | f23d28674 | 2019-12-26 | Y | p.shi |
| `release20191015_local` | 89bc4828e | 2019-12-06 | Y | s.watarai |
| `release20190911_local` | f77dbd048 | 2019-09-06 | Y | p.shi |
| `release20190724_Local` | f3e89f6d4 | 2019-07-25 | Y | t.kikitsu |

## 专用/案件 release（116 支）

| 分支 | tip | 末次提交日 | 并入基线 | tip 作者 |
|---|---|---|---|---|
| `releaseFullTurn` | 6e19617a2 | 2022-04-13 | N | p.shi |
| `releaseFC20240701` | 784e4608c | 2024-09-05 | N | q.li |
| `release20260601_FixDrugFlagLogicLSPre` | 34f671026 | 2026-05-26 | N | p.shi |
| `release20260601_BestBeforeMarkDownMaster` | c75406a93 | 2026-06-01 | N | p.shi |
| `release20260407_TLogDrugOperatorInfo` | 93f4673cb | 2026-03-27 | N | q.qin |
| `release20260330_MstEmployeeDrugOperatorFlag` | 9a95e1038 | 2026-03-27 | N | qu jian |
| `release20260302_AzureDbData` | 9c70051ce | 2026-02-25 | N | p.shi |
| `release20260223_FC` | d59ce74d5 | 2026-01-06 | N | q.li |
| `release20260210_PartialRefondDiff` | 53b03bae1 | 2026-03-04 | Y | k.nakagawa |
| `release20260210_FanCouponLocal` | e6674ece5 | 2026-01-29 | Y | p.shi |
| `release20260209_FanCoupon` | ffccacc64 | 2026-01-28 | N | p.shi |
| `release20260209_FanCouponLocal` | a0043b1fc | 2026-01-23 | Y | p.shi |
| `release20260106_CashierSum` | 7b682f224 | 2025-12-25 | N | q.li |
| `release20251215_BestBeforeMarkDown` | c26d88c42 | 2025-12-18 | N | p.shi |
| `release20251201_TrialPlus` | 127492aad | 2025-11-21 | N | p.shi |
| `release20251126_LaneSelfCredit` | bf7df38aa | 2025-12-09 | N | q.li |
| `release20251125_LaneSelf` | 706062c88 | 2025-12-08 | N | q.qin |
| `release20251125_LaneSelfCredit` | e5ca24652 | 2025-12-08 | N | q.qin |
| `release20251125_AzureLaneSelf` | b1c6062d4 | 2026-03-12 | N | q.qin |
| `release20251107_SelfCreditSum` | cb580a698 | 2025-11-11 | N | p.shi |
| `release20251028_BOEjounalTaxFree` | 837e22e65 | 2025-11-11 | N | p.shi |
| `release20250929_tls12Problem` | 389ed7373 | 2025-10-30 | N | p.shi |
| `release20250922_InboundTaxFree` | fccb94ebe | 2025-09-12 | N | q.li |
| `release20250915_AzureDbData` | 2450576f6 | 2025-09-12 | N | p.shi |
| `release20250908_TaxFreePOC` | af431b08c | 2025-09-04 | Y | q.li |
| `release20250908_InboundTaxFree` | 51716c65e | 2025-09-04 | N | q.li |
| `release20250901_QueDelayProblem` | 6b82f33af | 2025-08-29 | N | qu_jian |
| `release20250826_ChinaPayPOS` | ae9da314a | 2025-09-02 | N | q.li |
| `release20250819_FC` | f594041d7 | 2025-08-06 | N | q.li |
| `release20250722_FC` | 3abdfebcf | 2025-07-31 | N | p.shi |
| `release20250722_AeonTenant` | 690b7a7a8 | 2025-07-10 | N | q.qin |
| `release20250715_ChinaPayPOS` | f5ab377b3 | 2025-07-11 | N | q.li |
| `release20250707_AzureDbData` | 909872f35 | 2025-08-05 | N | p.shi |
| `release20250704_TrialPromoApp` | f378e4de7 | 2025-07-04 | N | n.hu |
| `release20250617_PointInfinityPOS` | 981ca818e | 2025-06-13 | Y | q.li |
| `release20250611_SelfFraudDetection_TrialPOC` | ef1e0c833 | 2025-06-19 | Y | n.hu |
| `release20250521_NEXTMART01GO` | 05e88930d | 2025-05-21 | Y | q.qin |
| `release20250521_CartReceipt` | 7955e551e | 2025-05-21 | N | n.hu |
| `release20250519_ChinaPayPOS` | 9fd3702ed | 2025-06-06 | N | q.li |
| `release20250512_PointInfinity` | d2e219b7a | 2025-07-29 | N | p.shi |
| `release20250507_AeonTenant` | 526101e65 | 2025-05-07 | N | q.qin |
| `release20250421_ChinaPay` | fa890c352 | 2025-04-30 | N | p.shi |
| `release20250414_ExcludedTaxCloud` | d0a7476f9 | 2025-04-30 | N | p.shi |
| `release20250407_ExcludedTaxCloud` | 8dd3c9438 | 2025-04-03 | N | p.shi |
| `release20250401_ExcludedTax` | dbceadd1e | 2025-03-21 | N | qu_jian |
| `release20250317_SelfFraudDetection_TrialPOC` | e1f8936b7 | 2025-03-17 | Y | q.li |
| `release20250310_PosSalesHeader` | dbceadd1e | 2025-03-21 | N | qu_jian |
| `release20250110_TrialGODashboardAPI` | aebee2bd9 | 2025-02-18 | N | p.shi |
| `release20241219_CT6100ModeSelf` | 1ca6afc2b | 2024-12-19 | Y | q.li |
| `release20241202_SummaryMakeFileProblem` | dc1bd030e | 2024-11-29 | N | qu_jian |
| `release20241127_FoodPark` | c96a5ae56 | 2024-11-28 | N | m.liu |
| `release20241125_FoodPark` | 622078257 | 2024-11-26 | N | q.li |
| `release20241106_FoodPark` | e86423213 | 2024-11-05 | N | p.shi |
| `release20240927_NEXMART01GO` | 4ee1f80b0 | 2024-09-25 | Y | p.shi |
| `release20240924_POC` | e032d246e | 2024-09-18 | Y | q.li |
| `release20240903_IncommQRApiService` | 561255a1b | 2024-09-23 | N | p.shi |
| `release20240820_POC` | d7fe1e7db | 2024-08-08 | Y | q.qin |
| `release20240820_BlankMessage` | 9639c9381 | 2024-07-24 | N | q.qin |
| `release20240722_TranLogToMD` | 61b2900e4 | 2024-09-18 | N | qu_jian |
| `release20240711_TaxInvoice` | 8897329a8 | 2024-07-11 | N | q.li |
| `release20240628_DealCodeTrainingRevison` | f4ac4a406 | 2024-06-28 | N | q.li |
| `release20240611_TrialGoPOC` | 165d5ef10 | 2024-06-04 | Y | q.li |
| `release20240530_PosSalesDetail` | 998fe99fd | 2024-06-26 | N | p.shi |
| `release20240401_OperationMonitoring` | de4493316 | 2024-04-15 | N | q.qin |
| `release20240318AeonTenant` | 574e15c3f | 2024-03-07 | N | p.shi |
| `release20240115_Indicator` | 470537f5c | 2024-01-10 | Y | p.shi |
| `release20231212_NEXMART01GO` | 948bcc31b | 2023-12-25 | Y | p.shi |
| `release20231211_RealPointDetail` | f0ab05c1b | 2023-11-22 | N | a.yu |
| `release20230918_Dango` | 1ec00583a | 2023-09-14 | N | n.hu |
| `release20230906_NonBarcodeItem` | 8d045cc08 | 2023-09-07 | Y | q.li |
| `release20230904_EJournalBackup` | 790960b08 | 2023-09-22 | N | n.hu |
| `release20230710_HybridPointDetails` | d739168df | 2023-07-07 | N | a.yu |
| `release20230703_PreferredQueue` | 5c8bbfc12 | 2023-06-28 | N | qu_jian |
| `release20230510_FaceMe` | 9dc32b54a | 2023-05-04 | Y | q.li |
| `release20230424_HybridProblem` | d60e6820f | 2023-04-24 | N | a.yu |
| `release20230418` | 59062a507 | 2023-06-06 | N | p.shi |
| `release20230406_BestBefore` | d714c651b | 2023-06-07 | N | p.shi |
| `release20230405` | 240278d5a | 2023-03-27 | Y | p.shi |
| `release20230327FaceMe` | 6d5768395 | 2023-05-17 | N | q.li |
| `release20230321_sscreceipt` | 950497a30 | 2023-03-20 | N | qu_jian |
| `release20230306_ValueCardUnfinished` | 7d8c1eb5a | 2023-03-01 | N | a.yu |
| `release20230301` | 485ca6675 | 2023-02-27 | Y | q.li |
| `release20230301_Dango` | b85cb544e | 2023-09-08 | N | p.shi |
| `release20230215` | 8a9e78100 | 2023-02-09 | Y | q.li |
| `release20230206_TrainingMode` | 950f01266 | 2023-02-06 | N | qu_jian |
| `release20230201` | 6b4cd61f2 | 2023-01-25 | Y | p.shi |
| `release20230123_TrainingMode` | a8d6848b5 | 2023-01-18 | N | qu_jian |
| `release20230111_AzureHybrid` | a60a025fc | 2022-12-29 | N | a.yu |
| `release20230110` | bf55d3600 | 2023-01-12 | Y | p.shi |
| `release20221130` | 46b854d7e | 2023-01-12 | Y | a.yu |
| `release20221031` | c84d4cd01 | 2022-11-01 | N | qu_jian |
| `release20221026` | ea7dcf1e6 | 2022-10-07 | Y | qu_jian |
| `release20221003` | ec4481f1b | 2022-11-02 | Y | qu_jian |
| `release20220929` | cc84e1297 | 2022-09-27 | Y | p.shi |
| `release20220909SuPayUI` | c7cb56a16 | 2022-09-15 | Y | q.qin |
| `release20220630` | 3c612611e | 2022-08-23 | Y | ken.qu |
| `release20220524` | 05fd8af8b | 2022-05-20 | Y | = |
| `release20220331` | 1586e7702 | 2022-05-20 | Y | s.watarai |
| `release20220112` | 52ddaf1a0 | 2022-04-13 | Y | p.shi |
| `release20210930` | de6e1c870 | 2021-11-02 | N | s.okamoto |
| `release20210830` | 32a4954cf | 2021-12-13 | Y | s.watarai |
| `release20210630` | 65ff854a6 | 2021-09-01 | Y | s.watarai |
| `release20210511` | d3ea7c9ee | 2021-06-07 | Y | p.shi |
| `release20210302Credit` | 5e830e413 | 2021-06-07 | Y | p.shi |
| `release20210126` | 071154ee9 | 2021-03-01 | Y | s.watarai |
| `release20210120DP` | 5a6e48b33 | 2021-01-20 | Y | y.kawate |
| `release20210113` | d64b4dc3e | 2021-01-15 | Y | p.shi |
| `release20201208` | 2cf771ddf | 2020-12-18 | Y | p.shi |
| `release20201027` | 8c0ae209f | 2020-11-20 | Y | s.watarai |
| `release20200902` | 67aaca1f6 | 2020-10-01 | Y | s.watarai |
| `release20200618` | 4bedcd13a | 2020-06-22 | Y | s.watarai |
| `release20200602` | 1f522d678 | 2020-06-17 | Y | T.Kodate |
| `release20200128` | 85f645898 | 2020-02-07 | Y | q.qin |
| `release20191001` | 3b3dd1346 | 2019-11-13 | Y | KensukeKomobuchi |
| `release20190903` | 5a012b17c | 2019-09-05 | Y | t.kikitsu |
| `release20190710` | 8dee5ebb2 | 2019-07-25 | Y | y.uehara |

## feature（168 支）

| 分支 | tip | 末次提交日 | 并入基线 | tip 作者 |
|---|---|---|---|---|
| `feature/#786_localpos_creditpayment` | 74ecfcd66 | 2021-01-22 | Y | s.watarai |
| `feature435` | d7efd5ad6 | 2019-09-13 | Y | isobe |
| `feature487` | de886b39c | 2019-10-04 | N | s.watarai |
| `feature781` | 7b29af772 | 2020-09-16 | Y | s.watarai |
| `feature826` | 877a50289 | 2021-01-29 | N | T.Kodate |
| `feature888` | dd341271e | 2022-05-19 | N | = |
| `feature992` | da0408d28 | 2022-03-28 | N | s.watarai |
| `featureAddAfterPoint` | 66c8f45ba | 2021-02-25 | Y | T.Kodate |
| `featureAeonTenant` | b76624790 | 2024-03-04 | N | p.shi |
| `featureAttendantServer` | 6cffcdcdd | 2022-04-21 | N | m.liu |
| `featureAzureDbData` | cead991cf | 2026-02-11 | N | p.shi |
| `featureBOChargePointViewTest` | 8f367a721 | 2026-04-20 | N | shiraishi |
| `featureBOChargePointView` | d144c27b9 | 2026-05-11 | N | c.lu |
| `featureBOEJournal` | 6dfc34297 | 2021-12-13 | Y | s.kikuta |
| `featureBOMixMatch` | 07ea1ad8a | 2022-09-14 | Y | q.qin |
| `featureBarcodeCoupon` | 992e6bda5 | 2025-11-10 | N | p.shi |
| `featureBestBeforeDate20230215` | 648030cd4 | 2023-03-13 | N | a.yu |
| `featureBestBeforeDate` | 54ff0c278 | 2023-05-24 | Y | q.qin |
| `featureBestBeforeMarkDownLocal` | 867823faa | 2025-12-11 | Y | p.shi |
| `featureBestBeforeMarkDown` | 320014245 | 2025-12-09 | N | p.shi |
| `featureBusinessCounter_Azure` | a2f9a6c5c | 2023-08-01 | N | q.li |
| `featureBusinessCounter` | 1152da206 | 2023-08-01 | N | q.li |
| `featureCAFISArch2` | 86f589746 | 2020-08-18 | Y | p.shi |
| `featureCAFISArch3` | f85058f74 | 2021-04-01 | Y | p.shi |
| `featureCAFISArchLAN` | e6c6f0c2c | 2022-01-12 | Y | p.shi |
| `featureCAFISArch` | 508be0b9f | 2020-06-05 | N | T.Kodate |
| `featureCT6100ModeSelf` | 1ca6afc2b | 2024-12-19 | Y | q.li |
| `featureChangePriceApi` | a0b052763 | 2019-11-08 | N | 川手雄二 |
| `featureChargeEJournal` | ae13b1b0b | 2020-10-19 | Y | s.watarai |
| `featureChargeFaceMeLogin` | dd4989c0a | 2026-03-02 | N | q.qin |
| `featureChinaPay` | 144b6713e | 2025-04-21 | N | q.li |
| `featureCouponImage` | 7373258fc | 2021-09-15 | Y | y.kawate |
| `featureCreditCombinedPaymentForServiceCounter` | daf45306f | 2026-05-26 | N | 中川 憲抄 |
| `featureCreditPartialRefund` | f3b12ae36 | 2026-01-28 | Y | k.nakagawa |
| `featureDailyDealCodeTotal` | 88a0b1b38 | 2020-09-09 | Y | k.ooga |
| `featureDangoDelete` | 13ecd5a65 | 2025-07-22 | N | p.shi |
| `featureDangoNewApi20230118` | 022c3721f | 2023-02-06 | N | a.yu |
| `featureDango` | 9b7d3852c | 2022-10-21 | N | p.shi |
| `featureDynamicPricing2nd` | 34fadea6a | 2021-01-19 | Y | y.kawate |
| `featureDynamicPricing` | bd3543965 | 2019-08-22 | Y | t.kikitsu |
| `featureEJournalBackupForDelete` | 4ccf669ca | 2021-12-27 | Y | T.Kodate |
| `featureEJournalBackup` | 46646c6fd | 2023-08-30 | N | n.hu |
| `featureEJournalReceiptReprint` | a69add669 | 2022-04-25 | Y | s.watarai |
| `featureEJournalReprint` | 126b4dbb4 | 2022-03-25 | Y | p.shi |
| `featureEmoneytest` | 66d268f98 | 2024-07-01 | N | a.yu |
| `featureEmployeeMaster` | 526538171 | 2022-05-16 | N | s.watarai |
| `featureErrorLog` | 2bf63a8aa | 2020-02-07 | Y | 川手雄二 |
| `featureExcludedTax_POS` | 7457d84d4 | 2025-04-08 | Y | q.li |
| `featureFTPRetry2` | 0e4d191f4 | 2020-12-28 | Y | s.watarai |
| `featureFTPRetry` | c5933178d | 2020-12-17 | Y | s.watarai |
| `featureFaceMe` | 067784758 | 2024-06-03 | Y | q.li |
| `featureFanCouponLocal` | a0043b1fc | 2026-01-23 | Y | p.shi |
| `featureFanCoupon` | ffccacc64 | 2026-01-28 | N | p.shi |
| `featureFixIsOTCDrugSaleFlagLogic_LS_Pre` | e7c2a20c9 | 2026-05-15 | N | shiraishi |
| `featureFixIsOTCDrugSaleFlagLogic_LS_Prod` | f63af0830 | 2026-05-19 | N | shiraishi |
| `featureFixIsOTCDrugSalesFlagLogic_Pre` | 1d3edf489 | 2026-05-15 | N | shiraishi |
| `featureFixIsOTCDrugSalesFlagLogic_Prod` | 93f3b5a14 | 2026-05-19 | N | shiraishi |
| `featureFixUnknownStatusTranForCreditCombined` | d385e93d1 | 2026-07-17 | N | 中川 憲抄 |
| `featureFoodPark` | 0e604ab03 | 2024-11-29 | Y | m.liu |
| `featureFullSelf2` | 7012c90ff | 2019-11-12 | N | a.yu |
| `featureFullSelf3` | 68ad0ad0d | 2019-12-06 | Y | p.shi |
| `featureFullSelf` | 67313dd02 | 2019-09-05 | Y | p.shi |
| `featureFullTurnKey` | 280211b51 | 2021-11-24 | N | y.kawate |
| `featureFullTurnMergeToTrial` | f3a75f309 | 2022-04-11 | N | T.Kodate |
| `featureFullTurnSummary` | ca19c6d93 | 2021-09-30 | N | k.ooga |
| `featureGUIApi` | 19106bb41 | 2021-05-14 | Y | p.shi |
| `featureGasolineStandPOS` | a7a834a73 | 2025-12-05 | N | p.shi |
| `featureGetItemMasterInfo` | 937997b97 | 2025-03-31 | N | p.shi |
| `featureGetScheduleLogDelay` | 59fb7e451 | 2020-10-29 | Y | T.Kodate |
| `featureGetTLogOrderForPPM` | 24f0226e4 | 2022-01-26 | N | T.Kodate |
| `featureHQDailyBackup` | 7bdf0a905 | 2022-01-07 | Y | T.Kodate |
| `featureHQDailyFaster` | d6a9d9e20 | 2022-01-12 | Y | y.kawate |
| `featureHQMasterSyncFaster` | c40cd8dc1 | 2022-03-29 | N | y.inoue |
| `featureHQMasterSyncRetryConnection` | bfd30d034 | 2022-02-03 | N | T.Kodate |
| `featureHQTransactionNo` | 67aaca1f6 | 2020-10-01 | Y | s.watarai |
| `featureHakari` | 825d7a51c | 2019-08-16 | Y | isobe |
| `featureHybrid20221101` | d6adb0844 | 2022-11-16 | N | q.li |
| `featureHybrid293` | d7ec91061 | 2025-11-05 | N | p.shi |
| `featureHybridPointDetails` | 8ef082860 | 2023-07-06 | N | qu_jian |
| `featureHybrid` | 8b9f5123e | 2022-10-31 | Y | a.yu |
| `featureIPOCALog2` | 4eeb83ec2 | 2021-01-26 | N | y.kawate |
| `featureIPOCALogMerge` | cd54ddd65 | 2022-02-25 | Y | s.kikuta |
| `featureIPOCALog` | 49050df44 | 2019-10-30 | N | k.ooga |
| `featureImproveBO` | 41eedb586 | 2026-05-11 | N | c.lu |
| `featureImproveOperationMonitoringAndBO_Bugfix` | 379f10858 | 2026-04-27 | N | 中川 憲抄 |
| `featureImproveOperationMonitoringAndBO` | 781cb648f | 2026-04-30 | N | shiraishi |
| `featureImproveOperationMonitoring_MasterBulkRegister` | 8cd94414f | 2026-04-22 | N | 中川 憲抄 |
| `featureImproveOperationMonitoring_ModuleBulkRegister` | 023f0f05d | 2026-04-21 | N | 中川 憲抄 |
| `featureImproveOperationMonitoring_Verify` | b13182824 | 2026-04-22 | N | shiraishi |
| `featureImproveOperationMonitoring` | a2bf8b1af | 2026-04-22 | N | 中川 憲抄 |
| `featureInboundTaxFree_POS` | b9aa12e85 | 2025-09-12 | Y | q.li |
| `featureIndicator` | e67eebe16 | 2024-01-10 | Y | p.shi |
| `featureInsertEJournalFailure` | 9fe1349c1 | 2020-12-23 | Y | T.Kodate |
| `featureJTaxFreePosDataApi_mergedBO` | a83afba59 | 2026-06-24 | N | q.qin |
| `featureJTaxFreePosDataApi` | 05ffe7bfd | 2026-06-24 | N | q.qin |
| `featureJournalItemCode` | bfa9b865e | 2020-11-26 | Y | s.watarai |
| `featureLaneSelf_Local` | 1c767976a | 2026-03-26 | Y | q.qin |
| `featureLocalPOS` | adeed2e5b | 2023-06-30 | N | p.shi |
| `featureLogOutputClientIP` | eae920b49 | 2020-11-12 | Y | s.watarai |
| `featureMarukyuBase` | 157d854f7 | 2020-02-13 | N | s.watarai |
| `featureMasterSyncTimeout` | aa4aa9d97 | 2019-09-17 | N | y.uehara |
| `featureMemberOffline` | fddbf8f26 | 2020-10-02 | Y | s.watarai |
| `featureMierukaMerge` | 9c658b314 | 2020-09-28 | N | T.Kodate |
| `featureMieruka` | 0f6ace06c | 2019-12-17 | N | 川手雄二 |
| `featureMinorVersion` | 1022bf3ef | 2020-11-27 | Y | T.Kodate |
| `featureMiscBugs` | e3e40f63c | 2020-01-17 | Y | T.Kodate |
| `featureNEXMART01GOQRPay` | 7c1265e94 | 2024-09-19 | Y | q.qin |
| `featureNEXMART01GO` | 5f455625d | 2025-02-06 | Y | n.hu |
| `featureNRF` | 240eaa953 | 2023-12-25 | N | p.shi |
| `featureNotifyPosMasterSync` | 000654722 | 2019-11-05 | N | k.ooga |
| `featureOneTimeBarcodeSupay` | 455947b12 | 2023-04-04 | N | p.shi |
| `featureOneTimeBarcodeTime` | d5081bf0d | 2022-06-16 | N | = |
| `featureOperationMonitoring` | e051a6353 | 2024-04-15 | N | q.qin |
| `featureOrderKitchenFaceMe` | 0dc7d762b | 2024-05-23 | Y | q.li |
| `featureOrderKitchenSelf` | 5c34c8682 | 2022-11-14 | N | p.shi |
| `featureOrderKitchen` | ac1b8dc64 | 2022-12-02 | Y | q.li |
| `featurePINEncrypt` | b6646f7d0 | 2019-12-02 | N | p.shi |
| `featurePointDetailMainte` | 2450ef455 | 2023-08-25 | N | a.yu |
| `featurePointInfinity_FC` | 8f2dcde81 | 2025-07-09 | N | q.qin |
| `featurePointInfinity_Local` | 4b214e2a8 | 2025-05-30 | N | q.qin |
| `featurePointInfinity` | 245389093 | 2025-06-30 | N | p.shi |
| `featurePreferredQueue` | 5c8bbfc12 | 2023-06-28 | N | qu_jian |
| `featureQueueImprove` | 5d80fba2e | 2023-08-17 | N | m.liu |
| `featureReSales` | 1ae9e60dc | 2019-12-18 | Y | t.kikitsu |
| `featureRealPointDetail` | f0ab05c1b | 2023-11-22 | N | a.yu |
| `featureRemoteSignIn` | 8f2c43d11 | 2024-05-23 | Y | q.li |
| `featureRetailMediaSimulator` | 4158f4fb7 | 2019-10-10 | Y | k.ooga |
| `featureSS950` | ebbd9eb35 | 2019-12-24 | Y | p.shi |
| `featureSTPOSBackground` | 2c72cb495 | 2026-03-10 | N | p.shi |
| `featureSelfCamera` | 887b84ed1 | 2021-03-05 | N | T.Kodate |
| `featureSelfCreditBulkSending` | 9584188e0 | 2026-01-21 | Y | k.nakagawa |
| `featureSelfCreditPayment` | 4456fd556 | 2025-10-27 | N | k.nakagawa |
| `featureSelfFraudDetection_Trial` | 1675cfeee | 2025-04-07 | N | q.li |
| `featureSemiSelf2` | 86f589746 | 2020-08-18 | Y | p.shi |
| `featureSemiSelfMTran` | a99cc7e39 | 2020-02-06 | Y | p.shi |
| `featureSemiSelf` | ff349c06f | 2019-10-22 | N | a.yu |
| `featureSendHourly` | be264bef4 | 2020-05-15 | Y | T.Kodate |
| `featureSendTerminalCapacity` | 8245a7dd2 | 2020-11-19 | Y | y.kawate |
| `featureStoreServer` | 5f3ed49eb | 2021-01-26 | N | k.ooga |
| `featureSuPay20220802` | 60fbd95b2 | 2022-08-12 | N | = |
| `featureSuPay20220812` | 8a8f40fd6 | 2022-09-08 | N | a.yu |
| `featureSummaryTranTime` | c029bb667 | 2025-02-28 | N | qu_jian |
| `featureTFTMainte` | 98fbe50e3 | 2021-06-21 | Y | k.ooga |
| `featureTLogTransfer` | f68441c9d | 2019-12-10 | N | KensukeKomobuchi |
| `featureTaxInvoice_Azure` | eaa2db0d4 | 2024-03-06 | N | q.li |
| `featureTaxInvoice` | 3cffcedcf | 2024-03-06 | N | q.li |
| `featureTrainingMode20230128` | ea19ec0bb | 2023-01-30 | N | a.yu |
| `featureTrainingModeMerage0113` | c725d620c | 2023-01-17 | N | qu_jian |
| `featureTrainingMode` | 3e869847d | 2023-01-09 | N | a.yu |
| `featureTranLogToMD` | f386613dd | 2024-07-16 | N | qu_jian |
| `featureTranRMResult` | 4bae8e726 | 2022-05-19 | Y | = |
| `featureTransactionLogToStorage2` | c993752b8 | 2021-07-29 | Y | s.kikuta |
| `featureTransactionLogToStorage` | e1dabd130 | 2019-12-18 | Y | s.watarai |
| `featureTransportationICcard` | 0da0b47d4 | 2026-03-24 | N | k.nakagawa |
| `featureTrialGODashboardAPI` | 35022ee2c | 2025-02-18 | N | p.shi |
| `featureTrialSelfFraudDetection` | c0c159202 | 2024-09-18 | Y | q.li |
| `featureTwoOperator` | d0bb12372 | 2021-11-02 | N | s.okamoto |
| `featureUnifyReceiptLayout` | 8c163a88b | 2020-10-19 | Y | s.watarai |
| `featureUnmannedStore` | 62fdfeaa5 | 2024-04-08 | N | q.li |
| `featureV4BO` | 64bb9a3bb | 2022-01-26 | Y | T.Kodate |
| `featureVATRelief` | 76f3e9594 | 2019-09-13 | Y | s.watarai |
| `featureVDUnFinished` | 79a6f37ba | 2023-01-23 | N | qu_jian |
| `featureVerifyTaxFree` | c812cfd7a | 2026-06-09 | N | q.li |
| `featureVoiceFileDownload` | 1e55ae41f | 2019-08-06 | N | KensukeKomobuchi |
| `featureWinPOSVersionUpTool` | 6c0bd9ad3 | 2019-11-06 | Y | 川手雄二 |
| `feature_20251104Version_Base20251007` | 54ab8748d | 2025-10-27 | Y | q.li |
| `feature_ChangeFaceLoginUI` | 3318418c1 | 2025-10-23 | Y | q.li |
| `feature_NEXMART01GO_trialMerged` | 70fd9013d | 2025-06-19 | Y | q.qin |

## fix / hotfix（39 支）

| 分支 | tip | 末次提交日 | 并入基线 | tip 作者 |
|---|---|---|---|---|
| `hotfix#863` | d17a75130 | 2021-03-12 | Y | y.inoue |
| `hotfix1008` | 5877cacb8 | 2022-03-08 | Y | T.Kodate |
| `hotfix1009_receipt` | 950497a30 | 2023-03-20 | N | qu_jian |
| `hotfix446` | 096f26c4f | 2019-09-11 | Y | k.ooga |
| `hotfix460` | dc9b5a959 | 2019-09-18 | Y | T.Kodate |
| `hotfix485` | b9621e6dd | 2019-10-03 | Y | S.Nishi |
| `hotfix494` | f34b7ed7f | 2019-10-07 | Y | p.shi |
| `hotfix522` | 0d9e895be | 2019-10-31 | Y | y.uehara |
| `hotfix523-525` | 03df2f7a7 | 2019-11-01 | Y | p.shi |
| `hotfix573` | 89bc4828e | 2019-12-06 | Y | s.watarai |
| `hotfix621` | ad76209fd | 2020-01-29 | Y | s.watarai |
| `hotfix712` | 83dfb0c02 | 2020-08-21 | Y | 大賀 香澄 |
| `hotfix743` | 3f95c85ef | 2020-11-06 | Y | k.ooga |
| `hotfix752` | 18017cc8d | 2020-07-30 | Y | y.kawate |
| `hotfix755` | ad370f743 | 2020-08-20 | Y | T.Kodate |
| `hotfix774` | 7e4dcb247 | 2020-09-08 | Y | T.Kodate |
| `hotfix807` | 2087b3042 | 2021-04-28 | Y | y.kawate |
| `hotfix849` | e41587a27 | 2022-05-26 | N | T.Kodate |
| `hotfix850` | 6c07de010 | 2021-02-05 | Y | T.Kodate |
| `hotfix851` | a1a0e18b5 | 2021-02-19 | Y | s.kikuta |
| `hotfix852` | 4aa96a9e9 | 2021-02-16 | Y | s.watarai |
| `hotfix854` | c06342427 | 2021-02-18 | Y | T.Kodate |
| `hotfix855` | 46eff8329 | 2021-02-17 | Y | s.watarai |
| `hotfix861` | 37d0f579e | 2021-03-02 | N | y.kawate |
| `hotfix864` | 0151370e5 | 2021-03-04 | Y | T.Kodate |
| `hotfix884` | 313446e0f | 2021-04-20 | Y | T.Kodate |
| `hotfix910` | 9096923fa | 2021-08-16 | Y | k.ooga |
| `hotfix912` | ebf2a085b | 2022-02-17 | N | y.kawate |
| `hotfix914` | bd59f902e | 2021-08-13 | N | y.kawate |
| `hotfix932` | c9c4ab546 | 2021-10-08 | Y | y.kawate |
| `hotfix938` | 60b21e475 | 2021-11-17 | N | T.Kodate |
| `hotfix939_947` | 63afdc1d5 | 2021-11-17 | Y | s.watarai |
| `hotfix946` | c8d529d96 | 2021-11-01 | Y | y.kawate |
| `hotfix952` | bf81aabb4 | 2021-11-26 | Y | s.kikuta |
| `hotfix978` | 1ee9dc13a | 2022-01-18 | Y | T.Kodate |
| `hotfix986` | 898e9ce5f | 2022-02-08 | Y | T.Kodate |
| `hotfix989` | 333a86dab | 2022-02-17 | Y | T.Kodate |
| `hotfix999` | c10f7f179 | 2022-02-28 | N | T.Kodate |
| `hotfixReceiptPrint` | ea7dcf1e6 | 2022-10-07 | Y | qu_jian |

## 其他（4 支）

| 分支 | tip | 末次提交日 | 并入基线 | tip 作者 |
|---|---|---|---|---|
| `001-role-based-access` | e1ec487c3 | 2026-04-22 | N | 中川 憲抄 |
| `master` | 9356c8b15 | 2024-09-18 | N | p.shi |
| `testDownloadBlob` | 46e6c4a16 | 2023-05-18 | N | n.hu |
| `v1.4` | 20ff860af | 2019-07-29 | Y | y.uehara |

