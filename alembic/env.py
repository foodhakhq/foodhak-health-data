from logging.config import fileConfig
import os
from dotenv import load_dotenv

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# Import only the health-related models
from models.base import Base
from models.device_connection import DeviceConnection
from models.user import FoodhakUser

# Load environment variables
load_dotenv()

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Override sqlalchemy.url with environment variable for health models database
config.set_main_option("sqlalchemy.url", os.getenv("DATABASE_URL", "postgresql://admin:admin123@localhost:9988/postgres"))

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = Base.metadata

# Import only the health-related models
from models.base import Base
from models.device_connection import DeviceConnection
from models.user import FoodhakUser 