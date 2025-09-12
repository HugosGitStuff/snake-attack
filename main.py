import pygame
import json
import os
import sys
from enum import Enum
from typing import List, Tuple, Dict
import random

# Initialize Pygame
pygame.init()
pygame.mixer.init()

# Game States
class GameState(Enum):
    MENU = 1
    PLAYING = 2
    GAME_OVER = 3

class Button:
    def __init__(self, x: int, y: int, width: int, height: int, text: str, color: Tuple[int, int, int]):
        self.rect = pygame.Rect(x, y, width, height)
        self.text = text
        self.color = color
        self.hover_color = (
            min(color[0] + 30, 255),
            min(color[1] + 30, 255),
            min(color[2] + 30, 255)
        )
        self.is_hovered = False

    def draw(self, surface: pygame.Surface) -> None:
        color = self.hover_color if self.is_hovered else self.color
        # Draw button background
        pygame.draw.rect(surface, color, self.rect)
        # Draw border
        pygame.draw.rect(surface, (255, 255, 255), self.rect, 2)
        
        # Render text
        font = pygame.font.Font(None, 50)
        text_surface = font.render(self.text, True, (255, 255, 255))
        # Center text on button
        text_rect = text_surface.get_rect(center=self.rect.center)
        surface.blit(text_surface, text_rect)

    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.MOUSEMOTION:
            self.is_hovered = self.rect.collidepoint(event.pos)
            return False
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if self.is_hovered:
                return True
        return False

# Load configuration
with open('config.json', 'r') as f:
    CONFIG = json.load(f)

# Initialize window
WINDOW = pygame.display.set_mode((CONFIG['window']['width'], CONFIG['window']['height']))
pygame.display.set_caption(CONFIG['window']['title'])

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)

class Snake:
    def __init__(self, x: int, y: int, level_config: Dict):
        self.positions = [(x, y)]  # Head position
        self.direction = (0, 0)  # Start stationary
        self.length = CONFIG['snake']['initial_length']
        self.speed = CONFIG['snake']['initial_speed']
        self.move_timer = 0  # Add timer for movement control
        self.facing = (1, 0)  # Initially face right since we spawn on right side
        self.targets_collected = 0  # Track number of targets collected
        
        # Load images
        self.head_img = pygame.image.load(level_config['snake_head'])
        self.body_img = pygame.image.load(level_config['snake_body'])
        
        # Scale images
        target_size = (30, 30)
        self.head_img = pygame.transform.scale(self.head_img, target_size)
        self.body_img = pygame.transform.scale(self.body_img, target_size)
        
        # Initialize body
        for i in range(self.length - 1):
            self.positions.append((x - (i + 1) * 30, y))

    def move(self) -> None:
        x, y = self.positions[0]
        dx, dy = self.direction
        new_head = (x + dx * 30, y + dy * 30)
        self.positions.insert(0, new_head)
        if len(self.positions) > self.length:
            self.positions.pop()

    def grow(self) -> None:
        self.length += 1
        self.targets_collected += 1
        
        # Start increasing speed after collecting certain number of targets
        if (self.targets_collected > CONFIG['snake']['targets_before_speedup'] and 
            self.speed < CONFIG['snake']['max_speed']):
            self.speed = min(
                self.speed + CONFIG['snake']['speed_increase_amount'],
                CONFIG['snake']['max_speed']
            )

    def draw(self, surface: pygame.Surface) -> None:
        for i, pos in enumerate(self.positions):
            if i == 0:  # Head
                # Head should point in movement direction
                rotated_head = pygame.transform.rotate(self.head_img, self._get_rotation_angle(self.direction))
                surface.blit(rotated_head, pos)
            else:  # Body
                # Body follows movement direction
                rotated_body = pygame.transform.rotate(self.body_img, self._get_rotation_angle(self.direction))
                surface.blit(rotated_body, pos)

    def _get_rotation_angle(self, direction: Tuple[int, int], is_tail: bool = False) -> float:
        # Use facing direction for head when stationary
        dir_to_use = self.facing if direction == (0, 0) else direction
        
        # Both head and body segments use the same rotation logic to ensure red lines face each other
        if dir_to_use == (1, 0):  # Moving right
            return 0  # Red lines face left (towards previous segment)
        elif dir_to_use == (-1, 0):  # Moving left
            return 180  # Red lines face right (towards previous segment)
        elif dir_to_use == (0, -1):  # Moving up
            return 90  # When moving up, rotate 90° so red lines face right
        elif dir_to_use == (0, 1):  # Moving down
            return -90  # When moving down, rotate -90° so red lines face left
        
        return 180  # Default facing left

    def check_collision(self, walls: List[pygame.Rect]) -> bool:
        head = self.positions[0]
        head_rect = pygame.Rect(head[0], head[1], 30, 30)
        
        # Wall collision
        for wall in walls:
            if head_rect.colliderect(wall):
                return True
        
        # Self collision (excluding head)
        for pos in self.positions[1:]:
            if head == pos:
                return True
        
        return False

