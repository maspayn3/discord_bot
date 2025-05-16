import json
# great for async file operations
import aiofiles
import os.path

class PlaylistManager:
    def __init__(self, file_path="playlists.json"):
        # cant call async methods from __init__
        self.file_path = file_path
        self.playlists = {}


    async def initialize(self):
        await self.load_playlists()
        return self


    async def load_playlists(self):
        if os.path.exists(self.file_path):
            try:
                async with aiofiles.open("playlists.json") as file:
                    content = await file.read()
                    self.playlists = json.loads(content)
            except Exception as e:
                self.playlists = {}
                print("Error loading playlists file")
                print(e)

        else:
            print("No playlists file found")

        
    async def save_playlists(self):
        async with aiofiles.open(self.file_path, 'w') as file:
            await file.write(json.dumps(self.playlists, indent=4))


    async def create_playlist(self, name):
        """Create a new playlist"""
        if name in self.playlists:
            return False
        self.playlists[name] = []
        await self.save_playlists()
        return True 


    async def delete_playlist(self, name):
        """Delete a playlist"""
        if name not in self.playlists:
            return False
        del self.playlists[name]
        await self.save_playlists()
        return True
    

    async def add_song_to_playlist(self, playlist_name, song):
        """Add a song to a playlist"""
        if playlist_name not in self.playlists:
            return False
        
        # Check if song already exists in playlist
        for existing_song in self.playlists[playlist_name]:
            if existing_song['url'] == song['url']:
                return False
                
        self.playlists[playlist_name].append(song)
        await self.save_playlists()
        return True
    

    async def remove_song_from_playlist(self, playlist_name, index):
        """Remove a song from a playlist by index"""
        if playlist_name not in self.playlists:
            return False
        
        if index < 0 or index >= len(self.playlists[playlist_name]):
            return False
            
        self.playlists[playlist_name].pop(index)
        await self.save_playlists()
        return True


    def get_playlist(self, name):
        """Get a playlist by name (no need for async here as it's just dictionary access)"""
        if name not in self.playlists:
            return None
        return self.playlists[name]
    

    def list_playlists(self):
        """Get a list of all playlist names (no need for async here as it's just dictionary access)"""
        return list(self.playlists.keys())