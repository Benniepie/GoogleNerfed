import os
import argparse


class Settings:
    """
    Class representing the settings for the CTOD application.

    Args:
        args (argparse.Namespace, optional): Command-line arguments. If not provided, the arguments will be parsed from the command line.
    """

    def __init__(self, args=None):
        # We bypass argparse if we are running in fastapi mounted
        class DummyArgs:
            def __init__(self):
                self.tile_cache_path = None
                self.dataset_config_path = None
                self.logging_level = None
                self.db_name = None
                self.port = None
                self.dev = False
                self.unsafe = False
                self.no_dynamic = False
                self.cors_allow_origins = None
        args = DummyArgs()


        # Get values from command-line arguments or environment variables
        self.tile_cache_path = args.tile_cache_path or os.getenv(
            "CTOD_TILE_CACHE_PATH", None)
        self.dataset_config_path = args.dataset_config_path or os.getenv(
            "CTOD_DATASET_CONFIG_PATH", "./config/datasets.json")
        self.logging_level = args.logging_level or os.getenv(
            "CTOD_LOGGING_LEVEL", "info")
        self.db_name = args.db_name or os.getenv(
            "CTOD_DB_NAME", "factory_cache.db")
        self.cors_allow_origins = args.cors_allow_origins or os.getenv(
            "CTOD_CORS_ALLOW_ORIGINS", "http://localhost:5000")
        self.port = args.port or int(os.getenv("CTOD_PORT", 5000))

        # Handle boolean flags
        self.dev = args.dev if args.dev else os.getenv(
            "CTOD_DEV", "False").lower() in ("true", "1", "t")
        self.unsafe = args.unsafe if args.unsafe else os.getenv(
            "CTOD_UNSAFE", "False").lower() in ("true", "1", "t")
        self.no_dynamic = args.no_dynamic if args.no_dynamic else os.getenv(
            "CTOD_NO_DYNAMIC", "False").lower() in ("true", "1", "t")
        self.factory_cache_ttl = 15
