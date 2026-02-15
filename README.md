This README is also available in: [Русский](README-ru.md)

# spansh2edjp

Takes a route CSV file downloaded from Spansh and converts it into the EDJP route format. Simple as that.
Suitable for Neutron and Galactic plotters.

### Interface
![App interface](img/interface.png)

### About system coordinates

Spansh route CSVs contain very little information about the systems along the way, which isn't enough to fully populate an EDJP route file. The app will offer to fetch the missing information from Spansh servers. Please note that this is a fairly time-consuming process, as Spansh doesn't like frequent requests to its API; I limit the speed to a maximum of one system per second, plus the time for the actual request, plus a three-second wait before retrying if a request fails. These values are taken out of thin air, hard-coded and cannot be adjusted in the app without editing the source code.
You can disable this feature. In that case, the app will generate dummy coordinates while preserving the actual distances between systems and the number of jumps between hops (for the Neutron plotter; in the Galaxy plotter, this value is always assumed to be 1). Note that some EDJP features may not work correctly as a result; however, this shouldn't affect following the route itself.

### Running and building

No additional requirements are needed to run the executable file.

To run from source code:
```bash
pip install -r requirements.txt
python spansh2edjp.py
```

To build the executable from source code:
```bash
pip install -r requirements-dev.txt
python -m nuitka spansh2edjp.py
```

In addition to `nuitka`, `requirements-dev.txt` contains dependencies for linters used during development. If you don't want to install them, just use `pip install nuitka[onefile]`.

The project was written and tested on Python 3.13, but in theory, it should work on older versions starting from 3.9.
