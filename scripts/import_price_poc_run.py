import argparse
import subprocess
import sys
import time
from pathlib import Path

from sqlalchemy.exc import OperationalError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import settings  # noqa: E402
from app.services.pricing_service import PricingService  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Import saved Avito POC price run into backend tables.")
    parser.add_argument("run_dir", help="Path to saved POC run directory with run_report.json")
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    if not (run_dir / "run_report.json").exists():
        raise SystemExit(f"run_report.json not found in {run_dir}")

    result = None
    last_error: OperationalError | None = None
    for attempt in range(1, 4):
        engine = create_engine(settings.database_url, poolclass=NullPool)
        session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        try:
            with session_factory() as db:
                result = PricingService(db).import_poc_run(run_dir)
            break
        except OperationalError as exc:
            last_error = exc
            if attempt == 3:
                raise
            time.sleep(0.5)
        finally:
            engine.dispose()

    if result is None:
        raise SystemExit(f"Import failed: {last_error}")

    print(
        "\n".join(
            [
                f"run_id={result.run.external_run_id}",
                f"status={result.run.status.value}",
                f"observations_created={result.observations_created}",
                f"snapshots_saved={result.snapshots_saved}",
                f"parser_errors_created={result.parser_errors_created}",
            ]
        )
    )
    return 0


if __name__ == "__main__":
    if __package__ in {None, ""}:
        completed = subprocess.run(
            [
                sys.executable,
                "-c",
                f"import os, sys; os.chdir({str(PROJECT_ROOT)!r}); "
                "from scripts.import_price_poc_run import main; "
                "sys.argv = ['import_price_poc_run.py', *sys.argv[1:]]; "
                "raise SystemExit(main())",
                *sys.argv[1:],
            ],
            cwd=PROJECT_ROOT,
            check=False,
        )
        raise SystemExit(completed.returncode)
    raise SystemExit(main())
