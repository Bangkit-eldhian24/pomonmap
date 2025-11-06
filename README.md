# <summary><strong>🎭Pomodoro Running with ethical hacking tools🎭 </strong></summary>
Short version: A curses-based Pomodoro that can execute tools (nmap, gobuster, dirb, etc.) detached and save the output to a per-tool log folder.

Author: ardx
Goal: Facilitate focused sessions while running non-interactive tools in a controlled home-lab/VM.
### **I HOPE U R'NOT SKIDS** joke dude...😓😓
<p align="left"> <img src="https://komarev.com/ghpvc/?username=bangkit-eldhian24&label=Viewer&color=0e75b6&style=flat" alt="bangkit-eldhian24" />
</p> <p align="left"> 
<img src="https://img.shields.io/badge/Python-FFD43B?style=for-the-badge&logo=python&logoColor=blue" />
<img src="https://img.shields.io/badge/MIT-green?style=for-the-badge" />
<img src="https://img.shields.io/badge/Linux-FCC624?style=for-the-badge&logo=linux&logoColor=black" />

### Key Features
- Curses-based terminal UI with a large clock display (tty-clock style).
- Executes commands detached when a focus session starts (-c/--cmd).
- Saves Pomodoro event logs to CSV.
- Saves tool output to /home/ardx/pomonmap/logs/<tool>/YYYYMMDDTHHMMSS_<cmd>.log.
- Wrapper (pomo-cmd-wrapper.sh) for: per-tool subfolders, PID files, header metadata, and an END line when the job completes.
- Flexible duration format support: 25, 10m, 2h, 1:30, etc.
- UI keybindings: SPACE pause/resume, n skip, r reset, q/ESC quit.

### <summary><strong>**installation**:</strong></summary>
<p>
    
    cd pomonmap
    chmod 700 /home/{USERNAME}/logs
    chmod +x main.py
    chmod +x ~/bin/pomo-cmd-wrapper.sh
    
</p>

### <summary><strong>**logs**:</strong></summary>
- CSV Pomodoro =
/home/{USERNAME}/pomonmap/logs/pomo_clock_log.csv
- Output = 
/home/{USERNAME}/pomonmap/logs/<tool>/YYYYMMDDTHHMMSS_<sanitized_cmd>.log
- PID =
/home/ardx/pomonmap/logs/<tool>/YYYYMMDDTHHMMSS.pid

**Dir List**

<img width="365" height="268" alt="Screenshot_20251106_151706" src="https://github.com/user-attachments/assets/aae96227-56b7-493e-b2ae-092818c3f282" />

### <summary><strong>**TROUBLESHOOTING**</strong></summary>
- Error parsing duration: If the first argument is not a duration, use -c or place the command after the duration.
- No log output: Check the logs folder permissions and ensure the wrapper/script has write permissions.
- Tool requires root: Run the wrapper in the home-lab VM as root or use sudo for the wrapper with secure sudoers rules.
- Terminal error while job is running: Always use a detached wrapper; do not run interactive tools from the main process.

### <summary><strong>EXAMPLE</strong></summary>

<p>
    
    python3 main.py "nmap -Pn 216.239.38.120"
    python3 main.py -c "~/bin/pomo-cmd-wrapper.sh nmap -Pn -sC -sV 192.168.56.101"
    
</p>





