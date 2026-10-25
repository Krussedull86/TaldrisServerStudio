import sys
from .db import migrate
if sys.argv[1:] == ["migrate"]:
    migrate()
    print("RPVerse MapLink database migrated")
else:
    print("Usage: python -m backend migrate")
