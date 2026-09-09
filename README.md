# Rencher - Play and mod Ren'Py games
<p align="center">
	<img src="data/assets/rencher-logo.png" width="400px"/>
<p/>

<p>
	Rencher is a game manager for Ren'Py, designed around DDLC mods.
	It has support for Ren'Py 7 DDLC mods, and also fixes many bugs when trying to launch mods on Linux.
</p>
Main features:
<ul>
	<li>Clean UI made with GTK4 and Adwaita</li>
	<li>Asynchronous importing and deleting</li>
	<li>Discord RPC</li>
	<li>The ability to skip the splash screen and/or main menu</li>
	<li>Self contained game saves</li>
</ul>

[Link to the Trello board](https://trello.com/b/CGaqf0xx/rencher)
<br/>

<p>
	<img src="data/screenshots/Screenshot From 2025-11-02 17-47-53.png" alt="Screenshot of Rencher's UI showing off the main window" width="384px"/>
	<img src="data/screenshots/Screenshot From 2025-11-02 17-48-27.png" alt="Screenshot of Rencher's UI showing off the import menu" width="384px"/>
</p>

## Download!
### [Windows](https://github.com/danatationn/Rencher/releases/latest/download/RencherInstaller.exe) - [Linux](https://github.com/danatationn/Rencher/releases/latest/download/Rencher.flatpak)

## Possible upcoming features
- [x] Discord RPC
- [ ] Asset Viewer (unrpa + unrpyc)
- [ ] Store (vndb, itch.io, the old DDMC mod list thing)
- [ ] More...

## Testing / Building
### Linux
1. `uv sync`
2. `meson setup build --prefix $(pwd)/build/root`
3. `ninja -C build install`

<details> <summary> Flatpak </summary>

`flatpak-builder --install --user build/flatpak build-aux/flatpak/com.github.danatationn.rencher.yml`

* running the flatpak

	`flatpak run com.github.danatationn.rencher`
* exporting as .flatpak	

	`flatpak build-bundle ~/.local/share/flatpak/repo build/Rencher.flatpak com.github.danatationn.rencher`
</details>

### Windows
* Setting up the environment
	1. Install [MSYS2](https://www.msys2.org/)
	2. Launch MSYS2 UCRT64
	3. `pacman -Sy mingw-w64-ucrt-x86_64-python\
            mingw-w64-ucrt-x86_64-python-pip\
            mingw-w64-ucrt-x86_64-uv\
            mingw-w64-ucrt-x86_64-meson\
            mingw-w64-ucrt-x86_64-gtk4\
            mingw-w64-ucrt-x86_64-gobject-introspection\
            mingw-w64-ucrt-x86_64-libadwaita\
            mingw-w64-ucrt-x86_64-blueprint-compiler\
            mingw-w64-ucrt-x86_64-cmake\
            mingw-w64-ucrt-x86_64-gcc\
            mingw-w64-ucrt-x86_64-python-cx-freeze\
            mingw-w64-ucrt-x86_64-nsis`
	4. `git clone https://github.com/danatationn/rencher`
	5. `cd rencher`
	6. `uv sync`
	7. `meson setup build --prefix $(pwd)/build/root`
	8. `ninja -C build install`

* Freezing (Python to EXE)

	`ninja -C build freeze`

* Making the installer

	`ninja -C build makensis`

### Universal

* Running Rencher within Meson

	`ninja -C build run` or `ninja -C build dev` if you want debug logs

## Credits and License

[Nicotine+](https://github.com/nicotine-plus/nicotine-plus) was used as reference for what I should do regarding PyGObject and packaging
<br>
Logo made by [vl1](https://vl1.neocities.org/). check him out!
<br>
This project is under the [GPL-3](https://github.com/danatationn/rencher?tab=GPL-3.0-1-ov-file)

#### © 2026 danatationn
