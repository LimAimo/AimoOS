AimoOS 0.2.0 提供 Windows VMware Workstation 用的 BIOS 安装 ISO 和 VMX/VMDK 虚拟机压缩包。

- `AimoOS-0.2.0-VMware.zip`：解压后在 VMware 中打开 `AimoOS.vmx`，开机创建自己的账户。
- `AimoOS-0.2.0-amd64.iso`：新建 BIOS / SATA / 20 GB 虚拟机，从 ISO 启动，按中文安装器操作；完成后断开 ISO 再开机。
- `VMWARE.md`：两套完整中文教程与常见问题。
- `SHA256SUMS.txt`：下载校验值。

建议 4 GB 内存、2–4 核、NAT 网络，关闭 3D 加速。本版不支持 UEFI / Secure Boot，没有预设用户或密码。

真实 Linux、中文 Qt 桌面、LibreOffice 和中文输入均已集成。这是预览版：BIOS + SATA 路径通过 QEMU 验证，当前环境无法运行 Windows VMware；剪贴板和自动分辨率等 VMware 主机集成功能还没有真实 VMware 验证。Windows `.exe` 不在支持范围。

第三方 Ubuntu 软件沿用各自许可证；AimoOS 自有代码采用 MIT，构建脚本与依赖清单位于源码中。
