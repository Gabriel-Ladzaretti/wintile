# Window tiling manager for Linux
> Drag and tile windows to pre-configured positions.
> Enhances productivity with ultrawide displays, 
> Makes better use of screen real estate by tiling windows and programs intelligently.
> - Requires "X Window system" manager (X11) such as:
>   - Gnome, Xfce, unity, KDE etc.


## Dependencies
> installation instruction are for ubuntu based systems.
- Xlib library:
  - $ sudo apt-get update
  - $ sudo apt-get install python-xlib 
- tkinter:
  - $ sudo apt-get install python3-tk

### Tested on:
* Ubuntu 16.04 LTS Gnome 3.18
* manjaro - xfce 18.1.3
* Pop!_OS 19.04 - Gnome 3.32.2
* Pop!_OS 19.10 - Gnome 3.34.3
* Ubuntu 18.04.3 LTS - Gnome 3.28.2
## Running instructions
- Disable gnome's native edge tiling:
  -  $ dconf write /org/gnome/mutter/edge-tiling false
- $ python3 wintile.py


## Usage
- Drag and drop into predefined areas to auto tile: 
    * upper left/right corner -> populate left/right 2/3 of the display
    * upper middle edge -> populate centered 7/10 display area
    * middle left/right edge -> populate left/right display half
    * bottom left/middle/right third edge -> populate left/middle/right display third

# Demo
![Demo gif](https://raw.githubusercontent.com/ladzaretti/wintile/master/opt_win.gif)
