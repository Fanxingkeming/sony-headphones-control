# full-version — 带官方素材的完整版

这个文件夹里的 `SonyHeadphonesControl-full.exe` 与
[Releases](https://github.com/Fanxingkeming/sony-headphones-control/releases) 里的
官方发布包**功能完全相同**，区别只有一点：

| | 官方发布包 | 本文件夹的完整版 |
|---|---|---|
| 产品渲染图（按识别到的机身颜色换图） | ❌ 内嵌线稿图 | ✅ 内置 Sony 官方渲染图 |
| Sound Connect 应用图标（exe / 托盘 / favicon） | ❌ 程序化图标 | ✅ 内置官方图标 |
| 体积 | ≈ 3.3 MiB | ≈ 3.5 MiB |

**版权说明**：完整版内置的渲染图与应用图标版权归 **Sony** 所有，从 Sound Connect
客户端素材中提取，**仅供个人使用**，请勿二次分发。正式的 Releases 发布包出于版权
考虑不带这些素材——这也是它被作为默认下载的原因。

不想用这个完整版的话，也可以：下载官方发布包，把你自己的图片放进 exe 旁边的
`assets` 文件夹（`xm4.webp`、`ls900n_w.webp`、`app-icon.ico` 等），效果相同、还不用
换文件——见主 README 的「仓库里不包含什么」。

两个版本都不包含任何真实设备 MAC 地址；首次连接时通过蓝牙枚举自动识别。
