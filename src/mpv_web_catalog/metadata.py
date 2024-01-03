import ast
import asyncio
import copy
import glob
import json
import logging
import os
import re
from collections import Counter
from pathlib import Path

import aiohttp
import cv2
import requests
from dotenv import load_dotenv
from Levenshtein import distance

DOTENV_ENVVAR = 'MPV_MOVIECTL_DOTENV'
DEFAULT_DOTENV_PATH = '~/.config/mpvremote/config.env'

load_dotenv()
load_dotenv(os.getenv(DOTENV_ENVVAR, DEFAULT_DOTENV_PATH))

OMDB_APIKEY = os.environ['OMDB_APIKEY']
GLOB_MOVIE_FNAMES = os.environ['GLOB_MOVIE_FNAMES']
CACHE_DIR = Path(os.getenv('MPV_MOVIECTL_CACHE_DIR',
                           '~/.cache/mpvremote')).expanduser()

SEARCH_CACHE_FILE = CACHE_DIR / 'search-cache.json'
MAIN_CACHE_FILE = CACHE_DIR / 'main-cache.json'
POSTER_DIR = CACHE_DIR / 'posters'

logging.info(f'Using {CACHE_DIR=}')
logging.info(f'Using {GLOB_MOVIE_FNAMES=}')


class ApiException(Exception):
    pass


def initialize(confirm=True):
    '''Create the cache directory and begin downloading movie metadata'''
    if confirm and input(
            f'Initialize cache at {CACHE_DIR}? [y/N] ').lower() != 'y':
        return 1

    if CACHE_DIR.exists():
        print(f'Cache directory already exists: {CACHE_DIR}')
    else:
        CACHE_DIR.mkdir()
        print(f'Created cache directory: {CACHE_DIR}')

    print()
    print(
        f'Remember to set OMDB_APIKEY and GLOB_MOVIE_FNAMES in {DEFAULT_DOTENV_PATH}\nor the file pointed to by {DOTENV_ENVVAR}.'
    )
    if confirm:
        input('\nPress enter to begin downloading metadata...')

    return retrieve_metadata(offline=False)


def retrieve_metadata(movie_path_glob=GLOB_MOVIE_FNAMES,
                      offline=False,
                      write_data_cache=True,
                      warn_dupes=True):
    '''
    Given a list of paths to local movie files, retrieve metadata for them from
    OMDb using (1) the local filename and (2) total runtime to distinguish
    between remakes and similar titles. Movie poster images are also downloaded
    and API searches are cached.
    '''
    movie_paths = list(map(Path, glob.glob(movie_path_glob)))
    movie_paths = [p for p in map(Path, movie_paths) if p.is_file()]

    # retrieve movie data from OMDB based on local filenames and their durations
    search = SearchClient(OMDB_APIKEY,
                          cachefile=SEARCH_CACHE_FILE,
                          offline=offline)

    found, notfound = search.find_best_movie_matches(movie_paths)
    if notfound:
        print("Some movies were not found:")
        for path in notfound:
            print(path)

    # download posters and retrieve their local file paths
    posterdl = PosterDownloader(POSTER_DIR, offline=offline)
    urls = {
        movie['Poster']
        for movie in found.values() if movie['Poster'].startswith('http')
    }
    posterdl.download_posters(urls)

    # create a list of local movie files, titles, years, and posters
    movies = {}
    seen = {}
    for path, movie in found.items():
        if movie['Poster'].startswith('http'):
            poster = str(movie['Poster'])
        else:
            poster = ''
        movies[str(path)] = {
            'title': movie['Title'],
            'year': movie['Year'],
            'path': str(path),
            'poster': poster,
        }
        key = (movie['Title'], movie['Year'])
        seen[key] = seen.get(key, []) + [path]

    dupes = Counter({k: len(v) for k, v in seen.items() if len(v) > 1})
    if dupes and warn_dupes:
        print('Duplicate titles detected:')
        for key in dupes:
            print('-', *key)
            for path in seen[key]:
                print(f'    {path}')

    def sorter(args):
        _, movie = args
        return re.sub(r'^(the|a|an) \s*', '',
                      movie['title'].lower()), movie['year']

    sorted_data = dict(sorted(movies.items(), key=sorter))

    if write_data_cache:
        with open(MAIN_CACHE_FILE, 'w') as f:
            json.dump(sorted_data, f)

    return sorted_data


def video_length(path):
    video = cv2.VideoCapture(str(path))
    frames = video.get(cv2.CAP_PROP_FRAME_COUNT)
    fps = video.get(cv2.CAP_PROP_FPS)
    return round(frames / fps / 60)


