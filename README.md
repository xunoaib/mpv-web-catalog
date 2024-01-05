# Web-Based Movie Browser and mpv Remote Control

Browse your movie collection and control mpv playback on another PC from a web browser.

## Overview

This tool:
- Finds local movie files matching a pattern defined by `GLOB_MOVIE_FNAMES`
- Queries OMDb for matching movies based on their filename and total runtime
- Displays the movie posters on a web page, and allows users to click on them
  to begin playing them in an external video player (mpv) on the server.
- Allows the mpv instance to be controlled using buttons on the web page or
  with an infrared remote if [mpvremote](https://github.com/xunoaib/mpvremote)
  has been properly configured.

## Requirements

- Python 3.8+
- [mpvremote](https://github.com/xunoaib/mpvremote)
- An [OMDb API Key](http://www.omdbapi.com/apikey.aspx)

## Installation

- Install [mpvremote](https://github.com/xunoaib/mpvremote) and create an
  appropriate mpv config with IPC support
- Install `mpv-web-catalog` (this package) (i.e.: with `pip install .`)
- Define `OMDB_APIKEY` and `GLOB_MOVIE_FNAMES` per this package's
  [configuration](#Configuration) instructions
- Run `mpv-web-catalog init` to create the cache directory, scan for movies,
  and begin downloading posters and metadata for them
- Install the systemd service OR execute a command like `gunicorn
  mpv_web_catalog.wsgi:app` to launch the web server
- Navigate to http://localhost:3239 or whatever URL you've configured

## Configuration

Required environment variables:
- `OMDB_APIKEY`: Free API key generated from http://www.omdbapi.com/apikey.aspx
- `GLOB_MOVIE_FNAMES`: A glob pattern describing file paths for the movies to be considered

These variables can also be defined in a configuration file. Copy `config.env`
to `~/.config/mpvremote/config.env` and modify it as needed.

### Autostart

A systemd service file is provided for convenience and can be used to autostart
the web server:

- Copy `mpv-web-catalog.service` into `~/.config/systemd/user/` and modify it as needed
- Run `systemctl --user daemon-reload`
- Run `systemctl --user enable --now mpv-web-catalog` to enable autostart and immediately start the service
