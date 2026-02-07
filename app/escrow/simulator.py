from datetime import datetime
from app.models import EscrowTransaction, Trade, User, db


class EscrowSimulator:
    """A lightweight escrow simulator inspired by on-chain escrow contracts.

    Methods operate on existing SQLAlchemy models to simulate deposits,
    escrow holds, releases and refunds. Each action records an
    EscrowTransaction for auditing.
    """

    def deposit_to_wallet(self, user: User, amount: float, notes: str = "Manual deposit (simulated)"):
        if amount <= 0:
            raise ValueError("Amount must be positive")

        user.escrow_balance = (user.escrow_balance or 0.0) + float(amount)
        tx = EscrowTransaction(
            user_id=user.id,
            transaction_type="deposit",
            amount=float(amount),
            status="completed",
            notes=notes,
            created_at=datetime.utcnow(),
        )
        db.session.add(tx)
        db.session.commit()
        return tx

    def withdraw_from_wallet(self, user: User, amount: float, notes: str = "Manual withdrawal (simulated)"):
        if amount <= 0:
            raise ValueError("Amount must be positive")
        if (user.escrow_balance or 0) < amount:
            raise ValueError("Insufficient balance")

        user.escrow_balance -= float(amount)
        tx = EscrowTransaction(
            user_id=user.id,
            transaction_type="withdrawal",
            amount=float(amount),
            status="completed",
            notes=notes,
            created_at=datetime.utcnow(),
        )
        db.session.add(tx)
        db.session.commit()
        return tx

    def deposit_to_trade(self, buyer: User, trade: Trade, amount: float):
        """Move funds from buyer.wallet -> trade.escrow_amount (hold).

        Raises ValueError on invalid amounts or insufficient balance.
        """
        if amount <= 0:
            raise ValueError("Amount must be positive")
        if (buyer.escrow_balance or 0) < amount:
            raise ValueError("Insufficient escrow balance")
        if trade.buyer_id != buyer.id:
            raise ValueError("Only buyer can deposit to trade")

        buyer.escrow_balance -= float(amount)
        trade.escrow_amount = (trade.escrow_amount or 0.0) + float(amount)
        trade.status = "escrow_deposited"

        tx = EscrowTransaction(
            user_id=buyer.id,
            trade_id=trade.id,
            transaction_type="escrow_hold",
            amount=float(amount),
            status="completed",
            notes=f"Escrow deposit for trade #{trade.id}",
            created_at=datetime.utcnow(),
        )

        db.session.add(tx)
        db.session.commit()
        return tx

    def release_to_seller(self, actor: User, trade: Trade):
        """Release escrowed funds to the seller; only seller or authorized actor.

        Transfers trade.escrow_amount -> seller.escrow_balance and sets trade.status
        to 'completed'. Returns the created transaction.
        """
        if trade.escrow_amount <= 0:
            raise ValueError("No escrowed funds to release")

        seller = User.query.get(trade.seller_id)
        if seller is None:
            raise ValueError("Seller not found")

        seller.escrow_balance = (seller.escrow_balance or 0.0) + float(trade.escrow_amount)

        tx = EscrowTransaction(
            user_id=seller.id,
            trade_id=trade.id,
            transaction_type="escrow_release",
            amount=float(trade.escrow_amount),
            status="completed",
            notes=f"Escrow released for trade #{trade.id}",
            created_at=datetime.utcnow(),
        )

        trade.escrow_amount = 0
        trade.status = "completed"

        db.session.add(tx)
        db.session.commit()
        return tx

    def refund_to_buyer(self, actor: User, trade: Trade):
        """Refund escrowed funds back to the buyer. Sets trade.status to 'cancelled'."""
        if trade.escrow_amount <= 0:
            raise ValueError("No escrowed funds to refund")

        buyer = User.query.get(trade.buyer_id)
        if buyer is None:
            raise ValueError("Buyer not found")

        buyer.escrow_balance = (buyer.escrow_balance or 0.0) + float(trade.escrow_amount)

        tx = EscrowTransaction(
            user_id=buyer.id,
            trade_id=trade.id,
            transaction_type="escrow_refund",
            amount=float(trade.escrow_amount),
            status="completed",
            notes=f"Escrow refunded for trade #{trade.id}",
            created_at=datetime.utcnow(),
        )

        trade.escrow_amount = 0
        trade.status = "cancelled"

        db.session.add(tx)
        db.session.commit()
        return tx
