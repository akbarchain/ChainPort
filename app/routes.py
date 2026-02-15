from datetime import datetime
import time
import os
import base64
import uuid
import io

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
    abort,
    send_file,
)

from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from app.models import (
    User,
    Trade,
    Product,
    Message,
    MessageAttachment,
    EscrowTransaction,
    KYCDocument,
    db,
)
from app.extensions import csrf
from app.escrow.simulator import EscrowSimulator
from app.utils.pdf_report import create_trade_pdf

# Optional PyNaCl import for ed25519 verification; wallet endpoints degrade if unavailable
try:
    import nacl.signing
    _HAS_PYNACL = True
except Exception:
    nacl = None
    _HAS_PYNACL = False

main_bp = Blueprint("main", __name__)

_MESSAGE_RATE_LIMIT = {}
_MESSAGE_RATE_WINDOW = 60
_MESSAGE_RATE_MAX = 12


def get_or_404(model, obj_id):
    obj = db.session.get(model, obj_id)
    if obj is None:
        abort(404)
    return obj


def build_conversations(user_id):
    messages = (
        Message.query.filter(
            (Message.sender_id == user_id) | (Message.receiver_id == user_id)
        )
        .order_by(Message.timestamp.desc())
        .all()
    )

    latest_by_user = {}
    for msg in messages:
        other_id = msg.receiver_id if msg.sender_id == user_id else msg.sender_id
        if other_id not in latest_by_user:
            latest_by_user[other_id] = msg

    conversations = []
    for other_id, last_message in latest_by_user.items():
        other_user = db.session.get(User, other_id)
        if other_user:
            conversations.append({"user": other_user, "last_message": last_message})

    return conversations


def get_preferred_chat_user_id(user_id):
    last_tx = (
        EscrowTransaction.query.filter(
            EscrowTransaction.user_id == user_id,
            EscrowTransaction.trade_id.isnot(None),
        )
        .order_by(EscrowTransaction.created_at.desc())
        .first()
    )
    if not last_tx:
        return None
    trade = db.session.get(Trade, last_tx.trade_id)
    if not trade:
        return None
    if trade.buyer_id == user_id:
        return trade.seller_id
    if trade.seller_id == user_id:
        return trade.buyer_id
    return None


def allowed_file(filename, allowed_extensions):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed_extensions


@main_bp.route('/product/<int:product_id>/upload-image', methods=['POST'])
@login_required
def upload_product_image(product_id):
    product = get_or_404(Product, product_id)

    # only seller may upload product image
    if product.seller_id != current_user.id:
        flash('Permission denied: only the seller can upload product images.', 'error')
        return redirect(url_for('main.product_detail', product_id=product.id))

    if 'image' not in request.files:
        flash('No file part in request.', 'error')
        return redirect(url_for('main.product_detail', product_id=product.id))

    file = request.files['image']
    if file.filename == '':
        flash('No file selected.', 'error')
        return redirect(url_for('main.product_detail', product_id=product.id))

    ALLOWED = {'png', 'jpg', 'jpeg', 'webp', 'svg'}
    MAX_BYTES = 2 * 1024 * 1024  # 2 MB
    if file and allowed_file(file.filename, ALLOWED):
        filename = secure_filename(file.filename)
        ext = filename.rsplit('.', 1)[1].lower()

        uploads_dir = os.path.join(current_app.static_folder, 'uploads', 'products')
        os.makedirs(uploads_dir, exist_ok=True)

        dest_name = f"{product.id}.{ext}"
        dest_path = os.path.join(uploads_dir, dest_name)

        # Read file into memory first to enforce size limits
        from io import BytesIO
        data = file.read()
        if len(data) > MAX_BYTES:
            flash('Image too large. Maximum size is 2 MB.', 'error')
            return redirect(url_for('main.product_detail', product_id=product.id))

        # Remove existing images for this product with other extensions
        for cand_ext in ALLOWED:
            cand = os.path.join(uploads_dir, f"{product.id}.{cand_ext}")
            try:
                if os.path.exists(cand) and os.path.abspath(cand) != os.path.abspath(dest_path):
                    os.remove(cand)
            except Exception:
                pass

        # Save uploaded bytes
        try:
            with open(dest_path, 'wb') as f:
                f.write(data)

            # Create a standard JPG thumbnail (preserve aspect) if Pillow available
            try:
                from PIL import Image
                img_buf = BytesIO(data)
                with Image.open(img_buf) as im:
                    im = im.convert('RGB')
                    im.thumbnail((800, 800))
                    thumb_path = os.path.join(uploads_dir, f"{product.id}_thumb.jpg")
                    im.save(thumb_path, format='JPEG', quality=85)
            except Exception:
                thumb_path = None

            flash('Product image uploaded successfully.', 'success')
        except Exception as e:
            flash(f'Failed to save image: {e}', 'error')

    else:
        flash('Invalid file type. Allowed: png, jpg, jpeg, webp, svg', 'error')

    return redirect(url_for('main.product_detail', product_id=product.id))


