import sys
from pathlib import Path
sys.path.insert(0, r'C:/Users/Mukadam/Desktop/ChainPort1/ChainPort')
from app import create_app
from flask import current_app
import os

app = create_app()
with app.app_context():
    cand = []
    try:
        cand.append(os.path.join(current_app.root_path, 'static', 'images', 'logo.png'))
    except Exception:
        pass
    try:
        cand.append(os.path.join(current_app.static_folder, 'images', 'logo.png'))
    except Exception:
        pass
    cand.append(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'images', 'logo.png'))

    print('Candidate paths:')
    for p in cand:
        print(' -', p, 'exists=', os.path.exists(p))
        if os.path.exists(p):
            print('   size=', os.path.getsize(p))

    try:
        import PIL
        from PIL import Image
        print('Pillow version:', PIL.__version__)
    except Exception as e:
        print('Pillow not available:', e)

    # Try importing reportlab and creating small PDF
    try:
        from app.utils.pdf_report import create_trade_pdf
        # find a trade and tx
        from app.models import EscrowTransaction, Trade, db
        tx = (
            EscrowTransaction.query.filter(EscrowTransaction.trade_id.isnot(None))
            .order_by(EscrowTransaction.created_at.desc())
            .first()
        )
        if not tx:
            print('No tx found')
        else:
            trade = db.session.get(Trade, tx.trade_id)
            print('Using trade', trade.id, 'tx', tx.id)
            buf = create_trade_pdf(trade, tx)
            out = Path(current_app.static_folder) / 'tmp' / f'diag_trade_{trade.id}_tx_{tx.id}.pdf'
            out.parent.mkdir(parents=True, exist_ok=True)
            with open(out, 'wb') as f:
                f.write(buf.getbuffer())
            print('Wrote diagnostic PDF to', out)
    except Exception as e:
        import traceback
        traceback.print_exc()
        print('Exception during create_trade_pdf:', e)
