from datetime import datetime
import os

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    jsonify,
    session,
    current_app,
)

from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from app.models import User, Trade, Product, Message, EscrowTransaction, KYCDocument, db
from app.extensions import csrf

main_bp = Blueprint("main", __name__)


def allowed_file(filename, allowed_extensions):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed_extensions


# 👉 Landing Page
@main_bp.route("/")
def index():
    return render_template("index.html")


# 👉 Dashboard (protected)
@main_bp.route("/dashboard")
@login_required
def dashboard():
    user = current_user
    trades = (
        Trade.query.filter((Trade.buyer_id == user.id) | (Trade.seller_id == user.id))
        .limit(5)
        .all()
    )

    # Calculate stats
    active_trades = len(
        [
            t
            for t in trades
            if t.status in ["pending", "escrow_deposited", "in_progress"]
        ]
    )
    completed_trades = len([t for t in trades if t.status == "completed"])
    total_deals = len(trades)

    return render_template(
        "dashboard.html",
        user=user,
        trades=trades,
        active_trades=active_trades,
        completed_trades=completed_trades,
        total_deals=total_deals,
    )


@main_bp.route("/marketplace")
@login_required
def marketplace():
    page = request.args.get("page", 1, type=int)
    per_page = 12

    # Get filter parameters
    search = request.args.get("search", "")
    category = request.args.get("category", "")
    country = request.args.get("country", "")
    verified = request.args.get("verified", "")

    query = Product.query.filter_by(is_active=True)

    if search:
        query = query.filter(
            (Product.title.contains(search))
            | (Product.description.contains(search))
            | (Product.hs_code.contains(search))
        )

    if category:
        query = query.filter_by(category=category)

    if country:
        query = query.filter_by(country_of_origin=country)

    if verified:
        if verified.lower() == "true":
            query = query.join(User, Product.seller_id == User.id).filter(User.is_verified == True)
        elif verified.lower() == "false":
            query = query.join(User, Product.seller_id == User.id).filter(User.is_verified == False)

    products = query.paginate(page=page, per_page=per_page, error_out=False)

    # Get unique categories and countries for filters
    categories = (
        db.session.query(Product.category)
        .filter(Product.category.isnot(None))
        .distinct()
        .all()
    )
    categories = [cat[0] for cat in categories]

    countries = (
        db.session.query(Product.country_of_origin)
        .filter(Product.country_of_origin.isnot(None))
        .distinct()
        .all()
    )
    countries = [country[0] for country in countries]

    return render_template(
        "marketplace.html",
        products=products,
        categories=categories,
        countries=countries,
        search=search,
        selected_category=category,
        selected_country=country,
        selected_verified=verified,
    )


@main_bp.route("/product/<int:product_id>")
@login_required
def product_detail(product_id):
    product = Product.query.get_or_404(product_id)
    return render_template("product_detail.html", product=product)


@main_bp.route("/create-trade/<int:product_id>", methods=["GET", "POST"])
@login_required
def create_trade(product_id):
    product = Product.query.get_or_404(product_id)

    if product.seller_id == current_user.id:
        flash("You cannot trade with yourself.", "error")
        return redirect(url_for("main.marketplace"))

    if request.method == "POST":
        quantity = float(request.form.get("quantity", 0))
        notes = request.form.get("notes", "")

        if quantity <= 0:
            flash("Please enter a valid quantity.", "error")
            return render_template("create_trade.html", product=product)

        if quantity < (product.min_order_quantity or 0):
            flash(
                f"Minimum order quantity is {product.min_order_quantity} {product.unit}.",
                "error",
            )
            return render_template("create_trade.html", product=product)

        total_amount = quantity * product.price_per_unit

        trade = Trade(
            buyer_id=current_user.id,
            seller_id=product.seller_id,
            product_id=product.id,
            quantity=quantity,
            unit=product.unit,
            price_per_unit=product.price_per_unit,
            total_amount=total_amount,
            currency=product.currency,
            payment_terms=product.payment_terms,
            delivery_terms=product.delivery_terms,
            notes=notes,
        )

        db.session.add(trade)
        db.session.commit()

        flash("Trade request created successfully!", "success")
        return redirect(url_for("main.trade_detail", trade_id=trade.id))

    return render_template("create_trade.html", product=product)


@main_bp.route("/trade/<int:trade_id>")
@login_required
def trade_detail(trade_id):
    trade = Trade.query.get_or_404(trade_id)

    if trade.buyer_id != current_user.id and trade.seller_id != current_user.id:
        flash("You don't have permission to view this trade.", "error")
        return redirect(url_for("main.dashboard"))

    messages = (
        Message.query.filter_by(trade_id=trade_id).order_by(Message.timestamp).all()
    )

    return render_template("trade_detail.html", trade=trade, messages=messages)


