# mGit

mGit is a fast, lightweight, and streamlined Terminal User Interface (TUI) for exploring GitHub profiles, viewing repository data, reading README files, and downloading source code archives directly from your command line.

Built with Python and Textual.

# Website: mgit.great-site.net

## Features

- **Quick Launch Pins:** Immediate access to curated projects and your personal GitHub profile from startup.
- **Async Architecture:** Non-blocking background requests mean zero terminal UI stuttering or freezes.
- **Live User Search:** Look up any public GitHub profile to browse their repository listings.
- **Built-in README Viewer:** Read and scroll through raw project documentation inside the main panel.
- **Direct Downloads:** Instantly download any repository as a structured source ZIP to your local directory.

## Installation

1. Clone the repository or copy the core script layout:
   ```bash
   git clone [https://github.com/larprxlokm/mgit.git](https://github.com/larprxlokm/mgit.git)
   cd mgit

    Install the required external modules:
    Bash

    pip install textual httpx

Usage

Launch the interface by running:
Bash

python app.py

Keybindings
Key	Action
F	Focus the user search input field
Enter (on Search)	Submit username to query public repositories
Arrow Keys / Mouse	Navigate the sidebar items or scroll through README files
D	Download the zip archive of the currently selected repository
H	Return to the Home interface to view Pinned entries
Q	Safely close connection pools and exit mGit
License

This project is licensed under the MIT License - see the LICENSE file for details.
