# PowerSupply

[English](README_EN.md)

PowerSupply 是一个基于 PyQt5 的程控电源上位机软件，适用于NGI-N3412E型号电源。通过 VISA/TCPIP 与电源通信，提供通道输出控制、实时电压/电流曲线、执行流程编排和多种通道联动模式。

## 功能特性

| 功能 | 说明 |
| --- | --- |
| 三通道控制 | 支持 CH1、CH2、CH3 的电压、限流和输出开关控制 |
| 实时曲线 | 使用 pyqtgraph 实时显示各通道电压、电流数据 |
| 曲线开关 | 支持按 U1/I1/U2/I2/U3/I3 选择显示曲线 |
| 执行流程 | 可添加通道选择、输出开关、电压、限流、延时等步骤并顺序执行 |
| 流程控制 | 支持开始、暂停、继续、停止和重复执行 |
| 通道模式 | 支持普通、并联、串联、跟踪模式 |
| 状态刷新 | 周期性读取设备测量值、设定值和输出状态 |
| 日志记录 | 运行日志输出到 Logs 目录 |
| Windows 打包 | 提供 PyInstaller 打包脚本生成独立 exe |

## 项目结构

| 路径 | 说明 |
| --- | --- |
| `PyqtPowerSupply.py` | 主程序入口，包含界面逻辑、流程执行线程和电源通信逻辑 |
| `Ui_powerMainWindow.py` | 由 Qt Designer UI 文件生成的界面代码 |
| `powerMainWindow.ui` | Qt Designer 原始 UI 文件 |
| `MyWidgets.py` | 自定义控件 |
| `PyqtPowerSupply_log.py` | 日志模块 |
| `resource.qrc` / `resource_rc.py` | Qt 资源文件与生成文件 |
| `icon/` | 界面图标资源 |
| `PowerSupply.spec` | PyInstaller 打包配置 |
| `build.bat` | Windows 一键打包脚本 |
| `LICENSE` | MIT License |

## 环境要求

| 项目 | 建议 |
| --- | --- |
| 操作系统 | Windows |
| Python | Python 3.8+ |
| GUI 框架 | PyQt5 |
| 仪器通信 | PyVISA，需可用 VISA 后端，如 NI-VISA 或 pyvisa-py |
| 打包工具 | PyInstaller |

## 安装依赖

```bash
pip install PyQt5 pyvisa pyvisa-py numpy pyqtgraph pyinstaller
```

如果使用 NI-VISA 作为后端，请先安装 NI-VISA Runtime，并确认设备可被 VISA 识别。

## 设备连接

当前程序默认连接地址写在 `PyqtPowerSupply.py` 中：

```python
TCPIP0::172.16.40.214::7000::SOCKET
```

使用前请确认：

| 检查项 | 说明 |
| --- | --- |
| 网络连接 | 电脑与电源设备处于可通信网络中 |
| IP/端口 | 设备 IP 和端口与程序中的 VISA 地址一致 |
| VISA 后端 | PyVISA 能正常打开 TCPIP SOCKET 资源 |
| 终止符 | 当前读取终止符为 `\r\n` |

如需连接其他设备，请修改 `PowerSupply.powerInit()` 中的资源地址。

## 运行

```bash
python PyqtPowerSupply.py
```

启动后程序会立即初始化设备连接。如果连接失败，会弹出错误提示并退出。

## 打包

在 Windows 下可直接运行：

```bat
build.bat
```

打包成功后输出文件位于：

```text
dist\PowerSupply.exe
```

也可以手动执行：

```bash
pyinstaller PowerSupply.spec --noconfirm --clean
```

## 基本使用流程

| 步骤 | 操作 |
| --- | --- |
| 1 | 确认设备已上电并与电脑网络连通 |
| 2 | 启动 `PyqtPowerSupply.py` 或 `dist\PowerSupply.exe` |
| 3 | 在通道区域设置 CH1/CH2/CH3 的电压与限流 |
| 4 | 使用 ON/OFF 控制通道输出 |
| 5 | 在实时曲线区域查看电压、电流变化 |
| 6 | 如需自动化执行，在“执行流程”中添加步骤并点击开始 |

## 执行流程命令

| 命令 | 参数含义 |
| --- | --- |
| 通道选择 | 选择后续步骤作用的通道 |
| 输出开关 | `1` 表示开启，`0` 表示关闭 |
| 电压(V) | 设置当前通道输出电压 |
| 限流(A) | 设置当前通道限流值 |
| 延时(S) | 等待指定秒数后继续执行下一步 |

## 注意事项

| 项目 | 说明 |
| --- | --- |
| 安全 | 操作真实电源设备前，请确认负载、电压和限流范围安全 |
| 地址配置 | 当前设备地址为硬编码，部署到其他环境时需要手动修改 |
| 实时性 | 程序采用线程和队列处理设备命令，实际响应速度受设备通信延迟影响 |
| 日志 | 运行过程中产生的日志目录 `Logs/` 已被 `.gitignore` 忽略 |
| 构建产物 | `build/`、`dist/`、`__pycache__/` 不纳入版本管理 |

## License

本项目基于 [MIT License](LICENSE) 开源。