def path_to_title(path):
    '''Converts a movie filename to a search-friendly string'''

    title = path.name.rsplit('.', 1)[0]
    title = title.replace('Widescreen', '')
    title = re.sub(r'Disc \d+', '', title)
    title = re.sub(r'\(\d+\)', '', title)
    title = title.replace('_', ' ')
    title = title.strip('- ')
    return title.lower()


class BaseSearchClient:

    def __init__(self, apikey):
        self.apikey = apikey

    def request(self, **kwargs):
        params = {'apikey': self.apikey} | kwargs
        response = requests.get('http://www.omdbapi.com/', params=params)
        if response.status_code != 200:
            print(response.text)
            raise Exception(
                f'Received bad response code: {response.status_code}')
        return response.json()


class SearchClient(BaseSearchClient):

    def __init__(self, apikey, cachefile, offline=False):
        super().__init__(apikey)
        self.offline = offline
        self.cache = {}
        self.cachefile = Path(cachefile)
        if self.cachefile.exists():
            self.cache = ast.literal_eval(open(self.cachefile).read())

    def request(self, **kwargs):
        key = tuple(sorted(kwargs.items()))
        if key not in self.cache:
            if self.offline:
                msg = ', '.join(f'{k}="{v}"' for k, v in kwargs.items())
                raise ApiException(
                    f'API client is in offline mode. SearchClient requested: {msg}'
                )
            print('Searching', kwargs)
            self.cache[key] = super().request(**kwargs)
            self.save()
        return self.cache[key]

    def save(self):
        self.cachefile.parent.mkdir(exist_ok=True)
        with open(self.cachefile, 'w') as f:
            f.write(repr(self.cache))

    def find_movie_matches(self, path: Path):
        '''
        Finds the best movie matches based on a title (parsed from the file)
        and the movie's duration. Returns a list of OMDB movie results ordered
        by the similarity of their title and runtime.
        '''

        ranked_results = []
        title = path_to_title(path)
        results = self.request(s=title, type='movie')['Search']
        for result in results:
            details = self.request(i=result['imdbID'])
            if not (m := re.search(r'(\d+) min', details['Runtime'])):
                continue
            runtime1 = video_length(path)
            runtime2 = int(m.group(1))
            score_time = abs(runtime2 - runtime1)
            score_title = distance(details['Title'].lower(), title)
            ranked_results.append(
                (score_title, score_time, len(ranked_results), details))
        return [r[-1] for r in sorted(ranked_results)]

    def find_best_movie_match(self, path: Path, fix_posters=True):
        '''
        Finds the single best movie match and optionally attempts to find a
        fallback movie poster if one is missing.

        WARN: IndexError if no matches are found
        '''
        matches = self.find_movie_matches(path)
        final = copy.deepcopy(matches[0])
        if final['Poster'] == 'N/A' and fix_posters:
            for match in matches:
                if match['Poster'] != 'N/A':
                    final['Poster'] = match['Poster']
                    break
        return final

    def find_best_movie_matches(self, paths: list[Path], fix_posters=True):
        '''
        Finds the best movie matches for each file path.
        '''
        found = {}
        notfound = []
        for path in sorted(paths, key=path_to_title):
            if result := self.find_best_movie_match(path, fix_posters):
                found[path] = copy.deepcopy(result)
            else:
                notfound.append(path)
        return found, notfound


class PosterDownloader:

    def __init__(self, poster_dir, offline=False):
        self.poster_dir = poster_dir
        self.offline = offline

    async def _download_url(self, session, url):
        path = Path(self.poster_dir) / url.split('/')[-1]
        if path.exists():
            return path.name

        if self.offline:
            raise ApiException(
                f'API client is in offline mode. PosterDownloader requested: {url}'
            )

        async with session.get(url) as response:
            if response.status == 200:
                content = await response.read()
                path.parent.mkdir(exist_ok=True)
                with open(path, 'wb') as f:
                    f.write(content)
                print(f'Downloaded {url}')
                return path.name
            else:
                print(
                    f'Failed to download {url}. Status code: {response.status}'
                )

    async def _download_urls(self, poster_urls):
        async with aiohttp.ClientSession() as session:
            tasks = [self._download_url(session, url) for url in poster_urls]
            return await asyncio.gather(*tasks)

    def download_posters(self, poster_urls):
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()  # avoid this
        return loop.run_until_complete(self._download_urls(poster_urls))
