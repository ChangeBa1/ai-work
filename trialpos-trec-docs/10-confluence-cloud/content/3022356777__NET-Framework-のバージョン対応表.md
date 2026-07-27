---
confluence_id: 3022356777
title: ".NET Framework のバージョン対応表"
parent_id: 3022225734
version: 1
version_at: 2024-11-11T05:41:27.677Z
status: current
source_url: https://retailai.atlassian.net/wiki/spaces/POSSYS/pages/3022356777
synced_at: 2026-07-07
---

# .NET Framework のバージョン対応表

「.NET Framework」のバージョンは「Visual Studio」や「C#」のバージョンと複雑に絡み合っていて、相互関係や機能を確認するのが大変です。

すぐに確認できるように、バージョン対応表を作成してみました。

##   
.NET Framework バージョン対応表

| .NET Framework | インストール可能  
Windows | インストール可能  
Windows Server | Visual Studio | C# | 新機能 |
| --- | --- | --- | --- | --- | --- |
| 1.0 | 2000, XP | 2000, 2003 | 2002 | 1.0 | - |
| 1.1 | 2000, XP, Vista | 2000, 2003, 2008 | 2003 | 1.2 | ODBCとOracle Database用のデータ接続  
IPv6 |
| 2.0 | 2000, XP, **Vista**, **7**, 8, 8.1, 10 | 2000, **2003**, **2008**, 2012, 2016 | 2005 | 2.0 | 64ビットシステム  
.NET Micro Framework  
\[C#\]ジェネリック  
\[C#\]イテレータ |
| 3.0 | XP, **Vista**, **7**, 8, 8.1, 10 | 2003, 2008, 2012, 2016 | 2005 | 2.0 | WPF・WCF・WF・WCS |
| 3.5 | XP, Vista, **7**, 8, 8.1, 10 | 2003, 2008, 2012, 2016 | 2008, 2010 | 3.0 | <custom data-type="smartlink" data-id="id-0">http://ASP.NET</custom>  MVC  
<custom data-type="smartlink" data-id="id-1">http://ASP.NET</custom>  AJAX  
\[C#\]LINQ  
\[C#\]ラムダ式  
\[C#\]暗黙的型付け(var) |
| 4 | XP, Vista, 7 | 2003, 2008 | 2012 | 4.0 | F#言語  
Dynamic Language Runtime  
MEF  
Velocity  
Windows タッチ  
<custom data-type="smartlink" data-id="id-2">http://ADO.NET</custom>  Entity Framework  
\[C#\]Parallel Extensions(Parallel/PLINQ)  
\[C#\]dynamic型  
\[C#\]オプション引数/名前付き引数 |
| 4.5 | Vista, 7, **8**, **8.1** | 2008, **2012** | 2013 | 5.0 | Windowsストアアプリ  
\[C#\]非同期プログラミング(async/await)  
\[C#\]Caller Info |
| 4.6 | Vista, 7, 8, 8.1, **10** | 2008, 2012, **2016** | 2015 | 6.0 | RyuJIT  
.NET Native  
.NET Compiler Platform |
| 4.7 | 7, 8.1, 10, **10 Creators Update** | 2008, 2012, 2016 | 2017 | 7.0 | Windows Formsの高DPI  
WPFのタッチ  
拡張された暗号  
\[C#\]タプル  
\[C#\]パターンマッチング |
| 4.8 | 7, 8.1, 10 | 2008, 2012, 2016, 2019 | 2019 | 7.3 | JITとNGENの強化  
ZLibのセキュリティ強化  
Windows Formsのアクセシビリティ強化  
WCPのService Behavior強化  
WPFの高DPI強化 |
| Core 1.0 | 7, 8, 8.1, 10 | 2012, 2016 | 2015 Update 3, 2017 | 6.0 | <custom data-type="smartlink" data-id="id-3">http://ASP.NET</custom>  Core  
オープンソース化  
Mac/Linux/iOS/Android対応 |
| Core 1.1 | 7, 8, 8.1, 10 | 2012, 2016 | 2015 Update 3, 2017 | 6.0 | 1380個のAPI追加 |
| Core 2.0 | 7, 8, 8.1, 10 | 2012, 2016 | 2017 15.5 | 7.1 | .NET Standard 2.0対応  
<custom data-type="smartlink" data-id="id-4">http://ASP.NET</custom>  Core 2.0  
Entity Framework Core 2.0  
<custom data-type="smartlink" data-id="id-5">http://ML.NET</custom>  |
| Core 2.1 | 7, 8, 8.1, 10 | 2012, 2016 | 2017 15.8.6 | 7.2 | <custom data-type="smartlink" data-id="id-6">http://ASP.NET</custom>  Core 2.1  
Entity Framework Core 2.1  
.NET Core グローバルツール  
HttpClient のパフォーマンス改善  
Windows互換機能パック  
\[C#\]Span<T>, Memory<T> |
| Core 2.2 | 7, 8, 8.1, 10 | 2012, 2016 | 2017 15.9 | 7.3 | <custom data-type="smartlink" data-id="id-7">http://ASP.NET</custom>  Core 2.2  
Entity Framework Core 2.2 |
| Core 3.0 | 7, 8, 8.1, 10 | 2012, 2016 | 2019 | 8.0 | .NET Standard 2.1対応  
WPF・Windows Forms  
\[C#\]Null 許容参照型  
\[C#\]Interfaceのデフォルト実装  
\[C#\]非同期ストリーム  
\[C#\]Range型, Index型 |
| Core 3.1 | 7, 8, 8.1, 10, 11 | 2012, 2016 | 2019 16.4 | 8.0 | C++/CLI対応  
<custom data-type="smartlink" data-id="id-8">http://ASP.NET</custom>  Core 3.1  
Entity Framework Core 3.1 |
| 5 | 7, 8, 8.1, 10, 11 | 2012, 2016 | 2019 16.8 | 9.0 | 「.NET Framework」と「.NET Core」を統合  
<custom data-type="smartlink" data-id="id-9">http://ASP.NET</custom>  Core 5.0  
Entity Framework Core 5.0 |
| 6 | 7, 8, 8.1, 10, 11 | 2012, 2016 | 2022 17.0 | 10.0 | Arm64対応  
ホット リロード  
.NET MAUI |
| 7 | 10, 11 | 2012, 2016, 2019 | 2022 17.4 | 11.0 | ネイティブ AOT  
HTTP/3  
\[C#\]生文字列リテラル |
| 8 | 10, 11 | 2019, 2022 | 2022 17.8 | 12.0 | Blazor United  
\[C#\]コレクション式  
\[C#\]プライマリ コンストラクター |

* インストール可能欄の太文字はプレインストールを表します。
* インストール可能欄に表記がなくてもインストールできる場合もありますが、動作保証されません。
* Windows Server のバージョン表記は「R2」も含みます。
* 新機能については別記事「[.NET Framework の新機能を超簡単に説明する](http://qiita.com/nskydiving/items/2ff8285acb72c4e59caf)」を参照してください。

‌

# .NET Framework の互換性

「.NET Framework」のバージョンは、以下の表に示す互換グループごとに互換性を確保しています。  
例えば「.NET Framework 3.5」をインストールすれば「.NET Framework 2.0」のアプリケーションを実行できます。

| 　互換グループ　 | 　所属バージョン　 |
| --- | --- |
| .NET Framework 1.0 | 1.0 |
| .NET Framework 1.1 | 1.1 |
| .NET Framework 2.0, 3.x | 2.0, 3.0, 3.5 |
| .NET Framework 4.x | 4, 4.5, 4.6, 4.7, 4.8 |
| .NET Core 1.ｘ | Core 1.0, Core 1.1 |
| .NET Core 2.ｘ | Core 2.0, Core 2.1, Core 2.2 |
| .NET Core 3.ｘ | Core 3.0, Core 3.1 |
| .NET 5 | 5 |
| .NET 6 | 6 |
| .NET 7 | 7 |
| .NET 8 | 8 |

# 参考

.NET Framework サポート ライフサイクル ポリシーについて (2015年10月)  
<custom data-type="smartlink" data-id="id-10">https://blogs.msdn.microsoft.com/visualstudio_jpn/2015/10/18/net-framework-201510/</custom> 

.NET Frameworkのバージョンを整理する  
<custom data-type="smartlink" data-id="id-11">http://www.atmarkit.co.jp/ait/articles/1211/16/news093.html</custom> 

++C++; \[C# の機能一覧（索引的なもの）\] バージョン  
<custom data-type="smartlink" data-id="id-12">http://ufcpp.net/study/csharp/list_versions.html</custom> 

.NETにおけるマネージヒープとガベージコレクション  
[http://qiita.com/mima_ita/items/8303f2a476e8630f0728](http://qiita.com/mima_ita/items/8303f2a476e8630f0728)
