import pygame
import sys
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any
import requests
import random
import string
import datetime
import os
import webview
from dataclasses import dataclass
import threading
import multiprocessing
import numpy as np

class GoogleBooksAPI:
    def __init__(self, api_key: Optional[str] = None):
        """Initialize with API key from parameter or environment variable."""
        self.api_key = api_key or os.getenv('GOOGLE_BOOKS_API_KEY')
        if not self.api_key:
            raise ValueError(
                "API key is required. Either pass it to GoogleBooksAPI() or "
                "set the GOOGLE_BOOKS_API_KEY environment variable."
            )
        self.base_url = "https://www.googleapis.com/books/v1/volumes"

    def get_random_word(self) -> str:
        """Returns a random single letter or two-letter combination to use as a search term."""
        letters = string.ascii_lowercase
        if random.random() < 0.5:  # 50% chance for single letter
            return random.choice(letters)
        return random.choice(letters) + random.choice(letters)

    def get_random_year(self) -> int:
        """Returns a weighted random year between 1800 and current year."""
        start_year = 1800
        current_year = datetime.datetime.now().year
        years = np.arange(start_year, current_year + 1)
        weights = np.exp(0.01 * (years - start_year))
        weights /= weights.sum()  # Normalize to make it a probability distribution
        return np.random.choice(years, p=weights)

    def get_random_book(self, preview_type: str = 'partial') -> Optional[Dict[str, Any]]:
        """Queries Google Books API with random parameters and returns a random book."""
        search_term = self.get_random_word()
        year = self.get_random_year()
        params = {
            'q': f'{search_term}+publishedDate:{year}',
            'maxResults': 40,
            'langRestrict': 'en',
            'printType': 'books',
            'filter': preview_type,
            'key': self.api_key,
            'orderBy': 'relevance'
        }
        try:
            response = requests.get(self.base_url, params=params)
            response.raise_for_status()
            data = response.json()
            if data.get('totalItems', 0) > 0 and 'items' in data:
                random.shuffle(data['items'])
                for book in data['items']:
                    info = book.get('volumeInfo', {})
                    if info.get('previewLink'):
                        return {
                            'title': info.get('title', 'Unknown Title'),
                            'authors': info.get('authors', []),
                            'published_date': info.get('publishedDate', ''),
                            'preview_link': info.get('previewLink', ''),
                            'description': info.get('description', ''),
                            'preview_availability': info.get('accessInfo', {}).get('viewability', ''),
                            'page_count': info.get('pageCount', None),
                            'categories': info.get('categories', [])
                        }
            return None
        except requests.RequestException as e:
            print(f"Error accessing Google Books API: {e}")
            return None

    def get_random_book_with_retries(self, max_retries: int = 3, preview_type: str = 'partial') -> Optional[Dict[str, Any]]:
        """Attempts to get a random book multiple times if initial attempts fail."""
        for _ in range(max_retries):
            result = self.get_random_book(preview_type)
            if result is not None:
                return result
        return None

class Direction(Enum):
    NORTH = 0
    EAST = 1
    SOUTH = 2
    WEST = 3

class Location:
    def __init__(self, image_path: str, allowed_directions: List[Direction], hotspots: Dict[str, Tuple[pygame.Rect, callable]]):
        self.image_path = image_path
        self.allowed_directions = allowed_directions
        self.hotspots = hotspots
        self.image = None

    def load_image(self, screen_size: Tuple[int, int]):
        img = pygame.image.load(self.image_path)
        self.image = pygame.transform.scale(img, screen_size)

def open_webview(url, title):
    """Open a webview window with the given URL and title."""
    webview.create_window(title, url, width=1000, height=1200, resizable=True)
    webview.start()