def product_image_url(product):
    title = (getattr(product, "title", "") or "").lower()
    category = (getattr(product, "category", "") or "").lower()

    filename_map = {
        "plywood": "plywood.jpg",
        "adhesive": "adhesive.jpg",
        "fabric": "fabric.jpg",
        "fiber glass": "fiberglass.jpg",
        "fiberglass": "fiberglass.jpg",
        "epoxy resin": "epoxy.jpg",
        "polyurethane foam": "foam.jpg",
        "acrylic": "paint.jpg",
        "floor coating": "coating.jpg",
        "solvent": "solvent.jpg",
        "pipe": "pipes.jpg",
        "rice": "agriculture.jpg",
        "spice": "agriculture.jpg",
        "cashew": "agriculture.jpg",
        "cotton": "textiles.jpg",
        "silk": "textiles.jpg",
        "yarn": "textiles.jpg",
    }

    filename = None
    for key, mapped_name in filename_map.items():
        if key in title:
            filename = mapped_name
            break

    if not filename:
        if "textile" in category:
            filename = "textiles.jpg"
        elif "chemical" in category:
            filename = "solvent.jpg"
        elif "agri" in category:
            filename = "agriculture.jpg"
        else:
            filename = "default.jpg"

    return url_for("static", filename=f"images/products/{filename}")


def _serialize_message(msg):
    return {
        "id": msg.id,
        "sender_id": msg.sender_id,
        "receiver_id": msg.receiver_id,
        "subject": msg.subject,
        "content": msg.content,
        "timestamp": msg.timestamp.isoformat() if msg.timestamp else None,
        "is_read": msg.is_read,
        "attachments": [
            {
                "id": att.id,
                "name": att.original_filename,
                "url": url_for("main.message_attachment", attachment_id=att.id),
            }
            for att in (msg.attachments or [])
        ],
    }


# Landing Page
@main_bp.route("/")
def index():
    return render_template("index.html")


# Dashboard (protected)
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
    # product.image_url is provided by the Product model; no assignment needed

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
    product = get_or_404(Product, product_id)
    return render_template("product_detail.html", product=product)


@main_bp.route("/create-trade/<int:product_id>", methods=["GET", "POST"])
@login_required
def create_trade(product_id):
    product = get_or_404(Product, product_id)

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
    trade = get_or_404(Trade, trade_id)

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
    # In a real application, this would integrate with a payment gateway.
    # Use simulator to perform and record the deposit.
    sim = EscrowSimulator()
    try:
        sim.deposit_to_wallet(current_user, amount)
        flash(f"Successfully deposited INR {amount:.2f} to your escrow wallet.", "success")
    except Exception as e:
        flash(str(e), "error")

    return redirect(url_for("main.escrow"))


@main_bp.route("/escrow/withdraw", methods=["POST"])
@login_required
def escrow_withdraw():
    amount = float(request.form.get("amount", 0))

    if amount <= 0:
        flash("Please enter a valid amount.", "error")
        return redirect(url_for("main.escrow"))
    sim = EscrowSimulator()
    try:
        sim.withdraw_from_wallet(current_user, amount)
        flash(f"Successfully withdrew INR {amount:.2f} from your escrow wallet.", "success")
    except Exception as e:
        flash(str(e), "error")

    return redirect(url_for("main.escrow"))


@main_bp.route("/messages")
@login_required
def messages():
    conversations = build_conversations(current_user.id)
    preferred_user_id = get_preferred_chat_user_id(current_user.id)
    selected_user_id = request.args.get("user_id", type=int)
    selected_user = None
    thread_messages = []

    if selected_user_id:
        selected_user = db.session.get(User, selected_user_id)
        if selected_user:
            Message.query.filter_by(
                sender_id=selected_user.id,
                receiver_id=current_user.id,
                is_read=False,
            ).update({"is_read": True})
            db.session.commit()

            thread_messages = (
                Message.query.filter(
                    ((Message.sender_id == current_user.id) & (Message.receiver_id == selected_user.id))
                    | ((Message.sender_id == selected_user.id) & (Message.receiver_id == current_user.id))
                )
                .order_by(Message.timestamp.desc())
                .limit(200)
                .all()
            )
            thread_messages = list(reversed(thread_messages))

    return render_template(
        "messages.html",
        conversations=conversations,
        preferred_user_id=preferred_user_id,
        selected_user=selected_user,
        messages=thread_messages,
    )