@main_bp.route("/trades")
@login_required
def trades():
    user = current_user
    user_trades = Trade.query.filter(
        (Trade.buyer_id == user.id) | (Trade.seller_id == user.id)
    ).all()
    return render_template("trades.html", trades=user_trades)


@main_bp.route("/escrow")
@login_required
def escrow():
    user = current_user
    transactions = (
        EscrowTransaction.query.filter_by(user_id=user.id)
        .order_by(EscrowTransaction.created_at.desc())
        .limit(20)
        .all()
    )
    return render_template("escrow.html", user=user, transactions=transactions)


@main_bp.route("/escrow/deposit", methods=["POST"])
@login_required
def escrow_deposit():
    amount = float(request.form.get("amount", 0))

    if amount <= 0:
        flash("Please enter a valid amount.", "error")
        return redirect(url_for("main.escrow"))

    # In a real application, this would integrate with a payment gateway
    # For now, we'll simulate a deposit
    transaction = EscrowTransaction(
        user_id=current_user.id,
        transaction_type="deposit",
        amount=amount,
        status="completed",
        notes="Manual deposit (simulated)",
    )

    current_user.escrow_balance += amount

    db.session.add(transaction)
    db.session.commit()

    flash(f"Successfully deposited ₹{amount:.2f} to your escrow wallet.", "success")
    return redirect(url_for("main.escrow"))


@main_bp.route("/escrow/withdraw", methods=["POST"])
@login_required
def escrow_withdraw():
    amount = float(request.form.get("amount", 0))

    if amount <= 0:
        flash("Please enter a valid amount.", "error")
        return redirect(url_for("main.escrow"))

    if amount > current_user.escrow_balance:
        flash("Insufficient escrow balance.", "error")
        return redirect(url_for("main.escrow"))

    # In a real application, this would integrate with a payment gateway
    transaction = EscrowTransaction(
        user_id=current_user.id,
        transaction_type="withdrawal",
        amount=amount,
        status="completed",
        notes="Manual withdrawal (simulated)",
    )

    current_user.escrow_balance -= amount

    db.session.add(transaction)
    db.session.commit()

    flash(f"Successfully withdrew ₹{amount:.2f} from your escrow wallet.", "success")
    return redirect(url_for("main.escrow"))


@main_bp.route("/messages")
@login_required
def messages():
    # Get conversations (unique users with message history)
    sent_messages = (
        db.session.query(Message.receiver_id)
        .filter_by(sender_id=current_user.id)
        .distinct()
    )
    received_messages = (
        db.session.query(Message.sender_id)
        .filter_by(receiver_id=current_user.id)
        .distinct()
    )

    user_ids = set()
    for msg in sent_messages:
        user_ids.add(msg[0])
    for msg in received_messages:
        user_ids.add(msg[0])

    conversations = []
    for user_id in user_ids:
        other_user = User.query.get(user_id)
        if other_user:
            last_message = (
                Message.query.filter(
                    (
                        (Message.sender_id == current_user.id)
                        & (Message.receiver_id == user_id)
                    )
                    | (
                        (Message.sender_id == user_id)
                        & (Message.receiver_id == current_user.id)
                    )
                )
                .order_by(Message.timestamp.desc())
                .first()
            )

            conversations.append({"user": other_user, "last_message": last_message})

    conversations.sort(
        key=lambda x: (
            x["last_message"].timestamp if x["last_message"] else datetime.min
        ),
        reverse=True,
    )

    return render_template("messages.html", conversations=conversations)


@main_bp.route("/messages/<int:user_id>")
@login_required
def conversation(user_id):
    other_user = User.query.get_or_404(user_id)

    # Mark messages as read
    Message.query.filter_by(
        sender_id=user_id, receiver_id=current_user.id, is_read=False
    ).update({"is_read": True})
    db.session.commit()

    messages = (
        Message.query.filter(
            ((Message.sender_id == current_user.id) & (Message.receiver_id == user_id))
            | (
                (Message.sender_id == user_id)
                & (Message.receiver_id == current_user.id)
            )
        )
        .order_by(Message.timestamp)
        .all()
    )

    return render_template(
        "conversation.html", other_user=other_user, messages=messages
    )


@main_bp.route("/send-message", methods=["POST"])
@login_required
def send_message():
    receiver_id = int(request.form.get("receiver_id"))
    trade_id = request.form.get("trade_id")
    subject = request.form.get("subject", "")
    content = request.form.get("content", "").strip()

    if not content:
        flash("Message cannot be empty.", "error")
        return redirect(request.referrer or url_for("main.messages"))

    message = Message(
        sender_id=current_user.id,
        receiver_id=receiver_id,
        trade_id=int(trade_id) if trade_id else None,
        subject=subject,
        content=content,
    )

    db.session.add(message)
    db.session.commit()

    flash("Message sent successfully!", "success")
    return redirect(request.referrer or url_for("main.messages"))


