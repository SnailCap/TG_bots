import os

# absolute dir path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", ".."))

# resource path folder
RESOURCE_FOLDER_PATH = os.path.join(ROOT_DIR, "resources")

# text folders paths
TEXT_FOLDER = os.path.join(RESOURCE_FOLDER_PATH, "text")
TEXT_PAGES_FOLDER = os.path.join(TEXT_FOLDER, "pages")
TEXT_STEPS_FOLDER = os.path.join(TEXT_FOLDER, "steps")
TEXT_NOTIFICATION_FOLDER = os.path.join(TEXT_FOLDER, "notifications")
TEXT_NOTIFICATIONS_FOLDER = os.path.join(TEXT_FOLDER, "notifications")

# config paths
CONFIG_FOLDER_PATH = os.path.join(RESOURCE_FOLDER_PATH, "config")
CONFIG_PAGES_FOLDER_PATH = os.path.join(CONFIG_FOLDER_PATH, "pages")
CONFIG_NOTIFICATIONS_FOLDER_PATH = os.path.join(CONFIG_FOLDER_PATH, "notifications")
CONFIG_STEPS_FOLDER_PATH = os.path.join(CONFIG_FOLDER_PATH, "steps")
CONFIG_BUTTONS_FOLDER_PATH = os.path.join(CONFIG_FOLDER_PATH, "buttons")
