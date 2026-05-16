import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
import threading, time, os, asyncio, json
import pandas as pd
from dataclasses import asdict, dataclass
from datetime import datetime

# Import core engine
from enricher_core import EnrichedCompany, run_enrichment

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

VERSION = "6.0 — WORLD EDITION"

class AliceNexusGUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(f"AliceLabs B2B Nexus — {VERSION}")
        self.geometry("1400x900")
        
        # Colors (Blue Skin)
        self.bg_color = "#0F172A"
        self.sidebar_color = "#1E293B"
        self.accent_color = "#3B82F6"
        self.success_color = "#10B981"
        self.text_color = "#F8FAFC"
        self.border_color = "#334155"
        
        self.configure(fg_color=self.bg_color)
        
        # State
        self.df = None
        self.loaded_path = None
        self.output_dir = None
        self.running = False
        self.mapping_confirmed = False
        self.total_records = 0
        
        # Initialize UI
        self._setup_ui()
        self.log_system("System Initialized. Awaiting Data Protocol...")

    def _setup_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ─── SIDEBAR ───
        self.sidebar = ctk.CTkFrame(self, width=280, corner_radius=0, fg_color=self.sidebar_color, border_width=1, border_color=self.border_color)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(6, weight=1)

        # Logo / Title
        self.logo_label = ctk.CTkLabel(self.sidebar, text="AliceLabs", font=ctk.CTkFont(size=28, weight="bold"), text_color=self.accent_color)
        self.logo_label.grid(row=0, column=0, padx=20, pady=(30, 5))
        
        self.sub_label = ctk.CTkLabel(self.sidebar, text="B2B Nexus v6.0 — WORLD EDITION", font=ctk.CTkFont(size=12), text_color="#94A3B8")
        self.sub_label.grid(row=1, column=0, padx=20, pady=(0, 40))

        # Sidebar Buttons
        btn_opts = {"height": 45, "anchor": "w", "font": ctk.CTkFont(size=13, weight="bold")}
        self.btn_enrich = ctk.CTkButton(self.sidebar, text="🎯 Enrichment Engine", fg_color=self.accent_color, command=lambda: self.show_view("enrich"), **btn_opts)
        self.btn_enrich.grid(row=2, column=0, padx=20, pady=8, sticky="ew")
        
        self.btn_niche = ctk.CTkButton(self.sidebar, text="🏷️ Niche Searcher", fg_color="transparent", border_width=1, border_color=self.accent_color, command=lambda: self.show_view("niche"), **btn_opts)
        self.btn_niche.grid(row=3, column=0, padx=20, pady=8, sticky="ew")
        
        self.btn_brain = ctk.CTkButton(self.sidebar, text="🧠 AI Brain Hub", fg_color="transparent", border_width=1, border_color=self.accent_color, command=lambda: self.show_view("brain"), **btn_opts)
        self.btn_brain.grid(row=4, column=0, padx=20, pady=8, sticky="ew")

        self.btn_warmer = ctk.CTkButton(self.sidebar, text="🔥 Email Warmer", fg_color="transparent", border_width=1, border_color=self.accent_color, command=lambda: self.show_view("warmer"), **btn_opts)
        self.btn_warmer.grid(row=5, column=0, padx=20, pady=8, sticky="ew")

        # ─── MAIN CONTENT ───
        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.main_container.grid(row=0, column=1, sticky="nsew", padx=40, pady=30)
        self.main_container.grid_columnconfigure(0, weight=1)
        self.main_container.grid_rowconfigure(1, weight=1)

        # Header Title
        self.header_lbl = ctk.CTkLabel(self.main_container, text="Lead Enrichment Engine v6.0 — WORLD EDITION", font=ctk.CTkFont(size=24, weight="bold"), text_color=self.accent_color)
        self.header_lbl.grid(row=0, column=0, sticky="w", pady=(0, 20))

        # Engine Control Panel
        self.engine_frame = ctk.CTkFrame(self.main_container, fg_color=self.sidebar_color, corner_radius=15, border_width=1, border_color=self.border_color)
        self.engine_frame.grid(row=1, column=0, sticky="nsew", padx=2, pady=2)
        
        # 1. Loading Area
        load_section = ctk.CTkFrame(self.engine_frame, fg_color="transparent")
        load_section.pack(fill="x", padx=40, pady=(30, 10))
        
        self.btn_load = ctk.CTkButton(load_section, text="📥 LOAD DATASET", command=self.load_dataset, height=50, width=250, fg_color=self.success_color, font=ctk.CTkFont(size=14, weight="bold"))
        self.btn_load.pack(side="left", padx=10)
        
        self.lbl_file = ctk.CTkLabel(load_section, text="Status: No data loaded.", font=ctk.CTkFont(size=13), text_color="#94A3B8")
        self.lbl_file.pack(side="left", padx=20)

        # 2. Mapping Configuration
        map_section = ctk.CTkFrame(self.engine_frame, fg_color="transparent")
        map_section.pack(fill="x", padx=40, pady=10)
        
        # Left side: Dropdowns
        drop_side = ctk.CTkFrame(map_section, fg_color="transparent")
        drop_side.pack(side="left")
        
        ctk.CTkLabel(drop_side, text="Identification Column:", font=ctk.CTkFont(size=11, weight="bold")).grid(row=0, column=0, padx=5, sticky="w")
        self.var_name = ctk.StringVar(value="-- select --")
        self.dd_name = ctk.CTkOptionMenu(drop_side, variable=self.var_name, values=["-- select --"], width=220, fg_color=self.bg_color)
        self.dd_name.grid(row=1, column=0, padx=5, pady=(0, 10))
        
        ctk.CTkLabel(drop_side, text="Location Column:", font=ctk.CTkFont(size=11, weight="bold")).grid(row=2, column=0, padx=5, sticky="w")
        self.var_city = ctk.StringVar(value="-- select --")
        self.dd_city = ctk.CTkOptionMenu(drop_side, variable=self.var_city, values=["-- select --"], width=220, fg_color=self.bg_color)
        self.dd_city.grid(row=3, column=0, padx=5)

        # Right side: Meta & Output Folder
        meta_side = ctk.CTkFrame(map_section, fg_color="transparent")
        meta_side.pack(side="right", anchor="ne")
        
        self.btn_out = ctk.CTkButton(meta_side, text="📂 Output Folder", width=120, height=30, font=ctk.CTkFont(size=11), command=self.select_output_dir, fg_color="#334155")
        self.btn_out.grid(row=0, column=0, columnspan=2, padx=5, pady=(0, 10))
        
        ctk.CTkLabel(meta_side, text="Limit:", font=ctk.CTkFont(size=11, weight="bold")).grid(row=1, column=0, padx=5, sticky="w")
        self.var_limit = ctk.StringVar(value="100")
        ctk.CTkEntry(meta_side, textvariable=self.var_limit, width=80, fg_color=self.bg_color).grid(row=2, column=0, padx=5)
        
        ctk.CTkLabel(meta_side, text="Ext:", font=ctk.CTkFont(size=11, weight="bold")).grid(row=1, column=1, padx=5, sticky="w")
        self.var_format = ctk.StringVar(value="CSV")
        ctk.CTkOptionMenu(meta_side, variable=self.var_format, values=["CSV", "XLSX"], width=80, fg_color=self.bg_color).grid(row=2, column=1, padx=5)

        # 3. Column Mapper
        mapper_header = ctk.CTkFrame(self.engine_frame, fg_color="transparent")
        mapper_header.pack(fill="x", padx=40, pady=(20, 0))
        
        ctk.CTkLabel(mapper_header, text="📋 Analysis & Column Mapper (Automatic Headers)", font=ctk.CTkFont(size=15, weight="bold"), text_color=self.text_color).pack(side="left")
        
        self.btn_toggle_all = ctk.CTkButton(mapper_header, text="Toggle All", width=80, height=20, font=ctk.CTkFont(size=10), command=self.toggle_all_columns)
        self.btn_toggle_all.pack(side="right", padx=10)

        self.col_scroll = ctk.CTkScrollableFrame(self.engine_frame, height=200, fg_color=self.bg_color, border_width=1, border_color=self.border_color)
        self.col_scroll.pack(fill="x", padx=40, pady=10)
        self.col_vars = {}

        # 4. Confirmation
        self.btn_confirm = ctk.CTkButton(self.engine_frame, text="✅ CONFIRM MAPPING & SYNC", command=self.confirm_mapping, height=45, fg_color=self.accent_color, font=ctk.CTkFont(weight="bold"))
        self.btn_confirm.pack(pady=10)

        # 5. Enrichment Options
        opts_row = ctk.CTkFrame(self.engine_frame, fg_color="transparent")
        opts_row.pack(fill="x", padx=40, pady=10)
        
        self.chk_mail = ctk.CTkCheckBox(opts_row, text="📧 Emails", font=ctk.CTkFont(size=11)); self.chk_mail.select()
        self.chk_mail.pack(side="left", padx=10)
        
        self.chk_web = ctk.CTkCheckBox(opts_row, text="🌐 Websites", font=ctk.CTkFont(size=11)); self.chk_web.select()
        self.chk_web.pack(side="left", padx=10)
        
        self.chk_social = ctk.CTkCheckBox(opts_row, text="📱 Social Media", font=ctk.CTkFont(size=11)); self.chk_social.select()
        self.chk_social.pack(side="left", padx=10)
        
        self.chk_tax = ctk.CTkCheckBox(opts_row, text="🧾 Tax ID/RUC", font=ctk.CTkFont(size=11)); self.chk_tax.select()
        self.chk_tax.pack(side="left", padx=10)
        
        self.chk_ai = ctk.CTkCheckBox(opts_row, text="🧠 AI Agent", font=ctk.CTkFont(size=11)); self.chk_ai.select()
        self.chk_ai.pack(side="left", padx=10)
        
        self.chk_global = ctk.CTkCheckBox(opts_row, text="🌍 Global IDs (VAT/CNPJ/RFC/RUT)", font=ctk.CTkFont(size=11)); self.chk_global.select()
        self.chk_global.pack(side="left", padx=10)

        # ─── FOOTER CONTROLS ───
        self.footer = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.footer.grid(row=2, column=0, sticky="ew", pady=(20, 0))
        
        self.btn_run = ctk.CTkButton(self.footer, text="🚀 INITIALIZE EXTRACTION ENGINE", command=self.toggle_engine, height=65, fg_color=self.success_color, font=ctk.CTkFont(size=20, weight="bold"))
        self.btn_run.pack(fill="x", side="top")
        
        # Stats Row
        stats_row = ctk.CTkFrame(self.footer, fg_color="transparent")
        stats_row.pack(fill="x", pady=5)
        
        self.prog_bar = ctk.CTkProgressBar(stats_row, height=15, progress_color=self.accent_color)
        self.prog_bar.pack(fill="x", side="left", expand=True, padx=(0, 20))
        self.prog_bar.set(0)
        
        self.lbl_stats = ctk.CTkLabel(stats_row, text="Enriched: 0 | Total: 0", font=ctk.CTkFont(size=12, weight="bold"), text_color=self.accent_color)
        self.lbl_stats.pack(side="right")

        # Log Console
        self.log_box = ctk.CTkTextbox(self.main_container, height=120, font=ctk.CTkFont(family="Consolas", size=11), fg_color="#000", border_width=1, border_color=self.border_color)
        self.log_box.grid(row=3, column=0, sticky="ew", pady=(15, 0))

    # --- UI Logic ---

    def show_view(self, view_name):
        # Reset colors
        for btn in [self.btn_enrich, self.btn_niche, self.btn_brain, self.btn_warmer]:
            btn.configure(fg_color="transparent")

        # Hide main engine frame if not enrich
        if view_name == "enrich":
            self.btn_enrich.configure(fg_color=self.accent_color)
            self.engine_frame.grid()
            self.footer.grid()
            self.header_lbl.configure(text="Lead Enrichment Engine v6.0 — WORLD EDITION")
        else:
            self.engine_frame.grid_remove()
            self.footer.grid_remove()
            if view_name == "niche":
                self.btn_niche.configure(fg_color=self.accent_color)
                self.header_lbl.configure(text="Niche Searcher Protocol — [PENDING IMPLEMENTATION]")
                self.log_system("Module 'Niche Searcher' is under development.")
            elif view_name == "brain":
                self.btn_brain.configure(fg_color=self.accent_color)
                self.header_lbl.configure(text="AI Brain Hub — [PENDING IMPLEMENTATION]")
                self.log_system("Module 'AI Brain Hub' is under development.")
            elif view_name == "warmer":
                self.btn_warmer.configure(fg_color=self.accent_color)
                self.header_lbl.configure(text="Email Warmer v6.0 — WORLD EDITION")
                self.log_system("Email Warmer module selected.")

    def log_system(self, msg):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_box.insert("end", f"[{ts}] {msg}\n")
        self.log_box.see("end")

    def toggle_all_columns(self):
        if not self.col_vars: return
        any_off = any(not v.get() for v in self.col_vars.values())
        for v in self.col_vars.values():
            v.set(any_off)

    def select_output_dir(self):
        d = filedialog.askdirectory()
        if d:
            self.output_dir = d
            self.log_system(f"Output Target: {d}")

    def load_dataset(self):
        p = filedialog.askopenfilename(filetypes=[("Data Files", "*.csv *.xlsx")])
        if not p: return
        self.loaded_path = p
        if not self.output_dir:
            self.output_dir = os.path.dirname(p)
            
        try:
            self.df = pd.read_csv(p) if p.endswith('.csv') else pd.read_excel(p)
            cols = list(self.df.columns)
            
            # Reset UI
            self.dd_name.configure(values=cols)
            self.dd_city.configure(values=cols + ["-- none --"])
            
            for widget in self.col_scroll.winfo_children():
                widget.destroy()
            
            self.col_vars = {}
            for i, col in enumerate(cols):
                var = tk.BooleanVar(value=True)
                self.col_vars[col] = var
                chk = ctk.CTkCheckBox(self.col_scroll, text=col, variable=var, font=ctk.CTkFont(size=11), height=18, checkbox_width=16, checkbox_height=16)
                chk.grid(row=i // 4, column=i % 4, padx=15, pady=4, sticky="w")
            
            self.lbl_file.configure(text=f"Loaded: {os.path.basename(p)} | {len(self.df)} Rows", text_color=self.success_color)
            self.lbl_stats.configure(text=f"Enriched: 0 | Total: {len(self.df)}")
            self.log_system(f"Dataset mapped. Output defaults to input folder.")
            self.mapping_confirmed = False
            self.btn_confirm.configure(text="✅ CONFIRM MAPPING & SYNC", fg_color=self.accent_color)
            
        except Exception as e:
            messagebox.showerror("IO Error", f"Fatal Error: {e}")

    def confirm_mapping(self):
        if self.df is None: return
        if self.var_name.get() == "-- select --":
            messagebox.showwarning("Logic Error", "Map Identity Column before confirmation.")
            return
        
        self.mapping_confirmed = True
        self.btn_confirm.configure(fg_color=self.success_color, text="✅ MAPPING SYNCED")
        self.log_system("Column mapping confirmed. Protocol ready.")

    def toggle_engine(self):
        if self.running:
            self.running = False
            self.btn_run.configure(text="🚀 INITIALIZE EXTRACTION ENGINE", fg_color=self.success_color)
            return
            
        if not self.mapping_confirmed:
            messagebox.showwarning("Sync Required", "Sync Mapping before initialization.")
            return
            
        self.running = True
        self.btn_run.configure(text="🛑 TERMINATE ENGINE PROCESS", fg_color="#EF4444")
        threading.Thread(target=self._engine_thread, daemon=True).start()

    def _update_progress(self, current, total, company):
        perc = current / total
        self.prog_bar.set(perc)
        self.lbl_stats.configure(text=f"Enriched: {current} | Total: {total}")
        self.log_system(f"Record {current}/{total}: {company.company_name} -> {company.status}")

    def _engine_thread(self):
        try:
            limit = int(self.var_limit.get() or 100)
            export_cols = [c for c, v in self.col_vars.items() if v.get()]
            raw_data = self.df.head(limit).to_dict('records')
            
            name_col = self.var_name.get()
            city_col = self.var_city.get()
            
            companies = []
            original_data_storage = {} 
            
            for i, row in enumerate(raw_data):
                name = str(row.get(name_col, "")).strip()
                if not name or name == "nan": continue
                
                comp = EnrichedCompany(
                    company_name=name,
                    city=str(row.get(city_col, "")) if city_col not in ["-- select --", "-- none --"] else ""
                )
                # Country detection from company name / context
                if any(kw in name.lower() for kw in ['gmbh', 'g.m.b.h']):
                    comp.country = 'DE'
                elif any(kw in name.lower() for kw in ['sas', 'sarl']):
                    if any(kw in name.lower() for kw in ['colombia', 'mx', 'mexico', 'brasil', 'chile', 'peru', 'argentina']):
                        comp.country = 'CO'
                    else:
                        comp.country = 'FR'
                elif any(kw in name.lower() for kw in ['ltda', 'limitada']):
                    comp.country = 'BR'
                elif 'pty' in name.lower():
                    comp.country = 'AU'
                elif 'ltd' in name.lower() and not any(kw in name.lower() for kw in ['llc', 'gmbh']):
                    comp.country = 'GB'
                companies.append(comp)
                original_data_storage[id(comp)] = {k: row.get(k, "") for k in export_cols}
            
            total = len(companies)
            self.log_system(f"Engine warming up... Target: {total} records.")
            
            def cb(i, t, c): self.after(0, lambda: self._update_progress(i, t, c))
            results = run_enrichment(companies, workers=20, progress_callback=cb, stop_flag=lambda: not self.running)
            
            if self.running:
                final_rows = []
                for res in results:
                    row = original_data_storage.get(id(res), {}).copy()
                    row['ENRICHED_EMAIL'] = res.email
                    row['ENRICHED_WEBSITE'] = res.website
                    row['ENRICHED_DOMAIN'] = res.domain
                    row['ENRICHED_LINKEDIN'] = res.linkedin
                    row['ENRICHED_FACEBOOK'] = res.facebook
                    row['ENRICHED_TWITTER_X'] = res.twitter
                    row['ENRICHED_INSTAGRAM'] = res.instagram
                    row['ENRICHED_YOUTUBE'] = res.youtube
                    row['ENRICHED_PHONE'] = res.phone
                    row['ENRICHED_ADDRESS'] = res.address
                    row['ENRICHED_DESCRIPTION'] = res.description
                    row['ENRICHED_INDUSTRY'] = res.industry
                    row['ENRICHED_BUSINESS_TYPE'] = res.business_type
                    row['ENRICHED_COUNTRY'] = res.country
                    row['ENRICHED_REGION'] = res.region
                    row['ENRICHED_DUNS'] = res.duns
                    row['ENRICHED_EIN'] = res.ein
                    row['ENRICHED_RUC'] = res.ruc
                    row['ENRICHED_VAT'] = res.vat
                    row['ENRICHED_CNPJ'] = res.cnpj
                    row['ENRICHED_RFC'] = res.rfc
                    row['ENRICHED_RUT'] = res.rut
                    row['ENRICHED_NIF'] = res.nif
                    row['ENRICHED_ABN'] = res.abn
                    row['ENRICHED_CIN'] = res.cin
                    row['ENRICHED_COMPANY_NUMBER'] = res.company_number
                    row['ENRICHED_SIC_CODE'] = res.sic_code
                    row['ENRICHED_EMPLOYEES'] = res.employees
                    row['ENRICHED_REVENUE'] = res.revenue
                    row['ENRICHED_FOUNDED'] = res.founded
                    row['CONFIDENCE'] = f"{res.confidence}%"
                    row['STATUS'] = res.status
                    row['SOURCES'] = res.sources_used
                    final_rows.append(row)
                
                out_df = pd.DataFrame(final_rows)
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                # Add timestamp to filename to avoid Permission Denied if file is open
                fname = f"NEXUS_ENRICHED_{ts}.{self.var_format.get().lower()}"
                out_path = os.path.join(self.output_dir, fname)
                
                try:
                    if self.var_format.get() == "XLSX":
                        out_df.to_excel(out_path, index=False)
                    else:
                        out_df.to_csv(out_path, index=False)
                    
                    self.log_system(f"SUCCESS: Exported to {out_path}")
                    self.after(0, lambda: messagebox.showinfo("Nexus PRO", f"Extraction completed!\n\nLocation: {out_path}"))
                except PermissionError:
                    # If even with unique timestamp it fails (rare), or folder is locked
                    self.log_system(f"PERMISSION ERROR: Folder {self.output_dir} is locked.")
                    self.after(0, lambda: messagebox.showerror("Permission Error", f"Cannot write to {self.output_dir}.\nPlease close the file if open or select another folder."))

                self.after(0, lambda: self.btn_run.configure(text="🚀 INITIALIZE EXTRACTION ENGINE", fg_color=self.success_color))
                self.running = False
                
        except Exception as e:
            self.log_system(f"CRITICAL ENGINE FAILURE: {e}")
            self.running = False
            self.after(0, lambda: self.btn_run.configure(text="🚀 INITIALIZE EXTRACTION ENGINE", fg_color=self.success_color))

if __name__ == "__main__":
    app = AliceNexusGUI()
    app.mainloop()
