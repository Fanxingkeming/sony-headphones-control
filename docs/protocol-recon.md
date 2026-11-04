# Sony Sound Connect 协议逆向 · 探索日志
> 这是过程记录（含试错与更正）。**要查协议字节请看 `sony-protocol-reference.md`**，
> 那份是提炼后的参考版，结论以它为准。

# Sony Sound Connect 13.3.0 协议侦察报告

生成时间：2026-11-02  |  工具链：REA 6.8.0 + jadx-headless-mcp 0.7.1（JADX 0.7.1 引擎）

## 1. 目标本体

| 项 | 值 |
|---|---|
| 文件 | `E://Downloads//sound_connect_v13.3.0.apk` |
| 包名 | `com.sony.songpal.mdr` |
| 版本 | 13.3.0（versionCode 130305109） |
| minSdk / targetSdk | 30 / 36 |
| SHA-256 | `e6c5ac8085d5cb785a9391b53ef96944c3aac9dcd20512794a4a4847e819e1a2` |
| 规模 | 29,015 类，9,055 资源 |
| 蓝牙权限 | BLUETOOTH, BLUETOOTH_ADMIN, BLUETOOTH_SCAN, BLUETOOTH_CONNECT, 精确定位 |

这是 SonyHeadphonesClient 当年逆向的那套 App 的现役版本（Headphones Connect 已更名为 Sound Connect）。

## 2. 协议层在哪

协议核心不在 `com.sony.songpal.mdr.*`（那是应用业务层），而在：

```
com.sony.songpal.tandemfamily.message.mdr
├── v1
│   ├── table1   104 类   ← Table#1 命令（SonyHeadphonesClient 的 T1）
│   └── table2    18 类   ← Table#2 命令（EQ/UPSCALE 等）
└── v2
    ├── table1   154 类   ← 新版本 Table#1（XM4/XM5 走这套）
    ├── table2    67 类
    └── EnableDisable / FunctionType / OnOffSettingValue /
        RequestResult / StreamingStatus / UnavailableReason
```

"tandem" 是索尼内部对这套耳机控制协议的叫法。上层业务模型在
`com.sony.songpal.mdr.kmp.tandem.command.v1/v2.table1/table2`（Kotlin Multiplatform 重写版），
两者一一对应。

## 3. 命令字节表（已提取）

`Command` 是枚举，`byteCode()` 返回线上字节，`fromByteCode(byte)` 用于解析。
完整表见同目录 CSV，下面各取前 24 条。

### 3.1 Table#1 / protocol v1（129 条）

| byte | name |
|---|---|
| `0x00` | CONNECT_GET_PROTOCOL_INFO |
| `0x01` | CONNECT_RET_PROTOCOL_INFO |
| `0x02` | CONNECT_GET_CAPABILITY_INFO |
| `0x03` | CONNECT_RET_CAPABILITY_INFO |
| `0x04` | CONNECT_GET_DEVICE_INFO |
| `0x05` | CONNECT_RET_DEVICE_INFO |
| `0x06` | CONNECT_GET_SUPPORT_FUNCTION |
| `0x07` | CONNECT_RET_SUPPORT_FUNCTION |
| `0x10` | COMMON_GET_BATTERY_LEVEL |
| `0x11` | COMMON_RET_BATTERY_LEVEL |
| `0x13` | COMMON_NTFY_BATTERY_LEVEL |
| `0x14` | COMMON_GET_UPSCALING_EFFECT |
| `0x15` | COMMON_RET_UPSCALING_EFFECT |
| `0x17` | COMMON_NTFY_UPSCALING_EFFECT |
| `0x18` | COMMON_GET_AUDIO_CODEC |
| `0x19` | COMMON_RET_AUDIO_CODEC |
| `0x1B` | COMMON_NTFY_AUDIO_CODEC |
| `0x1C` | COMMON_GET_BLUETOOTH_DEVICE_INFO |
| `0x1D` | COMMON_RET_BLUETOOTH_DEVICE_INFO |
| `0x22` | COMMON_SET_POWER_OFF |
| `0x24` | COMMON_GET_CONNECTION_STATUS |
| `0x25` | COMMON_RET_CONNECTION_STATUS |
| `0x27` | COMMON_NTFY_CONNECTION_STATUS |
| `0x28` | COMMON_GET_CONCIERGE_DATA |

### 3.2 Table#1 / protocol v2（157 条）

| byte | name |
|---|---|
| `0x00` | CONNECT_GET_PROTOCOL_INFO |
| `0x01` | CONNECT_RET_PROTOCOL_INFO |
| `0x02` | CONNECT_GET_CAPABILITY_INFO |
| `0x03` | CONNECT_RET_CAPABILITY_INFO |
| `0x04` | CONNECT_GET_DEVICE_INFO |
| `0x05` | CONNECT_RET_DEVICE_INFO |
| `0x06` | CONNECT_GET_SUPPORT_FUNCTION |
| `0x07` | CONNECT_RET_SUPPORT_FUNCTION |
| `0x0F` | GET_TEST |
| `0x10` | COMMON_GET_CAPABILITY |
| `0x11` | COMMON_RET_CAPABILITY |
| `0x12` | COMMON_GET_STATUS |
| `0x13` | COMMON_RET_STATUS |
| `0x15` | COMMON_NTFY_STATUS |
| `0x18` | COMMON_SET_PARAM |
| `0x19` | COMMON_NTFY_PARAM |
| `0x20` | POWER_GET_CAPABILITY |
| `0x21` | POWER_RET_CAPABILITY |
| `0x22` | POWER_GET_STATUS |
| `0x23` | POWER_RET_STATUS |
| `0x24` | POWER_SET_STATUS |
| `0x25` | POWER_NTFY_STATUS |
| `0x26` | POWER_GET_PARAM |
| `0x27` | POWER_RET_PARAM |

## 4. v1 与 v2 差异（这是 XM4/XM5 的关键）

| | 数量 |
|---|---|
| 共同命令 | 83 |
| 仅 v1 | 46 |
| 仅 v2 | 74 |

v2 新增里最值得注意的是 **LE Audio（LEA）** 一组，共 13 条：

- `LEA_GET_CAPABILITY`
- `LEA_GET_EXTENDED_PARAM`
- `LEA_GET_PARAM`
- `LEA_GET_STATUS`
- `LEA_NTFY_EXTENDED_PARAM`
- `LEA_NTFY_PARAM`
- `LEA_NTFY_STATUS`
- `LEA_RET_CAPABILITY`
- `LEA_RET_EXTENDED_PARAM`
- `LEA_RET_PARAM`
- `LEA_RET_STATUS`
- `LEA_SET_EXTENDED_PARAM`

以及通用能力查询 `COMMON_GET_CAPABILITY` / `COMMON_RET_CAPABILITY`——
v1 没有这一层，v2 改成先问能力再按能力取参数。**SonyHeadphonesClient 之所以对 XM4 只做到"部分可用"，就是因为它按 v1 的固定命令集硬编码，而 XM4 及以后的机型走 v2 的能力协商模型。**

## 5. 还没拿到的部分

诚实说明边界，以下都还没做：

1. **帧结构**：tandem 消息在实际 SPP/RFCOMM 流上的封装（header 字节、表号、长度、校验）。要在 `com.sony.songpal.tandemfamily.*` 的传输层或 `*Protocol*` 类里找，JADX 侧尚未定位到。
2. **Payload 布局**：每个命令的具体字段偏移。`v1.table1.param.*`（AlertAction 之类）是枚举类，但真正的字节序列化在各类的 `toByteArray`/`fromBytes` 里。
3. **传输通道**：APK 里搜索 `Rfcomm` / `Spp` 零命中，说明经典蓝牙 SPP 连接可能封装在别的命名空间或 native 层。

## 6. 建议的下一步

给 SonyHeadphonesClient 补 XM4/XM5，优先级如下：

1. 先提 `COMMON_GET_CAPABILITY` / `CONNECT_GET_PROTOCOL_INFO` 的 payload 结构 —— 拿到机型能力位图，才知道该发哪些命令。
2. 再提 v2 `table1.param.*` 各枚举的字节值（和本报告同样的方法，反编译 `<clinit>`）。
3. 最后处理传输层：确认 v2 是否仍走 SPP/RFCOMM 同一 channel，还是迁到 BLE GATT。

## 7. 复现命令

```bash
# 概览
rea inspect-android-package E://Downloads//sound_connect_v13.3.0.apk

# 类名检索（大小写敏感的子串）
rea search-android-classes E://Downloads//sound_connect_v13.3.0.apk tandemfamily.message.mdr.v2.

# 类结构（字段/方法/签名）
rea inspect-android-class E://Downloads//sound_connect_v13.3.0.apk \
  com.sony.songpal.tandemfamily.message.mdr.v1.table1.Command

# 反编译单个方法（提取枚举字节值靠它）
rea inspect-android-method E://Downloads//sound_connect_v13.3.0.apk \
  com.sony.songpal.tandemfamily.message.mdr.v1.table1.Command "<clinit>"
```

