from ytmusicapi import YTMusic
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import html, click
import concurrent.futures as cf

@click.command()
@click.option('--ytheaders', priompt='Paste YouTube Music request headers:',
    help='YouTube Music request headers. Obtain these by using Chrome to navigate to YouTube Music. Open Developer Tools in Options -> More Tools. Refresh the page. In developer tools, click network and filter results by "/browse". In the headers tab, scroll to the section "Request headers" and copy everything starting from "accept: */*" to the end of the section.')
@click.option('--spotify_client_id', default='', help='Sign up for a spotify developer account, create a new app, this will be the client-id from that app.')
@click.option('--spotify_client_secret', default='', help='Similar to "--spotify-client-id", this will be the client-secret from that app.')
@click.option('--spotify', default=True, help='Set to False to disable syncing to Spotify. Default: True')
@click.option('--ytmusic', default=True, help='Set to False to disable syncing to YouTube Music. Default: True')
@click.option('--sync_target', default='albums', help='Targets item types to sync. Currently supported are albums, songs, and playlists. Multiple instances of this command are allowed.')
@click.option('--threads', default=5, help='Advanced Command. Specifies the number of sub-threads to use when fetching items and syncing.')

class Album:
    def __init__(self, item, platform) -> None:
        self._title = ""
        self._artists = []
        self._platform = {
            'ytmusic': False,
            'spotify': False
        }
        
        if 'name' in item.keys():
            self._title = item['name']
        else:
            self._title = item['title']

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
        if platform == "ytmusic":
            self._platform['ytmusic'] = True
        elif platform == "spotify":
            self._platform['spotify'] = True

class Song:
    def __init__(self, item, platform) -> None:
        self._title = ""
        self._artists = []
        self._album = ""
        self._platform = {
            'ytmusic': False,
            'spotify': False
        }
        
        if 'name' in item.keys():
            self._title = item['name']
        elif 'title' in item.keys():
            self._title = item['title']

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
        if platform == "ytmusic":
            self._platform['ytmusic'] = True
        elif platform == "spotify":
            self._platform['spotify'] = True

class Spotube:
    def __init__(self, ytheaders, spotify_client_id, spotify_client_secret) -> None:
        self._items = []
        self._ytm = YTMusic(ytheaders)
        self._sp = spotipy.Spotify(
            auth_manager=SpotifyOAuth(
                client_id=spotify_client_id,
                client_secret=spotify_client_secret,
                redirect_uri="http://localhost:8080",
                scope="user-library-modify,user-library-read"
            )
        )
        pass

    def _paginationHelper(self, spotifyFunction):
        results = spotifyFunction
        albums = results['items']
        while results['next']:
            results = self._sp.next(results)
            albums.extend(results['items'])
        return albums

    def _processAlbum(self, item, platform):
        def exists():
            for _item in self._items:
                if (('title' in item.keys() and _item.getTitle() == item['title']) or
                    ('name' in item.keys() and _item.getTitle() == item['name'])):
                    for artist in item['artists']:
                        if artist['name'] in _item.getArtists():
                            _item.setPlatform(platform)
                            return True
            return False
        if not exists():
            self._items.append(
                Album(item, platform)
            )

    def _ytmAddAlbum(self, title, artists):
        for album in self._ytm.search(query=title, filter="albums", limit=50):
            for artist in album['artists']:
                if artist['name'] in artists:
                    self._ytm.rate_playlist(
                        self._ytm.get_album(
                            album['browseId']
                        )['playlistId'], 'LIKE'
                    )
                    return

    def _spotifyAddAlbum(self, title, artists):
        for album in self._sp.search(type="album", q=html.escape(title), limit=50)['albums']['items']:
            for artist in album['artists']:
                if artist['name'] in artists:
                    self._sp.current_user_saved_albums_add([album['id']])
                    return

    def sync(self, spotify, ytmusic, sync_target, threads):
        with cf.ThreadPoolExecutor(max_workers=threads) as executor:
            if 'albums' in sync_target:
                for album in self._paginationHelper(self._sp.current_user_saved_albums()):
                    executor.submit(self._processAlbum, album['album'], "spotify")
                for album in self._ytm.get_library_albums(limit=1000):
                    executor.submit(self._processAlbum, album, "ytmusic")

        with cf.ThreadPoolExecutor(max_workers=threads) as executor:
            for _item in self._items:
                if isinstance(_item, Album) and 'albums' in sync_target:
                    if not _item.getPlatforms()['ytmusic'] and spotify:
                        executor.submit(self._ytmAddAlbum, _item.getTitle(), _item.getArtists())
                    elif not _item.getPlatforms()['spotify'] and ytmusic:
                        executor.submit(self._spotifyAddAlbum, _item.getTitle(), _item.getArtists())


def main(ytheaders, spotify_client_id, spotify_client_secret, spotify, ytmusic, sync_target, threads):
    spotube = Spotube(ytheaders, spotify_client_id, spotify_client_secret)
    spotube.sync(spotify, ytmusic, sync_target, threads)
    quit()

if __name__ == "__main__":
    main()