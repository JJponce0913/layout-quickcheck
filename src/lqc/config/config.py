import json
from pathlib import Path

DEFAULT_STYLE_WEIGHT = 10
DEFAULT_STYLE_VALUE_WEIGHT = 10
DEFAULT_WEBDRIVER_CONFIG = (
    Path(__file__).resolve().parents[3]
    / "config"
    / "artifact-configs"
    / "webdrivers.json"
)

def parse_config(config_path):
    with open(config_path, 'r') as f:
        config = json.loads(f.read())

    if DEFAULT_WEBDRIVER_CONFIG.is_file():
        with DEFAULT_WEBDRIVER_CONFIG.open(encoding="utf-8") as f:
            webdriver_paths = json.load(f)
        for variant in config.get("variants", []):
            if not variant.get("webdriver_path"):
                driver_path = webdriver_paths.get(variant.get("type"), "")
                if driver_path:
                    variant["webdriver_path"] = driver_path

    return config

def _weightToProbability(weight):
    return weight/100

def _bound(low, high, value):
    return max(low, min(high, value))

class Config:
    """ Singleton Class """
    __instance = None

    def __new__(cls, config=None):
        """ Singleton Constructor/Accessor 
        If constructed with config, replace the singleton instance
        If called without config, return the existing singleton instance
        """
        if config != None:
            cls.__instance = super(Config, cls).__new__(cls)
            # Class Initialization Code
            cls.__instance.style_weights = config.get("style-weights", {})
            cls.__instance.variants = config.get("variants", [])
            cls.__instance.rules = config.get("rules", [])
            paths = config.get("paths", {})
            cls.__instance.path_bug_reports_dir = paths.get("bug-reports-directory", "./bug_reports")
            cls.__instance.path_tmp_files_dir = paths.get("tmp-files-directory", "./tmp_generated_files")

        elif cls.__instance == None:
            raise RuntimeError("Config must be initialized before use")

        return cls.__instance
    
    def getStyleProbability(self, style_name):
        weight = self.style_weights.get(style_name, DEFAULT_STYLE_WEIGHT)
        weight = _bound(0, 100, weight)
        return _weightToProbability(weight)
    
    def getStyleValueWeights(self, style_name, value_type="", keyword=None):
        key_suffix = keyword if keyword != None else "<" + value_type + ">"
        style_and_type = style_name + ":" + key_suffix
        weight = self.style_weights.get(style_and_type, DEFAULT_STYLE_VALUE_WEIGHT)
        return _bound(0, 100000, weight)
    
    def getRules(self):
        return self.rules
    
    def getVariants(self):
        return self.variants

    def getBugReportDirectory(self):
        return self.path_bug_reports_dir

    def getTmpFilesDirectory(self):
        return self.path_tmp_files_dir
    
