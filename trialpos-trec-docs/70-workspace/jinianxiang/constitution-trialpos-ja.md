<!--
Sync Impact Report
====================
Version: 1.0.1 → 2.0.0 [MAJOR · 全面日本語化＋第一原理による再制定]
Ratification: 2026-07-16 | Last Amended: 2026-07-18

改訂根拠（ユーザー指示 2026-07-18「SDD 開発フローの重大改善」）:
  1. 統治言語の全面日本語化 — 「言語規約」セクション新設。SDD 成果物・プロセスファイル・
     コードコメント等の言語を stpos-backend-kugelpos（正式コードリポジトリ＝日本語）の
     慣例に整合させる。全テンプレート・スキル・ナレッジ層を同時に日本語化（同一コミット）。
  2. 第一原理（F1〜F5）を明文化し、8 基本原則をそこから再導出・再記述。
     原則 I〜VIII の実質（番号・意図・具体的制約）は v1.0.1 から保全
     — v1.0.1 はユーザー承認済みであり、事実基盤（実測）に変化はないため。
  3. ワークフローに「人手ゲート表」（AI は代替不可）と「コミット規約」
     （Conventional Commits＋[spec:] トレーサビリティタグ）を追加。

MAJOR の理由: 統治言語の変更は後方非互換のガバナンス変更（以後の全成果物に適用）。

