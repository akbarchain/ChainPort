from flask import render_template, request, redirect, url_for, session, flash
from flask_login import login_user, logout_user, login_required, current_user
from . import auth_bp
from app.models import db, User
from app.extensions import login_manager
from werkzeug.security import generate_password_hash, check_password_hash


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
            session["user_id"] = user.id
            session["user_email"] = user.email
            session["logged_in"] = True
            next_page = request.args.get("next")
            return (
                redirect(next_page)
                if next_page
                else redirect(url_for("main.dashboard"))
            )

        flash("Invalid email or password", "error")
        return render_template("auth/login.html")

    return render_template("auth/login.html")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        first_name = request.form.get("first_name", "").strip()
        last_name = request.form.get("last_name", "").strip()
        company_name = request.form.get("company_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "")

        if User.query.filter_by(email=email).first():
            flash("Email already registered", "error")
            return render_template("auth/register.html")

        user = User(
            email=email,
            first_name=first_name,
            last_name=last_name,
            company_name=company_name,
            phone=phone,
        )
        user.set_password(password)

        db.session.add(user)
        db.session.commit()

        login_user(user)
        session["user_id"] = user.id
        session["user_email"] = user.email
        session["logged_in"] = True

        flash("Registration successful! Welcome to ChainPort.", "success")
        return redirect(url_for("main.dashboard"))

    return render_template("auth/register.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    session.clear()
    flash("You have been logged out successfully.", "success")
    return redirect(url_for("main.index"))
