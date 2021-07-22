from ytmusicapi import YTMusic
import spotipy
from spotipy.oauth2 import SpotifyOAuth

import html

ytmusic = YTMusic(YTMusic.setup())

sp = spotipy.Spotify(
        auth_manager=SpotifyOAuth(
            client_id=input("Spotify Client ID: "),
            client_secret=input("Spotify Client Secret: "),
            redirect_uri="http://localhost:8080",
            scope="user-library-modify,user-library-read")
    )

class Item:
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

    def getType(self):
        return self._type
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

class Items:
    def __init__(self) -> None:
        self._items = []
        pass

    def processAlbum(self, item, platform):
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
                Item(item, platform)
            )

    def sync(self, ytCallback, spotifyCallback):
        for _item in self._items:
            if not _item.getPlatforms()['ytmusic']:
                ytCallback(_item.getTitle(), _item.getArtists())
            elif not _item.getPlatforms()['spotify']:
                spotifyCallback(_item.getTitle(), _item.getArtists())
    
    def getItems(self):
        return self._items

def main():
    items = Items()

    def current_user_saved_albums():
        results = sp.current_user_saved_albums()
        albums = results['items']
        while results['next']:
            results = sp.next(results)
            albums.extend(results['items'])
        return albums

    for album in current_user_saved_albums():
        items.processAlbum(album['album'], "spotify")

    for album in ytmusic.get_library_albums(limit=1000):
        items.processAlbum(album, "ytmusic")

    def ytAdd(title, artists):
        for album in ytmusic.search(query=title, filter="albums", limit=50):
            for artist in album['artists']:
                if artist['name'] in artists:
                    ytmusic.rate_playlist(
                        ytmusic.get_album(album['browseId'])['playlistId'], 'LIKE'
                    )
                    return

    def spotifyAdd(title, artists):
        for album in sp.search(type="album", q=html.escape(title), limit=50)['albums']['items']:
            for artist in album['artists']:
                if artist['name'] in artists:
                    sp.current_user_saved_albums_add([album['id']])
                    return
    
    items.sync(ytAdd, spotifyAdd)

    quit()

if __name__ == "__main__":
    main()