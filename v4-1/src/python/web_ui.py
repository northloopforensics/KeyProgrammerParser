from flask import Flask, render_template, request, Response, url_for
import subprocess
import shlex
import os
import sys
import urllib.parse

app = Flask(__name__, template_folder='templates', static_folder='static')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/start')
def start():
    input_path = request.args.get('input')
    report_path = request.args.get('report')
    if not input_path or not report_path:
        return "Missing input or report query parameters", 400

    # Build command
    python_exe = sys.executable or 'python'
    script = os.path.join(os.path.dirname(__file__), 'KeyProgrammerParser.py')
    cmd = [python_exe, script, '--cli', input_path, report_path]

    def generate():
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=1, universal_newlines=True)
            for line in proc.stdout:
                txt = line.rstrip()
                # If the parser emits PROGRESS:n tokens, forward them as-is so the client can parse
                if txt.startswith('PROGRESS:'):
                    yield f"data: {txt}\n\n"
                else:
                    # escape newlines are already handled; just forward
                    yield f"data: {txt}\n\n"
            proc.wait()
            # send a done event; include return code and report path
            payload = f"{proc.returncode}|{report_path}"
            yield f"event: done\ndata: {payload}\n\n"
        except Exception as e:
            yield f"data: Error starting parser: {e}\n\n"

    return Response(generate(), mimetype='text/event-stream')

if __name__ == '__main__':
    app.run(debug=False, port=5000)
