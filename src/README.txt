# Kaleido Scope

Artisan fork for Kaleido hybrid electric/convection roasters: coordinated heater + fan (Hybrid Controller), cooldown, Kaleido Network/Serial machines, and extra loggers (Phidget / TC4 / Yocto / Virtual).

Project home, what this adds versus Artisan, and how to roast:

<https://github.com/BrendenWalker/kaleido_scope>

Discussions: <https://github.com/BrendenWalker/kaleido_scope/discussions>

## Run from source

    cd src
    pip install -r requirements.txt
    python artisan.py

Then Config → Machine → Kaleido Network (or Kaleido Serial). The menu checkmarks the live connection. After ON, the left SV slider is the warmup set value.

## License

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

It is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.

A copy of the GNU General Public License is in `LICENSE.txt`.
<http://www.gnu.org/licenses/>

This fork is based on Artisan (https://github.com/artisan-roaster-scope/artisan).

## Libraries

Unmodified third-party libraries used by the Artisan tree:

- Python, PSF licence — http://www.python.org/
- Qt, LGPL 2.1 — http://qt-project.org/products/licensing
- Numpy and Scipy — http://www.scipy.org/
- PyQt, GPL 3.0, Riverbank Computing
- matplotlib, PSF-based licence
- py2app, PSF
- pyinstaller, GPL — http://www.pyinstaller.org
- pymodbus, BSD
- python-snap7, MIT
- arabic_reshaper.py, GPL
