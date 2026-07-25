# SteamOS Game Mode Display Selector

A graphical utility for SteamOS that allows you to force Game Mode to use a specific display output (e.g., DP-1, HDMI-A-1) instead of the default internal screen. 

## How It Works
The default script to create a Game Mode session on SteamOS is located at `/usr/lib/steamos/gamescope-session`. 

This app safely modifies this behavior by:
1. Creating a custom script at `~/.local/bin/gamescope-session` that dynamically injects your preferred display output into the gamescope command.
2. Creating a systemd override at `~/.config/systemd/user/gamescope-session.service.d/override.conf` to route the session through the new custom script.

**Failsafe:** The systemd override is designed to safely fall back to the default SteamOS script if the custom script goes missing, preventing black screens or broken sessions.

## Usage

### Using the AppImage (Recommended)
1. Go to the **[Releases](../../releases)** page and download the latest `.AppImage` file.
2. Make the file executable. You can do this by right-clicking the file in Desktop mode, going to Properties > Permissions, and checking "Is executable", or by running the following in your terminal:
   `chmod +x SteamOS_Display_Selector-x86_64.AppImage`
3. Double-click the file to run the GUI.

### Removing the Scripts
You can completely revert to default SteamOS behavior by clicking "Remove custom scripts" within the GUI, or by manually deleting the generated files from your `~/.local/bin/` and `~/.config/systemd/user/` directories.

## Building from Source

To build the AppImage yourself, you will need a Linux environment and Python 3 installed.

1. Clone the repository:
   `git clone https://github.com/MisterAnderson91/SteamOS-Game-Mode-Display-Selector.git`
2. Navigate into the directory and create a virtual environment:
   `cd SteamOS-Game-Mode-Display-Selector`
   `python3 -m venv venv`
   `source venv/bin/activate`
3. Install the required dependencies:
   `pip install -r requirements.txt`
4. Run the build script to compile the application and generate the AppImage:
   `./make_appimage.sh`

## License
This project is licensed under the GNU General Public License v3.0 (GPLv3) - see the [LICENSE](LICENSE) file for details.