@main_bp.route("/messages/start", methods=["POST"])
@login_required
def start_message():
    user_id = request.form.get("user_id", type=int)
    user = db.session.get(User, user_id) if user_id else None

    if user is None:
        email = request.form.get("email", "").strip().lower()
        if not email:
            flash("Enter a valid email to start a chat.", "error")
            return redirect(url_for("main.messages"))
        user = User.query.filter_by(email=email).first()

    if not user:
        flash("No user found for that chat request.", "error")
        return redirect(url_for("main.messages"))

    if user.id == current_user.id:
        flash("You cannot start a chat with yourself.", "error")
        return redirect(url_for("main.messages"))

    return redirect(url_for("main.messages", user_id=user.id))


@main_bp.route("/messages/<int:user_id>")
@login_required
def conversation(user_id):
    return redirect(url_for("main.messages", user_id=user_id))


@main_bp.route("/send-message", methods=["POST"])
@login_required
def send_message():
    now = time.time()
    key = f"user:{current_user.id}"
    timestamps = _MESSAGE_RATE_LIMIT.get(key, [])
    timestamps = [ts for ts in timestamps if now - ts < _MESSAGE_RATE_WINDOW]
    if len(timestamps) >= _MESSAGE_RATE_MAX:
        flash("You are sending messages too quickly. Please wait and try again.", "error")
        return redirect(request.referrer or url_for("main.messages"))
    timestamps.append(now)
    _MESSAGE_RATE_LIMIT[key] = timestamps

    receiver_raw = (request.form.get("receiver_id") or "").strip()
    if not receiver_raw:
        flash("Select a conversation before sending a message.", "error")
        return redirect(url_for("main.messages"))

    try:
        receiver_id = int(receiver_raw)
    except ValueError:
        flash("Invalid message recipient.", "error")
        return redirect(url_for("main.messages"))

    if receiver_id == current_user.id:
        flash("You cannot message yourself.", "error")
        return redirect(url_for("main.messages"))

    receiver = db.session.get(User, receiver_id)
    if not receiver:
        flash("Message recipient not found.", "error")
        return redirect(url_for("main.messages"))

    trade_id_raw = (request.form.get("trade_id") or "").strip()
    trade_id = None
    if trade_id_raw:
        try:
            trade_id = int(trade_id_raw)
        except ValueError:
            flash("Invalid trade reference.", "error")
            return redirect(url_for("main.messages", user_id=receiver.id))
    subject = request.form.get("subject", "").strip()
    if len(subject) > 200:
        flash("Subject is too long (max 200 characters).", "error")
        return redirect(url_for("main.messages", user_id=receiver.id))
    content = request.form.get("content", "").strip()
    uploaded_files = request.files.getlist("attachments")

    files = [f for f in uploaded_files if f and f.filename]
    if len(files) > current_app.config["MESSAGE_ATTACHMENT_LIMIT"]:
        flash("Too many attachments. Please limit your upload.", "error")
        return redirect(request.referrer or url_for("main.messages"))

    valid_files = [
        f
        for f in files
        if allowed_file(f.filename, current_app.config["ALLOWED_EXTENSIONS"])
    ]

    if files and not valid_files:
        flash("All selected attachments are invalid file types.", "error")
        return redirect(request.referrer or url_for("main.messages"))

    if not content and not valid_files:
        flash("Message cannot be empty.", "error")
        return redirect(request.referrer or url_for("main.messages"))

    message = Message(
        sender_id=current_user.id,
        receiver_id=receiver.id,
        trade_id=trade_id,
        subject=subject,
        content=content,
    )

    db.session.add(message)
    db.session.commit()

    if valid_files:
        for file in valid_files:
            original_filename = file.filename
            safe_name = secure_filename(original_filename)
            base_name, ext = os.path.splitext(safe_name)
            if not base_name:
                base_name = "attachment"
            unique_name = f"{base_name}-{uuid.uuid4().hex}{ext.lower()}"
            file_path = os.path.join(current_app.config["MESSAGE_UPLOAD_FOLDER"], unique_name)
            file.save(file_path)
            attachment = MessageAttachment(
                message_id=message.id,
                filename=unique_name,
                original_filename=original_filename,
                file_path=file_path,
                content_type=file.mimetype,
                file_size=os.path.getsize(file_path),
            )
            db.session.add(attachment)
        db.session.commit()

    flash("Message sent successfully!", "success")
    return redirect(url_for("main.messages", user_id=receiver.id))


