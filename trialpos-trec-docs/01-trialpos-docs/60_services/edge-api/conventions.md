---
title: 边缘 API 横切约定（路由 / 脱敏 / 鉴权 / 基类 / 错误码）
layer: 60_services
module: POS4ULogicService
audience: [重构开发, 读码]
genre: reference
code_baseline: latest
code_refs:
  - Application/Source/POS4ULogicService/App_Start/WebApiConfig.cs
  - Application/Source/POS4ULogicService/POS4ULogicServiceLibrary.cs
  - Application/Source/POS4ULogicService/ApiControllerBase.cs
  - Application/Source/POS4ULogicService/Global.asax.cs
  - Application/Source/POS4ULogicService/Controllers/MemberServiceController.cs
verification: verified
related:
  services:
    - ./index.md
    - ./controllers.md
    - ./command_layer.md
owner: jinianxiang
updated: 2026-07-14
---

# 边缘 API 横切约定

> 本文汇总 `POS4ULogicService` 层贯穿所有 Controller 的横切约定：路由风格、请求处理统一模式、日志脱敏、访问码鉴权、错误码、基类模式。逐 Controller 的 action 见 [controllers.md](./controllers.md)。

---

## 1. 路由：属性路由 + `.svc` 兼容后缀

- 路由注册唯一入口：`Application/Source/POS4ULogicService/App_Start/WebApiConfig.cs:25` `config.MapHttpAttributeRoutes()`。**不使用约定式路由表**，全部路由声明在各 Controller 的 `[RoutePrefix]` / `[Route]` 特性上。
- **`.svc` 后缀约定**：10 / 11 个 Controller 的 `RoutePrefix` 带 `.svc`（如 `POSLogicWebService.svc`、`DataService.svc`），是从旧 WCF 服务迁移到 Web API 时**为保持客户端 URL 不变**而保留的历史后缀，实现已是纯 HTTP Web API。
- **例外**：`ItemDetectionServiceController` 的 `RoutePrefix` 为 `ItemDetectionService`（无 `.svc`，`ItemDetectionServiceController.cs:15`）。
- 路由片段常用 `nameof(方法名)`（如 `BackgroundServiceController`、`ItemDetectionServiceController`、`ReportServiceController` 的部分 action），使 URL 与方法名强绑定。

---

## 2. 请求处理统一模式（手写型 Controller）

直接继承 `ApiController` 的 Controller，其每个业务 action 内部遵循几乎一致的骨架。以 `MemberServiceController.GetMemberInfo`（`MemberServiceController.cs:42-88`）为范式：

```csharp
Stopwatch sw = Stopwatch.StartNew();                              // ① 计时开始
try {
    string content = this.Request.Content.ReadAsStringAsync().Result;      // ② 读请求体
    string encryptedContent = POS4ULogicServiceLibrary.ContentEncrypt(content); // ③ 脱敏（供日志）
    string ip = POS4ULogicServiceLibrary.GetClientIPLogString(this.Request);    // ④ 取客户端 IP
    Logger.Info($"... content = {encryptedContent}");             // ⑤ 记日志（密文）
    var req = POS4ULogicServiceLibrary.GetRequest<T>(content);    // ⑥ JSON 反序列化
    if (req == null) { /* ErrorParameter */ }
    if (!POS4ULogicServiceLibrary.IsValidAccessCode(...)) { /* ErrorAccessCode */ } // ⑦ 鉴权
    return _logic.XXX(req);                                       // ⑧ 委托业务逻辑
} catch (Exception ex) { Logger.Error(...); /* ErrorException */ }
finally { Logger.Info($"... totalTime = {sw.ElapsedMilliseconds} msec"); }  // ⑨ 计时结束
```

关键点：**请求体明文绝不落日志**，只记 `ContentEncrypt` 后的密文（③⑤）；进入业务前必过 `req==null` 与 `IsValidAccessCode` 两道校验（⑥⑦）。

---

## 3. 日志脱敏：AES-256（CBC / PKCS7）

`POS4ULogicServiceLibrary`（`Application/Source/POS4ULogicService/POS4ULogicServiceLibrary.cs`）静态构造密钥并提供加解密：

| 项 | 值 | 行号 |
|---|---|---|
| 加密提供者 | `AesCryptoServiceProvider`（静态单例 `_provider`） | :29, :45-53 |
| 密钥派生 | `Rfc2898DeriveBytes`（PBKDF2），`IterationCount = 1013` | :40-42 |
| Salt | `FrameworkLibrarySettingValues.EncryptionSaltKey` | :39 |
| 模式 / 填充 | `CipherMode.CBC` / `PaddingMode.PKCS7` | :48-49 |
| KeySize / BlockSize | 取自 `RijndaelManaged`（默认 256 / 128） | :46-47 |
| 加密方法 | `ContentEncrypt(text)` → Base64 | :61 |
| 解密方法 | `ContentDecrypt(text)` | :91 |

