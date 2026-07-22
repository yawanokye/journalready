from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests'))

from app.report_exporter import build_docx_report
from test_concise_report import sample_review

output = Path('/mnt/data/v142_concise_supervisor_report.docx')
output.write_bytes(build_docx_report(sample_review()))
print(output)