@main_bp.route("/messages/attachment/<int:attachment_id>")
@login_required
def message_attachment(attachment_id):
    attachment = db.session.get(MessageAttachment, attachment_id)
    if not attachment:
        abort(404)
    if (
        attachment.message.sender_id != current_user.id
        and attachment.message.receiver_id != current_user.id
    ):
        abort(403)
    if not os.path.exists(attachment.file_path):
        abort(404)
    return send_file(
        attachment.file_path,
        as_attachment=True,
        download_name=attachment.original_filename,
    )


@main_bp.route("/api/messages/thread/<int:user_id>")
@login_required
def api_thread(user_id):
    other_user = db.session.get(User, user_id)
    if not other_user:
        return jsonify({"error": "User not found"}), 404

    since_id = request.args.get("since_id", type=int)
    query = Message.query.filter(
        ((Message.sender_id == current_user.id) & (Message.receiver_id == user_id))
        | ((Message.sender_id == user_id) & (Message.receiver_id == current_user.id))
    ).order_by(Message.timestamp)

    limit = request.args.get("limit", type=int) or 200
    limit = max(1, min(limit, 500))

    if since_id:
        query = query.filter(Message.id > since_id)

    messages = query.limit(limit).all()
    return jsonify({"messages": [_serialize_message(m) for m in messages]})


@main_bp.route("/api/messages/escrow-suggestions")
@login_required
def api_escrow_suggestions():
    trade_ids = set(
        row[0]
        for row in db.session.query(EscrowTransaction.trade_id)
        .filter(EscrowTransaction.user_id == current_user.id)
        .filter(EscrowTransaction.trade_id.isnot(None))
        .distinct()
        .all()
        if row[0] is not None
    )

    # Also include all trades where the user is buyer or seller.
    trade_ids.update(
        row[0]
        for row in db.session.query(Trade.id)
        .filter((Trade.buyer_id == current_user.id) | (Trade.seller_id == current_user.id))
        .all()
    )

    if not trade_ids:
        return jsonify({"users": []})

    trades = Trade.query.filter(Trade.id.in_(list(trade_ids))).all()
    user_ids = set()
    for trade in trades:
        if trade.buyer_id == current_user.id and trade.seller_id:
            user_ids.add(trade.seller_id)
        elif trade.seller_id == current_user.id and trade.buyer_id:
            user_ids.add(trade.buyer_id)

    users = []
    for uid in user_ids:
        u = db.session.get(User, uid)
        if u:
            users.append(
                {
                    "id": u.id,
                    "name": u.company_name or u.full_name or u.email,
                    "email": u.email,
                }
            )

    users.sort(key=lambda x: x["name"].lower())
    return jsonify({"users": users})


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
        business_registration = request.form.get("business_registration", "").strip()
        tax_id = request.form.get("tax_id", "").strip()

        if business_registration and len(business_registration) < 3:
            flash("Business registration number is too short.", "error")
            return redirect(url_for("main.kyc"))
        if tax_id and len(tax_id) < 3:
            flash("Tax ID is too short.", "error")
            return redirect(url_for("main.kyc"))

        has_valid_doc = False
        for file in uploaded_files:
            if file and allowed_file(
                file.filename, current_app.config["ALLOWED_EXTENSIONS"]
            ):
                has_valid_doc = True
                original_filename = file.filename
                safe_name = secure_filename(original_filename)
                base_name, ext = os.path.splitext(safe_name)
                if not base_name:
                    base_name = "document"
                unique_name = f"{base_name}-{uuid.uuid4().hex}{ext.lower()}"
                file_path = os.path.join(current_app.config["UPLOAD_FOLDER"], unique_name)
                file.save(file_path)

                kyc_doc = KYCDocument(
                    user_id=current_user.id,
                    document_type=request.form.get("document_type", "general"),
                    filename=unique_name,
                    original_filename=original_filename,
                    file_path=file_path,
                )

                db.session.add(kyc_doc)

        if not has_valid_doc:
            flash("Please upload at least one valid document.", "error")
            return redirect(url_for("main.kyc"))

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
def update_trade_status(trade_id):
    trade = get_or_404(Trade, trade_id)

    if trade.buyer_id != current_user.id and trade.seller_id != current_user.id:
        return jsonify({"error": "Permission denied"}), 403

    data = request.get_json(silent=True) or {}
    new_status = data.get("status")

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
def manage_escrow(trade_id):
    trade = get_or_404(Trade, trade_id)

    if trade.buyer_id != current_user.id and trade.seller_id != current_user.id:
        return jsonify({"error": "Permission denied"}), 403

    data = request.get_json(silent=True) or {}
    action = data.get("action")
    amount = data.get("amount", 0)
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid amount"}), 400

    sim = EscrowSimulator()
    try:
        if action == "deposit":
            if trade.buyer_id != current_user.id:
                return jsonify({"error": "Only buyer can deposit to escrow"}), 403
            tx = sim.deposit_to_trade(current_user, trade, amount)
            report_url = None
            try:
                report_url = url_for('main.trade_report', trade_id=trade.id, tx_id=tx.id)
            except Exception:
                report_url = None
            return jsonify({"success": True, "escrow_amount": trade.escrow_amount, "report_url": report_url})

        if action == "release":
            if trade.seller_id != current_user.id:
                return jsonify({"error": "Only seller can release escrow"}), 403
            tx = sim.release_to_seller(current_user, trade)
            report_url = None
            try:
                report_url = url_for('main.trade_report', trade_id=trade.id, tx_id=tx.id)
            except Exception:
                report_url = None
            return jsonify({"success": True, "escrow_amount": trade.escrow_amount, "report_url": report_url})

        if action == "refund":
            if trade.seller_id != current_user.id and trade.buyer_id != current_user.id:
                return jsonify({"error": "Only buyer or seller can refund escrow"}), 403
            tx = sim.refund_to_buyer(current_user, trade)
            report_url = None
            try:
                report_url = url_for('main.trade_report', trade_id=trade.id, tx_id=tx.id)
            except Exception:
                report_url = None
            return jsonify({"success": True, "escrow_amount": trade.escrow_amount, "report_url": report_url})

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception:
        return jsonify({"error": "Internal error"}), 500

    return jsonify({"error": "Invalid action"}), 400


