# Web-Based Movie Browser and mpv Remote Control

Browse your movie collection and control mpv playback on another PC from a web browser.

## Overview

This tool:
- Scans for local movie files matching a pattern defined by `GLOB_MOVIE_FNAMES`
- Searches OMDb for matching movies based on the filename and total runtime
- Shows local movies and their posters on a web page, allowing users to click
  on posters to launch the corresponding movie in an external video player on
  the server (mpv). This mpv instance can be controlled using buttons on the
  web page or with an infrared remote if
  [mpvremote](https://github.com/xunoaib/mpvremote) has been appropriately
  configured.

## Requirements

- Python 3.8+
- [mpvremote](https://github.com/xunoaib/mpvremote)

## Installation

- Install [mpvremote](https://github.com/xunoaib/mpvremote) and create an appropriate mpv config
- Install this package (i.e.: `pip install .`)
- Follow the [configuration](#Configuration) steps for this package
- Run `mpv-moviectl init` to create the cache directory, scan for movies, and
  begin downloading metadata and posters for them from OMDb
- Run `mpv-moviectl web` to launch the web server
- Navigate to http://localhost:8000 or http://<your_ip>:8000

## Configuration

- Copy `config.env.example` to `~/.config/mpvremote/config.env` or set the
  appropriate environment variables below.
- `OMDB_APIKEY`: Free API key generated from http://www.omdbapi.com/apikey.aspx
- `GLOB_MOVIE_FNAMES`: A glob pattern describing the file paths for the desired movies