## 8. 证据与限制

- 每条结论都有 REA Evidence ID 可回溯，原始返回存在 `raw/`。
- **限制**：两个 `Command.<clinit>` 的 JADX Java 反编译都失败，回退到 smali（`mode: smali, fell_back: true`）。字节表是从 smali 的 `const/16` + `invoke-direct` 寄存器分析还原的，逻辑上可靠，但未经运行时验证。
- 命令字节是 `byte`，报告里统一转成无符号（`& 0xFF`）。smali 中为负数（如 `-0x7F` → `0x81`）属正常。

## 9. 传输层与表号（2026-11-02 补充）

### 9.1 传输通道：经典 SPP 仍然存在

对 6 个 dex 做特征串扫描，结果：

| 特征 | 命中 |
|---|---|
| `00001101-0000-1000-8000-00805F9B34FB`（SPP 服务 UUID） | 1 处 |
| `createRfcommSocketToServiceRecord` | 2 处 |
| `createInsecureRfcommSocket` | 1 处 |
| `BluetoothSocket` | 2 处 |
| `connectGatt` / `BluetoothGatt` | 24 / 24 处 |

**结论：v2 协议没有抛弃 SPP。** 应用同时使用 SPP（tandem 主通道）和 BLE GATT。
`com.sony.songpal.tandemfamily.ble.*`（`BleTandemInitiationResult`、`BleTandemSessionCloseResult`）
说明 BLE 是 tandem 的第二条承载，而不是替代品。SonyHeadphonesClient 的连接层思路仍然成立。

设备侧佐证：当前 PC 上 WH-1000XM4 已配对（`AABBCCDDEE01`），Windows 只绑定了
AVRCP（0x110C / 0x110E），没有自动创建 SPP 虚拟串口——这与索尼客户端直连 RFCOMM
通道而非走 COM 口的行为一致。

### 9.2 表号（帧头的 data type 字节）

`com.sony.songpal.tandemfamily.TandemfamilyTableNumber`，`fromDataTypeByte(byte)` 用于解析：

| byte | 枚举 |
|---|---|
| `0x00` | TANDEM_NO1 |
| `0x01` | ACK |
| `0x02` | MC_NO1 |
| `0x07` | SSH |
| `0x08` | DJ |
| `0x09` | ICD |
| `0x0A` | EV |
| `0x0B` | LED_BULB |
| `0x0C` | MDR_NO1 |
| `0x0D` | COMMON |
| `0x0E` | MDR_NO2 |
| `0x0F` | PRODUCT_INTERNAL |

`MDR_NO1 = 0x0C`（Table#1）、`MDR_NO2 = 0x0E`（Table#2）、`COMMON = 0x0D`、`ACK = 0x01`。
这与 SonyHeadphonesClient 里写死的 T1/T2 表号完全一致，**说明帧头的表号层在 v1/v2 之间没变**，
变的是表内命令集和能力协商。

### 9.3 当前掌握的信息汇总

| 层 | 状态 |
|---|---|
| 传输 | ✅ SPP UUID + RFCOMM API 确认存在 |
| 表号 | ✅ 0x00–0x0F 全表已提取 |
| 命令字节 | ✅ v1 129 条 / v2 157 条 |
| 帧封装（起始符、序号、长度、校验） | ❌ 仍未定位 |
| Payload 字段布局 | ❌ 未做 |

## 10. 帧类型字节（Frame data type）

`com.sony.songpal.tandemfamily.message.DataType`，构造参数为 `(name, ordinal, byteCode, ackRequired)`，
`byteCode()` 是帧头第一个字节，`ackRequired()` 决定该帧是否需要对端回 ACK。

| byte | 枚举 | 需 ACK |
|---|---|---|
| `0x00` | DATA | 是 |
| `0x02` | DATA_MC_NO1 | 是 |
| `0x07` | DATA_SSH | 是 |
| `0x09` | DATA_ICD | 是 |
| `0x0A` | DATA_EV | 是 |
| `0x0C` | DATA_MDR | 是 |
| `0x0D` | DATA_COMMON | 是 |
| `0x0E` | DATA_MDR_NO2 | 是 |
| `0x01` | ACK | 否 |
| `0x10` | SHOT | 否 |
| `0x12` | SHOT_MC_NO1 | 否 |
| `0x19` | SHOT_ICD | 否 |
| `0x1A` | SHOT_EV | 否 |
| `0x1C` | SHOT_MDR | 否 |
| `0x1D` | SHOT_COMMON | 否 |
| `0x1E` | SHOT_MDR_NO2 | 否 |
| `0x27` | LARGE_DATA_SSH | 是 |
| `0x2C` | LARGE_DATA_MDR | 是 |
| `0x2D` | LARGE_DATA_COMMON | 是 |
| `0xFF` | UNKNOWN | 是 |

观察到的规律：

- `DATA_*` = 0x00 基址 + 表偏移：MC_NO1 `+0x02`、SSH `+0x07`、ICD `+0x09`、EV `+0x0A`、
  **MDR `+0x0C`（Table#1）**、COMMON `+0x0D`、**MDR_NO2 `+0x0E`（Table#2）**
- `SHOT_*` = `DATA_*` + 0x10，单发（不需 ACK）
- `LARGE_DATA_*` = `DATA_*` + 0x20，大载荷
- `ACK` = 0x01，`UNKNOWN` = 0xFF

**这意味着帧头结构是 `[帧类型字节][表号/命令...]`，且 MDR 表在 v1/v2 下字节相同。
SonyHeadphonesClient 的 `T1 = 0x0C` / `T2 = 0x0E` 常量无需修改。**

### 10.1 还缺的四个字段

| 待定项 | 说明 |
|---|---|
| 起始标记 | 帧是不是以固定字节开头（如 `0x3E`），尚未在代码里确认 |
| 序号 | 是否有递增 seq 字段及其清零规则 |
| 长度 | 显式长度字段还是靠流边界 |
| 校验 | 是否存在 checksum/CRC |

`v1.table1.b`（消息基类）的 `d()` 只是 `return f().toByteArray()`，`f()` 返回
`ByteArrayOutputStream` 且反编译返回空体（疑似接口默认实现或由子类覆写），
真正写帧头的代码还没定位到。

## 11. 帧格式（已由真机流量验证）

抓包环境：MEIZU 20（Android 16，KernelSU），Sony Sound Connect 连接 WH-1000XM4，
`persist.bluetooth.btsnooplogmode=full`，47,321 字节 HCI 日志，236 帧。

### 11.1 线上格式

```
3E | dataType | seq | 00 | 00 | len_hi | len_lo | payload ... | checksum | 3C
```

| 字段 | 长度 | 说明 |
|---|---|---|
| `3E` | 1 | 起始标记 |
| dataType | 1 | 见第 10 节：`0C`=Table#1、`0E`=Table#2、`01`=ACK |
| seq | 1 | 序号，0/1 交替；ACK 帧回显被确认帧的 seq |
| `00 00` | 2 | 保留，实测恒为 0 |
| len | 2 | payload 字节数，大端 |
| payload | N | 首个字节是命令码，其后是参数 |
| checksum | 1 | `sum(dataType .. payload 末字节) & 0xFF` |
| `3C` | 1 | 结束标记 |

**校验和公式在 236 帧中 234 帧成立（99.2%）**，因此可以确认。
唯一的 2 个例外都是 payload 长 21 字节的 `EQEBB` 扩展信息帧（`0x5B`），
它们的末字节不符合简单求和——暂记为未解释项，可能这类帧走另一套校验。

### 11.2 传输细节

- L2CAP **CID 0x0047**，RFCOMM 复用器上的 **DLCI 18**
- 控制字节 `0xEF`（host→device）/ `0xFF`（device→host），均为 UIH
- 单帧上限受 1 字节 RFCOMM 长度字段约束：payload ≤ 255 字节
  （超过则走 `LARGE_DATA_*` 类型 0x2C/0x2D）

### 11.3 真实握手序列（节选，按时间顺序）

