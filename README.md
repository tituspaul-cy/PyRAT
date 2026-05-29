# PyRAT

**PyRAT — Python Remote Access Trojan**
A basic Command and Control framework built from scratch in Python for educational purposes. Built as part of a personal cybersecurity learning project to understand how RATs and C2 frameworks work at the socket level.
Full writeup on Medium: [link]

Everything here was built and tested on machines I own. Do not use this on systems without explicit permission.

**What it does**
Reverse TCP connection — victim connects out to the operator
File system browsing — navigate the victim's directories
File exfiltration — pull any file from the victim's machine
Multi-client support — handle multiple victims simultaneously
Self-contained persistence — exe copies itself and installs startup entry automatically

**Requirements**
Python 3.11+
PyInstaller (for compiling the exe)
