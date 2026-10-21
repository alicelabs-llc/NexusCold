"""Desktop operator panel; workers communicate through a main-thread queue."""
import asyncio
import json
import os
import queue
import threading
from pathlib import Path
from tkinter import filedialog, messagebox
import customtkinter as ctk

from german_agent import DEFAULT_MODEL, inspect_rows, ask_german, ModelConfig
from german_jobs import MODES, SOURCES, read_csv, run_job
from domain_auth import check_domain
from product_identity import PRODUCT_SIGNATURE, PRODUCT_VERSION


class GermanPanel(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title(f'Germán · {PRODUCT_SIGNATURE} {PRODUCT_VERSION}')
        self.geometry('1000x840')
        self.minsize(820, 650)
        self.rows, self.analysis = [], {}
        self.analysis_mapping = {}
        self.path = None
        self.busy = False
        self.stop = threading.Event()
        self.events = queue.Queue()
        self.buttons = []
        self.protocol('WM_DELETE_WINDOW', self._close)
        frame = ctk.CTkScrollableFrame(self)
        frame.pack(fill='both', expand=True, padx=16, pady=16)
        ctk.CTkLabel(frame, text='Germán — tu operador de archivos', font=('', 24, 'bold')).pack(anchor='w')
        ctk.CTkLabel(frame, text='Revisa, ejecuta y reanuda. El chat es opcional y no ejecuta acciones.',
                    wraplength=780, justify='left').pack(anchor='w', pady=(0, 8))
        self.file_label = ctk.CTkLabel(frame, text='Abre un CSV para comenzar.', wraplength=780)
        self.file_label.pack(anchor='w')
        self._button(frame, 'Abrir CSV y revisar sin internet', self._load).pack(anchor='w', pady=4)
        mapping = ctk.CTkFrame(frame)
        mapping.pack(fill='x', pady=6)
        self.map_vars, self.map_widgets = {}, {}
        for index, key in enumerate(('company_name', 'email', 'website', 'city', 'state', 'country')):
            ctk.CTkLabel(mapping, text=key).grid(row=index//3*2, column=index%3, padx=6, sticky='w')
            variable = ctk.StringVar(value='')
            widget = ctk.CTkOptionMenu(mapping, variable=variable, values=[''], width=240)
            widget.grid(row=index//3*2+1, column=index%3, padx=6, pady=(0, 6), sticky='ew')
            self.map_vars[key], self.map_widgets[key] = variable, widget
            mapping.grid_columnconfigure(index%3, weight=1)
        controls = ctk.CTkFrame(frame)
        controls.pack(fill='x', pady=4)
        ctk.CTkLabel(controls, text='Trabajo:').pack(side='left', padx=6)
        self.mode = ctk.CTkOptionMenu(controls, values=list(MODES))
        self.mode.pack(side='left', padx=6)
        self.mode.set('offline')
        self.network = ctk.CTkCheckBox(frame, text='Autorizar consultas web/DNS/SMTP para el trabajo o diagnóstico elegido')
        self.network.pack(anchor='w', pady=6)
        ctk.CTkLabel(frame, text='offline: revisión · mx: ruta de correo · smtp: buzón · enrich: web · enrich_smtp: ambos',
                    wraplength=780, justify='left').pack(anchor='w')
        source_frame = ctk.CTkFrame(frame)
        source_frame.pack(fill='x', pady=4)
        ctk.CTkLabel(source_frame, text='Cascada web:').pack(side='left', padx=6)
        self.sources = {}
        for source in SOURCES:
            checkbox = ctk.CTkCheckBox(source_frame, text=source.upper(), width=100)
            checkbox.select()
            checkbox.pack(side='left', padx=8)
            self.sources[source] = checkbox
        jobs = ctk.CTkFrame(frame)
        jobs.pack(fill='x', pady=6)
        self._button(jobs, 'Ejecutar y guardar CSV', lambda: self._run(False)).pack(side='left', padx=6, pady=6)
        self._button(jobs, 'Reanudar con su CSV de salida', lambda: self._run(True)).pack(side='left', padx=6)
        ctk.CTkButton(jobs, text='Detener al terminar fila', command=self.stop.set, fg_color='#9B3434').pack(side='left', padx=6)
        self.status = ctk.CTkLabel(frame, text='Listo. Los checkpoints se cifran; el CSV exportado no.')
        self.status.pack(anchor='w')
        auth = ctk.CTkFrame(frame)
        auth.pack(fill='x', pady=6)
        self.domain = ctk.CTkEntry(auth, placeholder_text='Dominio remitente: empresa.com', width=330)
        self.domain.pack(side='left', padx=6, pady=6)
        self._button(auth, 'Consultar SPF / DMARC', self._domain).pack(side='left', padx=6)
        ctk.CTkLabel(frame, text='Chat opcional: instala Ollama y descarga el modelo. Solo se envían métricas y tu pregunta.',
                    wraplength=780, justify='left').pack(anchor='w', pady=(10, 0))
        llm = ctk.CTkFrame(frame)
        llm.pack(fill='x', pady=4)
        self.endpoint = ctk.CTkEntry(llm, width=400)
        self.endpoint.insert(0, 'http://127.0.0.1:11434')
        self.endpoint.pack(side='left', padx=6, pady=6)
        self.model = ctk.CTkEntry(llm, width=240)
        self.model.insert(0, DEFAULT_MODEL)
        self.model.pack(side='left', padx=6)
        self.remote = ctk.CTkCheckBox(frame, text='Autorizar envío de métricas y mi pregunta al servidor HTTPS elegido (token en NEXUS_GERMAN_TOKEN)')
        self.remote.pack(anchor='w', pady=6)
        question = ctk.CTkFrame(frame)
        question.pack(fill='x')
        self.question = ctk.CTkEntry(question, placeholder_text='¿Qué debería corregir en este archivo?', width=600)
        self.question.pack(side='left', padx=6, pady=6, fill='x', expand=True)
        self._button(question, 'Preguntar', self._ask).pack(side='left', padx=6)
        self.report = ctk.CTkTextbox(frame, height=240, wrap='word')
        self.report.pack(fill='both', expand=True, pady=8)
        self.after(100, self._poll)
        current = getattr(master, 'loaded_path', None)
        if current and Path(current).suffix.lower() == '.csv':
            self._load(current)

    def _button(self, parent, label, command):
        button = ctk.CTkButton(parent, text=label, command=command)
        self.buttons.append(button)
        return button

    def _show(self, value):
        self.report.delete('1.0', 'end')
        self.report.insert('end', value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2))

    def _load(self, path=None):
        path = path or filedialog.askopenfilename(parent=self, filetypes=[('CSV', '*.csv')])
        if not path:
            return
        try:
            rows = read_csv(path)
            self.analysis = inspect_rows(rows)
            self.analysis_mapping = self.analysis['mapping'].copy()
            self.path, self.rows = Path(path), rows
            self.file_label.configure(text=str(self.path))
            columns = [''] + list(rows[0]) if rows else ['']
            for key, widget in self.map_widgets.items():
                widget.configure(values=columns)
                self.map_vars[key].set(self.analysis['mapping'].get(key, ''))
            self._show(self.analysis)
        except (OSError, ValueError) as error:
            messagebox.showerror('No se pudo abrir', str(error), parent=self)

    def _start(self, operation, done=None):
        if self.busy:
            return
        self.busy = True
        self.stop.clear()
        self.status.configure(text='Trabajando…')
        for button in self.buttons:
            button.configure(state='disabled')
        def worker():
            try:
                self.events.put(('done', operation(), done))
            except Exception as error:
                self.events.put(('error', str(error), None))
        threading.Thread(target=worker, daemon=True).start()

    def _poll(self):
        try:
            while True:
                kind, value, callback = self.events.get_nowait()
                if kind == 'progress':
                    self.status.configure(text=value)
                else:
                    self.busy = False
                    for button in self.buttons:
                        button.configure(state='normal')
                    self.status.configure(text='Listo.' if kind == 'done' else 'Interrumpido; conserva el checkpoint si existe.')
                    self._show(value)
                    if callback:
                        callback(value)
        except queue.Empty:
            pass
        self.after(100, self._poll)

    def _run(self, resume):
        if not self.path:
            messagebox.showinfo('Archivo', 'Abre primero un CSV.', parent=self)
            return
        output = filedialog.asksaveasfilename(parent=self, defaultextension='.csv', filetypes=[('CSV', '*.csv')],
                                            title='Selecciona la salida del trabajo que reanudas' if resume else 'Guardar salida')
        if not output:
            return
        path, mode, network = self.path, self.mode.get(), bool(self.network.get())
        mapping = {key: var.get() for key, var in self.map_vars.items()}
        sources = tuple(source for source, checkbox in self.sources.items() if checkbox.get())
        def finished(result):
            self.analysis = result['summary']
            self.analysis_mapping = mapping.copy()
        self._start(lambda: run_job(path, output, mode=mode, allow_network=network, resume=resume,
            mapping=mapping, sources=sources, stop_flag=self.stop.is_set,
            progress_callback=lambda n, t: self.events.put(('progress', f'Procesadas {n}/{t}; guardando checkpoint cifrado.', None))),
            finished)

    def _domain(self):
        if not self.network.get():
            messagebox.showinfo('Consulta DNS', 'Activa la autorización de consultas de red.', parent=self)
            return
        domain = self.domain.get()
        self._start(lambda: asyncio.run(check_domain(domain)))

    def _ask(self):
        try:
            config = ModelConfig(self.endpoint.get(), self.model.get(), bool(self.remote.get()),
                                 os.environ.get('NEXUS_GERMAN_TOKEN', ''))
            mapping = {key: var.get() for key, var in self.map_vars.items()}
            if self.rows and mapping != self.analysis_mapping:
                self.analysis = inspect_rows(self.rows, mapping=mapping)
                self.analysis_mapping = mapping.copy()
            question, analysis = self.question.get(), self.analysis
            self._start(lambda: asyncio.run(ask_german(question, analysis, config)))
        except ValueError as error:
            messagebox.showerror('IA', str(error), parent=self)

    def _close(self):
        if self.busy:
            self.stop.set()
            self.status.configure(text='Deteniendo. Espera a que termine la consulta actual antes de cerrar.')
        else:
            self.destroy()
