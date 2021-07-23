#!/usr/bin/python3
from ytmusicapi import YTMusic
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import html, click
import concurrent.futures as cf
import logging, os.path

logger = logging.getLogger(__name__)

def _setPlatform(self, platform):
    if platform == "ytmusic":
        self._platform['ytmusic'] = True
    elif platform == "spotify":
        self._platform['spotify'] = True

def _titleHelper(item):
    return (
        item['title'] if 'title' in item.keys() else (
            item['name'] if 'name' in item.keys() else ""
        )
    )

class Album:
    def __init__(self, item, platform) -> None:
        self._title = ""
        self._artists = []
        self._platform = {
            'ytmusic': False,
            'spotify': False
        }
        
        self._title = _titleHelper(item)

        for artist in item['artists']:
            self._artists.append(
                artist['name']
            )
        
        self.setPlatform(platform)
        pass

    def getTitle(self):
        return self._title
    def getArtists(self):
        return self._artists
    def getPlatforms(self):
        return self._platform
    def setPlatform(self, platform):
        _setPlatform(self,platform)

class Song:
    def __init__(self, item, platform) -> None:
        self._title = ""
        self._artists = []
        self._platform = {
            'ytmusic': False,
            'spotify': False
        }
        
        self._title = _titleHelper(item)

        for artist in item['artists']:
            self._artists.append(
                artist['name']
            )
        
        self._album = item['album']
        
        self.setPlatform(platform)
        pass

    def getTitle(self):
        return self._title
    def getArtists(self):
        return self._artists
    def getPlatforms(self):
        return self._platform
    def setPlatform(self, platform):
        _setPlatform(self,platform)

class Spotube:
    def __init__(self, ytheaders, spotify_client_id, spotify_client_secret) -> None:
        self._items = []
        self._ytm = YTMusic('./request_headers.json'
            if os.path.isfile('./request_headers.json') else ytheaders)
        self._sp = spotipy.Spotify(
            auth_manager=SpotifyOAuth(
                client_id=spotify_client_id,
                client_secret=spotify_client_secret,
                redirect_uri="http://localhost:8080",
                scope="user-library-modify,user-library-read"
            )
        )
        logger.info("Spotube initialized.")
        pass

    def _paginationHelper(self, spotifyFunction):
        results = spotifyFunction()
        albums = results['items']
        while results['next']:
            results = self._sp.next(results)
            albums.extend(results['items'])
        return albums
    
    def _processAlbum(self, item, platform):
        def exists():
            for _item in self._items:
                if _item.getTitle() == _titleHelper(item):
                    for artist in item['artists']:
                        if artist['name'] in _item.getArtists():
                            logger.info("Album: {} already exists on {}. Updating with {}.".format(_titleHelper(item), _item.getPlatforms(), platform))
                            _item.setPlatform(platform)
                            return True
            return False
        if not exists():
            logger.info("Album: {} Platform: {} does not exist locally. Adding to process stack.".format(_titleHelper(item), platform))
            self._items.append(
                Album(item, platform)
            )

    def _processSong(self, item, platform):
        def exists():
            for _item in self._items:
                if isinstance(_item, Album):
                    if _item.getTitle() == _titleHelper(item['album']):
                        for artist in item['artists']:
                            if artist['name'] in _item.getArtists():
                                logger.info("Song: {} already exists in an album {}.".format(_titleHelper(item), _item.getTitle()))
                                return True
                if isinstance(_item, Song):
                    if _item.getTitle() == _titleHelper(item):
                        for artist in item['artists']:
                            if artist['name'] in _item.getArtists():
                                logger.info("Song: {} already exists on {}. Updating with {}.".format(_titleHelper(item), _item.getPlatforms(), platform))
                                _item.setPlatform(platform)
                                return True
            return False
        if not exists():
            logger.info("Song: {} Platform: {} does not exist locally or in any album. Adding to process stack.".format(_titleHelper(item), platform))
            self._items.append(
                Song(item, platform)
            )

    def _ytmAddAlbum(self, item, dryrun):
        for album in self._ytm.search(query=item.getTitle(), filter="albums", limit=50):
            for artist in album['artists']:
                if artist['name'] in item.getArtists():
                    logger.info("Adding album {} to YouTube Music.".format(item.getTitle()))
                    playlist = self._ytm.get_album(album['browseId'])['playlistId']
                    if not dryrun:
                        self._ytm.rate_playlist(playlist, 'LIKE')
                    else:
                        logger.info("DRYRUN: rate_playlist ID: {} 'LIKE'".format(playlist))
                    return

    def _spotifyAddAlbum(self, item, dryrun):
        for album in self._sp.search(type="album", q=html.escape(item.getTitle()), limit=50)['albums']['items']:
            for artist in album['artists']:
                if artist['name'] in item.getArtists():
                    logger.info("Adding album {} to Spotify.".format(item.getTitle()))
                    if not dryrun:
                        self._sp.current_user_saved_albums_add([album['id']])
                    else:
                        logger.info("DRYRUN: current_user_saved_albums_add ID: {} ".format(album['id']))                    
                    return
    
    def _ytmAddSong(self, item, dryrun):
        for song in self._ytm.search(query=item.getTitle(), filter="songs", limit=50):
            if 'feedbackTokens' not in song.keys():
                continue
            for artist in song['artists']:
                if artist['name'] in item.getArtists():
                    logger.info("Adding song {} to YouTube Music.".format(item.getTitle()))
                    if not dryrun:
                        self._ytm.edit_song_library_status(song['feedbackTokens']['add'])
                    else:
                        logger.info("DRYRUN: edit_song_library_status ID: {}".format(song['feedbackTokens']['add']))
                    return

    def _spotifyAddSong(self, item, dryrun):
        for song in self._sp.search(type="track", q=html.escape(item.getTitle()), limit=50)['tracks']['items']:
            for artist in song['artists']:
                if artist['name'] in item.getArtists():
                    logger.info("Adding song {} to Spotify.".format(item.getTitle()))
                    if not dryrun:
                        self._sp.current_user_saved_tracks_add([song['id']])
                    else:
                        logger.info("DRYRUN: current_user_saved_tracks_add ID: {} ".format(song['id']))                    
                    return

    def sync(self, spotify, ytmusic, sync_target, threads, dryrun):
        logger.info("Processing albums...")
        if 'albums' in sync_target:
            with cf.ThreadPoolExecutor(max_workers=threads) as executor:
                for album in self._paginationHelper(self._sp.current_user_saved_albums):
                    executor.submit(self._processAlbum, album['album'], "spotify")
                for album in self._ytm.get_library_albums(limit=1000):
                    executor.submit(self._processAlbum, album, "ytmusic")
        logger.info("Processing songs...")
        if 'songs' in sync_target:
            with cf.ThreadPoolExecutor(max_workers=threads) as executor:
                for song in self._paginationHelper(self._sp.current_user_saved_tracks):
                    executor.submit(self._processSong, song['track'], "spotify")
                for song in self._ytm.get_library_songs(limit=1000):
                    executor.submit(self._processSong, song, "ytmusic")

        with cf.ThreadPoolExecutor(max_workers=threads) as executor:
            for _item in self._items:
                if isinstance(_item, Album) and 'albums' in sync_target:
                    if not _item.getPlatforms()['ytmusic'] and spotify:
                        executor.submit(self._ytmAddAlbum, _item, dryrun)
                    elif not _item.getPlatforms()['spotify'] and ytmusic:
                        executor.submit(self._spotifyAddAlbum, _item, dryrun)
                elif isinstance(_item, Song):
                    if not _item.getPlatforms()['ytmusic'] and spotify:
                        executor.submit(self._ytmAddSong, _item, dryrun)
                    if not _item.getPlatforms()['spotify'] and ytmusic:
                        executor.submit(self._spotifyAddSong, _item, dryrun)

