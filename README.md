# Sony Headphones Control

在 Windows 上通过逆向得到的 **Sony MDR / Tandem 协议**，本地控制索尼耳机的单文件小工具。
纯 Python 标准库实现（运行时不依赖任何第三方包），带系统托盘和本地 Web 控制面板。

> ## ⚠️ 只支持两款机型
>
> | 机型 | 协议 | 状态 |
> |---|---|---|
> | **WH-1000XM4** | MDR v1 | 完整实测 |
> | **LinkBuds S (WF-LS900N)** | MDR v2 | 完整实测 |
>
> 其他型号（WH-1000XM3 / XM5、WF-1000XM5、WF-C500、ULT WEAR 等）**没有做任何适配**。
> 它们可能用不同的协议族、不同的命令字节和不同的握手顺序，本项目不保证能用，也不会为它们做兼容。
>
> 本项目为非官方项目，与 Sony 没有任何关联。

## 它做什么

把耳机当成一个可以本地直连的设备：绕开手机 App，用蓝牙 RFCOMM 直接和耳机对话。

- **单设备视图**：用真实的 MDR 握手判断"应用现在控制的是哪一副"，界面只显示这一副，没有双设备选择器
- **降噪 / 环境声**：模式切换、20 级环境声、关注语音、风噪降低
- **音质**：EQ 预设与 6 段自定义、DSEE Extreme、连接质量（音质优先 / 稳定优先）
- **系统**：智能免摘（Speak-to-Chat）、取下暂停、触摸面板、自动断电、多点连接（读写）、左右耳按键分配
- **颜色识别**：`04 03` 读取系列与机身颜色（如白色 `0x02`），据此选择对应的产品图
- **其他**：明暗主题、原始帧日志、托盘菜单、单实例、开机自启

## 快速开始

### 环境

- Windows 10 / 11 x64
- Python 3.11+（源码运行）；构建 exe 需要 PyInstaller
- 耳机已和 PC 完成蓝牙配对，且**手机上的 Sound Connect 已完全退出**（一副耳机同时只接受一个 tandem 客户端）

### 源码运行

```bash
python app/appmain.py            # 启动托盘 + 本地面板
python app/appmain.py --port 9000
python app/server.py --port 8765 --open   # 只跑 Web 面板
```

浏览器打开 `http://127.0.0.1:8765/`。托盘右键可以打开面板、切换耳机、设置自启。

### 构建单文件 exe

```bash
cd app
python build.py                  # 输出 app/SonyHeadphonesControl.exe
python build.py --no-upx         # 不压缩
python build.py --console        # 保留控制台，便于看报错
```

### 指定耳机 MAC

仓库里**不含任何真实 MAC**。三种方式任选：

1. 面板里的「蓝牙 MAC」输入框，填完点「保存并重连」
2. 编辑 `%LOCALAPPDATA%\SonyHeadphonesControl\config.json`（源码模式是 `app/config.json`）
3. 命令行工具用环境变量：`set SONY_MAC=AA:BB:CC:DD:EE:FF`

首次运行时，程序会扫描 Windows 已配对的蓝牙设备，按型号名自动匹配并写回配置；
匹配不到就在面板里手动填。

## 项目结构

```
app/     本地 Web 面板 + 托盘（server.py / appmain.py / tray.py / bt_presence.py）
tools/   协议客户端与命令行工具（tandem_client.py / xm4_control.py / linkbuds.py 等）
docs/    协议文档
```

### 常用命令行工具

```bash
python tools/probe_device.py AA:BB:CC:DD:EE:FF     # 判断是 v1 还是 v2（INIT 返回 4/8 字节）
python tools/xm4_control.py status                 # XM4 一次读 10 项
python tools/linkbuds.py status                    # LinkBuds S 一次读 12 项
python tools/linkbuds.py anc on|off|ambient
python tools/linkbuds.py eq bass
python tools/sdp_probe.py                          # 探测 RFCOMM 通道
```

## 协议文档

| 文档 | 内容 |
|---|---|
| [`docs/protocol-reference.md`](docs/protocol-reference.md) | **推荐入口**：帧格式、连接、seq/ACK、命令空间、已验证功能的完整字节表、告警门控、已知限制 |
| [`docs/protocol-recon.md`](docs/protocol-recon.md) | 完整探索日志：APK 静态分析、真机抓包、判断失误与更正。**结论以 reference 为准** |
| [`docs/linkbuds-capabilities.md`](docs/linkbuds-capabilities.md) | LinkBuds S 能力清单与逐项命令 |

## 引用的开源项目

本项目是独立实现，**没有复制下列项目的源代码**；它们用于协议对照、字节布局确认和回归验证。
感谢这些作者把逆向结果公开出来。

### 协议文档与实现（主要参考）

