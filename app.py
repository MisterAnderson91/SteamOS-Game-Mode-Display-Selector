import os
import stat
import re
import json
import urllib.request
import subprocess
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QComboBox, QPushButton, QMessageBox)

# Using a raw string (r""") fixes the SyntaxWarning for the '\*' sequence
SCRIPT_TEMPLATE = r"""#!/bin/bash

# Set the desired game mode display --- e.g. DP-1 or HDMI-A-1
GAME_MODE_DISPLAY="{display_output}"

# Path to the original script
ORIGINAL_SCRIPT="/usr/lib/steamos/gamescope-session"

# Load the original script through, adding GAME_MODE_DISPLAY at the front of display list to prioritise it
# If the output isn't found then pass the original script through unaltered
if ls /sys/class/drm/card*-"$GAME_MODE_DISPLAY" >/dev/null 2>&1; then
    # The output exists on the GPU. Dynamically inject it into the gamescope command.
    
    if [ "$GAME_MODE_DISPLAY" = "eDP-1" ]; then
        # Move eDP-1 to the front and remove the duplicate from the end
        source <(sed "s/-O '\*',eDP-1/-O ${{GAME_MODE_DISPLAY}},'\*'/" "$ORIGINAL_SCRIPT")
    else
        # Add GAME_MODE_DISPLAY to the front and keep eDP-1 at the end
        source <(sed "s/-O '\*',eDP-1/-O ${{GAME_MODE_DISPLAY}},'\*',eDP-1/" "$ORIGINAL_SCRIPT")
    fi
else
    # The output does not exist. Fall back to the unmodified original script.
    source "$ORIGINAL_SCRIPT"
fi
"""

# Systemd override config to fallback to the original script if the new one goes missing
CONF_TEMPLATE = """[Service]
ExecStart=
ExecStart=/bin/bash -c 'if [ -x {script_path} ]; then exec {script_path}; else exec /usr/lib/steamos/gamescope-session; fi'
"""

class UpdateCheckerThread(QThread):
    update_checked = pyqtSignal(str, str) # Emits (latest_version, release_url)

    def __init__(self, repo_owner, repo_name, current_version):
        super().__init__()
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.current_version = current_version

    def run(self):
        url = f"https://api.github.com/repos/{self.repo_owner}/{self.repo_name}/releases/latest"
        try:
            req = urllib.request.Request(
                url, 
                headers={"User-Agent": "SteamOS-Display-Selector-Updater"}
            )
            with urllib.request.urlopen(req, timeout=4) as response:
                data = json.loads(response.read().decode())
                latest_tag = data.get("tag_name", "").strip()
                html_url = data.get("html_url", "").strip()
                if latest_tag and latest_tag != self.current_version:
                    self.update_checked.emit(latest_tag, html_url)
        except Exception:
            # Silently fail on network/offline errors to prevent freezing or crashes
            pass

class DisplaySelectorApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SteamOS Game Mode Display Selector")
        self.setMinimumSize(450, 420) 
        self.current_app_version = "2026.07.27" # Track current build baseline

        # Main Vertical Layout
        layout = QVBoxLayout()

        # --- Sub-layout to reduce space between Label and Dropdown ---
        selection_layout = QVBoxLayout()
        selection_layout.setSpacing(5)

        # Label
        self.label = QLabel("Select preferred game mode display:")
        selection_layout.addWidget(self.label, alignment=Qt.AlignmentFlag.AlignHCenter)

        # Dropdown Box
        self.combo_box = QComboBox()
        self.combo_box.setFixedWidth(250)
        self.combo_box.setStyleSheet("""
            QComboBox {
                border: 1px solid #76797C;
                border-radius: 4px;
                padding: 6px;
                background-color: #3b4045;
                color: #ffffff;
            }
            QComboBox:hover {
                background-color: #4b5157;
                border: 1px solid #9ca0a4;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 0px;
                border-left-width: 0px;
                border-left-color: transparent;
                border-top-right-radius: 3px;
                border-bottom-right-radius: 3px;
            }
            QComboBox::down-arrow {
                image: none;
            }
            QComboBox QAbstractItemView {
                background-color: #3b4045;
                color: #ffffff;
                selection-background-color: #4b5157;
                selection-color: #ffffff;
                border: 1px solid #76797C;
            }
        """)
        selection_layout.addWidget(self.combo_box, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addLayout(selection_layout)

        layout.addSpacing(15)

        # Apply Button
        self.apply_button = QPushButton("Install game mode display selector scripts")
        self.apply_button.clicked.connect(self.install_script)
        layout.addWidget(self.apply_button)

        layout.addSpacing(20)

        # Action Buttons
        self.open_script_button = QPushButton("Open gamescope-session script")
        self.open_script_button.clicked.connect(self.open_script)
        layout.addWidget(self.open_script_button)
        
        self.open_conf_button = QPushButton("Open override.conf")
        self.open_conf_button.clicked.connect(self.open_conf)
        layout.addWidget(self.open_conf_button)

        self.remove_button = QPushButton("Remove custom scripts")
        self.remove_button.clicked.connect(self.remove_scripts)
        layout.addWidget(self.remove_button)

        layout.addSpacing(20)

        # Exit Button
        self.exit_button = QPushButton("Exit")
        self.exit_button.clicked.connect(QApplication.quit)
        layout.addWidget(self.exit_button)
        
        # Bottom Layout (Update notification on left, About button on right)
        about_layout = QHBoxLayout()
        
        # Update Notification Label (Hidden by default)
        self.update_label = QLabel()
        self.update_label.setStyleSheet("color: #4da6ff; font-weight: bold;")
        self.update_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.update_label.hide()
        about_layout.addWidget(self.update_label)
        
        about_layout.addStretch() # Pushes About button to the right
        
        self.about_button = QPushButton("About")
        self.about_button.setFlat(True) 
        self.about_button.setStyleSheet("color: #888888;") 
        self.about_button.clicked.connect(self.show_about)
        about_layout.addWidget(self.about_button)
        
        layout.addLayout(about_layout)
        self.setLayout(layout)

        self.populate_displays()

        # Trigger background update check safely after UI loads
        self.start_update_check("MisterAnderson91", "SteamOS-Game-Mode-Display-Selector")

    def start_update_check(self, owner, repo):
        self.update_thread = UpdateCheckerThread(owner, repo, self.current_app_version)
        self.update_thread.update_checked.connect(self.display_update_notification)
        self.update_thread.start()

    def display_update_notification(self, latest_version, url):
        self.release_url = url
        self.update_label.setText(f"🚀 Update v{latest_version} available!")
        # Make the label behave like a clickable link
        self.update_label.mousePressEvent = lambda event: self.open_url(self.release_url)
        self.update_label.show()

    def open_url(self, url):
        env = os.environ.copy()
        for k in ["LD_LIBRARY_PATH", "APPDIR", "APPIMAGE"]:
            env.pop(k, None)
        try:
            subprocess.Popen(["xdg-open", url], env=env)
        except Exception:
            pass

    def get_script_path(self):
        return os.path.expanduser("~/.local/bin/gamescope-session")

    def get_conf_path(self):
        return os.path.expanduser("~/.config/systemd/user/gamescope-session.service.d/override.conf")

    def populate_displays(self):
        drm_path = '/sys/class/drm/'
        available_displays = set()
        
        if os.path.exists(drm_path):
            for item in os.listdir(drm_path):
                match = re.match(r'^card\d+-(.+)$', item)
                if match:
                    display_name = match.group(1)
                    if "Writeback" not in display_name:
                        available_displays.add(display_name)
                    
        if not available_displays:
            self.combo_box.addItem("No available display outputs detected.")
            self.combo_box.setEnabled(False)
            self.apply_button.setEnabled(False)
            self.open_script_button.setEnabled(False)
            self.open_conf_button.setEnabled(False)
            self.remove_button.setEnabled(False)
        else:
            self.combo_box.addItems(sorted(list(available_displays)))

        for i in range(self.combo_box.count()):
            self.combo_box.setItemData(i, Qt.AlignmentFlag.AlignCenter, Qt.ItemDataRole.TextAlignmentRole)

    def show_about(self):
        about_text = (
            "About this app:\n\n"
            "The default script to create a Game Mode session on SteamOS is /usr/lib/steamos/gamescope-session.\n\n"
            "This app creates a new script at ~/.local/bin/gamescope-session and an override config at "
            "~/.config/systemd/user/gamescope-session.service.d/override.conf.\n\n"
            "The systemd override ensures SteamOS uses the new script, but will safely fall back to the default "
            "if the custom script goes missing.\n\n"
            "The new script simply loads and parses the original, and will inject your preferred display output "
            "when it reaches the appropriate line. Otherwise, it should have no other effect.\n\n"
            "These scripts can be removed and behavior restored to default by deleting them through this app "
            "or by deleting the files manually.\n\n"
            "For updates or more information, visit:\n"
            "https://github.com/MisterAnderson91/SteamOS-Game-Mode-Display-Selector"
        )
        QMessageBox.information(self, "About SteamOS Game Mode Display Selector", about_text)

    def install_script(self):
        selected_display = self.combo_box.currentText()
        script_path = self.get_script_path()
        conf_path = self.get_conf_path()
        
        script_content = SCRIPT_TEMPLATE.format(display_output=selected_display)
        conf_content = CONF_TEMPLATE.format(script_path=script_path)

        script_dir = os.path.dirname(script_path)
        conf_dir = os.path.dirname(conf_path)

        try:
            os.makedirs(script_dir, exist_ok=True)
            with open(script_path, "w") as f:
                f.write(script_content)
            
            st = os.stat(script_path)
            os.chmod(script_path, st.st_mode | stat.S_IEXEC)

            os.makedirs(conf_dir, exist_ok=True)
            with open(conf_path, "w") as f:
                f.write(conf_content)

            QMessageBox.information(self, "Success", f"Scripts installed successfully!\nDisplay set to: {selected_display}")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to install scripts:\n{str(e)}")

    def open_file(self, target_file):
        if os.path.exists(target_file):
            env = os.environ.copy()
            env.pop("LD_LIBRARY_PATH", None)
            env.pop("APPDIR", None)
            env.pop("APPIMAGE", None)
            
            try:
                subprocess.Popen(["xdg-open", target_file], env=env)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to open {target_file}:\n{str(e)}")
        else:
            filename = os.path.basename(target_file)
            QMessageBox.warning(self, "Not Found", f"The file '{filename}' does not exist yet. Please install first.")

    def open_script(self):
        self.open_file(self.get_script_path())
        
    def open_conf(self):
        self.open_file(self.get_conf_path())

    def remove_scripts(self):
        script_file = self.get_script_path()
        conf_file = self.get_conf_path()
        removed_any = False
        
        for file_path in [script_file, conf_file]:
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    removed_any = True
                    dir_path = os.path.dirname(file_path)
                    if os.path.exists(dir_path) and not os.listdir(dir_path):
                        os.rmdir(dir_path)
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Failed to remove {file_path}:\n{str(e)}")
                    return
                    
        if removed_any:
            QMessageBox.information(self, "Success", "Files successfully removed.\nSteamOS will now use the default display behavior.")
        else:
            QMessageBox.information(self, "Info", "No custom scripts found to remove.")

if __name__ == "__main__":
    app = QApplication([])
    window = DisplaySelectorApp()
    window.show()
    app.exec()
