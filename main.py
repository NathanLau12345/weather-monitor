import pygame
import requests
from io import BytesIO
from PIL import Image, ImageSequence
import time
import os
from config import font_small, font_large, title, sounds_path, pictures_path

# Initialize Pygame
pygame.init()
pygame.mixer.init()

# Screen setup
WIDTH, HEIGHT = 1100, 580
screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
pygame.display.set_caption(title)
icon = pygame.image.load(pictures_path + "icon.png")
pygame.display.set_icon(icon)

WARNSUM_URL = "https://data.weather.gov.hk/weatherAPI/opendata/weather.php?dataType=warnsum&lang=tc"
clock = pygame.time.Clock()
FPS = 60

# Warning positions
base_coords = (80, 150)  # Adjusted starting y-coordinate to make room for multiple lines
space_hor = 160
space_vert = 120  # Vertical space between lines
max_icons_per_line = 6  # Maximum icons per line

warning_icons_file_name: dict = {
    "WHOT": "vhot",
    "WRAINA": "raina",
    "WRAINR": "rainr",
    "WRAINB": "rainb",
    "TC1": "tc1",
    "TC3": "tc3",
    "TC8NE": "tc8ne",
    "TC8SE": "tc8se",
    "TC8NW": "tc8nw",
    "TC8SW": "tc8sw",
    "TC9": "tc9",
    "TC10": "tc10",
    "WHOT": "vhot",
    "WTS": "ts",
    "WFNTSA": "ntfl",
    "WL": "landslip",
    "WCOLD": "cold",
    "WMSGNL": "msn",
    "WFROST": "frost",
    "WFIREY": "firey",
    "WFIRER": "firer",
    "WTMW": "tsunami-warn"
}

warning_codes_to_track = ["WHOT", "WRAINA", "WRAINR", "WRAINB", "TC1", "TC3", "TC8NE", "TC8SE", 
                         "TC8NW", "TC8SW", "TC9", "TC10", "WTS", "WFNTSA", "WL", "WCOLD", 
                         "WMSGNL", "WFROST", "WFIREY", "WFIRER", "WTMW"]

# Global variables for animation and tracking
frame_stage = 0  # 0 or 1 for the two frames
last_frame_change = 0  # Time of last frame change
initial_warnings = set()  # Track warnings present at startup
initial_run_complete = False  # Flag to mark when initial run is done

class AnimatedGIF:
    def __init__(self, warning_code):
        self.frames = []
        self.frame_durations = []
        self.current_frame = 0
        self.warning_code = warning_code
        self.load_local_frames()
        
    def load_local_frames(self):
        """Try to load local PNG files first"""
        image_name = warning_icons_file_name.get(self.warning_code, '')
        frame0_path = os.path.join(pictures_path, f"{image_name}1.png")
        frame1_path = os.path.join(pictures_path, f"{image_name}2.png")
        
        if os.path.exists(frame0_path) and os.path.exists(frame1_path):
            try:
                frame0 = pygame.image.load(frame0_path).convert_alpha()
                frame1 = pygame.image.load(frame1_path).convert_alpha()
                self.frames = [frame0, frame1]
                self.frame_durations = [500, 500]  # 0.5 seconds per frame
                print(f"Loaded local frames for {self.warning_code}")
                return True
            except Exception as e:
                print(f"Error loading local frames for {self.warning_code}: {e}")
        
        return False
    
    def load_remote_gif(self):
        """Fallback to loading GIF from HKO if local frames not found"""
        image_name = warning_icons_file_name.get(self.warning_code, '')
        image_url = f"https://www.hko.gov.hk/tc/wxinfo/dailywx/images/{image_name}.issuing.gif"
        
        try:
            response = requests.get(image_url, timeout=5)
            response.raise_for_status()
            gif = Image.open(BytesIO(response.content))
            
            for frame in ImageSequence.Iterator(gif):
                if frame.mode != 'RGBA':
                    frame = frame.convert("RGBA")
                
                duration = frame.info.get('duration', 100)
                pygame_frame = pygame.image.fromstring(frame.tobytes(), frame.size, "RGBA")
                self.frames.append(pygame_frame)
                self.frame_durations.append(duration)
                
            if not any(self.frame_durations):
                self.frame_durations = [100] * len(self.frames)
            
            print(f"Loaded remote GIF for {self.warning_code}")
        except Exception as e:
            print(f"Error loading GIF for {self.warning_code}: {e}")
            # Create blank frame as fallback
            blank = pygame.Surface((100, 100), pygame.SRCALPHA)
            self.frames = [blank]
            self.frame_durations = [100]
    
    def update(self, global_time):
        global frame_stage, last_frame_change
        
        # For local frames (2 frames with 1 second cooldown)
        if len(self.frames) == 2:
            current_time = time.time()
            if current_time - last_frame_change >= 1.0:  # 1 second cooldown
                frame_stage = 1 - frame_stage  # Toggle between 0 and 1
                last_frame_change = current_time
            self.current_frame = frame_stage
        else:
            # For GIFs from HKO (original behavior)
            total_duration = sum(self.frame_durations)
            if total_duration == 0:
                return
                
            cycle_pos = (global_time * 1000) % total_duration
            accumulated = 0
            for i, duration in enumerate(self.frame_durations):
                accumulated += duration
                if cycle_pos < accumulated:
                    self.current_frame = i
                    break
    
    def get_current_frame(self):
        return self.frames[self.current_frame]