@main_bp.route("/profile")
@login_required
def profile():
    user = current_user
    return render_template("profile.html", user=user)


@main_bp.route("/kyc", methods=["GET", "POST"])
@login_required
def kyc():
    if request.method == "POST":
        # Handle file uploads
        uploaded_files = request.files.getlist("documents")

        for file in uploaded_files:
            if file and allowed_file(
                file.filename, current_app.config["ALLOWED_EXTENSIONS"]
            ):
                filename = secure_filename(file.filename)
                # In a real app, you'd want to generate unique filenames
                file_path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
                file.save(file_path)

                kyc_doc = KYCDocument(
                    user_id=current_user.id,
                    document_type=request.form.get("document_type", "general"),
                    filename=filename,
                    original_filename=file.filename,
                    file_path=file_path,
                )

                db.session.add(kyc_doc)

        current_user.kyc_status = "submitted"
        db.session.commit()

        flash("KYC documents uploaded successfully!", "success")
        return redirect(url_for("main.kyc"))

    documents = KYCDocument.query.filter_by(user_id=current_user.id).all()
    return render_template("kyc.html", documents=documents)


@main_bp.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    if request.method == "POST":
        action = request.form.get("action")

        if action == "update_profile":
            current_user.first_name = request.form.get("first_name", "").strip()
            current_user.last_name = request.form.get("last_name", "").strip()
            current_user.company_name = request.form.get("company_name", "").strip()
            current_user.phone = request.form.get("phone", "").strip()

            db.session.commit()
            flash("Profile updated successfully!", "success")

        elif action == "change_password":
            current_password = request.form.get("current_password")
            new_password = request.form.get("new_password")
            confirm_password = request.form.get("confirm_password")

            if not current_user.check_password(current_password):
                flash("Current password is incorrect.", "error")
            elif new_password != confirm_password:
                flash("New passwords do not match.", "error")
            elif len(new_password) < 6:
                flash("Password must be at least 6 characters long.", "error")
            else:
                current_user.set_password(new_password)
                db.session.commit()
                flash("Password changed successfully!", "success")

        return redirect(url_for("main.settings"))

    return render_template("settings.html", user=current_user)


# API endpoints for AJAX requests
@main_bp.route("/api/trade/<int:trade_id>/status", methods=["POST"])
@login_required
@csrf.exempt
def update_trade_status(trade_id):
    trade = Trade.query.get_or_404(trade_id)

    if trade.buyer_id != current_user.id and trade.seller_id != current_user.id:
        return jsonify({"error": "Permission denied"}), 403

    new_status = request.json.get("status")

    if new_status not in [
        "pending",
        "escrow_deposited",
        "in_progress",
        "completed",
        "cancelled",
        "disputed",
    ]:
        return jsonify({"error": "Invalid status"}), 400

    trade.status = new_status
    db.session.commit()

    return jsonify({"success": True, "status": new_status})


@main_bp.route("/api/trade/<int:trade_id>/escrow", methods=["POST"])
@login_required
@csrf.exempt
def manage_escrow(trade_id):
    trade = Trade.query.get_or_404(trade_id)

    if trade.buyer_id != current_user.id and trade.seller_id != current_user.id:
        return jsonify({"error": "Permission denied"}), 403

    action = request.json.get("action")
    amount = request.json.get("amount", 0)

    if action == "deposit" and trade.buyer_id == current_user.id:
        if amount > current_user.escrow_balance:
            return jsonify({"error": "Insufficient escrow balance"}), 400

        current_user.escrow_balance -= amount
        trade.escrow_amount += amount

        transaction = EscrowTransaction(
            user_id=current_user.id,
            trade_id=trade.id,
            transaction_type="escrow_hold",
            amount=amount,
            notes="Escrow deposit for trade",
        )

        db.session.add(transaction)
        db.session.commit()

        return jsonify({"success": True, "escrow_amount": trade.escrow_amount})

    elif (
        action == "release"
        and trade.seller_id == current_user.id
        and trade.escrow_amount > 0
    ):
        seller = User.query.get(trade.seller_id)
        seller.escrow_balance += trade.escrow_amount

        transaction = EscrowTransaction(
            user_id=seller.id,
            trade_id=trade.id,
            transaction_type="escrow_release",
            amount=trade.escrow_amount,
            notes="Escrow release to seller",
        )

        db.session.add(transaction)
        trade.escrow_amount = 0
        trade.status = "completed"
        db.session.commit()

        return jsonify({"success": True, "escrow_amount": 0})

    return jsonify({"error": "Invalid action"}), 400