用途：把请求/响应正文加密后写日志，供事后排查而不泄露明文（会员、金额等敏感数据）。加解密在 `lock (_lockProvider)` 内串行（:65, :93）。

---

## 4. 鉴权：AccessCode 与 VerifyUrl

两种入口校验，均在 `POS4ULogicServiceLibrary`：

- **`IsValidAccessCode(companyCode, storeCode, terminalNo, accessCode)`**（:187）：从 `SettingMaster` 取该端末配置的 `AccessCode`（`LogicServiceFrameworkSettingMasterKeys.AccessCode`，:195-198），与请求携带的 `AccessCode` 比对，不符即拒。**几乎所有业务 action 用之**（多以 `IsValidAccessCode(companyCode, string.Empty, 0, req.AccessCode)` 调用）。
  - 失败返回错误码 `MessageIds.ErrorAccessCode`（见 §5）。
  - `ReportServiceController` 另包了个私有同名 `IsValidAccessCode(companyCode, accessCode)`（`ReportServiceController.cs:529`）转调该方法并记错误日志。
- **`VerifyUrl(companyCode, storeCode, terminalNo, out errorCode, out errorMessage)`**（:221）：仅校验 `terminalNo` 可解析为整数（:229），**不校验 accessCode**。注释说明：BO 场景下企业码可能不存在、accessCode 校验会误报，故暂时只校验端末番号（:210-213）。`BackOfficeServiceController` 的部分 action 用之（如 `:237` / `:304` / `:371`）。

---

## 5. 错误码（`MessageIds`）

统一错误结构 `ServiceResultBase { IsSuccess, ErrorCode, ErrorMessage }`。常见错误码来源 `ForYouApplications.POS4U.Common.Const.MessageIds`：

| 错误 | 触发 |
|---|---|
| `MessageIds.ErrorParameter` | 请求体反序列化失败（`GetRequest` 返回 null）或参数非法 |
| `MessageIds.ErrorAccessCode` | `IsValidAccessCode` 校验失败 |
| `MessageIds.ErrorException` | action 内未捕获异常（catch 兜底） |

> `MessageIds` 常量定义在 `Common.Const`（本层引用），非本层文件。

---

## 6. 两种 Controller 基类模式

| 模式 | 基类 | 特征 | 使用者 |
|---|---|---|---|
| **手写型** | `ApiController` | 每个 action 内手写 §2 的 try/catch/finally + 脱敏 + 鉴权 | POSLogicWebService / BackOffice / DataService / CartMTran / MTran / Member / Receipt / CheckHealth（9 个） |
| **封装型** | `ApiControllerBase` | 用泛型 `ExecuteLogic<TParam,TResult>(func)` 统一「读体→反序列化→null 判定→异常兜底」 | BackgroundService / ReportService |
| **私有封装** | `ApiController` | 自带私有 `ExecuteLogic<TParam,TResult>(func, parameter)`（内含鉴权） | ItemDetectionService（`:120` / 鉴权 `:139`） |

`ApiControllerBase.ExecuteLogic` 定义：`Application/Source/POS4ULogicService/ApiControllerBase.cs:21-40`（`GetErrorResult` 在 :49）。封装型 action 常写成表达式体单行（如 `BackgroundServiceController.cs:46` `=> this.ExecuteLogic<...>(...)`）。

---

## 7. 序列化与网络

- **JSON 序列化**：`GetRequest<T>`（`POS4ULogicServiceLibrary.cs:122`）内部用 `SerializeUtility.DeserializeFromJsonString<T>`；`LogicService.ServiceAccessor.ServiceAccessorLibrary` 出站调用用 `DataContractJsonSerializer`（`ServiceAccessorLibrary.cs:431/448`）。详见 [command_layer.md §ServiceAccessor](./command_layer.md)。
- **连接上限**：`Global.asax.cs:29` `ServicePointManager.DefaultConnectionLimit = 12`。
- **优雅停机**：`Application_End` 轮询 `_processingRequestCount` 归零后再退出（`Global.asax.cs:39-60`）。

---

## 8. 可信度与核查

`verification: verified`：§1–§7 断言均实测 最新发布，file:line 逐条核对。AES 具体密钥/salt 值（如 `PostContentPassword`）虽在源码明文可见，本文不转录，仅记其算法参数。`SettingMaster` / `MessageIds` / `SerializeUtility` 等被引用类在本层之外，本文只描述其在本层的用法。
