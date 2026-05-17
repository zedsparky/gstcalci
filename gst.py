import logging
from datetime import datetime, timedelta

from flask import Flask, jsonify, render_template, request

app = Flask(__name__)
app.logger.setLevel(logging.INFO)

MAX_SESSION_DURATION_SECONDS = int(timedelta(hours=12).total_seconds())
ACTIVE_SESSIONS = []


def _get_active_session(user_id, context_id=None, task_id=None):
    for session in ACTIVE_SESSIONS:
        if session["user_id"] != user_id:
            continue
        if context_id is not None and session["context_id"] != context_id:
            continue
        if task_id is not None and session["task_id"] != task_id:
            continue
        return session
    return None


def _validate_duration(duration_seconds):
    if duration_seconds < 0:
        app.logger.warning("Duration validation failed: negative duration=%s", duration_seconds)
        return False, "Duration must be non-negative."
    if duration_seconds > MAX_SESSION_DURATION_SECONDS:
        app.logger.warning(
            "Duration validation failed: exceeds max duration=%s max=%s",
            duration_seconds,
            MAX_SESSION_DURATION_SECONDS,
        )
        return False, "Duration exceeds max allowed session duration (12 hours)."
    return True, None

@app.route('/', methods=['GET', 'POST'])
def calculate_gst():
    gst_result = None

    if request.method == 'POST':
        amount = float(request.form['amount'])
        tax_type = request.form['tax_type']

        # Check if CGST/SGST were submitted
        cgst = request.form.get('cgst')
        sgst = request.form.get('sgst')
        is_split = cgst and sgst

        if is_split:
            cgst = float(cgst)
            sgst = float(sgst)
            total_gst_rate = cgst + sgst
        else:
            total_gst_rate = float(request.form['gst_rate'])
            cgst = sgst = total_gst_rate / 2  # Optional: mimic a 50-50 split for display

        if tax_type == 'exclusive':
            gst_amount = (amount * total_gst_rate) / 100
            total = amount + gst_amount
        else:  # inclusive
            gst_amount = (amount * total_gst_rate) / (100 + total_gst_rate)
            total = amount

        gst_result = {
            'amount': round(amount, 2),
            'gst_rate': round(total_gst_rate, 2),
            'gst_amount': round(gst_amount, 2),
            'total': round(total, 2),
            'tax_type': tax_type,
            'cgst': round((gst_amount * cgst) / total_gst_rate, 2),
            'sgst': round((gst_amount * sgst) / total_gst_rate, 2),
            'is_split': is_split
        }

    return render_template('index.html', result=gst_result)


@app.route('/session/start', methods=['POST'])
def start_session():
    payload = request.get_json(force=True)
    user_id = payload.get("user_id")
    context_id = payload.get("context_id")
    task_id = payload.get("task_id")

    existing_session = _get_active_session(user_id=user_id, context_id=context_id)
    if existing_session:
        app.logger.warning(
            "Session start validation failed: user=%s context=%s already active session=%s",
            user_id,
            context_id,
            existing_session["session_id"],
        )
        return jsonify({"error": "An active session already exists for this user/context."}), 409

    session_id = len(ACTIVE_SESSIONS) + 1
    ACTIVE_SESSIONS.append(
        {
            "session_id": session_id,
            "user_id": user_id,
            "context_id": context_id,
            "task_id": task_id,
            "started_at": datetime.utcnow(),
        }
    )
    return jsonify({"session_id": session_id, "status": "started"}), 201


@app.route('/session/stop', methods=['POST'])
def stop_session():
    payload = request.get_json(force=True)
    user_id = payload.get("user_id")
    context_id = payload.get("context_id")
    duration_seconds = payload.get("duration_seconds", 0)

    is_valid, message = _validate_duration(duration_seconds)
    if not is_valid:
        return jsonify({"error": message}), 400

    active_session = _get_active_session(user_id=user_id, context_id=context_id)
    if not active_session:
        app.logger.warning(
            "Session stop validation failed: no active session for user=%s context=%s",
            user_id,
            context_id,
        )
        return jsonify({"status": "no_active_session"}), 200

    ACTIVE_SESSIONS.remove(active_session)
    return jsonify({"session_id": active_session["session_id"], "status": "stopped"}), 200


@app.route('/task/complete', methods=['POST'])
def complete_task():
    payload = request.get_json(force=True)
    user_id = payload.get("user_id")
    task_id = payload.get("task_id")
    auto_stop = bool(payload.get("auto_stop", False))
    duration_seconds = payload.get("duration_seconds", 0)

    active_session = _get_active_session(user_id=user_id, task_id=task_id)
    if active_session and not auto_stop:
        app.logger.warning(
            "Task completion validation failed: active session still open for user=%s task=%s session=%s",
            user_id,
            task_id,
            active_session["session_id"],
        )
        return jsonify({"error": "Active session exists for this task. Stop it before completion."}), 409

    if active_session and auto_stop:
        is_valid, message = _validate_duration(duration_seconds)
        if not is_valid:
            return jsonify({"error": message}), 400
        ACTIVE_SESSIONS.remove(active_session)

    return jsonify({"task_id": task_id, "status": "completed"}), 200


if __name__ == '__main__':
    app.run(debug=True)
