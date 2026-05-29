# PyRAT

**PyRAT — Python Remote Access Trojan**
A basic Command and Control framework built from scratch in Python for educational purposes. Built as part of a personal cybersecurity learning project to understand how RATs and C2 frameworks work at the socket level.
Full writeup on Medium: https://medium.com/@titus06/building-pyrat-a-python-remote-access-trojan-from-scratch-b47774f541ec

Everything here was built and tested on machines I own. Do not use this on systems without explicit permission.

**What it does**
Reverse TCP connection — client connects back to to the controller

File system browsing — navigate the victim's directories

Controlled file transfer functionality — pull any file from the client machine in a controlled lab environment

Multi-client support — handle multiple victims simultaneously

Explored pesistence mechanisims commonly observed in malware analysis research

**Requirements**
Python 3.11+
PyInstaller (for compiling the exe)
