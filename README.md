# AimoOS

AimoOS 0.1.0 是面向 x86-64 虚拟机的中文 Linux 桌面试用版。它使用真实的 Linux 内核、磁盘、用户账户和本机应用；桌面、开始菜单、统一控件和六个基础应用使用 Python / Qt 6 编写。视觉采用 AimoChat 的纸、墨、中性灰和低饱和陶土规范。

当前交付以 QEMU 为运行目标，定位是可启动、可保存工作、可运行 Linux 办公应用的第一版。还需要继续验证长期稳定性、更多硬件和复杂办公场景，才能作为主力工作系统。

## 已实现

- 居中任务栏、应用搜索、桌面入口，以及本机 Linux 窗口的任务切换。
- 窗口拖动、边框缩放、最小化、最大化、左右分屏、Alt+Tab。
- 文件管理器：真实目录、新建、重命名、复制粘贴、回收站与还原。
- 记事本：UTF-8 文档、原子保存、未保存更改提示。
- 计算器、真实 Bash / PTY 终端、设置，以及使用 Qt WebEngine 的浏览器。
- LibreOffice Writer、Calc、Impress，PDF / 图片查看器，Fcitx 5 中文拼音输入。
- 首次创建账户、管理员添加标准用户、密码登录、PAM 锁屏、退出登录。
- 每个 Linux 用户独立的主目录和偏好；可写 ext4 磁盘保留文档、账户和浏览器配置。
- 浅色 / 深色、原生壁纸与自选图片、文字大小、减少动态效果、24 小时时间。

## 构建与启动

构建主机使用 **Ubuntu 24.04 LTS amd64**。需要联网、至少 25 GB 可用空间，以及主机上的 Python 3、APT、dpkg、tar 和 e2fsprogs。推荐主机内存 8 GB。源代码不含预置账户、密码或 GitHub Token。

```bash
git clone https://github.com/LimAimo/AimoOS.git
cd AimoOS
sudo apt-get update
sudo apt-get install -y python3 apt dpkg tar e2fsprogs
sudo python3 scripts/fetch_runtime.py
sudo python3 scripts/build_image.py
sudo chown -R "$USER:$(id -gn)" out
python3 scripts/run_vm.py
```

下载阶段将 Ubuntu 官方仓库中的依赖解包到 `build/sysroot`，不向主机安装桌面软件。主机必须配置 noble 的 main / universe 仓库及更新、安全源。构建使用主机仓库解析出的内核版本，下载包的实际版本记录在 `build/packages.lock.json` 和 `out/packages.lock.json`。首次下载和构建会花费数分钟；脚本会输出包数与阶段进度。

生成 `out/aimoos.img`（默认 12 GiB 稀疏、可写 ext4）、`out/vmlinuz`、`out/initrd.gz`。三个文件必须配套使用。首次开机创建你自己的账户；第一个账户具有管理员权限。构建器遇到已有 `aimoos.img` 会停止，避免覆盖个人数据。

启动器自动使用可访问的 KVM，否则使用 TCG。无 KVM 时，首次字体缓存和办公应用冷启动会明显较慢。可指定：

```bash
python3 scripts/run_vm.py --accel tcg --memory 4096 --cpus 4
python3 scripts/run_vm.py --qemu /usr/bin/qemu-system-x86_64
python3 scripts/run_vm.py --headless --dry-run
```

图形启动需要主机桌面会话。默认使用 GTK，可选 `--display sdl`。关闭前使用系统菜单关机，让文件写入完成；下次使用同一磁盘启动即可保留数据。不要让两个虚拟机同时写同一磁盘。

可用 `AIMO_BUILD_DIR` 和 `AIMO_OUT_DIR` 把缓存和镜像放到其他磁盘。构建和运行时保持这两个变量一致；使用 sudo 时显式保留它们：`sudo --preserve-env=AIMO_BUILD_DIR,AIMO_OUT_DIR python3 scripts/build_image.py`。

## 操作

| 操作 | 快捷键 |
| --- | --- |
| 开始菜单 | Super+Space |
| 文件 / 终端 | Super+E / Super+R |
| 锁屏 | Super+L |
| 左右分屏 | Super+Left / Super+Right |
| 最大化 / 最小化 | Super+Up / Super+Down |
| 切换窗口 / 关闭 | Alt+Tab / Alt+F4 |
| 显示桌面 | Super+D |
| 中文输入切换 | Ctrl+Space |
| 记事本保存 / 打开 | Ctrl+S / Ctrl+O |
| 浏览器地址栏 | Ctrl+L |
| 终端粘贴 | Ctrl+Shift+V |

浏览器支持实际 HTTP / HTTPS 网页、持久化配置和下载到个人“下载”目录。当前是单窗口单标签；站点兼容性取决于系统所带 Qt WebEngine。办公文件由 LibreOffice 处理，复杂的微软 Office 文档格式需要逐份检查。

## 开发与验证

```bash
python3 -m unittest discover -s tests -v
python3 -m compileall -q aimo scripts tools
```

`tests/test_services.py` 检查文件名边界、回收站冲突与还原、计算器执行边界、偏好保存及多账户密码隔离；`tests/test_native.py` 检查异步目录加载、图标主题切换、反复关窗以及带动画窗口的退出登录。真实虚拟机的验证记录见 [docs/VALIDATION.md](docs/VALIDATION.md)。

`tools/vm_lab.py` 是开发者测试工具，使用 QMP 和本地 virtio 诊断通道。**它会开启实验用 root 命令通道，只能在隔离的开发环境使用。** 正常启动器不传入 `aimo.test=1`，也不创建这个通道；测试端口仅绑定主机回环地址。不要使用实验启动器处理私人或生产数据。

## 当前边界

- 当前镜像由 QEMU 直接加载内核启动，没有安装器、引导 ISO、Secure Boot 或 VirtualBox / VMware 兼容验证。
- 采用专用启动脚本，而非完整的 systemd 服务管理；APT 数据库用于基本包识别，包维护、升级和额外服务仍需专项验证。
- 本机 Linux 应用可以运行；Windows `.exe` 兼容层、应用商店、磁盘加密、企业管理没有实现。
- 网络使用 QEMU NAT；Wi-Fi、蓝牙、打印机、摄像头、真实 GPU 和主机共享目录尚未验证。
- 当前桌面基于 X11，适合个人虚拟机试用，多用户并发和强隔离需要进一步建设。
- 当前终端没有滚动历史或鼠标文本选择，完整终端可从开始菜单启动 XTerm。
- 音频组件已经包含，实际输出取决于主机后端，本次测试未验证声音。

## 源码与许可

`aimo/`：桌面与应用；`scripts/`：依赖提取、镜像构建、启动及受限系统辅助程序；`config/`：窗口管理和输入法配置；`assets/web/`：浏览器本地首页。

自有源代码采用 [MIT](LICENSE)。Linux、Ubuntu 软件包、Qt、LibreOffice 等第三方组件保留各自许可；镜像保留软件包的版权文件。`DESIGN_SYSTEM.md` 是用户提供的 AimoChat 设计规范。AimoOS 为独立项目。
