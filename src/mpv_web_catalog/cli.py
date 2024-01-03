import argparse

from dotenv import load_dotenv


def main():
    try:
        return _main()
    except KeyboardInterrupt:
        pass


def _main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-c',
                        '--config',
                        help='dotenv-style config to load variables from')

    parser.add_argument('command', choices=['init', 'web', 'web-debug'])
    args = parser.parse_args()

    if args.config:
        load_dotenv(args.config)

    match args.command:
        case 'init':
            initdb()
        case 'web':
            serve_web()
        case 'web-debug':
            serve_web_debug()


def serve_web():
    from subprocess import run
    run(['gunicorn', 'mpv_web_catalog.wsgi:app', '--access-logfile', '-'])


def serve_web_debug():
    from .wsgi import app
    app.run(debug=True, host='0.0.0.0')


def initdb():
    from . import metadata
    metadata.initialize()


if __name__ == '__main__':
    main()