| 方向 | 表 | 命令 | seq | payload |
|---|---|---|---|---|
| in | T1 | `PLAY_NTFY_STATUS` | seq=1 | `a5010002` |
| out | T1 | `CONNECT_GET_PROTOCOL_INFO` | seq=0 | `0000` |
| in | T1 | `PLAY_NTFY_PARAM` | seq=0 | `a90100` |
| in | T1 | `CONNECT_RET_PROTOCOL_INFO` | seq=1 | `01007000` |
| out | T1 | `CONNECT_GET_CAPABILITY_INFO` | seq=1 | `0200` |
| in | T1 | `CONNECT_RET_CAPABILITY_INFO` | seq=0 | `03000a1138383a43393a45383a39313a42453a3642` |
| out | T2 | `LEA_GET_PARAM` | seq=0 | `460105` |
| in | T2 | `LEA_RET_PARAM` | seq=1 | `4701052514141042363634334136333543334233393730` |
| out | T1 | `UPDT_GET_PARAM` | seq=1 | `3607` |
| in | T1 | `UPDT_RET_PARAM` | seq=0 | `3707cb` |
| out | T1 | `UPDT_GET_PARAM` | seq=0 | `3608` |
| in | T1 | `UPDT_RET_PARAM` | seq=1 | `370814` |
| out | T1 | `UPDT_GET_PARAM` | seq=1 | `3609` |
| in | T1 | `UPDT_RET_PARAM` | seq=0 | `370925` |
| out | T1 | `UPDT_GET_PARAM` | seq=0 | `360a` |
| in | T1 | `UPDT_RET_PARAM` | seq=1 | `370a14` |
| out | T1 | `UPDT_GET_PARAM` | seq=1 | `360b` |
| in | T1 | `UPDT_RET_PARAM` | seq=0 | `370b1042363634334136333543334233393730` |
| out | T1 | `UPDT_GET_PARAM` | seq=0 | `3602` |
| in | T1 | `UPDT_RET_PARAM` | seq=1 | `3702054850303032` |
| out | T1 | `UPDT_GET_PARAM` | seq=1 | `3603` |
| in | T1 | `UPDT_RET_PARAM` | seq=0 | `37030b4d44524944323934333032` |
| out | T1 | `UPDT_GET_PARAM` | seq=0 | `3604` |
| in | T1 | `UPDT_RET_PARAM` | seq=1 | `370402434e` |
| out | T1 | `UPDT_GET_PARAM` | seq=1 | `3605` |
| in | T1 | `UPDT_RET_PARAM` | seq=0 | `370500` |
| out | T1 | `UPDT_GET_PARAM` | seq=0 | `3606` |
| in | T1 | `UPDT_RET_PARAM` | seq=1 | `37061030303030303030303032323630373233` |
| out | T2 | `LEA_GET_STATUS` | seq=1 | `420101` |
| in | T2 | `LEA_RET_STATUS` | seq=0 | `43010100` |
| out | T2 | `LEA_GET_PARAM` | seq=0 | `460101` |
| in | T2 | `LEA_RET_PARAM` | seq=1 | `47010101` |
| out | T2 | `LEA_GET_STATUS` | seq=1 | `420102` |
| in | T2 | `LEA_RET_STATUS` | seq=0 | `43010201` |
| out | T2 | `LEA_GET_PARAM` | seq=0 | `460102` |
| in | T2 | `LEA_RET_PARAM` | seq=1 | `470102f0` |

可以看到 XM4 在**同一条链路上同时使用 Table#1（0x0C）和 Table#2（0x0E）**：
`CONNECT_*` 和大部分状态查询走 T1，`LEA_*`（LE Audio）走 T2。
这解释了为什么只实现 T1 的旧客户端在 XM4 上会缺功能。

### 11.4 复现

```bash
adb shell su -c 'setprop persist.bluetooth.btsnooplogmode full'
adb shell su -c 'svc bluetooth disable; svc bluetooth enable'
# 在手机 App 里操作耳机
adb shell su -c 'cp /data/misc/bluetooth/logs/btsnoop_hci.log /sdcard/'
adb pull /sdcard/btsnoop_hci.log
python tools/tandem_session.py btsnoop_hci.log
```

## 12. PC 端客户端实测（Windows AF_BTH）

### 12.1 结论：Windows 可以直连，控制通道是 RFCOMM **9**

不依赖 COM 口，直接 `WSASocketW(AF_BTH, SOCK_STREAM, BTHPROTO_RFCOMM)` +
`sockaddr_bth` 连接。通道扫描结果：

| 通道 | 反应 | 判断 |
|---|---|---|
| 8 | 接受连接，发探测帧无任何回应 | 非控制通道 |
| **9** | 返回 `3e0c010000000401007000823c` | **tandem 控制通道** |
| 10 | 返回 `ff550200ee10` | 其他厂商协议 |
| 11 | 返回 `type=0x00`，含 ASCII 串 `54f095d4` | 疑似设备信息服务 |

通道 9 的返回解析：`CONNECT_RET_PROTOCOL_INFO`，payload `01 00 70 00`，
与 Android 端抓包完全一致。**这证明 PC 端方案可行，SonyHeadphonesClient 补丁路线成立。**

### 12.2 三个必须踩过的坑

1. **BTH_ADDR 是数值不是字节串**：`AA:BB:CC:DD:EE:01` → `0xAABBCCDDEE01`。
   按小端字节翻转填会去 paging 一个不存在的 MAC，表现为 `10060 超时`。
2. **阻塞 connect 会挂死**：必须非阻塞 connect + select，且 select 可写**不代表成功**，
   要再查 `SO_ERROR`（`getsockopt(SOL_SOCKET, SO_ERROR)`）。
3. **channel=0（SDP 自动解析）在 Windows 上直接挂起**，必须写死通道号。

### 12.3 当前阻塞

连续试探多次后连接开始返回 `10064 (WSAEHOSTDOWN)`。耳机处于自动关机/休眠状态时
就是这个表现，需要佩戴或按电源键唤醒后重连。

工具：`tools/tandem_client.py`（握手）、`channel_scan.py`（通道扫描）、
`rfcomm_probe.py`（连通性探测）。

### 12.4 真机握手成功（2026-11-03 00:15）

```
[+] 已连接 AA:BB:CC:DD:EE:01 (channel=9)

CONNECT_GET_PROTOCOL_INFO  -> 3e0c000000000200000e3c
                           <- 3e010100000000023c            (ACK)
                           <- 3e0c010000000401007000823c    payload 01 00 70 00

CONNECT_GET_CAPABILITY_INFO -> 3e0c01000000020200113c
                           <- 3e0c010000001503000a1138383a43393a45383a39313a42453a3642333c
                              payload 03 00 0a 11 "AA:BB:CC:DD:EE:01"
```

PC 端从零实现，成功与真机完成协商并读到能力信息。capability 响应里直接带着
耳机自己的 MAC（ASCII `AA:BB:CC:DD:EE:01`）。

**未完成**：`COMMON_GET_BATTERY_LEVEL` 的响应没拿到——耳机持续重发上一条
capability 帧，说明我们的 ACK 未被接受。抓包里主机的 ACK 字节固定为
`3e010100000000023c`（seq=1），但按此发送仍判无效，说明 ACK 的 seq 语义
还没完全搞对（可能与设备侧待确认队列或 RFCOMM credit 有关），留待下一轮解决。

### 12.5 读操作全部打通（2026-11-03 00:22）

**决定性发现：ACK 的 seq = 被确认帧 seq XOR 1**（"下一个期望序号"）。
从 236 帧抓包里统计 59 组 in-DATA → out-ACK，57 组符合此规律。改对之后全部请求都有响应。

实测输出：

| 查询 | 请求 payload | 响应 payload |
|---|---|---|
| CONNECT_GET_PROTOCOL_INFO | `00 00` | `01 00 70 00` |
| CONNECT_GET_CAPABILITY_INFO | `02 00` | `03 00 0a 11` + ASCII MAC |
| COMMON_GET_BATTERY_LEVEL | `10 00` | `11 00 64 00`（100%） |
| NCASM_GET_STATUS | `62 02` | `63 02 00` |
| NCASM_GET_PARAM | `66 02` | `67 02 01 02 02 01 00 00` |
| EQEBB_GET_STATUS | `52 01` | `53 01 00` |
| OPT_GET_STATUS | `82 01` | `83 01 00 00` |

**尚未验证**：写操作（SET）。抓包里可见 `68 02 11 02 00 01 00 14 → 69 02 01 02 00 01 00 14`
形态的 SET 帧，实现路径已明确，但未对真机执行。

### 12.6 写操作验证（2026-11-03 00:25）

**EQ 写入格式（抓包 + 真机双向确认）**：

```
请求  58 01 <preset> 00
响应  59 01 <preset> 06 <band0> <band1> ... <band5>
```

真机实测（预设 0 → 1 → 复原 0）：

| 步骤 | 发送 | 耳机回显 |
|---|---|---|
| 读状态 | `52 01` | `53 01 00` |
| 设预设 1 | `58 01 01 00` | `59 01 01 06 00 00 00 00 00 00`（6 段全 0） |
| 复原 | `58 01 00 00` | `59 01 00 06 0a 0a 0a 0a 0a 0a`（6 段全 10 = 平直） |

