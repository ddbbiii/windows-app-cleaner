# Windows 应用清理器

面向 Windows 10/11 的原生桌面应用清理工具。它提供常驻悬浮球、前台与通知区域应用识别、白名单和两阶段安全清理。

## 主要功能

- 原生 `C# / .NET 10 / WPF` 单进程架构
- 启动默认收起，点击悬浮球展开，面板失焦自动关闭
- 多显示器 Per-Monitor DPI V2 拖动与边界修正
- 全屏应用或游戏运行时自动隐藏悬浮球
- 前台定义为任务栏应用，后台定义为 Windows 通知区域中可确认身份的应用
- 双状态应用显示为相邻的前台行和后台行
- 单项清理、批量清理前台、批量退出后台应用
- 先发送 `WM_CLOSE`，两秒后对残留应用汇总询问是否强制结束
- 强退前复核 PID、启动时间和 exe 路径，保护 Explorer、系统 Shell 和本工具
- 全局快捷键、系统托盘、开机启动和进程名白名单

## 开发运行

```powershell
dotnet run --project .\src\WindowsAppCleaner\WindowsAppCleaner.csproj -c Debug
```

运行测试：

```powershell
dotnet test .\WindowsAppCleaner.slnx -c Release
```

生成自包含 x64 版本：

```powershell
dotnet publish .\src\WindowsAppCleaner\WindowsAppCleaner.csproj `
  -c Release -r win-x64 --self-contained true `
  -p:PublishTrimmed=false -o .\artifacts\publish
```

## 配置

安装版配置位于 `%LocalAppData%\WindowsAppCleaner\config.json`。便携版目录中存在 `portable.flag` 时，配置保存在程序目录。

保留兼容字段：

- `hotkey`
- `allowlist_process_names`
- `autostart_enabled`
- `minimize_to_tray_on_launch`
- `cleanup_mode`

新增字段：

- `schema_version`
- `floating_position`
- `hide_in_fullscreen`

首次启动会导入旧版项目目录中的 `config.json`，并将旧启动 VBS 迁移为当前用户的注册表启动项。

## 清理语义

- 清理前台：关闭目标任务栏窗口。窗口消失后，即使应用退到托盘也视为成功。
- 清理后台：退出拥有通知区域图标的整个应用，因此会同时关闭该应用的前台窗口。
- 强制结束：只在正常关闭未完成且用户确认后执行。
- `explorer.exe` 只允许关闭具体文件窗口，永不强退整个 Shell。

## 发布

推送 `v*` 标签后，GitHub Actions 会运行测试并生成：

- 自包含便携 ZIP
- Inno Setup 用户级安装包
- SHA256 校验文件

当前发布物未签名，Windows SmartScreen 可能显示提示。

## 已知边界

Windows 没有公开、稳定的 API 可以完整枚举其他应用的通知区域图标。当前实现只把 `NotifyIconSettings` 中已显示、并且能与正在运行 exe 精确匹配的条目归为后台；身份不确定的进程不会被清理。
