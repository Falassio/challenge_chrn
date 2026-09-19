

from pathlib import Path
import sys
import uvicorn
from dotenv import load_dotenv

# aggiungo i percorsi di day1 e day2 al path
DAY2_SRC = Path(__file__).resolve().parents[1]
DAY1_SRC = DAY2_SRC.parents[1] / "day1" / "src"

for p in [str(DAY2_SRC), str(DAY1_SRC)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from chiron_service.config import get_service_settings
from chiron_service.api.app import create_app

load_dotenv()
settings = get_service_settings()
app = create_app()


def run():
    print("=" * 60)
    print("STARTING CHIRON AGENT SERVICE (FASTAPI)")
    print(f"URL     : http://{settings.host}:{settings.port}")
    print(f"Docs    : http://localhost:{settings.port}/docs")
    print(f"Database: {settings.database_url}")
    print("=" * 60)

    uvicorn.run(
        "chiron_service.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    run()
