import pygame
import sys
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any
import requests
import random
import string
import datetime
import os
import webbrowser
from dataclasses import dataclass

class GoogleBooksAPI:
    def __init__(self, api_key: Optional[str] = None):
        """Initialize with API key from parameter or environment variable."""
        self.api_key = api_key or os.getenv('GOOGLE_BOOKS_API_KEY')
        if not self.api_key:
            raise ValueError(
                "API key is required. Either pass it to GoogleBooksAPI() or "
                "set the GOOGLE_BOOKS_API_KEY environment variable."
            )
        
    def get_random_word(self) -> str:
        """Returns a random single letter or two-letter combination to use as a search term."""
        letters = string.ascii_lowercase
        if random.random() < 0.5:  # 50% chance for single letter
            return random.choice(letters)
        return random.choice(letters) + random.choice(letters)

    def get_random_year(self) -> int:
        """Returns a random year between 1800 and current year."""
        current_year = datetime.datetime.now().year
        return random.randint(1800, current_year)

    def get_random_book(self) -> Optional[Dict[str, Any]]:
        """Queries Google Books API with random parameters and returns a random book."""
        base_url = "https://www.googleapis.com/books/v1/volumes"
        
        # Generate random search parameters
        search_term = self.get_random_word()
        year = self.get_random_year()
        
        # Parameters for the API request
        params = {
            'q': f'{search_term}+year:{year}',
            'maxResults': 40,
            'langRestrict': 'en',
            'printType': 'books',
            'key': self.api_key
        }
        
        try:
            response = requests.get(base_url, params=params)
            response.raise_for_status()
            data = response.json()
            
            if data.get('totalItems', 0) > 0 and 'items' in data:
                # Keep trying until we find a book with a preview
                random.shuffle(data['items'])
                for book in data['items']:
                    info = book.get('volumeInfo', {})
                    if info.get('previewLink'):  # Only return books with preview links
                        return {
                            'title': info.get('title', 'Unknown Title'),
                            'preview_link': info.get('previewLink', '')
                        }
                return None
            return None
            
        except requests.RequestException as e:
            print(f"Error accessing Google Books API: {e}")
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

class Game:
    def __init__(self, screen_width: int = 800, screen_height: int = 600):
        pygame.init()
        self.screen_size = (screen_width, screen_height)
        self.screen = pygame.display.set_mode(self.screen_size)
        pygame.display.set_caption("Library Adventure")
        
        # Initialize Google Books API
        self.books_api = GoogleBooksAPI()
        
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
        self.current_pos = (0, 0)
        self.locations: Dict[Tuple[int, int], Location] = {}

    def add_location(self, grid_pos: Tuple[int, int], location: Location):
        """Add a new location to the game grid"""
        if 0 <= grid_pos[0] < 3 and 0 <= grid_pos[1] < 3:
            self.locations[grid_pos] = location
            location.load_image(self.screen_size)

    def can_move(self, direction: Direction) -> bool:
        """Check if movement in given direction is allowed"""
        current_location = self.locations.get(self.current_pos)
        if not current_location:
            return False
            
        if direction not in current_location.allowed_directions:
            return False
            
        new_pos = self.get_new_position(direction)
        return new_pos in self.locations

    def get_new_position(self, direction: Direction) -> Tuple[int, int]:
        """Calculate new position after moving in given direction"""
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
        """Draw navigation arrows for allowed directions"""
        for direction, rect in self.arrows.items():
            if self.can_move(direction):
                pygame.draw.rect(self.screen, (255, 255, 255), rect)
                # Draw arrow shape based on direction
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
        """Handle click on bookshelf - fetch and open random book in browser"""
        self.loading = True
        self.loading_start_time = pygame.time.get_ticks()
        
        book = self.books_api.get_random_book()
        if book and book['preview_link']:
            webbrowser.open(book['preview_link'])
            
        # Keep loading message visible briefly even if book loads quickly
        while pygame.time.get_ticks() - self.loading_start_time < 1000:
            self.screen.fill((0, 0, 0))
            loading_text = self.font.render('Opening book preview...', True, (255, 255, 255))
            text_rect = loading_text.get_rect(center=(self.screen_size[0]/2, self.screen_size[1]/2))
            self.screen.blit(loading_text, text_rect)
            pygame.display.flip()
            
        self.loading = False

    def run(self):
        """Main game loop"""
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
                text_rect = loading_text.get_rect(center=(self.screen_size[0]/2, self.screen_size[1]/2))
                self.screen.blit(loading_text, text_rect)
            
            pygame.display.flip()
        
        pygame.quit()
        sys.exit()

def main():
    game = Game(800, 600)
    
    # Define the bookshelf click action
    def bookshelf_action():
        game.handle_bookshelf_click()
    
    # Create a location with a bookshelf hotspot
    library_location = Location(
        "images/scene1.jpg",
        [Direction.EAST, Direction.SOUTH],  # Can move right and down from here
        {
            "bookshelf1": (pygame.Rect(6, 164, 250, 250), bookshelf_action),  # Clickable area for bookshelf
            "bookshelf2": (pygame.Rect(205, 193, 400, 250), bookshelf_action)  # Another clickable bookshelf area
        }
    )
    
    location2 = Location(
        "images/scene2.jpg",
        [Direction.WEST, Direction.EAST, Direction.SOUTH],  # Can move left, right, and down
        {
            "bookshelf": (pygame.Rect(350, 200, 100, 200), bookshelf_action)  # Clickable bookshelf area
        }
    )
    
    location3 = Location(
        "images/scene3.jpg",
        [Direction.WEST, Direction.SOUTH],  # Can move left and down
        {}  # No hotspots in this location
    )
    
    # Middle row (0,1), (1,1), (2,1)
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
        [Direction.NORTH, Direction.WEST, Direction.SOUTH],
        {}
    )
    
    # Bottom row (0,2), (1,2), (2,2)
    location7 = Location(
        "images/scene7.jpg",
        [Direction.NORTH, Direction.EAST],
        {}
    )
    
    location8 = Location(
        "images/scene8.jpg",
        [Direction.NORTH, Direction.EAST, Direction.WEST],
        {}
    )
    
    location9 = Location(
        "images/scene9.jpg",
        [Direction.NORTH, Direction.WEST],
        {}
    )
    
    # Add all locations to the game grid
    # First row (y=0)
    game.add_location((0, 0), library_location)
    game.add_location((1, 0), location2)
    game.add_location((2, 0), location3)
    
    # Second row (y=1)
    game.add_location((0, 1), location4)
    game.add_location((1, 1), location5)
    game.add_location((2, 1), location6)
    
    # Third row (y=2)
    game.add_location((0, 2), location7)
    game.add_location((1, 2), location8)
    game.add_location((2, 2), location9)
    
    game.run()

if __name__ == "__main__":
    main()