# SpankBang Downloader

[![PyPI version](https://badge.fury.io/py/cloudscraper.svg)](https://badge.fury.io/py/cloudscraper)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![image](https://img.shields.io/pypi/pyversions/cloudscraper.svg)](https://pypi.org/project/cloudscraper/)
[![Build Status](https://travis-ci.com/VeNoMouS/cloudscraper.svg?branch=master)](https://travis-ci.com/VeNoMouS/cloudscraper)
[![Donate](https://img.shields.io/badge/Donate-Buy%20Me%20A%20Coffee-brightgreen.svg)](https://www.buymeacoffee.com/venomous)



# Installation

Clone this repository and run `python setup.py install` or `sudo python3 setup.py install` if you need elevated permissions on macOS or Linux.
- On macOS you may do the alternative of running `pip3 install beautifulsoup4 tqdm cloudscraper --break-system-packages` if you're managing your version of Python externally.
Then `pip install bs4`
Then `pip install tqdm`

# Dependencies

- Python 3.x
- **[Requests](https://github.com/kennethreitz/requests)** >= 2.9.2
- **[requests_toolbelt](https://pypi.org/project/requests-toolbelt/)** >= 0.9.1

`python setup.py install` will install the Python dependencies automatically.

Any requests made from this session object to websites protected by Cloudflare anti-bot will be handled automatically. You can effectively treat SpankBang as if it is not protected with anything.

# Usage
1. Install Python 3
2. Clone this repository (download all files here)
3. Enter 'python3 setup.py install' in the console/command prompt in the downloaded directory.  Run `pip install setuptools` if you get an error that you don't have it.
4. Take input.txt and sb_scraper.py to any directory you want and use it. The text file contains a list of video, playlist, channel or profile URLs.
5. Or, Insert a custom .txt file as an argument in the command prompt/terminal (like 'sb_scraper.py theseurls.txt') (or drag a .txt file over the script file) into split.py to split it up into 4. You can run multiple instances of Scraper at once. 

# Features
- Drag a txt file of choice onto the .py file to run that, otherwise, double clicking will default to input.txt
- Playlist URLs as input work to output a .txt file of URLs which can then be fed back into the program
- split.py splits any txt file with several lines into 4 files. Can be used for playlists.
- Does not work with VR videos.
- You can rename the `.py` file and use it.