@main_bp.route('/trade/<int:trade_id>/report/<int:tx_id>')
@login_required
def trade_report(trade_id, tx_id):
    trade = get_or_404(Trade, trade_id)

    # Only participants may download the report
    if trade.buyer_id != current_user.id and trade.seller_id != current_user.id:
        flash("You don't have permission to view this report.", "error")
        return redirect(url_for('main.trade_detail', trade_id=trade.id))

    tx = None
    if tx_id:
        tx = db.session.get(EscrowTransaction, tx_id)

    try:
        buf = create_trade_pdf(trade, tx)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    buf.seek(0)
    return send_file(buf, mimetype='application/pdf', as_attachment=True, download_name=f'trade_{trade.id}_report.pdf')


@main_bp.route('/wallet/challenge')
def wallet_challenge():
    # generate a random challenge and store in session (base64 encoded)
    challenge = base64.b64encode(os.urandom(32)).decode('ascii')
    session['wallet_challenge'] = challenge
    return jsonify({'challenge': challenge})


@main_bp.route('/wallet/verify', methods=['POST'])
def wallet_verify():
    data = request.get_json() or {}
    pub_b64 = data.get('public_key')
    sig_b64 = data.get('signature')
    challenge_b64 = session.get('wallet_challenge')

    if not (pub_b64 and sig_b64 and challenge_b64):
        return jsonify({'error': 'Missing fields or no challenge'}), 400

    if not _HAS_PYNACL:
        return jsonify({'error': 'Server missing PyNaCl for signature verification'}), 501

    try:
        pub_bytes = base64.b64decode(pub_b64)
        sig_bytes = base64.b64decode(sig_b64)
        challenge_bytes = base64.b64decode(challenge_b64)

        verify_key = nacl.signing.VerifyKey(pub_bytes)
        verify_key.verify(challenge_bytes, sig_bytes)

    except Exception:
        return jsonify({'error': 'Verification failed'}), 400

    # mark wallet as connected in session
    session['wallet_address'] = base64.b64encode(pub_bytes).decode('ascii')
    session.pop('wallet_challenge', None)
    return jsonify({'success': True})