| 仓库 | 本项目用到了什么 | 许可证 |
|---|---|---|
| [`mos9527/SonyHeadphonesClient`](https://github.com/mos9527/SonyHeadphonesClient)（含 `libmdr`） | 最主要的对照对象：v1 初始化顺序、告警开关、`RequestCommit` 应答逻辑；v2 的 `ModelColor` / `ModelSeries` 枚举与 `docs/device-support/` 的机型文档格式 | MIT |
| [`Plutoberth/SonyHeadphonesClient`](https://github.com/Plutoberth/SonyHeadphonesClient) | 最早的 v1 客户端参考（原版只做 v1） | MIT |
| [`AndreasOlofsson/mdr-protocol`](https://github.com/AndreasOlofsson/mdr-protocol) | tandem 帧格式、转义表、DataType 全表、seq 语义、服务 UUID `96CC203E-…` 的文字文档 | 未核 |
| [`AndreasOlofsson/libmdr`](https://github.com/AndreasOlofsson/libmdr) / `mdrd` | 纯协议库与 D-Bus 守护进程的实现对照 | 未核 |
| [`enxy0/omarchy-sony-xm5`](https://github.com/enxy0/omarchy-sony-xm5) → `docs/protocol.md` | V2 逐字节参考（XM5 / WF-XM5），多点的告警应答流程由这里定位 | 未核 |
| [Gadgetbridge](https://codeberg.org/Freeyourgadget/Gadgetbridge) `SonyProtocolImplV1.java` / `V2.java` | v1 字节布局的权威参考（**仅阅读**，未抄代码） | AGPL-3.0 |

### Python / 其他实现（对照参考）

| 仓库 | 本项目用到了什么 | 许可证 |
|---|---|---|
| [`gabamnml/omarchy-sony-headphones`](https://github.com/gabamnml/omarchy-sony-headphones) | 同为纯标准库 Python + v1 的对照组，用于交叉验证状态解析（**仅阅读**） | AGPL-3.0 |
| [`impankratov/sony-headphones-control-py`](https://github.com/impankratov/sony-headphones-control-py) | 降噪四模式的实现对照 | GPL-2.0 |
| [`Leonard013/sony-ult-ctl`](https://github.com/Leonard013/sony-ult-ctl) | V2 CLI / 菜单栏实现参考 | 未核 |
| [`estvoid/sony_headphones`](https://github.com/estvoid/sony_headphones) | V2 脚本实现参考 | — |

### 固件与素材

| 来源 | 用途 | 说明 |
|---|---|---|
| [`lzghzr/MDR_Proxy`](https://github.com/lzghzr/MDR_Proxy) | 固件下载 / 刷机代理，用于核对固件版本号 | 不是协议实现 |
| [`helgesverre/sony-vp-extract`](https://github.com/helgesverre/sony-vp-extract) | XM4 固件 dump 与语音包解密的思路参考 | — |
| [Wikimedia Commons: `Sony_logo.svg`](https://commons.wikimedia.org/wiki/File:Sony_logo.svg) | 界面左上角的 SONY 字标矢量（纯文字标识，PD-textlogo） | 商标归 Sony |

### 合规说明

- **AGPL 项目（Gadgetbridge、omarchy-sony-headphones）只读不抄。** 我们阅读其字节布局，再用自己的代码重新实现；本仓库不包含它们的任何代码。
- 协议枚举常量（`ModelColor`、`ModelSeries`、`GsInquiredType` 等）参考的是 `libmdr`（MIT）的公开头文件。
- 本项目以 MIT 许可发布，见 [`LICENSE`](LICENSE)。

## 仓库里不包含什么

为了不重新分发他人的版权素材，以下内容**刻意没有放进仓库**：

- Sony 官方产品图、Sound Connect 应用图标、APK 内提取的图片（版权归 Sony）
- 任何真机抓包文件（`btsnoop` 等，含设备地址）
- 任何真实蓝牙 MAC 地址
- 固件文件

界面上的机型图片因此会退化为一个中性的占位图形。想显示真机图片，把自己的图片放到
`app/assets/` 下即可（会自动优先使用）：

```
app/assets/xm4.png         # WH-1000XM4
app/assets/ls900n.png      # LinkBuds S（默认色）
app/assets/ls900n_w.png    # LinkBuds S 白色
```

`tools/make_assets.py`、`tools/make_brand_assets.py`、`tools/make_cloud_assets.py`
是本地生成这些素材的脚本，需要你自备 Sound Connect APK；**它们生成的图片版权仍归 Sony，仅限个人使用**。

## 已知限制

- **只支持 WH-1000XM4 与 LinkBuds S**，其他机型不做适配
- 一副耳机同时只接受一个 tandem 客户端；手机 App 连着时会 `SO_ERROR=10060`
- Windows only（`AF_BTH` / RFCOMM）
- LinkBuds S 的 v2 握手比 v1 多一步 `06 00`，缺了后面所有命令都不响应
- v1 的 `04 03`（系列与颜色）回复格式尚未实测，因此颜色识别只在 v2 上启用
- 耳机休眠时连接会超时；连续快速试探 RFCOMM 通道可能让耳机暂时不可达

## 免责声明

- 仅供学习与研究使用，使用风险自负。
- 写操作会改变耳机设置；虽然都做了读回校验，但不排除个别固件版本行为不同。
- 本项目不提供固件刷写功能，也不建议这么做。
- "Sony"、"WH-1000XM4"、"LinkBuds" 等名称与商标归 Sony Group Corporation 所有。
- 本项目与 Sony 无任何隶属、赞助或背书关系。

## License

[MIT](LICENSE)