@click.command()
@click.option('--ytheaders', prompt='Paste YouTube Music request headers',
    help='YouTube Music request headers. Obtain these by using Chrome to navigate to YouTube Music. Open Developer Tools in Options -> More Tools. Refresh the page. In developer tools, click network and filter results by "/browse". In the headers tab, scroll to the section "Request headers" and copy everything starting from "accept: */*" to the end of the section.')
@click.option('--spotify_client_id', default='', help='Sign up for a spotify developer account, create a new app, this will be the client-id from that app.')
@click.option('--spotify_client_secret', default='', help='Similar to "--spotify-client-id", this will be the client-secret from that app.')
@click.option('--spotify/--no-spotify', default=True, help='Controls if Spotify will be synced to. Default: True')
@click.option('--ytmusic/--no-ytmusic', default=True, help='Controls if YouTube Music will be synced to. Default: True')
@click.option('--sync_target', default=['albums'], help='Targets item types to sync. Currently supported are albums, songs, and playlists. Multiple instances of this command are allowed.', multiple=True)
@click.option('--threads', default=5, help='Advanced Command. Specifies the number of async-threads to use when fetching items and syncing.')
@click.option('--dryrun', is_flag=True, help='Advanced Command. Outputs additions instead of performing them.')
def main(ytheaders, spotify_client_id, spotify_client_secret, spotify, ytmusic, sync_target, threads, dryrun):
    logging.basicConfig(level = logging.INFO)
    spotube = Spotube(ytheaders, spotify_client_id, spotify_client_secret)
    spotube.sync(spotify, ytmusic, sync_target, threads, dryrun)
    quit()

if __name__ == "__main__":
    main()