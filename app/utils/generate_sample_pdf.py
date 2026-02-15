from pathlib import Path
from app import create_app
from app.models import db, EscrowTransaction, Trade
from app.utils.pdf_report import create_trade_pdf

app = create_app()
app.app_context().push()

# Ensure tmp dir exists
out_dir = Path(app.static_folder) / 'tmp'
out_dir.mkdir(parents=True, exist_ok=True)

# Find latest escrow transaction with a trade_id
tx = (
    EscrowTransaction.query.filter(EscrowTransaction.trade_id.isnot(None))
    .order_by(EscrowTransaction.created_at.desc())
    .first()
)
if not tx:
    print('No escrow transaction with trade_id found.')
    raise SystemExit(1)

trade = db.session.get(Trade, tx.trade_id)
if not trade:
    print('Trade not found for tx:', tx.id)
    raise SystemExit(1)

buf = create_trade_pdf(trade, tx)
out_path = out_dir / f'trade_{trade.id}_tx_{tx.id}_report.pdf'
with open(out_path, 'wb') as f:
    f.write(buf.getbuffer())

print('Wrote sample PDF to', out_path)