class SoundPlayer:
    def __init__(self):
        self.current_sound = None
        self.sound_sequence = []
        self.sequence_start_time = 0
        self.playing = False
        
    def play_sequence(self, warning):
        """Prepare sound sequence for a specific warning"""
        warning = warning_icons_file_name.get(warning)
        
        try:
            mid = pygame.mixer.Sound(sounds_path + f"{warning}.mp3")
        except:
            try:
                print(fr"cannot found file: {sounds_path}{warning}.mp3, used place_holder.mp3")
                mid = pygame.mixer.Sound(sounds_path + "place_holder.mp3")
            except:
                print("Warning: Could not load sound files")
                return

        try:
            start = pygame.mixer.Sound(sounds_path + "start.mp3")
            end = pygame.mixer.Sound(sounds_path + "end.mp3")
            
            self.sound_sequence = [
                {"sound": start, "duration": start.get_length()},
                {"sound": mid, "duration": mid.get_length()},
                {"sound": end, "duration": end.get_length()}
            ]
            self.sequence_start_time = time.time()
            self.current_step = 0
            self.playing = True
            self.sound_sequence[0]["sound"].play()
            
        except Exception as e:
            print(f"Error preparing sound sequence: {e}")
    
    def update(self):
        """Update sound sequence playback"""
        if not self.playing or not self.sound_sequence:
            return
            
        current_time = time.time()
        elapsed = current_time - self.sequence_start_time
        total_duration = sum(step["duration"] for step in self.sound_sequence[:self.current_step+1])
        
        if elapsed > total_duration:
            self.current_step += 1
            if self.current_step < len(self.sound_sequence):
                self.sound_sequence[self.current_step]["sound"].play()
            else:
                self.playing = False

def get_active_warnings(api_data: dict) -> dict:
    global previous_warnings, sound_player, initial_warnings, initial_run_complete
    
    return_dict = {code: False for code in warning_codes_to_track}
    return_dict["no_active"] = True
    
    try:
        current_warnings = set()
        for warning in api_data.values():
            if warning['code'] in return_dict and warning['actionCode'] != "CANCEL" and warning['code'] != "CANCEL": # what should be considered as a active warning
                return_dict[warning['code']] = True
                return_dict['no_active'] = False
                current_warnings.add(warning['code'])
        
        # On first run, store the initial warnings
        if not initial_run_complete:
            initial_warnings = current_warnings.copy()
            initial_run_complete = True
            previous_warnings = current_warnings.copy()
            return return_dict
        
        # Check for new warnings (only those not in initial_warnings)
        new_warnings = current_warnings - previous_warnings - initial_warnings
        if new_warnings:
            for warning in new_warnings:
                sound_player.play_sequence(warning)
        
        previous_warnings = current_warnings
                
    except Exception as e:
        print(f"Error fetching warnings: {e}")
        
    return return_dict

def draw_warnings(global_time, api_data: dict):
    data = get_active_warnings(api_data)
    
    if data['no_active']:
        text = font_large.render("現時沒有生效的天氣警告", True, (0, 0, 0))
        screen.blit(text, (WIDTH//2 - text.get_width()//2, HEIGHT//2 - text.get_height()//2))
        return
    
    active_warnings = [w for w, active in data.items() if active and w != "no_active"]
    if not active_warnings:
        return
    
    # Calculate positions for multiple lines
    for line_num, line_start in enumerate(range(0, len(active_warnings), max_icons_per_line)):
        line_warnings = active_warnings[line_start:line_start + max_icons_per_line]
        y_pos = base_coords[1] + line_num * space_vert
        
        for i, warning in enumerate(line_warnings):
            if warning not in warning_gifs:
                warning_gifs[warning] = AnimatedGIF(warning)
                # If local frames not found, try to load remote GIF
                if not warning_gifs[warning].frames:
                    warning_gifs[warning].load_remote_gif()
            
            warning_gifs[warning].update(global_time)
            frame = warning_gifs[warning].get_current_frame()
            
            x_pos = base_coords[0] + i * space_hor
            frame = pygame.transform.scale(frame, (100, 100))
            screen.blit(frame, (x_pos, y_pos))
            
def get_warnsum_api_data() -> dict:
    data = requests.get(WARNSUM_URL, timeout=5)
    data.raise_for_status()
    data = data.json()
    return data

# Main game loop
warning_gifs = {}
previous_warnings = set()
sound_player = SoundPlayer()
running = True
start_time = time.time()
tick = 0

while running:
    clock.tick(FPS)
    current_time = time.time()
    global_time = current_time - start_time
    
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        if event.type == pygame.MOUSEBUTTONDOWN:
            print(pygame.mouse.get_pos())
    
    # Update sound player
    sound_player.update()
    
    screen.fill((255, 255, 255))
    data = get_warnsum_api_data()
    draw_warnings(global_time, api_data=data)
    
    # Display last update time
    update_time = font_small.render(f"最後更新: {time.strftime('%Y-%m-%d %H:%M:%S')}", True, (0, 0, 0))
    screen.blit(update_time, (WIDTH - update_time.get_width() - 20, HEIGHT - 30))
    
    pygame.display.flip()
    if tick >= 30:
        tick = 0
        data = get_warnsum_api_data()
    tick += 1

pygame.quit()