**写入路径已被真机接受并生效**：耳机回显的 6 段增益随写入值变化，复原后回到
`0a` 全平直。注意 `53 01 00` 这个状态字节不随预设变化，它不是"当前预设"，
具体语义待定。

### 12.7 尚未解开的：降噪模式写入

两次抓包（含用户手动切换降噪）里，NCASM 只有以下 SET，且两次内容完全相同：

```
68 02 11 02 00 01 00 14    (param 0x00, value 0x14 = 20)
68 02 11 02 02 01 00 00    (param 0x02, value 0x00)
```

向 param 0x02 写入 0x01 时耳机返回成功（`69 02 01 …`）但状态未变，回显值仍为 00，
说明 param 0x02 不是模式字段。`NCASM_GET_CAPABILITY (60 02)` 返回
`61 02 02 00 01 02 00 14 01 14`，其中 0x14=20 应该是环境声等级上限。

**另一个发现**：本次抓包里 tandem 流量分布在 **L2CAP cid 0x45 和 0x4a 两条通道**上，
不是上一次的 0x47，说明索尼会开多个 RFCOMM 通道。解析器已按 DLCI 18 聚合，未区分
通道，这对读操作无影响，但分析写操作时需要按通道分开看。

### 12.8 降噪模式写入：映射确认（2026-11-03 00:37）

**已由真机反复验证的映射**：

| 模式 | 帧格式 | 回读 |
|---|---|---|
| 降噪 | `68 02 00 02 00 01 00 <level>` | `67 02 00 02 00 01 00 <level>` |
| 环境声 | `68 02 11 02 00 01 00 <level>` | `67 02 01 02 00 01 00 <level>` |

- 第 3 字节是**模式组**：`0x00` = 降噪，`0x11` = 环境声（设备回显会把 `0x11` 规整成 `0x01`）
- 第 8 字节是等级，实测 15 有效
- `66 02` 的回读第 3 字节直接反映当前模式组（0/1），这是判断当前模式的正确方式；
  `62 02` 的返回 `63 02 00` 与模式无关
- 验收过程：环境声 15 → group 变 1、level 15；再设降噪 → group 变 0。两个方向都成立

**仍未解开**：

1. 「关闭」模式：对该组写 level=0 无效，实际走的是抓包里第三帧
   `68 02 11 02 02 01 00 00` 的形态（param=0x02），未验证。
2. 写 level=20 时耳机回显 15，等级上限/写法需再确认。

### 12.9 一个排查坑

抓包里 App 每次切换都发**同样的三帧**，导致早期误判为"帧不携带模式信息"。真正原因是
当时只解析了 DLCI 18，且没有意识到同一批字节在不同时刻含义不同。用 A/B 交替发送 +
用户听感确认，才定位到第 3 字节是模式组。

### 12.10 「关闭」模式是个陷阱（2026-11-03 00:44）

三种模式的写入映射（均已真机验证触发）：

| 模式 | 帧 |
|---|---|
| 降噪 | `68 02 00 02 00 01 00 <level>` |
| 环境声 | `68 02 11 02 00 01 00 <level>` |
| 关闭 | `68 02 00 02 02 01 00 00` |
| 退出关闭（未验证成功） | `68 02 00 02 02 01 00 01` ← 无效 |

**严重问题：写入「关闭」后，本客户端无法再切回降噪或环境声。**
实测被无视的尝试：

- `68 02 00 02 00 01 00 14`（降噪，连发两次）→ 回显 `69020002 02 010000`，状态仍是关闭
- `68 02 11 02 00 01 00 14`（环境声）→ 同上
- `68 02 00 02 02 01 00 01` / `68 02 11 02 02 01 00 01` → 均被规整成 value 0
- `param 02` 写 1 或 2 全部被设备压成 0

**必须由手机 App 手动切回。**

因此结论是：**不要让客户端发送「关闭」帧**。在搞清退出机制前，关闭模式只实现"进入"不实现"恢复"，
等于给用户挖坑。这条比功能缺失严重得多。

另外注意：`69` 开头的回显**不能作为状态确认依据**，它只表示命令被接收，不代表状态已改变。
之前误判"恢复成功"就是因为看了回显。

### 12.11 关闭状态可退出，但映射方向存在矛盾（2026-11-03 00:52）

**好消息：关闭不是死锁。** 重放 App 抓到的五帧序列后，耳机恢复正常：

```
68 02 11 02 02 01 00 00
34 01 00
94 01 00
68 02 11 02 00 01 00 14
68 02 11 02 02 01 00 00
```

用户确认重放后进入**降噪**状态。因此 12.10 里"客户端无法退出关闭"的结论要修正为：
**可以退出，但必须先 `param 02 = 0`、再 `param 00 = level`、再 `param 02 = 0`，
单独发 `param 00` 会被忽略。** 那层包裹是必需的。

**坏消息：模式组映射方向出现矛盾，尚未定论：**

| 观察 | 发送 | 用户反馈 |
|---|---|---|
| A | `68 02 00 02 00 01 00 14`（group 0x00） | 降噪 |
| B | 五帧重放，结束于 group 0x11 + level 20 | 降噪 |

两次都说"降噪"，但组不同。可能原因：A 那次耳机本来就在降噪（我误判为"切换成功"），
或用户听感判断有偏差。**必须做一次干净的 A/B 才能定论**，且不能再依赖 `66 02` 回读。

**判断依据的教训**：`66 02` 的回显从头到尾都在回显最后一次 SET 的内容，
包括那次假的"恢复成功"（回显 param 00 = 20 但实际没变）。**这个查询不能用作状态确认。**
唯一可靠的是用户听感或手机 App 显示。

### 12.12 下次开工的第一步

1. 耳机连上 PC 后，先做**一次干净的环境声↔降噪 A/B**（每次只发一组包裹帧，间隔 8 秒），
   用听感确定 group 0x00 / 0x11 到底哪个是降噪。
2. 找到真正能读状态的查询。候选：`62 02` 只回 `63 02 00` 恒定值；
   可能需要读 `NCASM_GET_CAPABILITY` 之外的命令，或状态藏在 `0x65 NTFY_STATUS` 的推送里
   （抓包四次都没见过 0x65，值得怀疑）。
3. 把最终映射和包裹规则固化成 `set_nc(mode, level)`，加"写完必须听感确认"的注释。

### 12.13 最终状态（2026-11-03 00:58，收工）

**已确认可用：**

| 能力 | 状态 |
|---|---|
| 连接（RFCOMM 通道 9，AF_BTH） | ✅ 稳定 |
| 帧格式 / 校验和 / ACK(seq^1) | ✅ 236+ 帧验证 |
| 读电量、协议版本、能力信息、EQ 状态、NC 参数 | ✅ 真机返回正确值 |
| EQ 写入 | ✅ 回显的 6 段增益随写入变化并复原 |
| 环境声/降噪/关闭 写入 | ⚠️ 被 ACK，但**听感无法确认生效** |

**关键疑点（必须承认）**：用户对"降噪 vs 关闭"的听感测试回答"不确定"。
降噪开关的听感差异本应非常明显，无法分辨意味着**写入很可能没有真正改变模式**，
耳机只是回了 ACK。因此 12.8/12.10/12.11 里"映射已确认"的结论**要降级为"未证实"**。

**为什么之前的"确认"不可靠**：
- `69` 回显 = 命令被接收，不等于状态改变
- `66 02` 回读 = 最后一次 SET 的复制，不是状态
- 用户听感在嘈杂/未佩戴场景下分辨率不足
- 三次"看起来成功"可能都是误判叠加

### 12.14 明天的新路线：不要继续猜字节

现有方法的根本缺陷是**没有可靠的状态观测**。改用有观测的手段：

1. **Frida 挂钩 App**（手机已 root，KernelSU）：hook `com.sony.songpal.tandemfamily.*`
   的发送方法，直接看 App 在"切到降噪"时构造的字节，而不是从抓包反推。
   - 优点：能看到完整调用栈 + 参数，绕开协议逆向
   - 前置：手机上装 frida-server（arm64），从 PC 注入
2. **状态观测**：用 `NCASM_GET_CAPABILITY (60 02)` 之外的命令，或直接读耳机推送的
   `0x65 NTFY_STATUS`——但四次抓包从未出现该帧，需先确认它是否存在。
3. **兜底**：既然读不可靠，就让"写入"这一侧完全对齐 App 的字节序列（Frida 抓到的原样），
   不做任何推测性修改。

