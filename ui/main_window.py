"""Main application window."""
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from threading import Thread


class MainWindow:
    def __init__(self, user):
        self.user = user
        self.speakers = {}       # {name: Speaker}
        self.agenda_items = []    # [AgendaItem]
        self.home_bg_path = ''
        self.content_bg_path = ''
        self.template_path = ''    # PPT template path (mutually exclusive with manual bg)
        self.speaker_files = []   # list of file paths

        self.root = tk.Tk()
        self.root.title('会议串场PPT生成器')
        self.root.geometry('950x720')
        self.root.minsize(800, 600)
        self.root.configure(bg='#E3F2FD')
        self._center()

        self._build()

    def _center(self):
        self.root.update_idletasks()
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.root.geometry(f'+{(sw-950)//2}+{(sh-720)//2}')

    def _show_progress(self, msg):
        self.progress_var.set(msg)
        self.progress_bar.start()
        self.progress_frame.pack(fill='x', before=self.canvas)

    def _hide_progress(self, msg=''):
        self.progress_bar.stop()
        self.progress_var.set(msg)
        self.root.after(3000, lambda: self.progress_frame.pack_forget()
                        if self.progress_var.get() == msg else None)

    def _section_label(self, parent, text):
        f = tk.Frame(parent, bg='#E3F2FD')
        bar = tk.Frame(f, bg='#1976D2', width=4)
        bar.pack(side='left', fill='y')
        tk.Label(f, text=text, font=('Microsoft YaHei', 12, 'bold'),
                 bg='#E3F2FD', fg='#1976D2').pack(side='left', padx=6)
        f.pack(fill='x', pady=(12, 4))
        return f

    # ---- Section 1: Speaker files ----
    def _build_speaker_section(self, parent):
        self._section_label(parent, '演讲者资料')

        row1 = tk.Frame(parent, bg='#E3F2FD')
        row1.pack(fill='x', pady=2)
        tk.Button(row1, text='选择文件', font=('Microsoft YaHei', 10),
                  bg='#1976D2', fg='white', relief='flat', padx=12,
                  command=self._select_speaker_files).pack(side='left')
        self.speaker_file_label = tk.Label(row1, text='未选择文件', bg='#E3F2FD', fg='#666',
                                           font=('Microsoft YaHei', 9))
        self.speaker_file_label.pack(side='left', padx=10)

        columns = ('name', 'title', 'institution', 'photo', 'bio_preview')
        tree_frame = tk.Frame(parent, bg='white')
        tree_frame.pack(fill='x', padx=2, pady=2)
        self.speaker_tree = ttk.Treeview(tree_frame, columns=columns, show='headings',
                                         height=4)
        self.speaker_tree.heading('name', text='姓名')
        self.speaker_tree.heading('title', text='职称')
        self.speaker_tree.heading('institution', text='医院')
        self.speaker_tree.heading('photo', text='照片')
        self.speaker_tree.heading('bio_preview', text='履历预览')
        self.speaker_tree.column('name', width=60, minwidth=45)
        self.speaker_tree.column('title', width=80, minwidth=60)
        self.speaker_tree.column('institution', width=140, minwidth=70)
        self.speaker_tree.column('photo', width=45, minwidth=35)
        self.speaker_tree.column('bio_preview', width=360, minwidth=120, stretch=True)
        spk_scroll = ttk.Scrollbar(tree_frame, orient='vertical',
                                   command=self.speaker_tree.yview)
        self.speaker_tree.configure(yscrollcommand=spk_scroll.set)
        self.speaker_tree.pack(side='left', fill='both', expand=True)
        spk_scroll.pack(side='right', fill='y')

        # Style tag for rows with photos (hyperlink look)
        self.speaker_tree.tag_configure('has_photo', foreground='#1976D2',
                                        font=('Microsoft YaHei', 10, 'underline'))

        self.speaker_tree.bind('<Double-1>', self._on_speaker_double_click)

        btn_row = tk.Frame(parent, bg='#E3F2FD')
        btn_row.pack(fill='x', pady=2)
        self.extract_btn = tk.Button(btn_row, text='开始提取', font=('Microsoft YaHei', 10),
                                       bg='#4CAF50', fg='white', relief='flat', padx=12,
                                       command=self._extract_speakers)
        self.extract_btn.pack(side='left', padx=(0, 8))
        tk.Button(btn_row, text='新增', font=('Microsoft YaHei', 10),
                  bg='#1976D2', fg='white', relief='flat', padx=12,
                  command=self._add_speaker).pack(side='left', padx=(0, 8))
        tk.Button(btn_row, text='删除', font=('Microsoft YaHei', 10),
                  bg='#E57373', fg='white', relief='flat', padx=12,
                  command=self._delete_speaker).pack(side='left')
        # "清空数据" button hidden; _clear_speakers method retained
        self.speaker_count_var = tk.StringVar(value='')
        tk.Label(btn_row, textvariable=self.speaker_count_var, bg='#E3F2FD',
                 fg='#1976D2', font=('Microsoft YaHei', 10, 'bold')).pack(
                 side='right', padx=8)

    # ---- Section 2: Agenda ----
    def _build_agenda_section(self, parent):
        self._section_label(parent, '会议日程')

        row1 = tk.Frame(parent, bg='#E3F2FD')
        row1.pack(fill='x', pady=2)
        tk.Button(row1, text='选择日程文件', font=('Microsoft YaHei', 10),
                  bg='#1976D2', fg='white', relief='flat', padx=12,
                  command=self._select_agenda_image).pack(side='left')
        self.agenda_file_label = tk.Label(row1, text='未选择文件', bg='#E3F2FD', fg='#666',
                                          font=('Microsoft YaHei', 9))
        self.agenda_file_label.pack(side='left', padx=10)

        columns = ('order', 'time', 'title_cn', 'title_en', 'speaker', 'host', 'type')
        tree_frame = tk.Frame(parent, bg='white')
        tree_frame.pack(fill='x', padx=2, pady=2)
        self.agenda_tree = ttk.Treeview(tree_frame, columns=columns, show='headings',
                                        height=6)
        self.agenda_tree.heading('order', text='#')
        self.agenda_tree.heading('time', text='时间')
        self.agenda_tree.heading('title_cn', text='中文标题')
        self.agenda_tree.heading('title_en', text='英文标题')
        self.agenda_tree.heading('speaker', text='讲者')
        self.agenda_tree.heading('host', text='主持')
        self.agenda_tree.heading('type', text='类型')
        self.agenda_tree.column('order', width=35)
        self.agenda_tree.column('time', width=90)
        self.agenda_tree.column('title_cn', width=180)
        self.agenda_tree.column('title_en', width=180)
        self.agenda_tree.column('speaker', width=100)
        self.agenda_tree.column('host', width=100)
        self.agenda_tree.column('type', width=70)
        agd_scroll = ttk.Scrollbar(tree_frame, orient='vertical',
                                   command=self.agenda_tree.yview)
        self.agenda_tree.configure(yscrollcommand=agd_scroll.set)
        self.agenda_tree.pack(side='left', fill='both', expand=True)
        agd_scroll.pack(side='right', fill='y')

        # Double-click to edit
        self.agenda_tree.bind('<Double-1>', self._edit_agenda_cell)

        btn_row = tk.Frame(parent, bg='#E3F2FD')
        btn_row.pack(fill='x', pady=2)
        self.agenda_btn = tk.Button(btn_row, text='开始识别', font=('Microsoft YaHei', 10),
                                     bg='#4CAF50', fg='white', relief='flat', padx=8,
                                     command=self._extract_agenda)
        self.agenda_btn.pack(side='left', padx=(0, 4))
        tk.Button(btn_row, text='新  增', font=('Microsoft YaHei', 10),
                  bg='#4CAF50', fg='white', relief='flat', padx=8,
                  command=self._add_agenda_row).pack(side='left', padx=(0, 4))
        tk.Button(btn_row, text='删  除', font=('Microsoft YaHei', 10),
                  bg='#E57373', fg='white', relief='flat', padx=8,
                  command=self._delete_agenda_row).pack(side='left', padx=(0, 4))
        tk.Button(btn_row, text='导入CSV', font=('Microsoft YaHei', 10),
                  bg='#1976D2', fg='white', relief='flat', padx=8,
                  command=self._import_agenda_csv).pack(side='left', padx=(0, 4))
        tk.Button(btn_row, text='导出CSV', font=('Microsoft YaHei', 10),
                  bg='#1976D2', fg='white', relief='flat', padx=8,
                  command=self._export_agenda_csv).pack(side='left')

    # ---- Section 3: Template images ----
    def _build_template_section(self, parent):
        self._section_label(parent, '模板图片')

        # --- Row 0: PPT template upload (mutually exclusive with manual selection) ---
        tpl_row = tk.Frame(parent, bg='#E3F2FD')
        tpl_row.pack(fill='x', pady=(2, 6))
        tk.Label(tpl_row, text='PPT模板:', bg='#E3F2FD', fg='#333', width=8, anchor='w',
                 font=('Microsoft YaHei', 10)).pack(side='left')
        self.template_label = tk.Label(tpl_row, text='未选择', bg='#E3F2FD', fg='#999',
                                       font=('Microsoft YaHei', 9), width=28, anchor='w')
        self.template_label.pack(side='left', padx=6)
        self.template_btn = tk.Button(tpl_row, text='上传PPT', font=('Microsoft YaHei', 9),
                                      bg='#1976D2', fg='white', relief='flat', padx=8,
                                      command=self._select_template)
        self.template_btn.pack(side='left', padx=(0, 4))
        self.template_clear_btn = tk.Button(tpl_row, text='清除', font=('Microsoft YaHei', 9),
                                            bg='#BBDEFB', fg='#1976D2', relief='flat', padx=8,
                                            command=self._clear_template,
                                            state='disabled')
        self.template_clear_btn.pack(side='left')

        # --- Row 1: Home page image (manual) ---
        f = tk.Frame(parent, bg='#E3F2FD')
        f.pack(fill='x', pady=4)

        tk.Label(f, text='首页图片:', bg='#E3F2FD', fg='#333', width=8, anchor='w',
                 font=('Microsoft YaHei', 10)).pack(side='left')
        self.home_bg_label = tk.Label(f, text='未选择', bg='#E3F2FD', fg='#999',
                                      font=('Microsoft YaHei', 9), width=30, anchor='w')
        self.home_bg_label.pack(side='left', padx=6)
        self.home_bg_btn = tk.Button(f, text='选择', font=('Microsoft YaHei', 9),
                                     bg='#1976D2', fg='white', relief='flat', padx=8,
                                     command=self._select_home_bg)
        self.home_bg_btn.pack(side='left')

        # --- Row 2: Content page image (manual) ---
        f2 = tk.Frame(parent, bg='#E3F2FD')
        f2.pack(fill='x', pady=4)

        tk.Label(f2, text='内容页图片:', bg='#E3F2FD', fg='#333', width=8, anchor='w',
                 font=('Microsoft YaHei', 10)).pack(side='left')
        self.content_bg_label = tk.Label(f2, text='未选择', bg='#E3F2FD', fg='#999',
                                         font=('Microsoft YaHei', 9), width=30, anchor='w')
        self.content_bg_label.pack(side='left', padx=6)
        self.content_bg_btn = tk.Button(f2, text='选择', font=('Microsoft YaHei', 9),
                                        bg='#1976D2', fg='white', relief='flat', padx=8,
                                        command=self._select_content_bg)
        self.content_bg_btn.pack(side='left')

    # ---- Section 4: PPT settings + Generate ----
    def _build_generate_section(self, parent):
        self._section_label(parent, 'PPT设置与生成')

        f = tk.Frame(parent, bg='#E3F2FD')
        f.pack(fill='x', pady=4)

        tk.Label(f, text='尺寸:', bg='#E3F2FD', fg='#333',
                 font=('Microsoft YaHei', 10)).pack(side='left')
        self.size_var = tk.StringVar(value='16:9')
        tk.Radiobutton(f, text='16:9 宽屏', variable=self.size_var, value='16:9',
                       bg='#E3F2FD', font=('Microsoft YaHei', 10)).pack(side='left', padx=10)
        tk.Radiobutton(f, text='超宽屏(舞台LED)', variable=self.size_var, value='ultrawide',
                       bg='#E3F2FD', font=('Microsoft YaHei', 10)).pack(side='left', padx=10)

        # Language selector
        f2 = tk.Frame(parent, bg='#E3F2FD')
        f2.pack(fill='x', pady=4)
        tk.Label(f2, text='语言:', bg='#E3F2FD', fg='#333',
                 font=('Microsoft YaHei', 10)).pack(side='left')
        self.lang_var = tk.StringVar(value='chinese')
        tk.Radiobutton(f2, text='中文', variable=self.lang_var, value='chinese',
                       bg='#E3F2FD', font=('Microsoft YaHei', 10)).pack(side='left', padx=10)
        tk.Radiobutton(f2, text='中英双语', variable=self.lang_var, value='bilingual',
                       bg='#E3F2FD', font=('Microsoft YaHei', 10)).pack(side='left', padx=10)

        btn_f = tk.Frame(parent, bg='#E3F2FD')
        btn_f.pack(fill='x', pady=12)
        self.gen_btn = tk.Button(btn_f, text='一键生成PPT', font=('Microsoft YaHei', 14, 'bold'),
                                 bg='#1976D2', fg='white', relief='flat',
                                 padx=30, pady=8, cursor='hand2',
                                 command=self._generate_ppt, state='disabled')
        self.gen_btn.pack()

    # ---- Build everything ----
    def _build(self):
        # Header bar (fixed at top)
        header = tk.Frame(self.root, bg='#1976D2', height=38)
        header.pack(fill='x', side='top')
        header.pack_propagate(False)
        tk.Label(header, text=f'会议串场PPT生成器', font=('Microsoft YaHei', 11, 'bold'),
                 bg='#1976D2', fg='white').pack(side='left', padx=(16, 0))
        self._header_user_label = tk.Label(
            header, text=f'用户: {self.user["username"]}',
            bg='#1976D2', fg='#BBDEFB', font=('Microsoft YaHei', 9))
        self._header_user_label.pack(side='left', padx=(6, 0))
        tk.Button(header, text='账户设置', font=('Microsoft YaHei', 9),
                  bg='#1565C0', fg='white', relief='flat', padx=10,
                  activebackground='#0D47A1', activeforeground='white',
                  cursor='hand2', command=self._open_settings).pack(
                  side='right', padx=(0, 12), pady=4)

        # Floating progress bar (hidden by default)
        self.progress_frame = tk.Frame(self.root, bg='#1976D2', height=36)
        self.progress_var = tk.StringVar(value='')
        tk.Label(self.progress_frame, textvariable=self.progress_var,
                 bg='#1976D2', fg='white', font=('Microsoft YaHei', 10)).pack(
                 side='left', padx=(16, 8))
        self.progress_bar = ttk.Progressbar(self.progress_frame, mode='indeterminate',
                                             length=200)
        self.progress_bar.pack(side='left', padx=(0, 16))

        # Canvas + Scrollbar for vertical scrolling
        self.canvas = tk.Canvas(self.root, bg='#E3F2FD', highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.root, orient='vertical', command=self.canvas.yview)
        self.scroll_frame = tk.Frame(self.canvas, bg='#E3F2FD', padx=20, pady=10)

        self.scroll_frame.bind('<Configure>',
                               lambda e: self.canvas.configure(scrollregion=self.canvas.bbox('all')))

        self._canvas_window = self.canvas.create_window((0, 0), window=self.scroll_frame, anchor='nw')

        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Adjust inner frame width to match canvas
        def _on_canvas_resize(event):
            self.canvas.itemconfig(self._canvas_window, width=event.width)
        self.canvas.bind('<Configure>', _on_canvas_resize, add='+')

        # Mousewheel scrolling
        def _on_mousewheel(event):
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), 'units')

        def _bind_wheel(event):
            self.canvas.bind_all('<MouseWheel>', _on_mousewheel)

        def _unbind_wheel(event):
            self.canvas.unbind_all('<MouseWheel>')

        self.canvas.bind('<Enter>', _bind_wheel)
        self.canvas.bind('<Leave>', _unbind_wheel)

        # Create card-like frames for each section
        for build_fn in [
            self._build_speaker_section,
            self._build_agenda_section,
            self._build_template_section,
            self._build_generate_section,
        ]:
            card = tk.Frame(self.scroll_frame, bg='white', padx=12, pady=8,
                            highlightbackground='#BBDEFB', highlightthickness=1)
            card.pack(fill='x', pady=4)
            build_fn(card)

    # ---- Callbacks ----
    def _open_settings(self):
        from ui.user_settings_window import UserSettingsWindow

        def on_saved(updated_user):
            self.user.update(updated_user)
            self._header_user_label.config(
                text=f'用户: {self.user["username"]}')

        UserSettingsWindow(self.root, self.user, on_saved)

    def _select_speaker_files(self):
        paths = filedialog.askopenfilenames(
            title='选择演讲者资料',
            filetypes=[('支持的格式', '*.docx;*.doc;*.pptx;*.ppt;*.pdf'),
                       ('所有文件', '*.*')])
        if paths:
            self.speaker_files = list(paths)
            self.speaker_file_label.config(
                text=f'已选 {len(self.speaker_files)} 个文件')

    def _extract_speakers(self):
        if not self.speaker_files:
            messagebox.showwarning('提示', '请先选择演讲者资料文件')
            return
        if not self.user.get('api_key'):
            messagebox.showwarning('提示', '请先在账户设置中配置 DeepSeek API Key')
            return

        self.extract_btn.config(state='disabled')
        self._show_progress('正在提取演讲者信息...')

        def _run():
            from extractors.speaker_extractor import extract_speaker
            for fp in self.speaker_files:
                try:
                    sp = extract_speaker(fp, self.user['api_key'])
                    self.speakers[sp.name] = sp
                except Exception as e:
                    self.root.after(0, lambda err=e: messagebox.showerror(
                        '提取失败', f'{os.path.basename(fp)}: {err}'))

            self.root.after(0, self._update_speaker_tree)
            self.root.after(0, lambda: self._hide_progress(
                f'完成！共识别 {len(self.speakers)} 位演讲者'))
            self.root.after(0, lambda: self.extract_btn.config(state='normal'))

        Thread(target=_run, daemon=True).start()

    def _update_speaker_tree(self):
        for row in self.speaker_tree.get_children():
            self.speaker_tree.delete(row)
        for name, sp in self.speakers.items():
            inst_preview = sp.institution[:16] if sp.institution else ''
            has_photo = '有' if sp.photo_path else '无'
            bio_preview = sp.bio[:50].replace('\n', ' ') + ('...' if len(sp.bio) > 50 else '')
            tags = ('has_photo',) if sp.photo_path else ()
            self.speaker_tree.insert('', 'end',
                                     values=(name, sp.title, inst_preview, has_photo, bio_preview),
                                     iid=name, tags=tags)
        count = len(self.speakers)
        self.speaker_count_var.set(f'共 {count} 位' if count else '')
        self._check_generate_ready()

    def _clear_speakers(self):
        if not self.speakers:
            return
        ok = messagebox.askyesno('确认', f'将清空当前所有演讲者数据（共 {len(self.speakers)} 位），\n'
                                          '包括照片文件。\n\n确定继续？')
        if not ok:
            return
        for name, sp in list(self.speakers.items()):
            if sp.photo_path and os.path.exists(sp.photo_path):
                try:
                    os.remove(sp.photo_path)
                except Exception:
                    pass
        self.speakers.clear()
        self._update_speaker_tree()
        self._hide_progress('演讲者数据已清空')

    def _add_speaker(self):
        """Manually add a new speaker entry."""
        from extractors.speaker_extractor import Speaker
        sp = Speaker(name='', title='教授')
        # Use a unique placeholder key; _on_speaker_added will re-key by name
        import uuid
        placeholder = f'__new__{uuid.uuid4().hex[:6]}'
        self.speakers[placeholder] = sp
        SpeakerEditWindow(self.root, sp, lambda: self._on_speaker_added(placeholder))

    def _on_speaker_added(self, placeholder):
        """Called after saving a newly added speaker — fixes the dict key."""
        sp = self.speakers.pop(placeholder, None)
        if sp is None:
            return
        new_name = sp.name.strip()
        if not new_name:
            # User cleared the name — discard the entry
            self._update_speaker_tree()
            self._check_generate_ready()
            return
        # Handle name conflict: overwrite existing entry with same name
        self.speakers[new_name] = sp
        self._update_speaker_tree()
        self._check_generate_ready()
        self._hide_progress(f'已添加演讲者: {new_name}')

    def _delete_speaker(self):
        """Delete the selected speaker(s) from the list."""
        selected = self.speaker_tree.selection()
        if not selected:
            messagebox.showwarning('提示', '请先在列表中选择要删除的演讲者')
            return
        names = [s for s in selected if s in self.speakers]
        if not names:
            return
        ok = messagebox.askyesno('确认删除',
                                  f'将删除以下 {len(names)} 位演讲者：\n\n'
                                  + '\n'.join(names))
        if not ok:
            return
        for name in names:
            sp = self.speakers.pop(name, None)
            if sp and sp.photo_path and os.path.exists(sp.photo_path):
                try:
                    os.remove(sp.photo_path)
                except Exception:
                    pass
        self._update_speaker_tree()
        self._check_generate_ready()
        self._hide_progress(f'已删除 {len(names)} 位演讲者')

    def _on_speaker_double_click(self, event):
        item = self.speaker_tree.focus()
        if not item:
            return
        sp = self.speakers.get(item)
        if sp:
            SpeakerEditWindow(self.root, sp, self._on_speaker_updated)

    def _on_speaker_updated(self):
        self._update_speaker_tree()

    def _select_agenda_image(self):
        path = filedialog.askopenfilename(
            title='选择会议日程文件',
            filetypes=[('支持的格式', '*.jpg;*.jpeg;*.png;*.pptx;*.ppt;*.docx;*.doc;*.xlsx'),
                       ('图片', '*.jpg;*.jpeg;*.png'),
                       ('文档', '*.pptx;*.ppt;*.docx;*.doc;*.xlsx'),
                       ('所有文件', '*.*')])
        if path:
            self.agenda_image_path = path
            self.agenda_file_label.config(text=os.path.basename(path))

    def _extract_agenda(self):
        if not hasattr(self, 'agenda_image_path'):
            messagebox.showwarning('提示', '请先选择会议日程文件')
            return
        if not self.user.get('api_key'):
            messagebox.showwarning('提示', '请先在账户设置中配置 DeepSeek API Key')
            return

        self.agenda_btn.config(state='disabled')
        self._show_progress('正在识别会议日程...')

        def _run():
            from extractors.agenda_extractor import extract_agenda
            try:
                self.agenda_items = extract_agenda(
                    self.agenda_image_path,
                    self.user['api_key'],
                    self.user.get('ocr_api_key', ''))
            except Exception as e:
                self.root.after(0, lambda err=e: messagebox.showerror(
                    '识别失败', str(err)))
            self.root.after(0, self._update_agenda_tree)
            self.root.after(0, lambda: self._hide_progress(
                f'完成！共识别 {len(self.agenda_items)} 个环节'))
            self.root.after(0, lambda: self.agenda_btn.config(state='normal'))

        Thread(target=_run, daemon=True).start()

    def _update_agenda_tree(self):
        for row in self.agenda_tree.get_children():
            self.agenda_tree.delete(row)
        for item in self.agenda_items:
            self.agenda_tree.insert('', 'end', values=(
                item.order, item.time_slot, item.session_title_cn,
                item.session_title_en, item.speaker_name, item.host,
                item.item_type))
        self._check_generate_ready()

    def _edit_agenda_cell(self, event):
        item_id = self.agenda_tree.focus()
        if not item_id:
            return
        col = self.agenda_tree.identify_column(event.x)
        col_idx = int(col.replace('#', '')) - 1

        old_value = self.agenda_tree.item(item_id, 'values')[col_idx]
        x, y, w, h = self.agenda_tree.bbox(item_id, col)

        edit = tk.Entry(self.agenda_tree, font=('Microsoft YaHei', 10))
        edit.place(x=x, y=y, width=w, height=h)
        edit.insert(0, str(old_value))
        edit.focus_set()

        def save(event=None):
            new_val = edit.get()
            edit.destroy()
            values = list(self.agenda_tree.item(item_id, 'values'))
            values[col_idx] = new_val
            self.agenda_tree.item(item_id, values=values)
            # Update agenda_items
            idx = self.agenda_tree.index(item_id)
            fields = ['order', 'time_slot', 'session_title_cn', 'session_title_en',
                      'speaker_name', 'host', 'item_type']
            setattr(self.agenda_items[idx], fields[col_idx],
                    int(new_val) if fields[col_idx] == 'order' else new_val)

        edit.bind('<Return>', save)
        edit.bind('<FocusOut>', save)

    def _export_agenda_csv(self):
        if not self.agenda_items:
            messagebox.showwarning('提示', '没有日程数据可导出')
            return
        path = filedialog.asksaveasfilename(
            title='导出日程CSV', defaultextension='.csv',
            filetypes=[('CSV文件', '*.csv')])
        if not path:
            return
        import csv
        with open(path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(['order', 'time_slot', 'session_title_cn',
                            'session_title_en', 'speaker_name', 'host',
                            'institution', 'item_type'])
            for item in self.agenda_items:
                writer.writerow([item.order, item.time_slot,
                                item.session_title_cn, item.session_title_en,
                                item.speaker_name, item.host,
                                item.institution, item.item_type])
        self._hide_progress(f'日程已导出: {os.path.basename(path)}')

    def _import_agenda_csv(self):
        path = filedialog.askopenfilename(
            title='导入日程CSV', filetypes=[('CSV文件', '*.csv')])
        if not path:
            return
        import csv
        from extractors.agenda_extractor import AgendaItem
        try:
            items = []
            with open(path, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    items.append(AgendaItem(
                        order=int(row.get('order', 0)),
                        time_slot=row.get('time_slot', ''),
                        session_title_cn=row.get('session_title_cn', ''),
                        session_title_en=row.get('session_title_en', ''),
                        speaker_name=row.get('speaker_name', ''),
                        host=row.get('host', ''),
                        institution=row.get('institution', ''),
                        item_type=row.get('item_type', 'speech'),
                    ))
            if not items:
                messagebox.showerror('导入失败', 'CSV文件中没有数据')
                return
            self.agenda_items = items
            self._update_agenda_tree()
            self._hide_progress(f'已导入 {len(items)} 个环节')
        except Exception as e:
            messagebox.showerror('导入失败', str(e))

    def _add_agenda_row(self):
        from extractors.agenda_extractor import AgendaItem
        order = len(self.agenda_items) + 1
        item = AgendaItem(order=order, time_slot='', session_title_cn='',
                          session_title_en='', speaker_name='', host='',
                          institution='', item_type='speech')
        self.agenda_items.append(item)
        self._update_agenda_tree()

    def _check_generate_ready(self):
        """Enable the generate button only when all content is ready."""
        ready = (bool(self.speakers)
                 and bool(self.agenda_items)
                 and bool(self.home_bg_path)
                 and bool(self.content_bg_path))
        self.gen_btn.config(state='normal' if ready else 'disabled')

    def _delete_agenda_row(self):
        selected = self.agenda_tree.selection()
        if not selected:
            messagebox.showwarning('提示', '请先选择要删除的行')
            return
        for item_id in selected:
            idx = self.agenda_tree.index(item_id)
            del self.agenda_items[idx]
        self._update_agenda_tree()

    # ---- Template upload ----
    def _select_template(self):
        path = filedialog.askopenfilename(
            title='选择PPT模板',
            filetypes=[('PPT文件', '*.pptx;*.ppt'), ('所有文件', '*.*')])
        if not path:
            return

        self.template_btn.config(state='disabled')
        self._show_progress('正在从PPT模板提取图片...')

        def _run():
            from utils.ppt_template_extractor import extract_slide_images
            import tempfile
            try:
                out_dir = tempfile.mkdtemp(prefix='ppt_tpl_')
                home_path, content_path = extract_slide_images(path, out_dir)
                self.home_bg_path = home_path
                self.content_bg_path = content_path
                self.template_path = path
            except Exception as e:
                self.root.after(0, lambda err=e: messagebox.showerror(
                    '提取失败', f'PPT模板提取失败: {err}'))
                self.root.after(0, lambda: self.template_btn.config(state='normal'))
                self.root.after(0, lambda: self._hide_progress(''))
                return

            self.root.after(0, self._on_template_loaded)

        Thread(target=_run, daemon=True).start()

    def _on_template_loaded(self):
        self.template_label.config(text=os.path.basename(self.template_path), fg='#333')
        self.template_clear_btn.config(state='normal')
        self.template_btn.config(state='normal')
        # Update manual labels to reflect extracted images
        self.home_bg_label.config(text='(来自模板)', fg='#4CAF50')
        self.content_bg_label.config(text='(来自模板)', fg='#4CAF50')
        # Disable manual selection — mutually exclusive
        self.home_bg_btn.config(state='disabled')
        self.content_bg_btn.config(state='disabled')
        self._check_generate_ready()
        self._hide_progress('PPT模板图片提取完成')

    def _clear_template(self):
        self.template_path = ''
        self.home_bg_path = ''
        self.content_bg_path = ''
        self.template_label.config(text='未选择', fg='#999')
        self.template_clear_btn.config(state='disabled')
        self.home_bg_label.config(text='未选择', fg='#999')
        self.content_bg_label.config(text='未选择', fg='#999')
        # Re-enable manual selection
        self.home_bg_btn.config(state='normal')
        self.content_bg_btn.config(state='normal')
        self._check_generate_ready()
        self._hide_progress('模板已清除')

    def _select_home_bg(self):
        path = filedialog.askopenfilename(
            title='选择首页背景图',
            filetypes=[('图片', '*.jpg;*.jpeg;*.png'), ('所有文件', '*.*')])
        if path:
            self.home_bg_path = path
            self.home_bg_label.config(text=os.path.basename(path))
            # Clear template — mutually exclusive
            self._clear_template_data()
            self._check_generate_ready()

    def _select_content_bg(self):
        path = filedialog.askopenfilename(
            title='选择内容页背景图',
            filetypes=[('图片', '*.jpg;*.jpeg;*.png'), ('所有文件', '*.*')])
        if path:
            self.content_bg_path = path
            self.content_bg_label.config(text=os.path.basename(path))
            # Clear template — mutually exclusive
            self._clear_template_data()
            self._check_generate_ready()

    def _clear_template_data(self):
        """Clear template reference without UI updates (called by manual selectors)."""
        if self.template_path:
            self.template_path = ''
            self.template_label.config(text='未选择', fg='#999')
            self.template_clear_btn.config(state='disabled')
            self.home_bg_btn.config(state='normal')
            self.content_bg_btn.config(state='normal')

    def _generate_ppt(self):
        if not self.agenda_items:
            messagebox.showwarning('提示', '请先识别会议日程')
            return
        if not self.home_bg_path or not self.content_bg_path:
            messagebox.showwarning('提示', '请先选择模板图片')
            return

        output_path = filedialog.asksaveasfilename(
            title='保存PPT文件',
            defaultextension='.pptx',
            filetypes=[('PPTX文件', '*.pptx')])
        if not output_path:
            return

        self.gen_btn.config(state='disabled')
        self._show_progress('正在生成PPT...')

        def _run():
            import subprocess
            import json as _json
            import tempfile
            import sys

            try:
                size = self.size_var.get()
                lang = self.lang_var.get()

                # Serialize agenda items and speakers to dicts
                agenda_dicts = []
                for item in self.agenda_items:
                    agenda_dicts.append({
                        'order': item.order,
                        'time_slot': item.time_slot,
                        'session_title_cn': item.session_title_cn,
                        'session_title_en': item.session_title_en,
                        'speaker_name': item.speaker_name,
                        'host': item.host,
                        'institution': item.institution,
                        'item_type': item.item_type,
                    })
                speaker_dicts = {}
                for name, sp in self.speakers.items():
                    speaker_dicts[name] = {
                        'name': sp.name,
                        'photo_path': sp.photo_path,
                        'bio': sp.bio,
                        'institution': sp.institution,
                        'title': sp.title,
                    }

                params = {
                    'agenda_items': agenda_dicts,
                    'speakers': speaker_dicts,
                    'home_bg': self.home_bg_path,
                    'content_bg': self.content_bg_path,
                    'slide_size': size,
                    'lang': lang,
                    'output_path': output_path,
                }

                # Write params to temp JSON file
                with tempfile.NamedTemporaryFile(
                        mode='w', suffix='.json', delete=False,
                        encoding='utf-8', prefix='ppt_params_') as tmp:
                    _json.dump(params, tmp, ensure_ascii=False)
                    params_path = tmp.name

                # Build command
                script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                script_path = os.path.join(script_dir, 'ppt_generator.py')
                cmd = [sys.executable, script_path, params_path]
                print(f'[PPT Generator] {" ".join(cmd)}')

                result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                if result.stdout:
                    print(result.stdout)
                if result.stderr:
                    print(result.stderr, file=sys.stderr)
                if result.returncode != 0:
                    raise RuntimeError(f'PPT生成失败 (exit={result.returncode}): {result.stderr}')
            except Exception as e:
                self.root.after(0, lambda err=e: messagebox.showerror(
                    '生成失败', str(err)))
            finally:
                # Clean up temp file
                try:
                    os.unlink(params_path)
                except Exception:
                    pass
            self.root.after(0, lambda: self._hide_progress(
                f'PPT已生成: {os.path.basename(output_path)}'))
            self.root.after(0, lambda: self.gen_btn.config(state='normal'))
            self.root.after(0, lambda: messagebox.showinfo(
                '完成', f'PPT已保存到:\n{output_path}'))

        Thread(target=_run, daemon=True).start()

    def run(self):
        self.root.mainloop()


class SpeakerEditWindow:
    def __init__(self, parent, speaker, on_save):
        self.speaker = speaker
        self.on_save = on_save
        self.photo_path = speaker.photo_path

        self.win = tk.Toplevel(parent)
        self.win.title(f'编辑演讲者 - {speaker.name}')
        self.win.geometry('540x720')
        self.win.resizable(True, True)
        self.win.minsize(450, 500)
        self.win.configure(bg='#E3F2FD')
        self._center()
        self.win.transient(parent)

        self._build()

    def _center(self):
        self.win.update_idletasks()
        w, h = self.win.winfo_width(), self.win.winfo_height()
        sw = self.win.winfo_screenwidth()
        sh = self.win.winfo_screenheight()
        self.win.geometry(f'+{(sw-w)//2}+{(sh-h)//2}')

    def _build(self):
        f = tk.Frame(self.win, bg='#E3F2FD', padx=20, pady=15)
        f.pack(expand=True, fill='both')

        # Name row
        name_row = tk.Frame(f, bg='#E3F2FD')
        name_row.pack(fill='x', pady=(5, 2))
        tk.Label(name_row, text='姓名', font=('Microsoft YaHei', 11, 'bold'),
                 bg='#E3F2FD', fg='#1F4E79', width=5, anchor='w').pack(side='left')
        self.name_var = tk.StringVar(value=self.speaker.name)
        tk.Entry(name_row, textvariable=self.name_var, font=('Microsoft YaHei', 11),
                 width=20).pack(side='left', ipady=3, padx=(0, 10))

        # Title
        tk.Label(name_row, text='职称', font=('Microsoft YaHei', 11, 'bold'),
                 bg='#E3F2FD', fg='#1F4E79', width=5, anchor='w').pack(side='left')
        self.title_var = tk.StringVar(value=self.speaker.title)
        tk.Entry(name_row, textvariable=self.title_var, font=('Microsoft YaHei', 11),
                 width=15).pack(side='left', ipady=3)

        # Institution
        tk.Label(f, text='医院', font=('Microsoft YaHei', 11, 'bold'),
                 bg='#E3F2FD', fg='#1F4E79').pack(anchor='w', pady=(8, 2))
        self.inst_var = tk.StringVar(value=self.speaker.institution)
        tk.Entry(f, textvariable=self.inst_var, font=('Microsoft YaHei', 11),
                 width=40).pack(fill='x', ipady=3)

        # Photo
        tk.Label(f, text='照片', font=('Microsoft YaHei', 11, 'bold'),
                 bg='#E3F2FD', fg='#1F4E79').pack(anchor='w', pady=(12, 2))

        photo_row = tk.Frame(f, bg='#E3F2FD')
        photo_row.pack(fill='x')
        self.photo_label = tk.Label(photo_row, text='未选择照片',
                                    bg='#E3F2FD', fg='#999',
                                    font=('Microsoft YaHei', 9), anchor='w')
        self.photo_label.pack(side='left', fill='x', expand=True)
        tk.Button(photo_row, text='上传', font=('Microsoft YaHei', 9),
                  bg='#1976D2', fg='white', relief='flat', padx=10,
                  command=self._upload_photo).pack(side='left', padx=(6, 0))
        tk.Button(photo_row, text='清除', font=('Microsoft YaHei', 9),
                  bg='#BBDEFB', fg='#1976D2', relief='flat', padx=10,
                  command=self._clear_photo).pack(side='left', padx=(4, 0))

        self._update_photo_label()

        # Photo preview
        self.preview_label = tk.Label(f, bg='#E3F2FD')
        self.preview_label.pack(pady=6)
        self._update_preview()

        # Bio
        tk.Label(f, text='履历', font=('Microsoft YaHei', 11, 'bold'),
                 bg='#E3F2FD', fg='#1F4E79').pack(anchor='w', pady=(8, 2))
        bio_frame = tk.Frame(f, bg='white', highlightbackground='#BBDEFB',
                             highlightthickness=1)
        bio_frame.pack(fill='both', expand=True, pady=(0, 10))
        self.bio_text = tk.Text(bio_frame, font=('Microsoft YaHei', 10),
                                wrap='word', relief='flat', borderwidth=4,
                                height=8)
        self.bio_text.insert('1.0', self.speaker.bio)
        bio_scroll = ttk.Scrollbar(bio_frame, orient='vertical',
                                   command=self.bio_text.yview)
        self.bio_text.configure(yscrollcommand=bio_scroll.set)
        self.bio_text.pack(side='left', fill='both', expand=True)
        bio_scroll.pack(side='right', fill='y')

        # Buttons
        btn_row = tk.Frame(f, bg='#E3F2FD')
        btn_row.pack(fill='x', pady=(8, 0))
        tk.Button(btn_row, text='保  存', font=('Microsoft YaHei', 11),
                  bg='#1976D2', fg='white', relief='flat', width=10,
                  command=self._save).pack(side='left', padx=(0, 6))
        tk.Button(btn_row, text='取  消', font=('Microsoft YaHei', 11),
                  bg='#BBDEFB', fg='#1976D2', relief='flat', width=10,
                  command=self.win.destroy).pack(side='left')

    def _update_photo_label(self):
        if self.photo_path and os.path.exists(self.photo_path):
            self.photo_label.config(text=os.path.basename(self.photo_path), fg='#333')
        else:
            self.photo_label.config(text='未选择照片', fg='#999')

    def _update_preview(self):
        if self.photo_path and os.path.exists(self.photo_path):
            try:
                from PIL import Image, ImageTk
                img = Image.open(self.photo_path)
                img.thumbnail((160, 180), Image.LANCZOS)
                self._photo_img = ImageTk.PhotoImage(img)
                self.preview_label.config(image=self._photo_img)
            except Exception:
                self.preview_label.config(image='', text='(无法预览)')
        else:
            self.preview_label.config(image='', text='')

    def _upload_photo(self):
        path = filedialog.askopenfilename(
            title='选择照片', parent=self.win,
            filetypes=[('图片', '*.jpg;*.jpeg;*.png'), ('所有文件', '*.*')])
        if path:
            from extractors.speaker_extractor import _get_session_photo_dir
            dest_dir = _get_session_photo_dir()
            ext = os.path.splitext(path)[1]
            safe_name = self.name_var.get().strip().replace('/', '_').replace('\\', '_')
            dest = os.path.join(dest_dir, f'{safe_name}{ext}')
            import shutil
            shutil.copy2(path, dest)
            self.photo_path = dest
            self._update_photo_label()
            self._update_preview()

    def _clear_photo(self):
        self.photo_path = ''
        self._update_photo_label()
        self._update_preview()

    def _save(self):
        new_name = self.name_var.get().strip()
        if not new_name:
            messagebox.showwarning('提示', '姓名不能为空', parent=self.win)
            return
        self.speaker.name = new_name
        self.speaker.photo_path = self.photo_path
        self.speaker.title = self.title_var.get().strip()
        self.speaker.institution = self.inst_var.get().strip()
        self.speaker.bio = self.bio_text.get('1.0', 'end-1c')
        self.on_save()
        self.win.destroy()
