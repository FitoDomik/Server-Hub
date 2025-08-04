import os
import sys
import threading
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename
import requests
import time
import tkinter.font as tkfont
from tkinter import PhotoImage
import contextlib
import io
class ScriptManager:
    def __init__(self):
        self.processes = {}
        self.lock = threading.Lock()
    def start_script(self, script_name):
        script_path = os.path.join('scripts', script_name)
        if not os.path.exists(script_path):
            raise FileNotFoundError(f'Скрипт {script_name} не найден')
        with self.lock:
            log_path = os.path.join('scripts', f'{script_name}.log')
            log_file = open(log_path, 'w', encoding='utf-8')
            proc = subprocess.Popen([sys.executable, script_path], stdout=log_file, stderr=subprocess.STDOUT)
            self.processes[proc.pid] = {'process': proc, 'script': script_name, 'status': 'running', 'logfile': log_path}
            return proc.pid
    def stop_script(self, pid):
        with self.lock:
            proc_info = self.processes.get(pid)
            if not proc_info:
                raise ValueError(f'Процесс с PID {pid} не найден')
            proc = proc_info['process']
            proc.terminate()
            proc.wait(timeout=5)
            proc_info['status'] = 'stopped'
            del self.processes[pid]
    def list_processes(self):
        with self.lock:
            result = []
            for pid, info in self.processes.items():
                if info['process'].poll() is not None:
                    info['status'] = 'stopped'
                result.append({'pid': pid, 'script': info['script'], 'status': info['status'], 'logfile': info['logfile']})
            return result
UPLOAD_FOLDER = 'scripts'
ALLOWED_EXTENSIONS = {'py'}
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
manager = ScriptManager()
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return 'No file part', 400
    file = request.files['file']
    if file.filename == '':
        return 'No selected file', 400
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        file.save(os.path.join(UPLOAD_FOLDER, filename))
        return 'File uploaded', 200
    return 'Invalid file', 400
@app.route('/start', methods=['POST'])
def start_script():
    script = request.args.get('script')
    if not script:
        return 'No script specified', 400
    try:
        pid = manager.start_script(script)
        return jsonify({'pid': pid}), 200
    except Exception as e:
        return str(e), 500
@app.route('/stop', methods=['POST'])
def stop_script():
    pid = request.args.get('pid')
    if not pid:
        return 'No PID specified', 400
    try:
        manager.stop_script(int(pid))
        return 'Stopped', 200
    except Exception as e:
        return str(e), 500
@app.route('/status', methods=['GET'])
def status():
    return jsonify(manager.list_processes())
def run_flask():
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    with open(os.devnull, 'w') as devnull:
        with contextlib.redirect_stdout(devnull), contextlib.redirect_stderr(devnull):
            app.run(debug=False, use_reloader=False)