**今晚的净成果**：协议骨架（帧格式、校验、ACK、通道）已经稳固到可以直接写客户端；
卡住的是 NC 模式语义，而这不是靠抓包能解决的，需要 Frida 级别的观测。

### 12.15 更正：模式组方向（2026-11-03 01:00，App 侧确认）

**手机 App 显示耳机当前为「降噪」，而最后一次生效的写入是 group `0x11` 的包裹帧**
（`68 02 11 02 00 01 00 14`）。因此：

| 更正项 | 原记录（12.8） | 更正后 |
|---|---|---|
| group `0x11` | 环境声 | **降噪**（App 确认） |
| group `0x00` | 降噪 | 环境声（**未证实**） |

12.8 节的方向记录是错的，以此节为准。

**另外，之前的「关闭」写入其实是生效的**：用户当时对听感"不确定"，但后续重放五帧
把耳机恢复成降噪（App 确认），反推出 1.4s 那次 `68 02 00 02 02 01 00 00` 确实把
耳机切到了关闭。听感判断不可靠，App 显示才是准的。

**当前仍待验证**：
1. group `0x00` 是否等于环境声（需一次 App 确认）
2. 关闭状态下的恢复路径（本次是通过重放五帧恢复的，五帧里的关键帧尚不明确）

## 13. 最终结论（2026-11-03 16:20，全部经手机 App 截图验证）

### 13.1 三种模式的写入帧

| 模式 | 帧 | 验证方式 |
|---|---|---|
| 降噪 | `68 02 **11** 02 **02** 01 00 **00**` | 我方通道写入 → App 显示降噪 |
| 环境声 | `68 02 **11** 02 **00** 01 00 **<等级>**` | 我方通道写入 → App 显示环境声音 |
| 关闭 | `68 02 **00** 02 **02** 01 00 **00**` | App 操作抓包 + 截图确认 |

**字节语义：**

| 位置 | 含义 |
|---|---|
| 第 3 字节 | 模式组：`0x11` = 降噪/环境声，`0x00` = 关闭 |
| 第 5 字节 | 参数项：`0x02` = 模式开关，`0x00` = 环境声等级 |
| 第 8 字节 | 值（等级 1–20，或模式开关的 0） |

### 13.2 关键教训：观测手段

之前连续误判的根因是**没有可靠的状态观测**：

| 观测方式 | 是否可靠 |
|---|---|
| `69` 开头的回显 | ❌ 只表示命令被接收 |
| `66 02` 回读 | ❌ 部分状态无响应；有响应时只复制最后一次 SET |
| `62 02` 回读 | ❌ 恒为 `63 02 00`，与模式无关 |
| 听感 | ❌ 嘈杂环境下分辨不出 |
| **手机 App 截图** | ✅ 唯一可靠 |

突破方法：`adb shell input tap` 点 App + `screencap` 截图读状态。
配合抓包 diff（对比操作前后的日志字节增量），能精确定位每一步发的帧。

### 13.3 定位关闭命令的关键手法

1. 抓包日志取基线 `c_before.log`
2. 用 adb 点击 App 的「关闭」
3. 再取 `c_after2.log`
4. 按 `(cid, dlci)` 拆流做差集，只保留出站新增字节
5. 解出的唯一 SET 帧即 `68 02 00 02 02 01 00 00`

这套流程可复用于定位任何未知功能的帧。

### 13.4 工具

| 脚本 | 用途 |
|---|---|
| `tandem_client.py` | 协议客户端（连接/握手/请求） |
| `nc_control.py` | 降噪控制 nc / ambient N / off |
| `tandem_by_cid.py` | 按 L2CAP cid + DLCI 拆流 |
| `tandem_session.py` | 还原双向按时间排序的帧会话 |
| `channel_scan.py` | RFCOMM 通道扫描 |

### 13.5 补充验证：三种模式均可在 PC 端独立完成（2026-11-03 16:16）

按"先写命令 → 断开手机蓝牙 → 开 App 截图"的流程逐个验证：

| 步骤 | 我方发送 | App 显示 | 截图 |
|---|---|---|---|
| 1 | `68 02 11 02 02 01 00 00`（降噪） | 降噪高亮 | `v1.png` |
| 2 | `68 02 00 02 02 01 00 00`（关闭） | 关闭高亮 | `v2.png` |

结合此前单帧 `68 02 11 02 00 01 00 14` → App 显示「环境声音」，
**三种模式全部由 PC 端客户端驱动成功，无一依赖手机 App。**

最后已把耳机恢复为降噪状态。

**验证流程（可复现）：**
```bash
adb shell su -c 'svc bluetooth disable'      # 让出耳机
python tools/nc_control.py nc          # 或 ambient N / off
adb shell su -c 'svc bluetooth enable'
adb shell am start -n com.sony.songpal.mdr/.vim.activity.MdrMainActivity
adb shell screencap -p /sdcard/x.png && adb pull /sdcard/x.png
# 查看截图确认模式
```

## 14. 三处重要更正（2026-11-03 16:45，对照 SonyHeadphonesClient 源码后）

### 14.1 帧格式：长度是 4 字节，且载荷有转义

**正确格式**（与 `SonyHeadphonesClient/Client/CommandSerializer.cpp` 一致，并已用本仓库实现往返验证）：

```
3E | ESCAPE( type | seq | size(4字节大端) | payload | checksum ) | 3C
```

**转义规则**（此前完全不知道，是解析出错的原因）：

| 明文字节 | 线上字节 |
|---|---|
| `0x3C` | `3D 2C` |
| `0x3D` | `3D 2D` |
| `0x3E` | `3D 2E` |

**校验和**在转义**前**对 `type..payload 末字节` 求和。

此前我用 `1 字节长度 + 按 0x3C 直接切帧`，小载荷时数值恰好相等所以没暴露；
一旦载荷含 0x3C/0x3D/0x3E（例如 EQ 扩展信息结尾的 `3D 2E`）就会切错帧。
**12.1 节的"236 帧中 2 帧校验和不符"由此得到解释**——那两帧是因为载荷里的 0x3E 被转义、
按明文切分导致长度错位。

### 14.2 连接方式：应该用索尼私有 UUID，不是通道 9

`SonyHeadphonesClient` 用 `96CC203E-5068-46AD-B32D-E316F5E069BA` + `port=0`（SDP 解析）。

实测确认：该 UUID 能正常解析并连接（`SO_ERROR=0`），随后协议版本、电量均正常返回。
**通道 9 是我用标准 SPP UUID（0x1101）失败后的绕路，正确做法是换 UUID。**

通道扫描的结论作废：不同设备/配对的通道号不同，写死 9 不可移植。

### 14.3 参考实现已修正

`tools/tandem_client.py` 已改为：

- 帧封装/解析支持转义，长度字段 4 字节大端
- 默认用 Sony UUID + SDP 连接（`CHANNEL = 0`），仍可传入数字直连指定通道

回归测试：协议版本 `01007000`、电量 `11006400` 均通过。往返测试覆盖含 `3C/3D/3E` 的载荷。

## 15. 自适应声音控制（ASC）不在协议里（2026-11-03 16:35）

### 15.1 抓包结果

App 里把 ASC 从关切到开，蓝牙日志新增只有一个帧（cid 0x44）：

```
68 02 10 02 02 01 00 00
        ^^ 0x10 = NC_ASM_EFFECT::ADJUSTMENT_IN_PROGRESS
```

### 15.2 单独发送该帧无效

从 PC 客户端发送 `68 02 10 02 02 01 00 00`，重新连上 App 查看，
ASC 仍显示「关闭」。

### 15.3 代码结构佐证

APK 里 ASC 的实现全部位于应用层：

```
com.sony.songpal.mdr.application.adaptivesoundcontrol.*
├── ActivityRecognitionUiTab               活动识别界面
├── AscLocationPositionSelectFragment      位置选择
├── AscBdLocationPositionSelectFragment    百度定位位置选择
├── NcAsmSetting                           计算出的降噪/环境声设置
└── ...
```

命令表（v1 129 条 / v2 157 条）里**没有任何 ASC 相关命令**。

### 15.4 结论

**ASC 是 App 端编排功能，耳机不保存 ASC 状态。** 工作方式：

1. App 用 Android 活动识别 API 判断用户状态（走路 / 静止 / 乘车）
2. App 用定位判断所处场所
3. 按用户配置查表得到「该场景用什么降噪模式」
4. 通过普通 `NCASM_SET_PARAM` 下发

**所以给 SonyHeadphonesClient 加 ASC，不是补协议，而是在客户端实现一套活动识别 + 规则引擎。**
`68 02 10 ...` 这帧只是"我要开始调整了"的提示，不承载任何状态。

### 15.5 选功能时的判断标准

只有满足"耳机自己保存状态"的功能才能通过协议实现：

