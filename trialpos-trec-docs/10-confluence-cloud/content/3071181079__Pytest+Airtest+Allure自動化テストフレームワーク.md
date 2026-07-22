---
confluence_id: 3071181079
title: "Pytest+Airtest+Allure自動化テストフレームワーク"
parent_id: 3071475818
version: 6
version_at: 2024-12-26T02:48:45.928Z
status: current
source_url: https://retailai.atlassian.net/wiki/spaces/POSSYS/pages/3071181079
synced_at: 2026-07-07
---

# Pytest+Airtest+Allure自動化テストフレームワーク

## **1. フレームワーク概要**

* **Pytest**: テストケースの管理と実行。
* **Airtest**: モバイルおよびデスクトップアプリの自動化テストツール。
* **Allure**: テスト結果を美しく可視化するレポート生成ツール。

## **2. 環境構築**

* 必要なライブラリのインストール
* 環境構築手順書参照資料：<custom data-type="smartlink" data-id="id-0">https://retailai.atlassian.net/wiki/spaces/POSSYS/pages/3024420984</custom>  

## **3. プロジェクト構成**

* プロジェクトの基本的な構成は以下の通りです：

```
project/
│
├── tests/                         # テストケースのディレクトリ
│   ├── test_sample.py             # Pytestのテストケース例
│   ├── test_login.py              # ログイン関連のテストケース
│   ├── conftest.py                # Pytestの設定ファイル
│   ├── airtest_cases/             # Airtestスクリプトのディレクトリ
│   │   ├── test_case_1.air        # Airtestスクリプトファイル
│   │   └── test_case_2.air        # Airtestスクリプトファイル
│   └── reports/                   # Allureレポートの生成ディレクトリ
│
├── utils/                         # ユーティリティモジュール
│   ├── airtest_runner.py          # Airtestの実行ユーティリティ
│   ├── config.py                  # 設定ファイルのユーティリティ
│   └── logger.py                  # ログモジュール
│
├── requirements.txt               # プロジェクトの依存ライブラリ
├── pytest.ini                     # Pytestの設定ファイル
├── allure-results/                # Allureの結果ファイルディレクトリ
└── README.md                      # プロジェクト説明文書
```