API_URL = 'http://127.0.0.1:5000'
SCRIPTS_DIR = 'scripts'
class ScriptHubApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Python Server Hub')
        self.geometry('800x500')
        self.configure(bg='#23272e')
        self.create_widgets()
        self.after(1000, self.try_connect)
        self.selected_pid = None
        self.process_logs = {}
    def try_connect(self):
        try:
            requests.get(f'{API_URL}/status', timeout=1)
            self.refresh_scripts()
            self.refresh_status()
        except Exception:
            self.after(1000, self.try_connect)
    def create_widgets(self):
        style = ttk.Style(self)
        try:
            self.tk.call('source', 'azure.tcl')
            style.theme_use('azure-dark')
        except Exception:
            style.theme_use('clam')
        style.configure('TFrame', background='#23272e')
        style.configure('TLabel', background='#23272e', foreground='#fff', font=('Segoe UI', 11))
        style.configure('TButton', font=('Segoe UI', 10))
        style.configure('Treeview', font=('Segoe UI', 10), rowheight=28)
        style.configure('Treeview.Heading', font=('Segoe UI', 10, 'bold'))
        main_frame = ttk.Frame(self)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        left = ttk.Frame(main_frame)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10), pady=0)
        right = ttk.Frame(main_frame)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        ttk.Label(left, text='Скрипты').pack(anchor='w', pady=(0, 5))
        self.scripts_list = tk.Listbox(left, height=15, font=('Segoe UI', 10))
        self.scripts_list.pack(fill=tk.X, pady=(0, 10))
        self.scripts_list.bind('<<ListboxSelect>>', self.on_script_select)
        self.upload_btn = ttk.Button(left, text='📤 Загрузить', command=self.upload_script)
        self.upload_btn.pack(fill=tk.X, pady=2)
        self.start_btn = ttk.Button(left, text='▶ Запустить', command=self.start_script)
        self.start_btn.pack(fill=tk.X, pady=2)
        self.stop_btn = ttk.Button(left, text='■ Остановить', command=self.stop_script)
        self.stop_btn.pack(fill=tk.X, pady=2)
        self.refresh_btn = ttk.Button(left, text='🔄 Обновить', command=self.refresh_all)
        self.refresh_btn.pack(fill=tk.X, pady=2)
        ttk.Label(right, text='Процессы').pack(anchor='w', pady=(0, 5))
        columns = ('script', 'pid', 'status')
        self.status_tree = ttk.Treeview(right, columns=columns, show='headings', selectmode='browse', height=8)
        self.status_tree.heading('script', text='Скрипт')
        self.status_tree.heading('pid', text='PID')
        self.status_tree.heading('status', text='Статус')
        self.status_tree.column('script', width=200)
        self.status_tree.column('pid', width=80)
        self.status_tree.column('status', width=100)
        self.status_tree.pack(fill=tk.X, pady=(0, 10))
        self.status_tree.bind('<<TreeviewSelect>>', self.on_process_select)
        ttk.Label(right, text='Логи процесса').pack(anchor='w', pady=(0, 5))
        self.log_text = tk.Text(right, height=10, font=('Consolas', 10), bg='#181a20', fg='#fff', insertbackground='#fff')
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self.log_text.config(state=tk.DISABLED)
    def on_script_select(self, event):
        pass  
    def on_process_select(self, event):
        selection = self.status_tree.selection()
        if not selection:
            self.selected_pid = None
            self.show_log('')
            return
        pid = self.status_tree.item(selection[0])['values'][1]
        self.selected_pid = pid
        self.show_log(self.process_logs.get(pid, ''))
    def show_log(self, text):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.insert(tk.END, text)
        self.log_text.config(state=tk.DISABLED)
    def upload_script(self):
        file_path = filedialog.askopenfilename(filetypes=[('Python files', '*.py')])
        if file_path:
            with open(file_path, 'rb') as f:
                files = {'file': (os.path.basename(file_path), f, 'text/x-python')}
                try:
                    r = requests.post(f'{API_URL}/upload', files=files)
                except Exception as e:
                    messagebox.showerror('Ошибка', f'Ошибка соединения: {e}')
                    return
            if r.status_code == 200:
                messagebox.showinfo('Успех', 'Файл загружен!')
                self.refresh_scripts()
            else:
                messagebox.showerror('Ошибка', f'Ошибка загрузки: {r.text}')
    def refresh_scripts(self):
        self.scripts_list.delete(0, tk.END)
        if not os.path.exists(SCRIPTS_DIR):
            os.makedirs(SCRIPTS_DIR)
        for fname in os.listdir(SCRIPTS_DIR):
            if fname.endswith('.py'):
                self.scripts_list.insert(tk.END, fname)
    def start_script(self):
        selection = self.scripts_list.curselection()
        if not selection:
            messagebox.showwarning('Внимание', 'Выберите скрипт для запуска!')
            return
        script = self.scripts_list.get(selection[0])
        try:
            r = requests.post(f'{API_URL}/start', params={'script': script})
        except Exception as e:
            messagebox.showerror('Ошибка', f'Ошибка соединения: {e}')
            return
        if r.status_code == 200:
            messagebox.showinfo('Успех', f'Скрипт {script} запущен!')
            self.refresh_status()
        else:
            messagebox.showerror('Ошибка', f'Ошибка запуска: {r.text}')
    def stop_script(self):
        selection = self.status_tree.selection()
        if not selection:
            messagebox.showwarning('Внимание', 'Выберите процесс для остановки!')
            return
        pid = self.status_tree.item(selection[0])['values'][1]
        try:
            r = requests.post(f'{API_URL}/stop', params={'pid': pid})
        except Exception as e:
            messagebox.showerror('Ошибка', f'Ошибка соединения: {e}')
            return
        if r.status_code == 200:
            messagebox.showinfo('Успех', f'Процесс {pid} остановлен!')
            self.refresh_status()
        else:
            messagebox.showerror('Ошибка', f'Ошибка остановки: {r.text}')
    def refresh_status(self):
        self.status_tree.delete(*self.status_tree.get_children())
        try:
            r = requests.get(f'{API_URL}/status')
            if r.status_code == 200:
                for proc in r.json():
                    self.status_tree.insert('', tk.END, values=(proc['script'], proc['pid'], proc['status']))
                    self.process_logs[str(proc['pid'])] = self.get_process_log(proc['pid'])
        except Exception as e:
            pass
        if self.selected_pid:
            self.show_log(self.process_logs.get(str(self.selected_pid), ''))
    def get_process_log(self, pid):
        try:
            for proc in manager.list_processes():
                if str(proc['pid']) == str(pid):
                    log_path = proc.get('logfile')
                    if log_path and os.path.exists(log_path):
                        with open(log_path, 'r', encoding='utf-8') as f:
                            return f.read()[-5000:]
        except Exception as e:
            return f'Ошибка чтения лога: {e}'
        return 'Нет лога для этого процесса.'
    def refresh_all(self):
        self.refresh_scripts()
        self.refresh_status()
if __name__ == '__main__':
    if not os.path.exists(SCRIPTS_DIR):
        os.makedirs(SCRIPTS_DIR)
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    for _ in range(10):
        try:
            requests.get(f'{API_URL}/status', timeout=1)
            break
        except Exception:
            time.sleep(0.5)
    app = ScriptHubApp()
    app.mainloop() 