| 判断依据 | 说明 |
|---|---|
| 命令表里有对应 GET/SET | 大概率设备端 |
| App 断开后重新连接，状态仍在 | 设备端 |
| 卸载 App 后状态保留 | 设备端 |

ASC 三条都不满足 → 应用层功能。

## 16. 语音向导开关（Table#2 命令，2026-11-03 16:50）

### 16.1 命令

**注意：这条命令在 Table#2（type `0x0E`），不在 T1。**

```
请求  48 01 01 <val>       val: 00 = 关，01 = 开
响应  49 01 01 <val>
```

抓包对比（App 操作方向）：

| App 操作 | 发出的载荷 |
|---|---|
| 开 → 关 | `48 01 01 00` |
| 关 → 开 | `48 01 01 01` |

### 16.2 真机验证

从 PC 客户端发送 `48 01 01 00`（type 0x0E）：

```
-> 3e0e0000000004480101005c3c
<- 3e0e0100000004490101005e3c
```

随后打开 App → 所有设备设置 → 系统，显示「通知和语音向导：**关闭**/语言：中文」，
**确认生效**。此功能属于设备端状态（App 重连后仍保持），可用协议控制。

### 16.3 意义

这是第一个成功控制的 **Table#2** 功能，证明 T2 命令空间独立于 T1：

| 表 | type | 已知用途 |
|---|---|---|
| Table#1 | `0x0C` | NCASM（降噪）、EQEBB、CONNECT、COMMON |
| Table#2 | `0x0E` | LEA（LE Audio）、`0x48` 语音向导 |

后续扩展功能时应同时查两张表。

## 17. DSEE Extreme 开关（T1 · AUDIO_SET_PARAM，2026-11-03 16:50）

### 17.1 命令

```
请求  E8 02 00 <val>     val: 01 = 自动，00 = 关闭
响应  E9 02 00 <val>
```

`0xE8` = AUDIO_SET_PARAM（Table#1，type `0x0C`），`0xE9` 为对应回执。

抓包双向对比：

| App 操作 | 载荷 |
|---|---|
| 自动 → 关闭 | `E8 02 00 00` |
| 关闭 → 自动 | `E8 02 00 01` |

### 17.2 真机验证

PC 客户端发送 `E8 02 00 00`：

```
-> 3e0c0000000004e8020000fa3c
<- 3e0c0100000004e9020000fc3c
```

App → 所有设备设置 → 音质/音量，DSEE Extreme 显示「**关闭**」，确认生效。
用户原设置为「自动」，已恢复。

## 18. 目前已实现的控制能力总览

| 功能 | 表 | 帧 | 验证 |
|---|---|---|---|
| 读电量 | T1 | `10 00` → `11 00 64 00` | ✅ |
| 降噪 | T1 | `68 02 11 02 02 01 00 00` | ✅ App |
| 环境声 N 级 | T1 | `68 02 11 02 00 01 00 NN` | ✅ App |
| 关闭降噪 | T1 | `68 02 00 02 02 01 00 00` | ✅ App |
| 语音向导 开/关 | **T2** | `48 01 01 00|01` | ✅ App |
| DSEE Extreme | T1 | `E8 02 00 00|01` | ✅ App |
| EQ 预设 | T1 | `58 01 <preset> 00` | ✅ 回显 |
| 读协议版本/能力 | T1 | `00 00` / `02 00` | ✅ |

统一入口：`tools/xm4_control.py`

```bash
python xm4_control.py battery
python xm4_control.py nc / ambient 15 / off
python xm4_control.py voice on|off
python xm4_control.py dsee auto|off
```

## 19. 第二批功能（2026-11-03 21:20）

### 19.1 观测手段的升级：用 GET_PARAM 代替抓包

抓 btsnoop 有个反复出现的坑：**日志文件缓冲不刷盘**。执行 `cp` 拿到的字节数会连着几次完全不变
（16:50 那次停在 46475 长达数分钟），此时做 diff 会得到空结果或错位结果。

两个可靠替代方案（本次都用上了）：

| 方法 | 做法 | 适用 |
|---|---|---|
| **参数读回** | 直接 `GET_PARAM` 读设备当前值，改前改后对比 | 已知参数编号时最可靠 |
| **刷盘后取 `.last`** | 操作完成后 `svc bluetooth disable/enable`，日志文件轮转成 `.last` 即已完整落盘 | 定位未知帧时用 |

`tools/param_scan.py` 实现了第一种：按命令族枚举参数编号，`dump` 存 JSON、`diff` 比对，
用于从"状态变化"反推参数位。本次声音质量与智能免摘都是用它对读回值做了独立确认。

另外记一个 UI 定位技巧：弹窗按钮靠截图估算坐标经常差 70–80 px 点空。
用 PIL 找弹窗区域内的蓝色文字像素并聚类，可直接得到"取消/确定"的精确中心坐标：

```python
# 蓝色像素 x 聚成两簇 = 两个按钮，取簇中心 x、整体 y 中心
```

### 19.2 蓝牙连接质量（AUDIO param 0x01）

```
读  E6 01  ->  E7 01 00 <val>
写  E8 01 00 <val>        val: 00 = 声音质量优先，01 = 稳定连接优先
```

- App 位置：所有设备设置 → 连接 → 声音质量模式
- 抓包帧（切到稳定优先）：`e8 01 00 01`
- 真机验证：写 `e8 01 00 00` 后 App 显示"声音质量优先"；`E6 01` 读回 `e7010000`
- 切换会触发音频重连（LDAC → AAC），App 会弹"需要重新连接"确认框，必须点确定才提交

### 19.3 智能免摘 Speak-to-Chat（SYSTEM param 0x05）

```
读  F6 05     ->  F7 05 00 <val>
写  F8 05 01 <val>        val: 00 = 关，01 = 开
```

- App 位置：所有设备设置 → **降噪/环境声音** → 智能免摘（不在"系统"分类下，这一点绕了几分钟）
- 抓包帧（关闭）：`f8 05 01 00` + `fc 05 00 01 01 01`（App 每帧发两次）
- 真机验证：写 `f8 05 01 01` → 读回 `f7050001`；写 `f8 05 01 00` → 读回 `f7050000`，双向成立
- **只需 `f8` 那一帧即可，`fc`（SET_EXT_PARAM）不是必需的**——单独发 `f8` 已生效

同一页面还有两个可探索项（未验证值域）：
`语音检测灵敏度`（高/标准）、`关注语音`（开/关）、`此模式关闭之前的时间`（约30秒等）。

### 19.4 DSEE Extreme（AUDIO param 0x02）—— 顺手修正旧记录

```
读  E6 02  ->  E7 02 00 <val>
写  E8 02 00 <val>        val: 00 = 关闭，01 = 自动
```

早前用 App 截图判断"DSEE 恢复自动失败"，实际是用 `E6 02` 读回确认：写入 `e8020001` 后
`e7020001`，**写入是成功的**，当时的截图是旧状态或未刷新。参数读回比截图更可靠。

### 19.5 多点连接（GENERAL param 0xD2）—— 能读，不能写

**参数身份已确认**：能力查询 `d0 d2 0c` 返回

```
d1 d2 02 12 "MULTIPOINT_SETTING" 1a "MULTIPOINT_SETTING_SUMMARY" 01 00
```

即 param 0xD2 = MULTIPOINT_SETTING，含两个子项（0x12 / 0x1a）。

```
读  D6 D2  ->  D7 D2 01 <val>      val: 00 = 关，01 = 开      ✅ 可靠
写  D8 D2 01 <val>                                          ❌ 被设备拒绝
```

验证过程（均失败，设备一律回 `d9 d2 01 00` 并保持原值）：

| 尝试 | 结果 |
|---|---|
| `d8 d2 01 01`（开启） | 回 `d9d20100`，读回仍 00 |
| `d8 d2 01 00`（关闭，App 抓到的原帧） | 回 `d9d20101`，读回仍 01 |
| 连发两次 | 同样被规整 |
| 先 `d0 d2 0c`（读能力）再写 | 无效 |
| 先 `d4 d2 01`（SET_STATUS）再写 | `d4` 无响应，写仍无效 |

**结论（已于第 20 节更正）：此处判断有误，实际可写，缺的是告警应答流程。原文保留如下。**
旧结论：多点连接只能读、不能写。 待查方向：App 是在另一条 RFCOMM 通道（抓包中为 cid 0x45）
发出该帧，可能存在"哪个通道可以改哪类参数"的限制；或该参数需要先建立某种编辑会话。
在解开之前，不要在客户端提供多点连接写入口——和「关闭降噪」那次一样，
一个改不回来的开关比没有这个功能更糟。

### 19.6 当前能力清单

