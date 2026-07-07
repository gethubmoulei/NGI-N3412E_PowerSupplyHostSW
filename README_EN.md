# PowerSupply

[中文](README.md)

PowerSupply is a PyQt5-based desktop control application for NGI-N3412E power supply. It communicates with power supply over VISA/TCPIP and provides channel control, real-time voltage/current plotting, step-based execution flows, and multiple channel coupling modes.

## Features

| Feature | Description |
| --- | --- |
| Three-channel control | Control voltage, current limit, and output state for CH1, CH2, and CH3 |
| Real-time plotting | Display live voltage and current curves with pyqtgraph |
| Curve toggles | Show or hide U1/I1/U2/I2/U3/I3 curves independently |
| Step execution | Build ordered flows with channel, output, voltage, current, and delay steps |
| Flow controls | Start, pause, resume, stop, and repeat execution flows |
| Channel modes | Supports normal, parallel, series, and tracking modes |
| Status refresh | Periodically reads measured values, setpoints, and output states |
| Logging | Writes runtime logs to the Logs directory |
| Windows packaging | Includes a PyInstaller build script for standalone executables |

## Project Structure

| Path | Description |
| --- | --- |
| `PyqtPowerSupply.py` | Main entry point with UI logic, execution thread, and power-supply communication |
| `Ui_powerMainWindow.py` | Python UI module generated from the Qt Designer file |
| `powerMainWindow.ui` | Original Qt Designer UI file |
| `MyWidgets.py` | Custom widgets |
| `PyqtPowerSupply_log.py` | Logging module |
| `resource.qrc` / `resource_rc.py` | Qt resource file and generated resource module |
| `icon/` | UI icon assets |
| `PowerSupply.spec` | PyInstaller packaging configuration |
| `build.bat` | One-click Windows build script |
| `LICENSE` | MIT License |

## Requirements

| Item | Recommendation |
| --- | --- |
| Operating system | Windows |
| Python | Python 3.8+ |
| GUI framework | PyQt5 |
| Instrument communication | PyVISA with an available VISA backend, such as NI-VISA or pyvisa-py |
| Packaging | PyInstaller |

## Install Dependencies

```bash
pip install PyQt5 pyvisa pyvisa-py numpy pyqtgraph pyinstaller
```

If you use NI-VISA as the backend, install NI-VISA Runtime first and make sure the instrument can be discovered by VISA.

## Device Connection

The default VISA resource address is currently defined in `PyqtPowerSupply.py`:

```python
TCPIP0::172.16.40.214::7000::SOCKET
```

Before running the application, check the following:

| Check | Description |
| --- | --- |
| Network | The PC and the power supply are reachable on the same network |
| IP/port | The device IP and port match the VISA resource address in the code |
| VISA backend | PyVISA can open the TCPIP SOCKET resource |
| Terminator | The current read termination is `\r\n` |

To connect to another device, update the resource address in `PowerSupply.powerInit()`.

## Run

```bash
python PyqtPowerSupply.py
```

The application initializes the device connection on startup. If the connection fails, an error dialog is shown and the program exits.

## Build

On Windows, run:

```bat
build.bat
```

The executable will be generated at:

```text
dist\PowerSupply.exe
```

You can also build manually:

```bash
pyinstaller PowerSupply.spec --noconfirm --clean
```

## Basic Workflow

| Step | Action |
| --- | --- |
| 1 | Make sure the power supply is powered on and reachable from the PC |
| 2 | Start `PyqtPowerSupply.py` or `dist\PowerSupply.exe` |
| 3 | Set voltage and current limit for CH1/CH2/CH3 |
| 4 | Use ON/OFF controls to switch channel outputs |
| 5 | Monitor voltage and current changes in the real-time plot |
| 6 | For automated operation, add steps in the execution-flow panel and click Start |

## Execution Flow Commands

| Command | Parameter |
| --- | --- |
| Channel | Selects the target channel for following steps |
| Output | `1` means ON, `0` means OFF |
| Voltage (V) | Sets the output voltage of the current channel |
| Current Limit (A) | Sets the current limit of the current channel |
| Delay (S) | Waits for the specified number of seconds before the next step |

## Notes

| Item | Description |
| --- | --- |
| Safety | Before operating real hardware, verify that the load, voltage, and current limits are safe |
| Address configuration | The device address is currently hard-coded and should be updated for other environments |
| Timing | Commands are handled with threads and queues; actual response time depends on instrument communication latency |
| Logs | The runtime log directory `Logs/` is ignored by `.gitignore` |
| Build artifacts | `build/`, `dist/`, and `__pycache__/` are not tracked |

## License

This project is licensed under the [MIT License](LICENSE).
