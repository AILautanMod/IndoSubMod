# IndoSubMod
IndoSubMod automatically creates Indonesian subtitles for video files. It creates an MKV file with a selectable Indonesian subtitle track, styled with a subtle translucent gray background to keep the text readable on bright scenes. It also saves a separate SRT subtitle file. 

What’s New In Version 1.6.54

Setup and first launch

Removed Ollama and model downloads from the installer.

Added a first-launch prompt offering to open Ollama’s official download page. You can decline and continue without being redirected.

IndoSubMod now selects Argos offline translation when it is installed; otherwise, it uses GPT online translation.

Refined the installer layout, version panel, labels, and component rows for better readability.

App reliability and interface

Fixed an issue that could interrupt processing when the first progress update arrived.

The app now restores the Create Video button after successful jobs, errors, or unexpected worker exits, so you can process another video without restarting.

Added a brief pressed-state animation to app and installer buttons.

Improved translation option labels and bundled a higher-resolution brand mark.

Installer icons

Added a refreshed set of icons for the install folder, components, Python, speech recognition, translation, and desktop shortcut.