class Game:
    def __init__(self):
        print("Initializing game...")
        self.clock = pygame.time.Clock()
        self.state = GameState.MENU
        self.current_level = 1
        self.score = 0
        self.high_score = self._load_high_score()
        
        # Create start button
        button_width = 200
        button_height = 60
        button_x = CONFIG['window']['width'] // 2 - button_width // 2
        button_y = 250
        self.start_button = Button(
            button_x, button_y, 
            button_width, button_height,
            "Start", 
            (34, 177, 76)  # Nice green color
        )
        
        # Pre-render the title banner
        self.title_banner, self.title_pos = self._create_title_banner()
        
        print("Loading level configuration...")
        # Load level configuration
        self.level_config = next(
            level for level in CONFIG['levels'] 
            if level['id'] == self.current_level
        )
        
        # Load images
        print("Loading background image...")
        try:
            self.background = pygame.image.load(self.level_config['background']).convert()
            print("Scaling background image...")
            self.background = pygame.transform.scale(
                self.background, 
                (CONFIG['window']['width'], CONFIG['window']['height'])
            )
        except pygame.error as e:
            print(f"Error loading background: {e}")
            # Create a fallback background
            self.background = pygame.Surface((CONFIG['window']['width'], CONFIG['window']['height']))
            self.background.fill((200, 200, 200))  # Light gray background
        
        print("Loading target images...")
        self.target_images = []
        for img_path in self.level_config['targets']:
            try:
                # Load image and convert for transparency
                img = pygame.image.load(img_path).convert_alpha()
                
                # Create a pixel array to access image data
                px_array = pygame.PixelArray(img)
                
                # Get the color of the top-left pixel (the border we want to remove)
                border_color = img.unmap_rgb(px_array[0, 0])
                
                # Delete the pixel array to unlock the surface
                del px_array
                
                # Set that color as transparent
                img.set_colorkey(border_color)
                
                # Scale the image
                scaled_img = pygame.transform.scale(img, (30, 30))
                
                # Convert again to ensure transparency is properly handled
                scaled_img = scaled_img.convert_alpha()
                
                self.target_images.append(scaled_img)
                print(f"Loaded target image: {img_path}")
            except pygame.error as e:
                print(f"Error loading target image {img_path}: {e}")
                # Create a fallback target image
                img = pygame.Surface((30, 30), pygame.SRCALPHA)
                pygame.draw.circle(img, (255, 0, 0), (15, 15), 15)
                self.target_images.append(img)
        
        # Load sounds
        print("Loading sounds...")
        self.sounds = {}
        for name, path in self.level_config['sounds'].items():
            try:
                self.sounds[name] = pygame.mixer.Sound(path)
                print(f"Loaded sound: {name}")
            except pygame.error as e:
                print(f"Error loading sound {name}: {e}")
                # Create a silent sound as fallback
                self.sounds[name] = pygame.mixer.Sound(buffer=bytes([0] * 44100))
        
        # Create walls
        self.walls = [
            pygame.Rect(0, 0, CONFIG['window']['width'], 30),  # Top
            pygame.Rect(0, CONFIG['window']['height'] - 30, CONFIG['window']['width'], 30),  # Bottom
            pygame.Rect(0, 0, 30, CONFIG['window']['height']),  # Left
            pygame.Rect(CONFIG['window']['width'] - 30, 0, 30, CONFIG['window']['height'])  # Right
        ]
        
        # Pre-render the desert-themed walls
        self.wall_surface = pygame.Surface((CONFIG['window']['width'], CONFIG['window']['height']), pygame.SRCALPHA)
        sand_colors = [
            (210, 180, 140),  # Light sand
            (200, 170, 130),  # Medium sand
            (190, 160, 120),  # Dark sand
            (220, 190, 150),  # Very light sand
        ]
        block_size = 30  # Size of each sand block
        
        for wall in self.walls:
            # Draw multiple sand blocks along the wall
            for x in range(wall.x, wall.x + wall.width, block_size):
                for y in range(wall.y, wall.y + wall.height, block_size):
                    # Create a slightly randomized block size for natural look
                    block_w = min(block_size, wall.x + wall.width - x)
                    block_h = min(block_size, wall.y + wall.height - y)
                    
                    # Create sand block with random color variation
                    sand_block = pygame.Rect(x, y, block_w, block_h)
                    color = random.choice(sand_colors)
                    pygame.draw.rect(self.wall_surface, color, sand_block)
                    
                    # Add some texture/detail
                    if random.random() < 0.3:  # 30% chance for detail
                        detail_color = (min(color[0] + 20, 255), 
                                      min(color[1] + 20, 255),
                                      min(color[2] + 20, 255))
                        detail_size = random.randint(4, 8)
                        detail_x = x + random.randint(0, block_w - detail_size)
                        detail_y = y + random.randint(0, block_h - detail_size)
                        pygame.draw.circle(self.wall_surface, detail_color, 
                                         (detail_x + detail_size//2, 
                                          detail_y + detail_size//2), 
                                         detail_size//2)
        
        # Initialize game objects
        self.reset_game()

    def reset_game(self) -> None:
        # Start snake towards the right side of screen so it can move left
        self.snake = Snake(
            (CONFIG['window']['width'] * 3) // 4,  # Start at 3/4 of screen width
            CONFIG['window']['height'] // 2,       # Vertical center
            self.level_config
        )
        # Initialize multiple targets
        self.targets = []
        self._spawn_multiple_targets()
        self.score = 0
        
    def _spawn_multiple_targets(self) -> None:
        # Spawn 3 of each target type
        for target_type in [0, 1]:  # 0 for target-1, 1 for target-2
            for _ in range(3):
                self.targets.append({
                    'position': self._spawn_target(),
                    'type': target_type
                })

    def _spawn_target(self) -> Tuple[int, int]:
        while True:
            x = random.randrange(30, CONFIG['window']['width'] - 60, 30)
            y = random.randrange(30, CONFIG['window']['height'] - 60, 30)
            pos = (x, y)
            
            # Check if position is valid (not on snake or other targets)
            if pos not in self.snake.positions and not any(t['position'] == pos for t in self.targets):
                return pos

    def _load_high_score(self) -> int:
        try:
            with open('highscore.txt', 'r') as f:
                return int(f.read())
        except FileNotFoundError:
            return 0

    def _save_high_score(self) -> None:
        with open('highscore.txt', 'w') as f:
            f.write(str(self.high_score))

    def handle_input(self) -> bool:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            
            if event.type == pygame.KEYDOWN:
                if self.state == GameState.PLAYING:
                    new_direction = None
                    if event.key == pygame.K_UP and self.snake.direction != (0, 1):
                        new_direction = (0, -1)
                        self.snake.facing = (0, -1)
                    elif event.key == pygame.K_DOWN and self.snake.direction != (0, -1):
                        new_direction = (0, 1)
                        self.snake.facing = (0, 1)
                    elif event.key == pygame.K_LEFT and self.snake.direction != (1, 0):
                        new_direction = (-1, 0)
                        self.snake.facing = (-1, 0)
                    elif event.key == pygame.K_RIGHT and self.snake.direction != (-1, 0):
                        new_direction = (1, 0)
                        self.snake.facing = (1, 0)
                        
                    if new_direction:
                        self.snake.direction = new_direction
                        self.sounds['direction_change'].play()
                
                elif event.key == pygame.K_SPACE and self.state == GameState.GAME_OVER:
                    self.reset_game()
                    self.state = GameState.MENU
            
            # Handle button clicks
            if self.state == GameState.MENU and self.start_button.handle_event(event):
                self.state = GameState.PLAYING
                self.sounds['background'].play(-1)  # Loop background music
        
        return True

    def update(self) -> None:
        if self.state == GameState.PLAYING:
            # Only move if snake has a direction
            if self.snake.direction != (0, 0):
                # Control snake speed
                self.snake.move_timer += 1
                if self.snake.move_timer >= (60 // self.snake.speed):  # Adjust speed based on FPS
                    self.snake.move()
                    self.snake.move_timer = 0
            
            # Check collisions
            if self.snake.check_collision(self.walls):
                self.state = GameState.GAME_OVER
                self.sounds['background'].stop()
                self.sounds['game_over'].play()
                if self.score > self.high_score:
                    self.high_score = self.score
                    self._save_high_score()
                return
            
            # Check target collection
            head = self.snake.positions[0]
            head_rect = pygame.Rect(head[0], head[1], 30, 30)
            
            # Check collision with each target
            collected_targets = []
            for i, target in enumerate(self.targets):
                target_rect = pygame.Rect(target['position'][0], target['position'][1], 30, 30)
                if head_rect.colliderect(target_rect):
                    collected_targets.append(i)
                    self.snake.grow()
                    self.score += (
                        CONFIG['scoring']['target_1_points'] 
                        if target['type'] == 0 
                        else CONFIG['scoring']['target_2_points']
                    )
                    self.sounds['target_collect'].play()
            
            # Remove collected targets and spawn new ones
            for i in reversed(collected_targets):
                target_type = self.targets[i]['type']
                self.targets.pop(i)
                self.targets.append({
                    'position': self._spawn_target(),
                    'type': target_type
                })

    def draw(self) -> None:
        WINDOW.blit(self.background, (0, 0))
        
        # Draw the pre-rendered walls
        WINDOW.blit(self.wall_surface, (0, 0))
        
        if self.state == GameState.MENU:
            self._draw_menu()
        elif self.state == GameState.PLAYING:
            self._draw_game()
        else:  # GAME_OVER
            self._draw_game_over()
        
        pygame.display.flip()

    def _create_title_banner(self) -> Tuple[pygame.Surface, Tuple[int, int]]:
        # Title setup
        title_font = pygame.font.Font(None, 74)
        title = title_font.render('Snake Attack!!!', True, WHITE)
        
        # Banner dimensions
        banner_padding = 40
        banner_width = title.get_width() + banner_padding * 2
        banner_height = title.get_height() + banner_padding
        banner_x = CONFIG['window']['width'] // 2 - banner_width // 2
        banner_y = 120
        
        # Create banner surface with alpha
        banner = pygame.Surface((banner_width, banner_height), pygame.SRCALPHA)
        
        # Desert theme colors
        sand_dark = (190, 160, 120)  # Dark sand color
        sand_light = (210, 180, 140)  # Light sand color
        
        # Draw rounded rectangle for banner
        pygame.draw.rect(banner, sand_dark, (0, 0, banner_width, banner_height), 
                        border_radius=20)  # Main banner
        
        # Add a subtle inner rectangle for depth
        pygame.draw.rect(banner, sand_light, 
                        (5, 5, banner_width-10, banner_height-10), 
                        border_radius=18)  # Inner highlight
        
        # Add static texture/detail to the banner
        random.seed(42)  # Use fixed seed for consistent pattern
        for _ in range(20):
            x = random.randint(20, banner_width-20)
            y = random.randint(20, banner_height-20)
            size = random.randint(4, 8)
            color = random.choice([sand_dark, sand_light])
            pygame.draw.circle(banner, color, (x, y), size)
        random.seed()  # Reset random seed
        
        # Add title to the banner
        banner.blit(
            title,
            (banner_padding, banner_padding // 2)
        )
        
        return banner, (banner_x, banner_y)

    def _draw_menu(self) -> None:
        # Draw the pre-rendered banner
        WINDOW.blit(self.title_banner, self.title_pos)
        
        # Instructions with smaller font
        inst_font = pygame.font.Font(None, 36)
        instructions = [
            "How to Play:",
            "• Use Arrow Keys to control the snake's direction",
            "• Collect targets to grow and score points",
            "• Avoid hitting walls and yourself",
            "• Press any Arrow Key to start moving"
        ]
        
        # Draw start button
        self.start_button.draw(WINDOW)
        
        # Draw instructions
        y_pos = 350
        for line in instructions:
            instruction = inst_font.render(line, True, WHITE)
            WINDOW.blit(
                instruction,
                (CONFIG['window']['width'] // 2 - instruction.get_width() // 2, y_pos)
            )
            y_pos += 40

    def _draw_game(self) -> None:
        # Draw all targets
        for target in self.targets:
            WINDOW.blit(
                self.target_images[target['type']], 
                target['position']
            )
        
        # Draw snake
        self.snake.draw(WINDOW)
        
        # Draw score
        font = pygame.font.Font(None, 36)
        score_text = font.render(f'Score: {self.score}', True, WHITE)
        WINDOW.blit(score_text, (10, 10))

    def _draw_game_over(self) -> None:
        font = pygame.font.Font(None, 74)
        game_over = font.render('Game Over', True, WHITE)
        score = font.render(f'Score: {self.score}', True, WHITE)
        high_score = font.render(f'High Score: {self.high_score}', True, WHITE)
        restart = font.render('Press SPACE to Restart', True, WHITE)
        
        y = 150
        for text in [game_over, score, high_score, restart]:
            WINDOW.blit(
                text,
                (CONFIG['window']['width'] // 2 - text.get_width() // 2, y)
            )
            y += 100

    def run(self) -> None:
        running = True
        while running:
            running = self.handle_input()
            self.update()
            self.draw()
            self.clock.tick(CONFIG['window']['fps'])

if __name__ == '__main__':
    game = Game()
    game.run()
    pygame.quit()
    sys.exit()
