import time
import board
import digitalio
import rotaryio
import neopixel

# --- Hardware Pinout from KiCad Schematic (XIAO ESP32-S3) ---
PIN_ENC_A = board.D0   # GPIO1 (ENC1_A)
PIN_SW    = board.D1   # GPIO2 (SW1)
PIN_ENC_B = board.D2   # GPIO3 (ENC1_B)
PIN_LED   = board.D3   # GPIO4 (LED1 -> 74AHCT1G125 -> D1..D16)

# --- Configuration ---
NUM_LEDS = 16          # D1 to D16 on PCB (increase if using a larger ring)
BYTES_PER_PIXEL = 3    # Set to 3 for RGB SK6812, or 4 for RGBW SK6812
TARGET_COLOR = (255, 255, 255)  # Full White (or (255, 255, 255, 255) for RGBW)

# --- Power Budget Constants (Under 3A Limit) ---
MAX_TOTAL_CURRENT_MA = 2800  # 2.8A hard ceiling (200mA safety margin under 3.0A)
MCU_OVERHEAD_MA      = 150   # XIAO ESP32-S3 + 74AHCT1G125 current draw
LED_IDLE_MA          = 1     # Quiescent current per SK6812
CHANNEL_MAX_MA       = 20    # Max current per color die (R, G, B, or W) at 255

def get_max_safe_brightness(num_leds, color):
    """Calculates the maximum brightness (0.0 to 1.0) to stay strictly under 3A."""
    available_led_ma = MAX_TOTAL_CURRENT_MA - MCU_OVERHEAD_MA - (num_leds * LED_IDLE_MA)
    if available_led_ma <= 0:
        return 0.0
    
    # Calculate current of 1 LED at 100% brightness for the chosen color
    led_full_ma = sum((c / 255.0) * CHANNEL_MAX_MA for c in color)
    total_full_ma = num_leds * led_full_ma
    
    if total_full_ma <= available_led_ma:
        return 1.0
    return available_led_ma / total_full_ma

MAX_BRIGHTNESS = get_max_safe_brightness(NUM_LEDS, TARGET_COLOR)
BRIGHTNESS_STEP = 0.05  # 5% per encoder click

# --- Initialize Peripherals ---
pixels = neopixel.NeoPixel(
    PIN_LED,
    NUM_LEDS,
    bpp=BYTES_PER_PIXEL,
    brightness=0.0,
    auto_write=False,
    pixel_order=neopixel.GRB if BYTES_PER_PIXEL == 3 else neopixel.GRBW
)

encoder = rotaryio.IncrementalEncoder(PIN_ENC_A, PIN_ENC_B)

button = digitalio.DigitalInOut(PIN_SW)
button.direction = digitalio.Direction.INPUT
button.pull = digitalio.Pull.UP

# --- State Variables ---
leds_on = False
current_brightness = min(0.5, MAX_BRIGHTNESS)  # Start at 50% (or max safe limit)
last_enc_pos = encoder.position
last_btn_state = button.value
last_debounce_time = 0

def update_leds():
    if leds_on:
        pixels.fill(TARGET_COLOR)
        pixels.brightness = min(current_brightness, MAX_BRIGHTNESS)
    else:
        pixels.brightness = 0.0
    pixels.show()

# Start with LEDs off
update_leds()

while True:
    now = time.monotonic()

    # 1. Handle Encoder Switch Click (Toggle ON/OFF with 30ms debounce)
    btn_state = button.value
    if btn_state != last_btn_state and (now - last_debounce_time) > 0.03:
        last_debounce_time = now
        last_btn_state = btn_state
        if not btn_state:  # Active LOW (pressed)
            leds_on = not leds_on
            update_leds()

    # 2. Handle Encoder Rotation (Dim / Brighten)
    enc_pos = encoder.position
    if enc_pos != last_enc_pos:
        delta = enc_pos - last_enc_pos
        last_enc_pos = enc_pos

        if leds_on:
            current_brightness += delta * BRIGHTNESS_STEP
            # Clamp between 2% minimum and the 3A-safe MAX_BRIGHTNESS ceiling
            current_brightness = max(0.02, min(MAX_BRIGHTNESS, current_brightness))
            update_leds()

    time.sleep(0.005)