* **コアモジュールの説明**

    * テストケースディレクトリ
    
        * Pytestテストケース：ロジックが明確で独立性の高い機能テストケースを記述します。  
          サンプルファイル：`test_sample.py`
        
            ```python
            import pytest
            from utils.airtest_runner import run_airtest_case
            
            @pytest.mark.parametrize("case", ["test_case_1.py", "test_case_2.py"])
            def test_airtest_cases(case):
                result = run_airtest_case(case)
                assert result['success'], f"Airtest case {case} failed!"
            
            ```
        
            * **※注意点**
            
                * **pytestテストケースの命名規則**
                
                    ・ ファイル名：`test_`で始まるか、`_test`で終わるようにします（例：`test_example.py`）。

                
                
                    ・ メソッド名：`test_`で始まるようにします（例：`test_addition()`）。

                
                
                    ・ クラス名：`Test`で始めるようにし、`__init__`メソッドの使用を避けます。

                
                * **テストケースの独立性を確保**
                
                    ・テストケース間の依存を避けることで、1つのテスト失敗が他のテストケースに影響を与えないようにします。

                
                
            
        * Airtestスクリプト：GUIベースの自動化テストケースを記述します。モバイルやデスクトップ環境をサポートしています。  
          サンプルファイル：`test_case_1.air`
        
            ```python
            from airtest.core.api import *
            
            auto_setup(__file__)
            
            # サンプル：ログインテスト
            start_app("com.example.app")
            touch(Template("login_button.png"))
            text("username", enter=True)
            text("password", enter=True)
            touch(Template("submit_button.png"))
            
            ```
        
    * Allureレポート
    
        * Allureの統合：
        
            * `pytest.ini`にAllureの設定を追加します。
            
                ```python
                [pytest]
                addopts = --alluredir=allure-results
                
                ```
            * コマンドでAllureレポートを生成します。
            
                ```python
                allure generate allure-results -o allure-report --clean
                
                ```
            
        * Allureレポートのパラメータと説明
        
            * 基本的なパラメータ
            
                * --alluredir=<ディレクトリ>：Allureの元データを生成するディレクトリのパスを指定します。pytest実行時に結果がこのディレクトリに書き込まれます。
                * --clean-alluredir：テスト実行前に指定されたディレクトリをクリアし、最新のテスト結果のみを保持します。
                * --maxfail=<数値>：許容されるテスト失敗の最大数を設定します。この数に達するとテストの実行が停止します。
                
                    ```python
                    pytest --alluredir=allure-results
                    
                    ```
                
            * テストケース内でのAllureアノテーション
            
                * @allure.step("ステップ説明")：テストステップを定義するために使用します。レポートにはステップ名が明確に表示されます。
                * @allure.title("テストケースタイトル")：テストケースのタイトルを設定し、レポートに表示します。
                * @allure.description("説明")：テストケースの詳細な説明を設定し、背景情報を提供します。
                * @allure.severity("レベル")：テストケースの重要度を設定します（例: `blocker`, `critical`, `normal`, `minor`, `trivial`）。
                * @allure.story("サブ機能")：特定のサブ機能モジュールにテストケースを関連付けます。
                * @allure.feature("主要機能")：特定の主要機能モジュールにテストケースを関連付けます。
                * @allure.link("リンク先URL")：レポートに外部リンク（バグ追跡システムや要件ドキュメントなど）を追加します。
                * @allure.issue("バグリンク")：関連するバグのリンクを追加します。
                * @allure.testcase("テストケースリンク")：関連するテストケースのリンクを追加します。
                * @allure.attachment：レポート添付ファイル（スクリーンショット、ログファイルなど）を追加します。
                
                    ```python
                    import allure
                    
                    @allure.feature("ユーザー管理")
                    @allure.story("ユーザーログイン")
                    @allure.severity("blocker")
                    def test_login():
                        allure.step("ユーザー名を入力")
                        allure.step("パスワードを入力")
                        allure.attach("詳細情報", "ユーザーログイン成功の詳細情報")
                        assert login() == True
                    
                    ```
                
            * Allureレポートの生成と表示
            
                * allure generate：Allureレポートを生成します。
                * allure open：Allureレポートのローカルサーバーを起動します。
                * allure serve：レポートを生成してその場で表示します。
                * allure report：レポート出力先ディレクトリやオプションをカスタマイズします。
                
            
        
    * ユーティリティモジュール
    
        * Airtest実行ユーティリティ：`airtest_runner.py`
        
            ```python
            import subprocess
            
            def run_airtest_case(case_path):
                cmd = f"airtest run {case_path}"
                process = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                return {
                    "success": process.returncode == 0,
                    "output": process.stdout,
                    "error": process.stderr,
                }
            
            ```
        * 設定ユーティリティ：グローバル設定パラメータ（デバイス情報やパス設定など）を管理します。`config.py`
        
            ```python
            CONFIG = {
                "device": "Android:///",
                "airtest_case_path": "./tests/airtest_cases/"
            }
            
            ```
        * **ログモジュール**：統一されたログ出力機能を提供します。`logger.py`
        
            ```python
            import logging
            
            def setup_logger():
                logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
                return logging.getLogger(__name__)
            
            logger = setup_logger()
            
            ```
        
    
* **依存関係ファイル**`requirements.txt`

    ```python
    pytest>=7.0.0
    airtest>=1.2.7
    allure-pytest>=2.9.45
    
    
    ```

## **4. 実行手順**

* 依存関係のインストール

    ```
    pip install -r requirements.txt
    
    ```
* テストの実行

    ```
    pytest tests/ --alluredir=allure-results
    
    ```
* Allureレポートの生成

    ```
    allure generate allure-results -o allure-report --clean
    
    ```
* Allureレポートの表示

    ```
    allure open allure-report
    
    ```

このように構成することで、Pytestのテスト管理、AirtestによるGUI自動化、およびAllureによる美しいテストレポートを統合した、包括的な自動化テストフレームワークを実現できます。