依存成果物の同期状態:
  ✅ .specify/templates/*（13）— 日本語化済み
  ✅ .claude/skills/speckit-*（16）— 日本語化済み＋言語規約ブロック挿入
  ✅ .claude/knowledge/*（16）— 日本語化済み
  ✅ CLAUDE.md / .specify/extensions.yml / SPECKIT_BASELINE.md — 日本語化済み
  ➖ .specify/workflows/ / scripts/bash/ — 上流バニラのまま（ゼロフォーク原則、台帳に記録）

以後の改訂は SemVer ＋ 本 Report の更新による。
-->

# POS4U（trialpos）開発憲章 · Constitution（参考コピー）

> **本書は参考コピーです。** 正本 = `trialpos-snapshots/.specify/memory/constitution.md`（**v2.0.0・日本語**）。齟齬がある場合は**正本を優先**。本コピーの編集は正本に反映されない。三言語版（zh/ja/en）は手動で同期する。
> v2.0.0 より正本の言語は日本語となったため、本書は「訳文」ではなく**原文のコピー**である。

> **適用対象**: `trialpos-snapshots`（POS4U コードベース、C#/.NET Framework + SQL Server）における SDD コード開発。
> **性質**: POS4U は TRIAL の**現行・運用中** POS システムであり、本リポジトリは社内 GitLab 正本のクローンである。本憲章はそのコード開発（**新機能＋バグ修正**）を統治する。プロジェクト残存寿命は **2〜3 年**（ST-POS への置換予定）。
> **最高精神**: 運用中のレガシーシステムの上で、**挙動保全の漸進開発**を行う — 書き直すのではなく、規律をもって直す。
> **権威**: 本憲章は最高統治文書である。真値基線に関する事実は `trialpos-snapshots` の実測コードを正とする（基線ブランチ `release20260728_Local` ＝ 202607 リリース版）。

---

## 第一原理 (First Principles)

本憲章の全原則は、以下の 5 つの動かせない事実（第一原理）から導出される。原則の解釈に迷ったら、ここに戻る。

- **F1 — 稼働中である**: POS4U は全店舗で現に稼働している。リグレッション＝営業事故（レジ停止・会計不整合）であり、守るべき最上位の価値は「店舗の会計を止めない・狂わせない」こと。
- **F2 — 残存寿命が短い**: 2〜3 年で ST-POS に置換される。大規模再構築・深い現代化は投資回収できない。改修は必要最小限・漸進が経済合理的。
- **F3 — 全検証は不可能**: 173 プロジェクト・既存テスト 0・`POS4U.Framework.dll` はソースなし・端末は Windows XP〜11 に混在。「すべて検証できる」前提は成立せず、検証可能性の境界を誠実に扱うしかない。
- **F4 — 知識は散逸している**: 現行挙動の知識は部族知識・リバースエンジニアリング文書に散在する。判断と教訓を記録しない開発は同じ事故を繰り返す。**判断の記録＝ナレッジ資産**。
- **F5 — 正本は日本語チームにある**: 正本は社内 GitLab、チームの作業言語・コード慣例は日本語。成果物は正本へ還流可能な形（日本語・チーム慣例準拠）で作らねば価値が半減する。

---

## 基本原則 (Core Principles)

### I. 挙動保全第一 (Behavior Preservation First) [NON-NEGOTIABLE]

〔導出: F1〕現行 POS は運用中であり、リグレッションリスクはそのまま本番事故である。いかなる変更も、**既定では既存の観察可能な挙動を変えてはならない** — UI 操作フロー、取引結果、状態遷移、データ永続化、集計結果。

- レガシーコードを修正する**前**に、まず**仕様化テスト（characterization test）で現行挙動を固定**してから着手する。
- 挙動変更は、spec に明示され承認された意図に**限る**。「ついで最適化」として混入してはならない。
- テストを付けられないレガシー領域（強結合 UI 等）は、spec/plan にリスクと手動検証方針を明示的に宣言する。

### II. 漸進改修・現行アーキテクチャの尊重 (Incremental & Respect AS-IS)

〔導出: F2〕残存寿命 2〜3 年のシステムに、ビッグバン書き直し・深い現代化は行わない（割に合わない）。新しいコードは既存のフレームワークとレイヤ構造の中で書く。

- **レイヤ（実測）**: Business(22) / Device(78) / WinPOS(38) / LogicService(6) / POS4ULogicService(11 Controller) / POS4UBackground(16)。フレームワーク基底クラスは `POS4U.Framework.dll`。
- **既存決定（ADR・必守）**: ADR-0001 5要素複合主キー · ADR-0002 WCF net.tcp ローカル IPC · ADR-0003 オフライン縮退 · ADR-0004 TransactionLog XML 永続化。
- 既存アーキテクチャから逸脱する必要が生じたら → **作業停止、`/speckit-adr` で協議**。「小さな例外」の独断処理は禁止。

### III. テスト戦略: 仕様化テスト + touch-only（全面 TDD ではない）

〔導出: F1×F3〕既存テスト 0 ＋ 173 プロジェクトに全量のテスト追加は非現実的かつ不経済。ルール:

- **触れたレガシーロジック**: 変更前に仕様化テスト（characterization）で挙動を固定する。
- **新規/変更ロジック**: その挙動契約をテストで覆う（恒真アサーション禁止、1 テスト＝1 契約）。
- 触れていないコードにテストを**書かない**（touch-only）。
- **カバレッジの数値ゲートは設けない**（全量・局所とも）。「触れた箇所はすべてテストされている」ことのみ要求し、コードレビュー＋ `/speckit-analyze` で担保する。数字合わせをしない。
- **テストフレームワーク＝ NUnit**（.NET Framework 4.x と互換良好、characterization/パラメタライズに強い）。テストプロジェクトは `<被験プロジェクト>.Tests`、本番プロジェクトに混入しない。
- **プラットフォーム分離**: spec/plan/コーディング/analyze は任意環境で可。**ビルド＋テストは Windows + MSBuild/VS で検証合格**して初めてマージ可（authoring ↔ build-verify 分離）。
- 詳細は `.claude/knowledge/testing-strategy.md`。

### IV. データ契約の安定 (Data Contract Stability)

〔導出: F1×F2〕データ層は SQL Server・**ストアドプロシージャ中心**（実測 160 テーブル / 405+ SP / 24 ビュー / 19 UDT）。

- **5要素複合主キー**（CompanyCode / StoreCode / TerminalNo / ManagedNo / TransactionNo）は取引アイデンティティの根幹であり、みだりに変更してはならない。
- テーブル / SP / UDT の契約変更は**後方互換**を保ち、レビューを経る。**SP の変更/新設はどちらの DB に置くかを明示**（Master / Tran 二重 DB）。
- クロスサイド BO 業務バックエンド SP（`usp_BO*`）は**店舗側 tran DB** にある。変更時は店舗/クラウド両側への影響を評価する。

### V. オフライン耐性の不可侵 (Offline Resilience)

〔導出: F1〕店舗が回線断でも営業を続けられることは POS の中核特性である（ADR-0003 オフライン縮退）。変更は**オフライン動作経路とその後の同期・集計を破壊してはならない**。

- 典型的な落とし穴（既知 gotcha）: 支払方法の新設 → Azure / Background の集計経路を連動修正しなければ、オフライン補填・日次集計が漏れる。

### VI. プロセス・IPC 境界の規律 (Process & IPC Discipline)

〔導出: F1×F2〕プロセス構成（実測）: `POS4U`（WPF フロント）↔ `TRAN4U`（WinForms デーモン / 周辺機器ホスト）を **WCF net.tcp:8012（タイムアウト 5 分、ADR-0002）** で接続。ほかに `POS4UTwoOperatorsCH`（二人制サブ画面）。

- **同一マシンのプロセス間のみ WCF net.tcp。マシンを跨ぐ通信は一律 HTTP Web API であり、WCF を使わない**（`.svc` は URL 互換の痕跡にすぎない）。
- プロセス跨ぎ / WCF 契約の変更は**バージョン互換**を保つ。**Device 関連の変更はレビューを経てから commit**（既知 gotcha）。

### VII. 検証不能境界の誠実 (Uncheckable Boundary Honesty)

〔導出: F3〕`Application/POS4UCloud/ExternalModule/Framework/POS4U.Framework.dll` は**ソースなし** → 内部挙動は **`uncheckable`**。

- 内部実装を憶測で断定しない。拡張は**公開フックポイントのみ**を経由する（`TranBase` / `CommandBase` / `Observer` / `EventCode` / `CheckDigitM10W31`）。
- フレームワーク挙動に関する仮定は**実機/実測で検証**する。できない場合は spec/plan に `[NEEDS CLARIFICATION]` / `unverified` を明示する。

### VIII. コンプライアンスと監査トレーサビリティ (Compliance & Audit Traceability)

〔導出: F1〕POS は税・取引・決済を扱い、監査可能性を損なってはならない。

- `TransactionLog` の完全性、販売状態機械（実測 SalesTranStates 28 / SelfStates 39 / CloseCountTranStates 28）の整合性を破壊しない。
- 金額 / 数量 / 税の処理は既存ドメインルールに従う（金額列は `[money]`。詳細は `.claude/knowledge/domain-knowledge/`）。
- 資格情報をコードに入れない。SQL は一律パラメタライズ（SP 呼び出しでインジェクション防止）。

---

## 技術制約 (Mandatory Stack · 実測)

| 項目 | 制約 |
|---|---|
| 言語/ランタイム | C# on **.NET Framework**（v4.0 主体 + v4.6.1）。⚠️ **ターゲットバージョン変更禁止**: POS 端末は **Windows XP / 7 / 10 / 11** に跨り、**v4.0 が XP 互換の上限**。引き上げると XP 端末が動作不能になる。新規コードは所属プロジェクトの現行ターゲットに従う。新規プロジェクトが必要な場合は配備端末の OS に応じ互換ターゲットを選ぶ（XP 端末に触れるものは v4.0 必須）。 |
| フロント UI | **WPF**（POS4U）+ **WinForms**（TRAN4U） |
| クラウド BO | **ASP.NET MVC5**（POS4UBO・Backoffice） |
| IPC | **WCF net.tcp**（店舗内プロセス間のみ） |
| エッジ API | **ASP.NET Web API（HTTP）**（POS4ULogicService。WCF ではない） |
| データ | **SQL Server（SQLEXPRESS）**・SP 中心。同一インスタンス二重 DB（Master / Tran） |
| テスト | **NUnit**。characterization + touch-only、カバレッジ数値ゲートなし（原則 III / testing-strategy.md） |
| コード規約 | **StyleCop**（`POS4U.ruleset`）。1 Class 1 File。全アセンブリ厳密名 |
| ビルド | **Visual Studio / MSBuild（Windows）**。3 sln: `POS4U_V4` / `POS4UBackground` / `POS4UBO_V4` |
| CI | 現状なし → 将来課題（GitLab CI / Azure） |

---

## 言語規約 (Language Conventions)

〔導出: F5〕成果物は正本チーム（日本語）へ還流可能であることを最優先する。`stpos-backend-kugelpos`（正式コードリポジトリ＝日本語）の慣例に整合。

| 対象 | 言語 |
|---|---|
| SDD 成果物（`specs/` 配下: spec / plan / tasks / research / data-model / contracts / quickstart / test-spec / test-results / spec_review / checklists） | **日本語** |
| SDD プロセスファイル（`.specify/` テンプレート・台帳、`.claude/skills/`、`.claude/knowledge/`、`CLAUDE.md`） | **日本語** |
| 憲章・ADR・ナレッジ層 | **日本語** |
| コードコメント | **日本語**（既存コードの慣例に従う。「なぜ」を説明し「何を」はコードで表現） |
| 変数・関数・クラス名 | **英語** |
| ログメッセージ | 既存慣例に従う（新規は周辺コードのパターンに合わせる） |
| コミットメッセージ | **Conventional Commits**: type/scope は英語、説明は日本語、`[spec:NNN-名]` タグ付与（下記ワークフロー参照） |
| ID・技術タグ | 英語のまま（FR/SC/TC/BP/ADR、verified / unverified / uncheckable、characterization / touch-only 等） |
| 対話言語 | ユーザー設定に従う（既定＝簡体中文）。**成果物の言語とは独立** |

> 境界注意: `trialpos-trec-docs`（チーム内部ナレッジ庫）は簡体中文が主であり、本規約の対象外。本リポジトリ（正式コード側）とは言語圏が異なることを混同しない。`/speckit-analyze` は成果物の言語整合性を検査する（違反 = MEDIUM）。

---

## 開発ワークフロー (SDD Workflow)

- **コマンドチェーン**: `/speckit-specify` → `clarify` → `plan`（after_plan フックで `test-spec` 自動生成）→ `tasks` → `implement`（after_implement フックで `test-results` 足場自動生成）→ `analyze`（**PR 前必須**、CRITICAL ゼロ化）。横断: `adr` / `approve-adr` / `feedback` / `approve-spec` / `checklist`（任意）/ `constitution`。
- **事前ロード**: 各コマンド前に `context-preload`（mandatory フック）が本憲章＋ `architecture-principles.md` ＋ ADR ＋関連 approved-specs ＋該当モジュール `domain-knowledge` をロードする。
- **人手ゲート（AI は代替不可）**: AI は成果物の初稿生成と整合性検出のみを担う。「これで良い」という最終判断は常に人間の責務である。

| ゲート | フェーズ | 担当 | 出力 |
|---|---|---|---|
| 仕様承認 | specify 終盤 | 有識者 / PO | spec.md → 承認済み ＋ `/speckit-approve-spec` で index 登録 |
| test-spec レビュー | plan 後 | 有識者 / QA | test-spec.md → 承認済み |
| test-results レビュー | implement 後（Windows 実行後） | 有識者 / QA | test-results.md → 承認済み（**マージ前の最終コミットで固定**、後付け禁止） |
| ADR 承認 | 随時 | 有識者 | ADR → 承認済み ＋ architecture-principles 反映 |
| 整合性検証 | PR 前 | 実装者（実行） | `/speckit-analyze` CRITICAL = 0 |

- **コミット規約**: Conventional Commits（type/scope 英語・説明日本語）＋ `[spec:NNN-名]` トレーサビリティタグ。原則 **1 タスク＝1 コミット**。例: `fix(discount): 小計値引の按分額を LineTotal に反映 [spec:001-fix-discount]`
- **成果物**: `specs/<NNN>-<名>/`（sequential 採番）、index-link モデル、永続 SDD 成果物として main 系へマージ。
- **ブランチ/マージ**: SDD 作業は `sdd/main`。feature ブランチは `sdd/main` から分岐。**merge commit（squash しない）** — SpecKit サブコミットの粒度を履歴に残し設計判断を追跡可能にする。`release*` ミラーブランチは `origin` とクリーンに保つ。
- **push 禁止**: origin は社内 GitLab 正本を指し、**fetch/バージョン切替のみ・push は無効化済み**。**いかなる push も事前の明示的許可が必須**（クローンの変更は正本へチーム既存チャネルで還流する）。

---

## ガバナンス (Governance)

- **権威の優先順位**: 本憲章 > `architecture-principles.md` > ADR > 説明文書。下位は本憲章と矛盾してはならない。
- **改訂（SemVer）**: MAJOR ＝ 原則の削除/再定義・後方非互換のガバナンス変更。MINOR ＝ 原則の新設/大幅拡張。PATCH ＝ 文言の明確化/事実訂正。改訂ごとに冒頭の **Sync Impact Report** を更新し、依存成果物（テンプレート/スキル/ナレッジ）を同期する。
- **適合性検証**: `/speckit-analyze` が PR 前に spec/plan/tasks の本憲章適合を検証する。CRITICAL 違反はゼロ化しなければ PR 不可。
- **例外は ADR**: 「小さな例外」の独断処理を許さない —「判断が必要な局面の記録」こそ本プロジェクトのナレッジ資産の中核である（F4）。明確な条項違反 → 作業停止 → `/speckit-adr`。グレーゾーンの岐路 → インライン記録で継続（二速 ADR、`legacy-sdd-disciplines.md` §6）。
- **適正規模の原則**: 残存寿命 2〜3 年に見合う統治投資に留める（F2）。重心は新機能/バグ修正の規律と挙動保全にあり、遠い将来のための過剰な制度設計はしない。

---

**Version**: 2.0.0 | **Ratified**: 2026-07-16 | **Last Amended**: 2026-07-18

> 本文書は SDD ツール基盤（標準 github/spec-kit）の管理下にあり、`/speckit-constitution` で改訂できる。v1.0.1（ユーザー承認済み）を基に、2026-07-18 のユーザー指示により第一原理から再導出・全面日本語化した（v2.0.0）。
