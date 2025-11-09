# PC-Canary: PC Agent Benchmark Evaluator

A PC Agent benchmark evaluation system based on trigger monitoring and open-source user software, designed to assess an Agent’s ability to perform desktop tasks.

## Features

- Non-intrusive application behavior monitoring, no accessibility permissions required  
- Asynchronous evaluation mode, does not interfere with normal Agent execution  
- Extensible task registration mechanism  
- Detailed evaluation report generation  
- Easy integration with Agent systems of any architecture  

## Currently Supported Tasks

- **Telegram Search Task**: evaluates the Agent’s ability to search for "news" in the Telegram client  

## Running
### Configure VNC Remote Desktop Environment
Clone this repository:
```bash
git clone https://github.com/k0zhevnikov/image_setup
```
Then manually build the image using the Dockerfile in this project directory:
```bash
docker build \ 
  --build-arg HTTP_PROXY=YOUR_PROXY   --build-arg HTTPS_PROXY=YOUR_PROXY   -t monitor_env:cpu   -f .devcontainer/Dockerfile .
```
Run this image and enter the container environment:
```bash
docker run --rm -it   --privileged   --network host   monitor_env:cpu                         
```
Inside the environment, run:
```bash
vncserver -xstartup /home/agent/.vnc/xstartup  -geometry  1024x768 :5
```
to start the VNC desktop. Then reset the DISPLAY variable according to the actual desktop number you started (e.g., :5):
```bash
export DISPLAY=:5
```
Next, connect with your VNC Viewer client to verify that the remote desktop service is running. The address may look like:
```
vnc://YOUR_SERVER_IP:5905
```

### Run the tdesktop Client in the Remote Desktop
This project includes the tdesktop source code repository as a submodule. First, initialize it:
```bash
git submodule update --init --recursive tdesktop
```

#### (Optional) Build and Configure the tdesktop Client and User Data Yourself
For project developers, it is recommended to go into the `apps/tdesktop` directory and follow the official documentation to build and configure a Debug mode tdesktop client.

After compilation, the executable file and user data will be installed into the `apps/tdesktop/out/Debug` directory. Typically, it will include:
```bash
Debug/
├── tdata # user data directory
│   └── ...
├── DebugLogs # directory containing all runtime logs
│   └── ...
├── Telegram # executable file under Linux
└── log.txt # runtime log
```
It is recommended to manually configure the user data in the GUI environment after building, such as logging into an account.

#### Configure Container to Save User Data State
Create a docker volume and copy the contents of the `tdata` directory into it. For example:
```bash
docker volume create telegram-data2
docker run --rm -it   monitor_env:cpu
  -v telegram-data2:/dest
  -v ${localWorkspaceFolder}/apps/tdesktop/out/Debug:/src
```
```bash
# Inside the container
cp -r /src/tdata /dest/
exit
```

Then mount the `tdata` data volume in volume mode into the container, and mount the `Telegram` file in bind mode. For state persistence and recovery, you should also make additional backups of the data volume.

In the end, the `tdata` folder should be in the same directory as the executable, and you must ensure the container user has read/write permission. You can refer to the configuration in `.devcontainer/devcontainer.json`:
```json
{
    "mounts": [
        "source=${localWorkspaceFolder},target=/workspace,type=bind",
        "source=telegram-data2,target=/apps/tdesktop/Debug,type=volume",
        "source=${localWorkspaceFolder}/apps/tdesktop/out/Debug/Telegram,target=/apps/tdesktop/Debug/Telegram,type=bind"
    ],
    "postCreateCommand": "bash ./.devcontainer/postCreateCommand.sh",
}
```
```bash
# postCreateCommand.sh, make sure this script runs
#!/bin/bash
sudo chown -R agent:agent /apps/tdesktop/Debug/
```
After configuration, rebuild the container and enter the environment. Run the `/apps/tdesktop/Debug/Telegram` client to verify whether user data is already present. If yes, then the basic environment setup is complete.

### Evaluator

You can directly run `test_evaluator.py` and `run_evaluator.py`, then manually operate the Telegram client in the GUI environment, click the search bar, enter search content, and check if the evaluator callback is triggered when correct input is detected:

```bash
python test_evaluator.py
```

#### VSCode User Data Cleanup

When evaluating VSCode tasks, stale Socket.IO session data in the user_data_dir can cause connection issues. The evaluator provides an opt-in cleanup mechanism to remove these files during context restoration.

To enable this feature, add the following configuration flag to your task's `config.json`:

```json
{
  "clear_vscode_storage_on_restore": true
}
```

**Important Notes:**
- This feature is **disabled by default** to prevent unintended data loss
- Only activates when:
  - The flag is explicitly set to `true` in the task configuration
  - The restore path contains both "vscode" and "user_data_dir"
- Clears the following VSCode storage items:
  - `Session Storage/` directory
  - `Local Storage/` directory
  - `Cookies` file
  - `Cookies-journal` file
- This is a **destructive operation** - use only when stale session data needs to be cleared

### Integration with Agent System

Currently, this project includes a basic prompt-based GUI Agent. You can test integrating the evaluator with the Agent system by running:

```bash
python run_agent_with_evaluator.py
```

## Architecture Overview

The entire evaluation system consists of the following core components:

```bash
project/                         # project root directory
├── agent/                           # agent system module
│   ├── models/                      
│   ├── base_agent.py                # agent base class, basic prompt agent implementation
│   └── prompt.py                    # prompt generation and management module
│
├── apps/                            # target application repositories
│   ├── tdesktop/                    # Telegram Desktop application
│   ├── ...
│
├── env/                             
│   └── controller/                  # environment controller, manages interfaces exposed to the Agent
│       └── code_execution_controller.py  # code execution interface, provides code execution capability for Agent
│
├── evaluator/                       # evaluation system, responsible for assessing agent performance
│   ├── core/                        # evaluator core components
│   │   ├── base_evaluator.py        # evaluator base class, defines basic evaluation process
│   │   ├── hook_manager.py          # hook manager, manages Frida scripts
│   │   └── result_collector.py      # result collector, saves evaluation data
│   │
│   └── utils/                       # logging utilities
│
├── tests/                           
│   └── tasks/                       # task test directory
│       └── telegram/                # all tasks under Telegram app
│           └── task01_search/       # Telegram search functionality test
│               ├── handler.py       # event handler, processes hook script events
│               ├── hooker.js        # Frida hook script, monitors Telegram
│               └── config.json      # task configuration file, defines test parameters
│
├── utils/                           # general utilities
│   └── logger.py                    # logging module
│
├── run_agent_with_evaluator.py       # test script
│
├── test_evaluator.py       # test script
│
├── run_evaluator.py       # run evaluator
│
└── README.md       # documentation
```