| 功能 | 表/命令 | 读 | 写 |
|---|---|---|---|
| 电量 | T1 `10 00` | ✅ | — |
| 降噪/环境声/关闭 | T1 NCASM `68 02` | ⚠️ `66 02` 仅回显 | ✅ App 验收 |
| EQ 预设 | T1 EQEBB `58 01` | ✅ | ✅ |
| 语音向导 | T2 `48 01 01` | 无查询命令 | ✅ App 验收 |
| DSEE Extreme | T1 AUDIO `E6/E8 02` | ✅ | ✅ |
| 蓝牙连接质量 | T1 AUDIO `E6/E8 01` | ✅ | ✅ App 验收 |
| 智能免摘 | T1 SYSTEM `F6/F8 05` | ✅ | ✅ 读回验收 |
| 多点连接 | T1 GENERAL `D6/D8 D2` | ✅ | ✅（需先开告警，见第 20 节） |

统一入口（已更新）：

```bash
python tools/xm4_control.py status
python tools/xm4_control.py nc / ambient 15 / off
python tools/xm4_control.py voice on|off
python tools/xm4_control.py dsee auto|off
python tools/xm4_control.py quality hifi|stable
python tools/xm4_control.py stc on|off
```

`status` 一次输出电量、DSEE、连接质量、智能免摘、多点连接，全部来自设备读回而非缓存。

### 19.7 多点连接写入：穷举排查后的结论（2026-11-03 21:55）

为解开 19.5 的写入拒绝，做了 10 组对照实验，全部排除：

| # | 假设 | 实验 | 结果 |
|---|---|---|---|
| 1 | 字节编码不对 | 反编译 `GsInquiredType` / `GsSettingType` 枚举 | `0xD2=GENERAL_SETTING2`、`0x01=BOOLEAN_TYPE`，与 App 帧完全一致 → 排除 |
| 2 | 缺能力查询 | 先 `d0 d2 0c`（GET_CAPABILITY）再写 | 仍被规整 → 排除 |
| 3 | 缺状态查询 | 先 `d2 d2`（GET_STATUS，返回 `d3 d2 00`）+ `d6 d2` 再写 | 仍被规整 → 排除 |
| 4 | 缺完整初始化同步 | 按时间顺序重放 App 写入前的 56 帧（含 T2 的 LEA/`3601` 系列） | 仍被规整 → 排除 |
| 5 | 需要连发 | 同一帧连发两次 | 仍被规整 → 排除 |
| 6 | 需要换 RFCOMM 通道 | 逐个测 ch 8/9/10/11/12/13 | 只有 ch9 承载 tandem，其余读 `d6 d2` 无响应 → 排除 |
| 7 | 需要第二条并发会话 | 模拟 App 的双会话 | Windows 拒绝：`WSASocket+connect` 返回 `10048`，加 `SO_REUSEADDR` 无效（`SO_ERROR` 仍 10048） → 无法验证；且 App 的 `d8` 是在**第一会话**上发的（第二会话 cid 0x40 在其后才建立），故此假设本身也不成立 |
| 8 | 写完需要重连才生效 | 写入后断开、等 10 秒、重连再读 | 仍是 `d7 d2 01 00` → 排除 |
| 9 | 需要活动音频链路 | 确认 PC 侧 A2DP/HFP 均为 `OK`（活动链路）后重试 | 仍被规整 → 排除 |
| 10 | 缺 `94 01 00`（ALERT_SET_STATUS，App 写入前紧邻的一帧） | 把它也纳入重放 | 这次连回应都没有 → 排除 |

**最终结论（已更正，见第 20 节）：本条判断错误——真正原因是漏了「先 `94 01 00` 开告警 + 应答 `99` 告警」这一步。原文保留。**
旧结论：多点连接的写入被设备拒绝，且不是上述任一客户端可控因素。
剩余最可能的解释是**设备侧授权**——即耳机只接受索尼自家 App 通过其专用注册流程发起的敏感设置变更
（抓包中第二会话开头有 `50 01 0c`、`60 02` 这类 HPC 专用能力协商），这是 PC 端第三方客户端无法复制的。

因此：**多点连接在客户端只提供读取，不提供开关。** 需要开关时用手机 App。
`xm4_control.py status` 里保留读取，便于判断当前状态。

副产品：本次排查确认了 `GENERAL` 族的帧结构 `D8 <inquiredType> <GsSettingType> <value>`，
以及 `D2`/`D6` 分别是 GET_STATUS / GET_PARAM（`D3`/`D7` 为对应响应），
这套结构对将来解析其他 GENERAL 设置直接可用。

## 20. 更正：多点连接可以写（2026-11-03 22:10）

**19.5 / 19.7 的「设备侧授权、不可写」结论是错误的，予以推翻。** 真正的门槛是漏了一个前置步骤：
**必须先开启固定消息告警，并在设备发来告警后应答**，写入才会生效。

### 20.1 完整流程（XM4 真机验证，双向）

```
94 01 00          ALERT_SET_STATUS(FIXED_MESSAGE=0x01, ENABLE=0x00)   ← 先打开告警
D8 D2 01 <val>    GENERAL_SETTING2 / BOOLEAN / val(01=开, 00=关)
  <- 99 01 MT 01  ALERT_NTFY_PARAM，MT 见下，最后一个字节 01 = 需要应答
98 01 MT 01       ALERT_SET_PARAM，回 MT + 01(接受)
  ← 设备断开 RFCOMM 链路
（重连后）D6 D2   ->  D7 D2 01 <val>   新状态已生效
```

| 方向 | 告警 MT | 含义（v1） |
|---|---|---|
| 开多点 | `0x06` | `DISCONNECT_CAUSED_BY_CHANGING_MULTIPOINT_TO_ON` |
| 关多点 | `0x07` | `DISCONNECT_CAUSED_BY_CHANGING_MULTIPOINT_TO_OFF` |

实测记录：

```
当前 d7d20100 → 94 01 00 → d8 d2 01 01 → 99 01 06 01 → 98 01 06 01 → 重连读 d7d20101  ✓
当前 d7d20101 → 94 01 00 → d8 d2 01 00 → 99 01 07 01 → 98 01 07 01 → 重连读 d7d20100  ✓
```

### 20.2 为什么之前十次全部失败

`94 01 00` 在抓包里出现过（就在 `d8` 前两帧），但我把它当成无关的提示音设置跳过了；
后来虽然把它纳入重放，却是在**同一连接里连发**，且没有处理随后到来的 `99` 告警 ——
设备发来的告警一直没人应答，设置自然不落地。

一条经验：**这类"先发告警、等确认、再断开"的写入，失败时的表现和"被拒绝"完全一样**
（回显旧值、读回不变），光看返回值无法区分"权限不足"和"等你确认"。
判断依据应该是**有没有收到 `0x99`**：收到 = 已受理，正等你确认；没收到 = 真的被拒。

### 20.3 资料来源

- `mos9527/SonyHeadphonesClient`（Plutoberth 原版的活跃分支）`libmdr/src/HeadphonesV1.cpp`：
  初始化时 `SetAlertStatus(FIXED_MESSAGE, ENABLE)` 之后才开始接收告警；
  `RequestCommitV1()` 里把 `SetAlertParamFixedMessageParam{type, messageType, action}` 发回去。
  头文件注释写明："*The setting that triggered it (e.g. multipoint, connection mode)
  is not applied until answered with MDR_ALERT_ACTION_POSITIVE, which may disconnect the device.*"
- `libmdr/include/mdr/ProtocolV1T1.hpp`：`GsInquiredType{0xD1,0xD2,0xD3}`、
  `GsSettingType{NO_USE=0,BOOLEAN=1,LIST=2}`、`AlertInquiredType{FIXED_MESSAGE=1}`、
  `CommonStatus{ENABLE=0, DISABLE=1}`、`AlertMessageType` 的 0x06/0x07。
- `enxy0/omarchy-sony-xm5/docs/protocol.md`：XM5 上同一机制的独立记录
  （XM5 用 `98 00 MT 01`，第三字节与 XM4 的 `01` 不同；XM4 以实测为准）。

### 20.4 对其他写入的推论

同一机制很可能也约束 **连接模式 / 声音质量 / 触摸设置** 这类"改了要断开重连"的项。
19.2 的「声音质量模式」当时能直接写入并生效（未收到告警），说明它不在告警保护的范围内；
但**遇到"回显旧值、读回不变"的写入时，先试 `94 01 00` + 处理 `99`，再判定失败**。

工具已更新：

```bash
python tools/xm4_control.py multipoint on|off   # 自动开告警、应答、重连回读
```

## 21. 第二批功能补全 + seq 修正（2026-11-03 22:20）