class Game:
    def door6_action(self, event=None):
        """Flickers the 'images/closet.jpg' image for 1 second."""
        # Load the image
        closet_img = pygame.image.load('images/closet.jpg')
        closet_img = pygame.transform.scale(closet_img, self.screen_size)

        # Set the flicker duration and start time
        flicker_duration = 1000  # 1 second in milliseconds
        start_time = pygame.time.get_ticks()
        flicker_interval = 100  # 100 ms per flicker (adjust for faster/slower flicker)

        # Flicker loop
        while pygame.time.get_ticks() - start_time < flicker_duration:
            # Determine whether to display the image or a black screen
            elapsed_time = pygame.time.get_ticks() - start_time
            if (elapsed_time // flicker_interval) % 2 == 0:
                self.screen.blit(closet_img, (0, 0))
            else:
                self.screen.fill((0, 0, 0))

            pygame.display.flip()
            pygame.time.delay(50)  # Short delay to control flicker speed

    def __init__(self, screen_width: int = 800, screen_height: int = 600):
        pygame.init()
        self.screen_size = (screen_width, screen_height)
        self.screen = pygame.display.set_mode(self.screen_size)
        pygame.display.set_caption("Where is everybody? Hello?")
        
        # Initialize Google Books API
        self.books_api = GoogleBooksAPI()
        
        # Initialize mixer for background music
        pygame.mixer.init()

        # Load and play background music
        pygame.mixer.music.load('./audio/horror.mp3')  # Replace with the actual path to your MP3 file
        pygame.mixer.music.play(-1)  # -1 makes the music loop indefinitely
        
        # Loading message font
        self.font = pygame.font.SysFont('Arial', 24)
        self.loading = False
        self.loading_start_time = 0
        
        # Navigation arrows
        arrow_size = 50
        self.arrows = {
            Direction.NORTH: pygame.Rect(screen_width // 2 - arrow_size // 2, 10, arrow_size, arrow_size),
            Direction.SOUTH: pygame.Rect(screen_width // 2 - arrow_size // 2, screen_height - arrow_size - 10, arrow_size, arrow_size),
            Direction.WEST: pygame.Rect(10, screen_height // 2 - arrow_size // 2, arrow_size, arrow_size),
            Direction.EAST: pygame.Rect(screen_width - arrow_size - 10, screen_height // 2 - arrow_size // 2, arrow_size, arrow_size)
        }
        
        # Grid position (0,0 is top-left)
        self.current_pos = (1, 2)
        self.locations: Dict[Tuple[int, int], Location] = {}

    def add_location(self, grid_pos: Tuple[int, int], location: Location):
        """Add a new location to the game grid."""
        if 0 <= grid_pos[0] < 3 and 0 <= grid_pos[1] < 3:
            self.locations[grid_pos] = location
            location.load_image(self.screen_size)

    def can_move(self, direction: Direction) -> bool:
        """Check if movement in given direction is allowed."""
        current_location = self.locations.get(self.current_pos)
        if not current_location:
            return False
            
        if direction not in current_location.allowed_directions:
            return False
            
        new_pos = self.get_new_position(direction)
        return new_pos in self.locations

    def get_new_position(self, direction: Direction) -> Tuple[int, int]:
        """Calculate new position after moving in given direction."""
        x, y = self.current_pos
        if direction == Direction.NORTH:
            return (x, y - 1)
        elif direction == Direction.SOUTH:
            return (x, y + 1)
        elif direction == Direction.WEST:
            return (x - 1, y)
        elif direction == Direction.EAST:
            return (x + 1, y)
        return self.current_pos

    def draw_arrows(self):
        """Draw navigation arrows for allowed directions."""
        for direction, rect in self.arrows.items():
            if self.can_move(direction):
                pygame.draw.rect(self.screen, (255, 255, 255), rect)
                points = []
                if direction == Direction.NORTH:
                    points = [(rect.centerx, rect.top), (rect.left, rect.bottom), (rect.right, rect.bottom)]
                elif direction == Direction.SOUTH:
                    points = [(rect.centerx, rect.bottom), (rect.left, rect.top), (rect.right, rect.top)]
                elif direction == Direction.WEST:
                    points = [(rect.left, rect.centery), (rect.right, rect.top), (rect.right, rect.bottom)]
                elif direction == Direction.EAST:
                    points = [(rect.right, rect.centery), (rect.left, rect.top), (rect.left, rect.bottom)]
                pygame.draw.polygon(self.screen, (0, 0, 0), points)

    def handle_bookshelf_click(self):
        """Handle click on bookshelf - show reader images, open random book, and wait for webview to close."""
        self.loading = True
        self.loading_start_time = pygame.time.get_ticks()
        
        # Step 1: Display 'images/reader.jpg' for 2 seconds
        reader_img1 = pygame.image.load('images/reader.jpg')
        reader_img1 = pygame.transform.scale(reader_img1, self.screen_size)
        self.screen.blit(reader_img1, (0, 0))
        pygame.display.flip()
        pygame.time.wait(2000)  # Wait for 2 seconds

        # Step 2: Display 'images/reader2.jpg' for 2 seconds
        reader_img2 = pygame.image.load('images/reader2.jpg')
        reader_img2 = pygame.transform.scale(reader_img2, self.screen_size)
        self.screen.blit(reader_img2, (0, 0))
        pygame.display.flip()
        pygame.time.wait(2000)  # Wait for 2 seconds

        # Step 3: Open the random book in a webview window
        book = self.books_api.get_random_book()
        if book and book['preview_link']:
            webview_process = multiprocessing.Process(
                target=open_webview, args=(book['preview_link'], book['title'])
            )
            webview_process.start()
            webview_process.join()  # Wait until the process is complete

        # Step 5: Reset to the previous screen
        self.loading = False

    def run(self):
        """Main game loop."""
        running = True
        while running:
            current_location = self.locations.get(self.current_pos)
            
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.MOUSEBUTTONDOWN and not self.loading:
                    mouse_pos = pygame.mouse.get_pos()
                    
                    # Check navigation arrows
                    for direction, rect in self.arrows.items():
                        if rect.collidepoint(mouse_pos) and self.can_move(direction):
                            self.current_pos = self.get_new_position(direction)
                            break
                    
                    # Check location hotspots
                    if current_location:
                        for rect, action in current_location.hotspots.values():
                            if rect.collidepoint(mouse_pos):
                                action()
            
            # Draw current location
            if current_location and current_location.image and not self.loading:
                self.screen.blit(current_location.image, (0, 0))
                self.draw_arrows()
            
            # Draw loading message if needed
            if self.loading:
                self.screen.fill((0, 0, 0))
                loading_text = self.font.render('Opening book preview...', True, (255, 255, 255))
                text_rect = loading_text.get_rect(center=(self.screen_size[0] / 2, self.screen_size[1] / 2))
                self.screen.blit(loading_text, text_rect)
            
            pygame.display.flip()
        
        pygame.quit()
        sys.exit()

def bookfloor_action(game):
    """Plays a scream sound and rapidly alternates between two images for 1 second."""
    # Load the images
    img1 = pygame.image.load('images/1.jpg')
    img1 = pygame.transform.scale(img1, game.screen_size)
    img2 = pygame.image.load('images/2.jpg')
    img2 = pygame.transform.scale(img2, game.screen_size)

    # Load and play the scream audio
    pygame.mixer.Sound('./audio/scream.mp3').play()

    # Set the flicker duration and start time
    flicker_duration = 1000  # 1 second in milliseconds
    start_time = pygame.time.get_ticks()
    flicker_interval = 100  # Adjust interval for faster flicker (100 ms)

    # Flicker loop
    while pygame.time.get_ticks() - start_time < flicker_duration:
        elapsed_time = pygame.time.get_ticks() - start_time
        # Alternate between img1 and img2
        if (elapsed_time // flicker_interval) % 2 == 0:
            game.screen.blit(img1, (0, 0))
        else:
            game.screen.blit(img2, (0, 0))

        pygame.display.flip()
        pygame.time.delay(50)  # Short delay to control flicker speed



def main():
    game = Game(1200, 1200)
    
    def bookshelf_action():
        game.handle_bookshelf_click()
    
    # Create a location with a bookshelf hotspot
    library_location = Location(
        "images/scene1.jpg",
        [Direction.EAST, Direction.SOUTH],
        {
            "bookshelf1": (pygame.Rect(6, 236, 992, 350), bookshelf_action),
            "bookshelf2": (pygame.Rect(586, 472, 400, 500), bookshelf_action)
        }
    )
    
    location2 = Location(
        "images/scene2.jpg",
        [Direction.WEST, Direction.EAST, Direction.SOUTH],
        {
            "bookshelf3": (pygame.Rect(6, 670, 400, 400), bookshelf_action),
            "bookshelf4": (pygame.Rect(764, 670, 400, 400), bookshelf_action)

        }
    )
    
    location3 = Location(
        "images/scene3.jpg",
        [Direction.WEST],
        {}
    )
    
    location4 = Location(
        "images/scene4.jpg",
        [Direction.NORTH, Direction.EAST, Direction.SOUTH],
        {}
    )
    
    location5 = Location(
        "images/scene5.jpg",
        [Direction.NORTH, Direction.EAST, Direction.SOUTH, Direction.WEST],
        {}
    )
    
    location6 = Location(
        "images/scene6.jpg",
        [Direction.WEST, Direction.SOUTH],
        {

            "bookshelf5": (pygame.Rect(6, 6, 1000, 500), bookshelf_action),
            "bookshelf6": (pygame.Rect(764, 670, 400, 400), bookshelf_action),
            "door1": (pygame.Rect(522, 508, 400, 400), game.door6_action)


        
        }
    )
    
    location7 = Location(
        "images/scene7.jpg",
        [Direction.NORTH, Direction.EAST],
        {}
    )
    
    location8 = Location(
        "images/scene8.jpg",
        [Direction.NORTH, Direction.EAST, Direction.WEST],
        {


        }
    )
    
    location9 = Location(
        "images/scene9.jpg",
        [Direction.NORTH, Direction.WEST],
        {


             "bookshelf7": (pygame.Rect(50, 300, 500, 500), bookshelf_action),
            "bookshelf8": (pygame.Rect(764, 670, 400, 400), bookshelf_action),
           "bookfloor": (pygame.Rect(350, 850, 300, 300), lambda: bookfloor_action(game))



        }        
        
    )
    
    game.add_location((0, 0), library_location)
    game.add_location((1, 0), location2)
    game.add_location((2, 0), location3)
    game.add_location((0, 1), location4)
    game.add_location((1, 1), location5)
    game.add_location((2, 1), location6)
    game.add_location((0, 2), location7)
    game.add_location((1, 2), location8)
    game.add_location((2, 2), location9)
    
    game.run()

if __name__ == "__main__":
    main()