### 21.1 修正：seq 推进必须等 ACK

按 `AndreasOlofsson/mdr-protocol` 与 libmdr 的实现，**序号只在收到对应 ACK 后才推进**，
未收到时应重发同一 seq。原实现是每发一帧无条件 `seq ^= 1`，一旦丢帧就会和设备的期望错位。

`tandem_client.py` 已改：

- `_send(seq=None)` 只记录 `pending_seq`，不推进
- `_read()` 里收到 ACK 且其 seq == `pending_seq ^ 1` 时才推进并清空 pending
- `request()` 超时且仍 pending 时，按协议**重发同一 seq**（默认 1 次）

实测设备 ACK 约定（连发三次 `66 02`）：

```
我方 seq=0  ->  ACK seq=1  ->  我方 seq 变 1
我方 seq=1  ->  ACK seq=0  ->  我方 seq 变 0
```

回归：`status` 连读 7 项零重传；写入偶发一次重传，重发同 seq 后设备正常应答（符合预期行为）。

### 21.2 ASC（降噪）载荷的完整结构

之前只知道"改某两个字节"，现在字段全清楚了（`68 02` 开头，8 字节）：

| 位置 | 含义 |
|---|---|
| 0 | `0x68` SET / `0x69` 回执 |
| 1 | `0x02` 参数组 |
| 2 | `0x00` = 关闭处理，`0x11` = 开启处理（设备回显会规整成 `0x01`） |
| 3 | 支持风噪降低时为 `0x02`，否则 `0x00` |
| 4 | **模式**：`0x00` 环境声、`0x01` 风噪降低、`0x02` 降噪 |
| 5 | 固定 `0x01` |
| 6 | **关注语音**：`0x01` 开 / `0x00` 关（仅环境声下有效，降噪时设备忽略） |
| 7 | 等级 0–20（仅环境声/关闭有意义） |

新打通（均读回验证）：

| 功能 | 发送 | 读回 |
|---|---|---|
| 风噪降低 | `68 02 11 02 **01** 01 00 00` | 模式 `0x01` |
| 关注语音开 | 环境声下把第 6 字节改 `01` | `focus=1 模式=环境声 等级=N` |

注意：关注语音是**粘性**的——发 `nc` 不会自动关掉它，回显里 focus 仍是 1。
要复位必须先进环境声、发 focus=0，再切回降噪。

### 21.3 自动断电（`F8 04 01 <c0> <c1>`）：XM4 只有两态

| 值 | 含义 | XM4 是否接受 |
|---|---|---|
| `11 00` | 关闭 | ✅ |
| `10 00` | 当耳机取下时关闭 | ✅ |
| `00 00` / `01 01` / `02 02` / `03 03` | 5 分钟 / 30 分钟 / 1 小时 / 3 小时 | ❌ 全部被规整成 `10 00` |

其他参考实现（omarchy）列了定时档，但那是给别的机型的；XM4 固件 2.5.0 的 App 页面也只有
「关闭 / 当耳机取下时关闭」两个选项，实测与界面一致。**不要照抄定时档的编码。**

### 21.4 取下暂停（`F8 03 01 <0|1>`）

双向验证通过，读回 `F7 03 00 <val>`。

### 21.5 EQ 自定义 6 段（`58 01 FF 06 <6 字节>`）

```
请求  58 01 FF 06 <bass+10> <b1+10> <b2+10> <b3+10> <b4+10> <b5+10>
响应  59 01 A0 06 <6 字节>      A0 = MANUAL 预设，说明写频段会自动切到手动
```

实测写 `[3,0,0,0,0,0]` → 读回 `5701A0060D0A0A0A0A0A` → 解析回 `[3,0,0,0,0,0]` ✓。
范围 −10..10，映射到 0..20。还原用 `58 01 00 00`（OFF 预设，六段全 10）。

### 21.6 本轮新增命令

```bash
python tools/xm4_control.py status                    # 一次读全部状态
python tools/xm4_control.py eq off|bass|vocal|...      # EQ 预设
python tools/xm4_control.py eqbands 3 0 0 0 0 0        # 自定义 6 段
python tools/xm4_control.py wind                       # 风噪降低
python tools/xm4_control.py focus on|off               # 关注语音（环境声下）
python tools/xm4_control.py pause on|off               # 取下暂停
python tools/xm4_control.py apo off|takenoff           # 自动断电
python tools/xm4_control.py multipoint on|off          # 多点（带告警应答）
```

`status` 现在输出：电量、DSEE、连接质量、智能免摘、多点、取下暂停、自动断电、
降噪模式/关注语音/等级——全部来自设备读回。

### 21.7 当前完整能力

| 功能 | 读 | 写 | 验证方式 |
|---|---|---|---|
| 电量 / 协议版本 / 能力 | ✅ | — | 真机 |
| 降噪 / 环境声 / 关闭 / 风噪 | ✅ `66 02` | ✅ | 读回 + App 截图 |
| 关注语音 | ✅ | ✅ | 读回 |
| EQ 预设 / 自定义 6 段 | ✅ `56 01` | ✅ | 读回 |
| DSEE Extreme | ✅ `E6 02` | ✅ | 读回 |
| 连接质量（LDAC/稳定） | ✅ `E6 01` | ✅ | App 截图 |
| 智能免摘 | ✅ `F6 05` | ✅ | 读回 |
| 取下暂停 | ✅ `F6 03` | ✅ | 读回 |
| 自动断电 | ✅ `F6 04` | ✅（两态） | 读回 |
| 多点连接 | ✅ `D6 D2` | ✅（需告警应答） | 读回 + 重连 |
| 语音向导 | 无查询命令 | ✅（T2） | App 截图 |

### 21.8 固件版本与编解码器查询（2026-11-03 22:05）

```
固件版本  请求 04 02   ->  05 02 <len> <len 字节 ASCII>
编解码器  请求 18 00   ->  19 00 <codec>
```

实测：

```
04 02  ->  05 02 05 "2.5.0"        固件 2.5.0（与 MDR_Proxy 固件库里的 UPG_2.5.0 一致）
18 00  ->  19 00 02                编解码器 = AAC
```

编解码器取值：`0x00` unknown、`0x01` SBC、`0x02` AAC、`0x10` LDAC、`0x20` aptX、`0x21` aptX HD。

已并入 `status`（现在 9 项）与 `version` 子命令：

```bash
python tools/xm4_control.py version    # 固件版本 + 当前编解码器
python tools/xm4_control.py status     # 9 项状态一次读完
```

**旁证一条**：参考实现 `omarchy-sony-headphones` 的源码注释里写着
"a WH-1000XM4 … answers 'when taken off' to every auto-power-off timer"，
和我们 21.3 的实测（定时档全被规整成 `10 00`）完全一致，可以确认这不是我们操作有误。

## 22. 触摸面板开关（2026-11-03 22:10）

### 22.1 参数定位：是 GENERAL_SETTING1（D1），不是 D2

向设备查能力表，参数名是明文返回的：

```
请求  D0 D1 0C
响应  D1 D1 02 13 "TOUCH_PANEL_SETTING" 00 01 00
                ^^ 0x13=19 即字符串长度
```

**`0xD1 = TOUCH_PANEL_SETTING`**（GENERAL_SETTING1），`D2` 是 MULTIPOINT_SETTING（第 20 节已证实）。
顺带确认 `GENERAL_SETTING3 (0xD3)` 在 XM4 上不存在（能力查询与读取均无响应）。

### 22.2 读写

```
读  D6 D1     ->  D7 D1 01 <val>
写  D8 D1 01 <val>     val: 01 = 开，00 = 关
```

真机双向验证：

```
基线 d7d10101 -> 写 d8d10100 -> 回 d9d10100 -> 读回 d7d10100   （关闭）
            -> 写 d8d10101 -> 回 d9d10101 -> 读回 d7d10101   （恢复）
```

**App 截图验收**：关闭后 App「所有设备设置 → 控制」显示「触摸式传感器控制面板：**关闭**」；
恢复后显示「**开**」。两端一致。

这个写入**不需要告警应答**，也不断开链路——和多点连接不同，回显直接反映新值。

### 22.3 参考实现的一处错误

`omarchy-sony-headphones` 把触摸面板映射到 `TOUCH_SET, 0xD2`，并在注释里写
"a WH-1000XM4 … answers 'still on' to every attempt at disabling its touch panel"。

原因就在这里：**XM4 的 0xD2 是多点连接，不是触摸面板**。它一直在往多点参数写 0/1，
触摸面板当然纹丝不动。正确的参数是 `0xD1`，一次就成。

### 22.4 新增命令

```bash
python tools/xm4_control.py touch on|off
```

`status` 增加「触摸面板」一项（现共 10 项）。
